"""Unit tests for FederationAlertDaemon — mode SM + classify dispatch."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.federation_alerts.config import FADConfig
from backend.services.federation_alerts.daemon import FederationAlertDaemon
from backend.services.federation_alerts.models import (
    AlertSeverity,
    FederationAlertMode,
    ProposalStatus,
    RiskLevel,
)


def _config(env_mode: str | None = None) -> FADConfig:
    return FADConfig(
        database_url="postgres://localhost/dummy",
        telegram_bot_token=None,
        telegram_chat_id=None,
        daemon_owner="test-daemon",
        lease_ttl_sec=60,
        deliberation_timeout_sec=10,
        env_mode=env_mode,
        audit_log_dir="/tmp/fad-test-audit",
    )


def _proposal(
    *,
    proposal_id: str = "pid-1",
    status: str = "received",
    requested_action: str | None = None,
    is_terminal: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        proposal_id=proposal_id,
        run_id=f"rid-{proposal_id}",
        idempotency_key=f"iden-{proposal_id}",
        status=status,
        mode=FederationAlertMode.OBSERVE.value,
        alert_type="cron_failure",
        severity=AlertSeverity.MEDIUM.value,
        risk_level=RiskLevel.L2.value,
        requested_action=requested_action,
        action_payload={},
        compact_payload={"v": 1},
        full_payload={},
        is_terminal=lambda: is_terminal,
    )


@pytest.fixture
def daemon_with_audit_mock(monkeypatch, tmp_path):
    """Daemon instance with FADConfig pointed at tmp dir + audit mocked."""
    config = _config()
    object.__setattr__(config, "audit_log_dir", str(tmp_path))
    with patch(
        "backend.services.federation_alerts.daemon.quick_subprocess_check",
        return_value=False,
    ):
        daemon = FederationAlertDaemon(config)
    return daemon


# ---------------------------------------------------------------------------
# Daemon construction
# ---------------------------------------------------------------------------


def test_daemon_requires_database_url() -> None:
    config = FADConfig(
        database_url="",
        telegram_bot_token=None,
        telegram_chat_id=None,
        daemon_owner="x",
        lease_ttl_sec=60,
        deliberation_timeout_sec=10,
        env_mode=None,
        audit_log_dir="/tmp",
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        FederationAlertDaemon(config)


def test_daemon_dispatch_unavailable_when_probe_fails(daemon_with_audit_mock) -> None:
    assert daemon_with_audit_mock._dispatch_available is False


# ---------------------------------------------------------------------------
# Mode dispatch — observe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_observe_advances_to_observed(daemon_with_audit_mock) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    proposal = _proposal(requested_action="cleanup_log")

    await daemon._dispatch_proposal(repo, proposal, "observe")

    repo.advance_status.assert_awaited_once()
    args = repo.advance_status.call_args
    assert args.args[0] == "pid-1"
    assert args.args[1] == ProposalStatus.OBSERVED


# ---------------------------------------------------------------------------
# Mode dispatch — dry_deliberate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_dry_deliberate_advances_to_proposed(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    proposal = _proposal(requested_action="cleanup_log")

    await daemon._dispatch_proposal(repo, proposal, "dry_deliberate")

    repo.advance_status.assert_awaited_once()
    args = repo.advance_status.call_args
    assert args.args[1] == ProposalStatus.PROPOSED


@pytest.mark.asyncio
async def test_dispatch_dry_deliberate_no_action_advances_proposed(
    daemon_with_audit_mock,
) -> None:
    """When action is None in dry_deliberate, still advance to proposed."""
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    proposal = _proposal(requested_action=None)

    await daemon._dispatch_proposal(repo, proposal, "dry_deliberate")

    args = repo.advance_status.call_args
    assert args.args[1] == ProposalStatus.PROPOSED


# ---------------------------------------------------------------------------
# Mode dispatch — production + blocked action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_no_action_in_production_quarantines(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    proposal = _proposal(requested_action=None)

    await daemon._dispatch_proposal(repo, proposal, "production")

    args = repo.advance_status.call_args
    assert args.args[1] == ProposalStatus.QUARANTINED


# ---------------------------------------------------------------------------
# HITL_ONLY: requires_approval routes to awaiting_approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_hitl_only_routes_to_awaiting_approval(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    repo.request_approval = AsyncMock(
        return_value=_proposal(requested_action="restart_agent", status="awaiting_approval")
    )

    daemon._pool = MagicMock()
    # Daemon falls back to "<no-telegram>" when bot_token/chat_id are None
    # (FADConfig in fixture has them as None).

    proposal = _proposal(requested_action="restart_agent")

    await daemon._dispatch_proposal(repo, proposal, "production")

    # restart_agent is HITL_ONLY → daemon calls repo.request_approval.
    # advance_status is NOT called for this path.
    repo.advance_status.assert_not_called()
    repo.request_approval.assert_awaited_once()
    # When telegram credentials are missing, chat_id="<no-telegram>"
    kwargs = repo.request_approval.call_args.kwargs
    assert kwargs["telegram_chat_id"] == "<no-telegram>"
    assert kwargs["telegram_message_id"] is None
    # Token must be a non-empty hex string
    assert isinstance(kwargs["approval_token"], str)
    assert len(kwargs["approval_token"]) == 64


# ---------------------------------------------------------------------------
# Action execution: dry_action runs with dry_run=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_dry_action_executes_with_dry_run_true(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()

    # Mock pool present so action runs
    daemon._pool = MagicMock()

    proposal = _proposal(requested_action="cleanup_log")

    # Capture action invocation
    fake_result = SimpleNamespace(success=True, message="dry-ok", side_effects=(), metadata={})
    fake_action = AsyncMock(return_value=fake_result)

    with patch(
        "backend.services.federation_alerts.daemon.get_action",
        return_value=fake_action,
    ):
        await daemon._dispatch_proposal(repo, proposal, "dry_action")

    fake_action.assert_awaited_once()
    kwargs = fake_action.call_args.kwargs
    assert kwargs["dry_run"] is True

    # Two advance_status calls: dry_executing, then dry_succeeded
    assert repo.advance_status.await_count == 2
    last_call_args = repo.advance_status.call_args_list[-1].args
    assert last_call_args[1] == ProposalStatus.DRY_SUCCEEDED


@pytest.mark.asyncio
async def test_dispatch_production_executes_with_dry_run_false(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    daemon._pool = MagicMock()

    proposal = _proposal(requested_action="cleanup_log")
    fake_result = SimpleNamespace(success=True, message="ok", side_effects=(), metadata={})
    fake_action = AsyncMock(return_value=fake_result)

    with patch(
        "backend.services.federation_alerts.daemon.get_action",
        return_value=fake_action,
    ):
        await daemon._dispatch_proposal(repo, proposal, "production")

    kwargs = fake_action.call_args.kwargs
    assert kwargs["dry_run"] is False
    last_call_args = repo.advance_status.call_args_list[-1].args
    assert last_call_args[1] == ProposalStatus.COMPLETED


@pytest.mark.asyncio
async def test_dispatch_production_action_failure_advances_failed(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.advance_status = AsyncMock()
    daemon._pool = MagicMock()

    proposal = _proposal(requested_action="cleanup_log")
    fake_result = SimpleNamespace(
        success=False, message="something broke", side_effects=(), metadata={}
    )
    fake_action = AsyncMock(return_value=fake_result)

    with patch(
        "backend.services.federation_alerts.daemon.get_action",
        return_value=fake_action,
    ):
        await daemon._dispatch_proposal(repo, proposal, "production")

    last = repo.advance_status.call_args_list[-1]
    assert last.args[1] == ProposalStatus.FAILED
    assert last.kwargs.get("last_error") == "something broke"


# ---------------------------------------------------------------------------
# Payload parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_notify_payload_malformed_json(
    daemon_with_audit_mock,
    tmp_path,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.get_by_proposal_id = AsyncMock()

    # Should NOT raise, and must audit-log the malformed payload instead of
    # silently dropping it.
    result = await daemon._process_notify_payload("not-json", repo)

    assert result is None
    repo.get_by_proposal_id.assert_not_called()

    audit_files = list(tmp_path.glob("*.jsonl"))
    assert len(audit_files) == 1
    lines = [json.loads(line) for line in audit_files[0].read_text().splitlines()]
    malformed_events = [line for line in lines if line["event"] == "daemon.payload_malformed"]
    assert len(malformed_events) == 1


@pytest.mark.asyncio
async def test_process_notify_payload_missing_proposal_id(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.get_by_proposal_id = AsyncMock()
    await daemon._process_notify_payload(json.dumps({"v": 1}), repo)
    repo.get_by_proposal_id.assert_not_called()


@pytest.mark.asyncio
async def test_process_notify_payload_unknown_proposal(
    daemon_with_audit_mock,
    caplog,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.get_by_proposal_id = AsyncMock(return_value=None)
    repo.acquire_lease = AsyncMock()

    caplog.set_level(logging.WARNING)
    result = await daemon._process_notify_payload(
        json.dumps({"v": 1, "proposal_id": "ghost"}), repo
    )

    # Should NOT raise, must return without dispatching, and must warn about
    # the unknown proposal instead of silently dropping the notification.
    assert result is None
    repo.get_by_proposal_id.assert_called_once_with("ghost")
    repo.acquire_lease.assert_not_called()
    assert "federation_alert references unknown proposal ghost" in caplog.text


@pytest.mark.asyncio
async def test_process_notify_payload_terminal_proposal_skipped(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    proposal = _proposal(is_terminal=True)
    repo.get_by_proposal_id = AsyncMock(return_value=proposal)
    repo.acquire_lease = AsyncMock()
    await daemon._process_notify_payload(json.dumps({"v": 1, "proposal_id": "pid-1"}), repo)
    repo.acquire_lease.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_replay_serialises_dict_payload(
    daemon_with_audit_mock,
) -> None:
    """Replay path receives a dict from outbox; daemon must JSON-encode it.

    Regression for the replay-kwarg + dict-vs-str mismatch surfaced during
    the live smoke test on Pro (2026-04-30). ``replay_unconsumed`` decodes
    the JSONB column and injects ``_outbox_id`` / ``_replay`` before
    dispatch — the daemon's ``_enqueue_replay`` must accept a dict and
    funnel it through ``_process_notify_payload`` (which expects str).
    """
    daemon = daemon_with_audit_mock
    daemon._pool = MagicMock()  # FederationAlertRepo() requires pool|conn
    captured: list[str] = []

    async def fake_process(payload_str, _repo):  # noqa: ANN001
        captured.append(payload_str)

    daemon._process_notify_payload = fake_process  # type: ignore[assignment]

    payload_dict = {
        "v": 1,
        "proposal_id": "replay-pid",
        "run_id": "replay-run",
        "_outbox_id": 42,
        "_replay": True,
    }
    await daemon._enqueue_replay(payload_dict)

    assert len(captured) == 1
    decoded = json.loads(captured[0])
    assert decoded["proposal_id"] == "replay-pid"
    assert decoded["_outbox_id"] == 42
    assert decoded["_replay"] is True


def test_replay_unconsumed_signature_uses_positional_dispatch_fn() -> None:
    """``replay_unconsumed`` takes ``dispatch_fn`` as positional arg.

    The daemon must NOT pass it as ``dispatch=`` kwarg — that crashed at
    boot during the 2026-04-30 smoke test with::

        TypeError: replay_unconsumed() got an unexpected keyword argument
        'dispatch'

    This test pins the contract so a future refactor can't reintroduce
    the mismatch silently.
    """
    import inspect

    from backend.services.events.outbox import replay_unconsumed

    sig = inspect.signature(replay_unconsumed)
    params = list(sig.parameters.values())
    # conn (positional), dispatch_fn (positional-or-keyword), then kw-only
    assert params[1].name == "dispatch_fn"
    assert params[1].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    assert "dispatch" not in sig.parameters


# ---------------------------------------------------------------------------
# LISTEN liveness probe — a silently dead connection must trigger reconnect
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, *, fetchval_raises: bool = False, closed: bool = False) -> None:
        self._raises = fetchval_raises
        self._closed = closed
        self.probes = 0
        self.terminated = False
        self.close_calls = 0

    async def add_listener(self, *_a, **_k) -> None:
        return None

    def add_termination_listener(self, _cb) -> None:
        return None

    def is_closed(self) -> bool:
        return self._closed

    async def fetchval(self, *_a, **_k):
        self.probes += 1
        if self._raises:
            raise OSError("proxy flap")
        return 1

    async def close(self) -> None:
        self.close_calls += 1

    def terminate(self) -> None:
        self.terminated = True


async def _run_listen(daemon, conns, monkeypatch, *, run_s: float = 0.15):
    from backend.services.federation_alerts import daemon as dmod

    monkeypatch.setattr(dmod, "LISTEN_PROBE_INTERVAL_S", 0.01)
    monkeypatch.setattr(dmod, "LISTEN_PROBE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(dmod, "LISTEN_IDLE_POLL_S", 0.005)
    import asyncio

    pending = list(conns)
    connect = AsyncMock(
        side_effect=lambda *_a, **_k: pending.pop(0) if len(pending) > 1 else pending[0]
    )
    monkeypatch.setattr(dmod.asyncpg, "connect", connect)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(dmod.asyncio, "sleep", lambda _s: real_sleep(0))
    daemon._replay_missed = AsyncMock()

    async def _stopper() -> None:
        await real_sleep(run_s)
        daemon._stop_event.set()

    stopper = asyncio.create_task(_stopper())
    await daemon._listen_loop(MagicMock())
    await stopper
    return connect


@pytest.mark.asyncio
async def test_dead_listen_connection_triggers_reconnect_and_replay(
    daemon_with_audit_mock, monkeypatch
) -> None:
    dead, healthy = _FakeConn(fetchval_raises=True), _FakeConn()
    connect = await _run_listen(daemon_with_audit_mock, [dead, healthy], monkeypatch)
    assert connect.await_count >= 2
    assert dead.close_calls == 1
    daemon_with_audit_mock._replay_missed.assert_awaited_with("reconnect")


@pytest.mark.asyncio
async def test_closed_listen_connection_triggers_reconnect(
    daemon_with_audit_mock, monkeypatch
) -> None:
    closed, healthy = _FakeConn(closed=True), _FakeConn()
    connect = await _run_listen(daemon_with_audit_mock, [closed, healthy], monkeypatch)
    assert connect.await_count >= 2
    daemon_with_audit_mock._replay_missed.assert_awaited_with("reconnect")


@pytest.mark.asyncio
async def test_healthy_idle_connection_never_reconnects(
    daemon_with_audit_mock, monkeypatch
) -> None:
    healthy = _FakeConn()
    connect = await _run_listen(daemon_with_audit_mock, [healthy], monkeypatch)
    assert connect.await_count == 1
    assert healthy.probes >= 3
    daemon_with_audit_mock._replay_missed.assert_not_awaited()
    assert daemon_with_audit_mock.probe_age_s() is not None


@pytest.mark.asyncio
async def test_close_quietly_terminates_when_close_hangs() -> None:
    import asyncio

    from backend.services.federation_alerts.daemon import _close_quietly

    class _Hang(_FakeConn):
        async def close(self) -> None:
            await asyncio.sleep(10)

    conn = _Hang()
    await _close_quietly(conn, timeout=0.01)
    assert conn.terminated is True


def test_heartbeat_classification_by_probe_age() -> None:
    from backend.scripts.federation_alert_daemon import classify_probe_age

    status, note = classify_probe_age(10)
    assert status == "ok" and "probe_age=10s" in note
    status, note = classify_probe_age(500)
    assert status == "degraded" and "probe_age=500s" in note
    assert classify_probe_age(None)[0] == "degraded"
