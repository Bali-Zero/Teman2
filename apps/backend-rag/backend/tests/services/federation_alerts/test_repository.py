"""Unit tests for FederationAlertRepo (mock asyncpg)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.federation_alerts.models import (
    AlertInput,
    AlertSeverity,
    FederationAlertMode,
    ProposalStatus,
    RequestedAction,
    RiskLevel,
)
from backend.services.federation_alerts.repository import FederationAlertRepo


@pytest.fixture
def repo_and_conn(mock_db_pool):
    pool, conn = mock_db_pool
    repo = FederationAlertRepo(pool=pool)
    return repo, conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _proposal_row(
    *,
    proposal_id: str = "pid-1",
    status: str = "received",
    mode: str = "observe",
    requested_action: str | None = None,
    lease_owner: str | None = None,
    lease_expires_at: datetime | None = None,
) -> dict:
    now = _now()
    return {
        "id": 1,
        "proposal_id": proposal_id,
        "run_id": f"rid-{proposal_id}",
        "idempotency_key": f"iden-{proposal_id}",
        "source_outbox_id": None,
        "source_channel": "federation_alert",
        "source_ref": None,
        "mode": mode,
        "status": status,
        "alert_type": "cron_failure",
        "severity": "medium",
        "risk_level": "L2",
        "requested_action": requested_action,
        "target_file": None,
        "action_payload": "{}",
        "compact_payload": '{"v":1}',
        "full_payload": "{}",
        "dispatch_plan": "{}",
        "deliberation_result": "{}",
        "votes": "{}",
        "gate_6_passes": None,
        "requires_approval": False,
        "approval_token": None,
        "telegram_chat_id": None,
        "telegram_message_id": None,
        "approved_by": None,
        "approved_at": None,
        "rejected_by": None,
        "rejected_at": None,
        "action_idempotency_key": None,
        "quarantine_token": None,
        "quarantine_reason": None,
        "quarantined_at": None,
        "lease_owner": lease_owner,
        "lease_expires_at": lease_expires_at,
        "attempt_count": 0,
        "max_attempts": 3,
        "next_attempt_at": now,
        "last_error": None,
        "last_error_at": None,
        "artifact_uri": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }


def _basic_alert(
    *,
    proposal_id: str = "pid-1",
    requested_action: RequestedAction | None = None,
) -> AlertInput:
    return AlertInput(
        proposal_id=proposal_id,
        run_id=f"rid-{proposal_id}",
        idempotency_key=f"iden-{proposal_id}",
        mode=FederationAlertMode.OBSERVE,
        alert_type="cron_failure",
        severity=AlertSeverity.MEDIUM,
        risk_level=RiskLevel.L2,
        requested_action=requested_action,
        compact_payload={"v": 1},
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_repo_requires_pool_or_conn() -> None:
    with pytest.raises(ValueError, match="pool or conn"):
        FederationAlertRepo()


def test_repo_accepts_pool(mock_db_pool) -> None:
    pool, _ = mock_db_pool
    repo = FederationAlertRepo(pool=pool)
    assert repo._pool is pool
    assert repo._conn is None


def test_repo_accepts_conn(mock_db_pool) -> None:
    _, conn = mock_db_pool
    repo = FederationAlertRepo(conn=conn)
    assert repo._conn is conn
    assert repo._pool is None


# ---------------------------------------------------------------------------
# create_from_alert — idempotency contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_alert_returns_proposal(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_proposal_row())
    proposal = await repo.create_from_alert(_basic_alert())
    assert proposal.proposal_id == "pid-1"
    assert proposal.status == ProposalStatus.RECEIVED.value
    assert proposal.mode == FederationAlertMode.OBSERVE.value
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_create_from_alert_serializes_jsonb(repo_and_conn) -> None:
    """JSONB args are passed as JSON text, not Python dicts."""
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_proposal_row())
    await repo.create_from_alert(
        _basic_alert(requested_action=RequestedAction.CLEANUP_LOG)
    )
    args = conn.fetchrow.call_args.args
    # Last 3 positional args are JSONB payloads serialized via json.dumps
    action_payload, compact_payload, full_payload = args[-3:]
    assert isinstance(action_payload, str)
    assert isinstance(compact_payload, str)
    assert isinstance(full_payload, str)
    assert compact_payload == '{"v":1}'


@pytest.mark.asyncio
async def test_create_from_alert_unwraps_enums(repo_and_conn) -> None:
    """Enum values are passed as strings to the SQL driver."""
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_proposal_row())
    await repo.create_from_alert(
        _basic_alert(requested_action=RequestedAction.QUARANTINE_ALERT)
    )
    args = conn.fetchrow.call_args.args
    # args[0] is SQL string. SQL params start at args[1].
    # Param order in INSERT: proposal_id, run_id, idempotency_key,
    # source_outbox_id, source_channel, source_ref,
    # mode, alert_type, severity, risk_level, requested_action, ...
    assert args[7] == "observe"          # mode
    assert args[9] == "medium"           # severity
    assert args[10] == "L2"              # risk_level
    assert args[11] == "quarantine_alert"  # requested_action


@pytest.mark.asyncio
async def test_create_from_alert_raises_when_db_returns_no_row(repo_and_conn) -> None:
    """Defensive: ON CONFLICT should always RETURN something; if not, raise."""
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(RuntimeError, match="returned no row"):
        await repo.create_from_alert(_basic_alert())


# ---------------------------------------------------------------------------
# get_by_proposal_id / get_by_idempotency_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_proposal_id_hit(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_proposal_row(proposal_id="pid-7"))
    proposal = await repo.get_by_proposal_id("pid-7")
    assert proposal is not None
    assert proposal.proposal_id == "pid-7"


@pytest.mark.asyncio
async def test_get_by_proposal_id_miss(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=None)
    proposal = await repo.get_by_proposal_id("nonexistent")
    assert proposal is None


@pytest.mark.asyncio
async def test_get_by_idempotency_key_hit(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=_proposal_row())
    proposal = await repo.get_by_idempotency_key("iden-pid-1")
    assert proposal is not None


# ---------------------------------------------------------------------------
# list_active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_active_returns_rows(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(
        return_value=[
            _proposal_row(proposal_id="pid-a", status="received"),
            _proposal_row(proposal_id="pid-b", status="awaiting_approval"),
        ]
    )
    rows = await repo.list_active()
    assert len(rows) == 2
    assert rows[0].proposal_id == "pid-a"
    assert rows[1].status == ProposalStatus.AWAITING_APPROVAL.value


@pytest.mark.asyncio
async def test_list_active_respects_limit(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetch = AsyncMock(return_value=[])
    await repo.list_active(limit=5)
    args = conn.fetch.call_args.args
    assert args[1] == 5


# ---------------------------------------------------------------------------
# advance_status — state machine guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_advance_status_normal_transition(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"status": "received"},  # current
            _proposal_row(status="deliberating"),  # updated
        ]
    )
    proposal = await repo.advance_status("pid-1", ProposalStatus.DELIBERATING)
    assert proposal.status == ProposalStatus.DELIBERATING.value


@pytest.mark.asyncio
async def test_advance_status_terminal_to_terminal_rejected(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value={"status": "completed"})
    with pytest.raises(ValueError, match="terminal status"):
        await repo.advance_status("pid-1", ProposalStatus.QUARANTINED)


@pytest.mark.asyncio
async def test_advance_status_proposal_not_found(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(LookupError, match="not found"):
        await repo.advance_status("ghost", ProposalStatus.DELIBERATING)


@pytest.mark.asyncio
async def test_advance_status_to_terminal_marks_completed(repo_and_conn) -> None:
    """When transitioning to a terminal state, completed_at is set."""
    repo, conn = repo_and_conn
    completed_row = _proposal_row(status="completed")
    completed_row["completed_at"] = _now()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"status": "executing"},
            completed_row,
        ]
    )
    proposal = await repo.advance_status("pid-1", ProposalStatus.COMPLETED)
    assert proposal.completed_at is not None


# ---------------------------------------------------------------------------
# Lease (B5 mitigation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_lease_first_taker_succeeds(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    acquired = await repo.acquire_lease("pid-1", owner="daemon-1")
    assert acquired is True


@pytest.mark.asyncio
async def test_acquire_lease_contention_returns_false(repo_and_conn) -> None:
    """When another daemon holds an unexpired lease, acquire_lease returns False."""
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=None)  # WHERE clause matched nothing
    acquired = await repo.acquire_lease("pid-1", owner="daemon-2")
    assert acquired is False


@pytest.mark.asyncio
async def test_release_lease_idempotent(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="UPDATE 0")
    await repo.release_lease("pid-1", owner="daemon-1")
    conn.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Mode persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_db_mode_returns_seeded_value(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value={"value": "observe"})
    mode = await repo.get_db_mode()
    assert mode == "observe"


@pytest.mark.asyncio
async def test_get_db_mode_defaults_to_observe_when_missing(repo_and_conn) -> None:
    """Defensive fallback: if the system_settings row is missing, return observe."""
    repo, conn = repo_and_conn
    conn.fetchrow = AsyncMock(return_value=None)
    mode = await repo.get_db_mode()
    assert mode == "observe"


@pytest.mark.asyncio
async def test_set_db_mode_validates(repo_and_conn) -> None:
    repo, _ = repo_and_conn
    with pytest.raises(ValueError, match="invalid"):
        await repo.set_db_mode("garbage")


@pytest.mark.asyncio
async def test_set_db_mode_accepts_valid_modes(repo_and_conn) -> None:
    repo, conn = repo_and_conn
    conn.execute = AsyncMock(return_value="INSERT 1")
    for mode in ("observe", "dry_deliberate", "dry_action", "production"):
        await repo.set_db_mode(mode, changed_by="zero")
    assert conn.execute.call_count == 4
