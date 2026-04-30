"""Unit tests for FederationAlertDaemon — mode SM + classify dispatch."""

from __future__ import annotations

import json
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
    repo.request_approval = AsyncMock(return_value=_proposal(
        requested_action="restart_agent", status="awaiting_approval"
    ))

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
    fake_result = SimpleNamespace(
        success=True, message="dry-ok", side_effects=(), metadata={}
    )
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
    fake_result = SimpleNamespace(
        success=True, message="ok", side_effects=(), metadata={}
    )
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
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    # Should NOT raise
    await daemon._process_notify_payload("not-json", repo)


@pytest.mark.asyncio
async def test_process_notify_payload_missing_proposal_id(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.get_by_proposal_id = AsyncMock()
    await daemon._process_notify_payload(
        json.dumps({"v": 1}), repo
    )
    repo.get_by_proposal_id.assert_not_called()


@pytest.mark.asyncio
async def test_process_notify_payload_unknown_proposal(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    repo.get_by_proposal_id = AsyncMock(return_value=None)
    await daemon._process_notify_payload(
        json.dumps({"v": 1, "proposal_id": "ghost"}), repo
    )


@pytest.mark.asyncio
async def test_process_notify_payload_terminal_proposal_skipped(
    daemon_with_audit_mock,
) -> None:
    daemon = daemon_with_audit_mock
    repo = MagicMock()
    proposal = _proposal(is_terminal=True)
    repo.get_by_proposal_id = AsyncMock(return_value=proposal)
    repo.acquire_lease = AsyncMock()
    await daemon._process_notify_payload(
        json.dumps({"v": 1, "proposal_id": "pid-1"}), repo
    )
    repo.acquire_lease.assert_not_called()
