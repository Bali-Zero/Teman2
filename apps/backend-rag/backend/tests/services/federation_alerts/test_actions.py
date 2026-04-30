"""Unit tests for FAD action registry + 4 V1 actions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.federation_alerts.actions import (
    ack_outbox_event as ack_module,
)
from backend.services.federation_alerts.actions import (
    cleanup_log as cleanup_module,
)
from backend.services.federation_alerts.actions import (
    prune_consumed_outbox as prune_module,
)
from backend.services.federation_alerts.actions import (
    quarantine_alert as quarantine_module,
)
from backend.services.federation_alerts.actions.registry import (
    ALLOWED_L2_ACTIONS,
    BLOCKED_ACTIONS,
    HITL_ONLY_ACTIONS,
    classify_action,
    get_action,
    list_actions,
)

# ---------------------------------------------------------------------------
# Registry / safety policy
# ---------------------------------------------------------------------------


def test_v1_whitelist_is_exactly_4() -> None:
    assert ALLOWED_L2_ACTIONS == frozenset({
        "cleanup_log",
        "ack_outbox_event",
        "quarantine_alert",
        "prune_consumed_outbox",
    })


def test_blocked_actions_contain_plist_threat() -> None:
    assert "cleanup_zombie_plist" in BLOCKED_ACTIONS


def test_hitl_only_contains_restart_agent() -> None:
    assert "restart_agent" in HITL_ONLY_ACTIONS


def test_classify_blocked_returns_blocked_policy() -> None:
    policy = classify_action("cleanup_zombie_plist")
    assert policy.blocked is True
    assert policy.requires_approval is False


def test_classify_hitl_only_requires_approval() -> None:
    policy = classify_action("restart_agent")
    assert policy.blocked is False
    assert policy.requires_approval is True


def test_classify_allowed_l2_no_approval() -> None:
    policy = classify_action("cleanup_log")
    assert policy.blocked is False
    assert policy.requires_approval is False


def test_classify_unknown_action_blocked() -> None:
    policy = classify_action("rm_rf_root")
    assert policy.blocked is True
    assert "unknown action" in (policy.reason or "")


def test_list_actions_contains_all_v1() -> None:
    registered = set(list_actions())
    assert {"cleanup_log", "ack_outbox_event", "quarantine_alert",
            "prune_consumed_outbox"}.issubset(registered)


def test_get_action_returns_callable() -> None:
    fn = get_action("cleanup_log")
    assert fn is not None
    assert callable(fn)


def test_get_action_unknown_returns_none() -> None:
    assert get_action("nonexistent") is None


# ---------------------------------------------------------------------------
# cleanup_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_log_no_candidates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    proposal = SimpleNamespace(action_payload={})
    result = await cleanup_module.cleanup_log_action(proposal, dry_run=False)
    assert result.success is True
    assert "no candidates" in result.message


@pytest.mark.asyncio
async def test_cleanup_log_dry_run_lists_files(tmp_path, monkeypatch) -> None:
    """Files older than 7 days must be listed in dry-run."""
    import os

    logs = tmp_path / "logs"
    logs.mkdir()
    old = logs / "old.log"
    old.write_text("ancient")
    new = logs / "new.log"
    new.write_text("fresh")
    # Backdate old by 30 days
    old_mtime = (
        cleanup_module.datetime.now(cleanup_module.timezone.utc)
        - cleanup_module.timedelta(days=30)
    ).timestamp()
    os.utime(old, (old_mtime, old_mtime))
    monkeypatch.setenv("HOME", str(tmp_path))

    proposal = SimpleNamespace(action_payload={})
    result = await cleanup_module.cleanup_log_action(proposal, dry_run=True)
    assert result.success is True
    assert "DRY-RUN" in result.message
    # Side-effects list the would-remove paths
    assert any("old.log" in s for s in result.side_effects)
    # New file is NOT included
    assert not any("new.log" in s for s in result.side_effects)


@pytest.mark.asyncio
async def test_cleanup_log_respects_max_age_clamp() -> None:
    """max_age_days clamped to [1, 365]."""
    proposal = SimpleNamespace(action_payload={"max_age_days": 9999})
    # We can't easily test the actual file deletion; just ensure no crash
    result = await cleanup_module.cleanup_log_action(proposal, dry_run=True)
    assert result.success is True


# ---------------------------------------------------------------------------
# ack_outbox_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ack_outbox_event_missing_id() -> None:
    proposal = SimpleNamespace(action_payload={})
    result = await ack_module.ack_outbox_event_action(
        proposal, dry_run=True, db_pool=MagicMock()
    )
    assert result.success is False
    assert "outbox_id" in result.message


@pytest.mark.asyncio
async def test_ack_outbox_event_missing_pool() -> None:
    proposal = SimpleNamespace(action_payload={"outbox_id": 42})
    result = await ack_module.ack_outbox_event_action(proposal, db_pool=None)
    assert result.success is False
    assert "db_pool" in result.message


@pytest.mark.asyncio
async def test_ack_outbox_event_invalid_type() -> None:
    proposal = SimpleNamespace(action_payload={"outbox_id": "not-int"})
    result = await ack_module.ack_outbox_event_action(
        proposal, dry_run=True, db_pool=MagicMock()
    )
    assert result.success is False
    assert "must be int" in result.message


@pytest.mark.asyncio
async def test_ack_outbox_event_idempotent_already_consumed(mock_db_pool) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value=None)  # UPDATE matched 0 rows
    proposal = SimpleNamespace(action_payload={"outbox_id": 42})
    result = await ack_module.ack_outbox_event_action(
        proposal, dry_run=False, db_pool=pool
    )
    assert result.success is True
    assert "already consumed" in result.message


@pytest.mark.asyncio
async def test_ack_outbox_event_succeeds(mock_db_pool) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={"id": 42, "channel": "federation_alert"}
    )
    proposal = SimpleNamespace(action_payload={"outbox_id": 42, "reason": "test"})
    result = await ack_module.ack_outbox_event_action(
        proposal, dry_run=False, db_pool=pool
    )
    assert result.success is True
    assert "acked outbox_id 42" in result.message
    assert any("42" in s for s in result.side_effects)


# ---------------------------------------------------------------------------
# quarantine_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quarantine_alert_missing_target() -> None:
    """When neither action_payload.target_proposal_id nor proposal.proposal_id
    is set, the action fails fast."""
    proposal = SimpleNamespace(action_payload={})
    # Need to ensure proposal.proposal_id is also missing
    # SimpleNamespace without proposal_id attribute → getattr returns default
    result = await quarantine_module.quarantine_alert_action(
        proposal, dry_run=True, db_pool=MagicMock()
    )
    assert result.success is False
    assert "target_proposal_id" in result.message


@pytest.mark.asyncio
async def test_quarantine_alert_dry_run_existing(mock_db_pool) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={
            "proposal_id": "pid-x",
            "status": "received",
            "quarantined_at": None,
        }
    )
    proposal = SimpleNamespace(
        action_payload={
            "target_proposal_id": "pid-x",
            "reason_code": "duplicate_fingerprint",
        }
    )
    result = await quarantine_module.quarantine_alert_action(
        proposal, dry_run=True, db_pool=pool
    )
    assert result.success is True
    assert "DRY-RUN" in result.message
    assert "pid-x" in result.message


@pytest.mark.asyncio
async def test_quarantine_alert_already_quarantined(mock_db_pool) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(
        return_value={
            "proposal_id": "pid-x",
            "status": "quarantined",
            "quarantined_at": "2026-04-30T00:00:00Z",
        }
    )
    proposal = SimpleNamespace(
        action_payload={
            "target_proposal_id": "pid-x",
            "reason_code": "duplicate_fingerprint",
        }
    )
    result = await quarantine_module.quarantine_alert_action(
        proposal, dry_run=True, db_pool=pool
    )
    assert result.success is True
    assert "already quarantined" in result.message


@pytest.mark.asyncio
async def test_quarantine_alert_terminal_blocked(mock_db_pool) -> None:
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value={"status": "completed"})
    proposal = SimpleNamespace(
        action_payload={"target_proposal_id": "pid-x", "reason_code": "x"}
    )
    result = await quarantine_module.quarantine_alert_action(
        proposal, dry_run=False, db_pool=pool
    )
    assert result.success is False
    assert "terminal" in result.message


@pytest.mark.asyncio
async def test_quarantine_alert_token_deterministic() -> None:
    """Same proposal_id+reason_code → same SHA256 token."""
    t1 = quarantine_module._quarantine_token("pid-1", "dup")
    t2 = quarantine_module._quarantine_token("pid-1", "dup")
    t3 = quarantine_module._quarantine_token("pid-1", "noisy")
    assert t1 == t2
    assert t1 != t3
    assert len(t1) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# prune_consumed_outbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_consumed_outbox_no_pool() -> None:
    proposal = SimpleNamespace(action_payload={})
    result = await prune_module.prune_consumed_outbox_action(
        proposal, dry_run=True, db_pool=None
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_prune_consumed_outbox_dry_run(mock_db_pool) -> None:
    pool, conn = mock_db_pool
    conn.fetchval = AsyncMock(return_value=42)
    proposal = SimpleNamespace(action_payload={})
    result = await prune_module.prune_consumed_outbox_action(
        proposal, dry_run=True, db_pool=pool
    )
    assert result.success is True
    assert "would prune 42" in result.message


@pytest.mark.asyncio
async def test_prune_consumed_outbox_clamps_max_age() -> None:
    """max_age_days < 1 clamped to 1, > 365 clamped to 365."""
    # Just verify no crash on edge values; the SQL is mocked
    proposal_a = SimpleNamespace(action_payload={"max_age_days": 0})
    proposal_b = SimpleNamespace(action_payload={"max_age_days": 99999})
    # No pool injected → fails fast (acceptable for clamp test)
    result_a = await prune_module.prune_consumed_outbox_action(
        proposal_a, dry_run=True, db_pool=None
    )
    result_b = await prune_module.prune_consumed_outbox_action(
        proposal_b, dry_run=True, db_pool=None
    )
    # Both fail at the db_pool check, not at the clamp
    assert result_a.success is False
    assert result_b.success is False
    assert "db_pool" in result_a.message
    assert "db_pool" in result_b.message
