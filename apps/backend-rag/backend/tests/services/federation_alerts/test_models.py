"""Unit tests for FAD models — schema, validators, mode arithmetic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.federation_alerts.models import (
    FAD_COMPACT_PAYLOAD_MAX_BYTES,
    AlertInput,
    AlertSeverity,
    FederationAlertMode,
    ProposalStatus,
    RequestedAction,
    RiskLevel,
    effective_mode,
    is_terminal_status,
)

# ---------------------------------------------------------------------------
# effective_mode (B10 — env can only DOWNGRADE from DB)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "db_mode,env_mode,expected",
    [
        ("production", None, "production"),
        ("production", "observe", "observe"),         # env downgrades
        ("production", "dry_action", "dry_action"),   # env downgrades
        ("observe", "production", "observe"),         # env CANNOT upgrade
        ("dry_action", "production", "dry_action"),   # env CANNOT upgrade
        ("dry_deliberate", "dry_deliberate", "dry_deliberate"),
        ("production", "garbage", "production"),      # invalid env → DB
    ],
)
def test_effective_mode_takes_safer(
    db_mode: str, env_mode: str | None, expected: str
) -> None:
    assert effective_mode(db_mode, env_mode) == expected


# ---------------------------------------------------------------------------
# is_terminal_status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected",
    [
        ("received", False),
        ("deliberating", False),
        ("proposed", False),
        ("dry_executing", False),
        ("awaiting_approval", False),
        ("executing", False),
        ("observed", True),
        ("dry_succeeded", True),
        ("dry_failed", True),
        ("completed", True),
        ("failed", True),
        ("quarantined", True),
        ("duplicate", True),
    ],
)
def test_is_terminal_status(status: str, expected: bool) -> None:
    assert is_terminal_status(status) is expected


# ---------------------------------------------------------------------------
# AlertInput — compact_payload size enforcement (B8: pg_notify 8000B limit)
# ---------------------------------------------------------------------------


def _make_alert(**overrides) -> AlertInput:
    base: dict = {
        "proposal_id": "pid-1",
        "run_id": "rid-1",
        "idempotency_key": "iden-1",
        "mode": FederationAlertMode.OBSERVE,
        "alert_type": "cron_failure",
        "severity": AlertSeverity.MEDIUM,
        "compact_payload": {"v": 1},
        "full_payload": {},
    }
    base.update(overrides)
    return AlertInput(**base)


def test_alert_input_minimal_valid() -> None:
    alert = _make_alert()
    assert alert.proposal_id == "pid-1"
    assert alert.severity == AlertSeverity.MEDIUM.value
    assert alert.risk_level == RiskLevel.L2.value


def test_alert_input_compact_payload_under_500b_passes() -> None:
    payload = {"v": 1, "msg": "x" * 100}
    alert = _make_alert(compact_payload=payload)
    assert alert.compact_payload == payload


def test_alert_input_compact_payload_over_500b_rejected() -> None:
    payload = {"v": 1, "msg": "x" * (FAD_COMPACT_PAYLOAD_MAX_BYTES + 100)}
    with pytest.raises(ValidationError) as exc_info:
        _make_alert(compact_payload=payload)
    err_msg = str(exc_info.value)
    assert "compact_payload too large" in err_msg
    assert "500B" in err_msg


def test_alert_input_full_payload_unconstrained() -> None:
    """full_payload has no size limit — it lives in the DB row only."""
    big = {"v": 1, "stack_trace": "x" * 5000}
    alert = _make_alert(full_payload=big)
    assert len(alert.full_payload["stack_trace"]) == 5000


def test_alert_input_requested_action_optional() -> None:
    alert = _make_alert(requested_action=None)
    assert alert.requested_action is None


def test_alert_input_requested_action_enum() -> None:
    alert = _make_alert(requested_action=RequestedAction.CLEANUP_LOG)
    assert alert.requested_action == RequestedAction.CLEANUP_LOG.value


def test_alert_input_unknown_field_rejected() -> None:
    """extra='forbid' — typos surface immediately."""
    with pytest.raises(ValidationError):
        _make_alert(unknown_field="oops")


def test_alert_input_severity_invalid_rejected() -> None:
    with pytest.raises(ValidationError):
        AlertInput(
            proposal_id="pid-1",
            run_id="rid-1",
            idempotency_key="iden-1",
            mode=FederationAlertMode.OBSERVE,
            alert_type="cron_failure",
            severity="catastrophic",  # not in AlertSeverity
        )


# ---------------------------------------------------------------------------
# Whitelist V1 — RequestedAction enum is exhaustive
# ---------------------------------------------------------------------------


def test_requested_action_v2_whitelist_exact() -> None:
    """V2 whitelist: V1 (4) + Codex 5.5 (4) = 8 actions total.

    V1 — idempotent maintenance ops:
        cleanup_log, ack_outbox_event, quarantine_alert, prune_consumed_outbox

    V2 — Codex 5.5 capabilities (OAuth Pro $200, no API key):
        codex_xhigh_fix         (HITL_ONLY: deep agentic fix)
        codex_overnight_queue   (ALLOWED_L2: non-destructive queue write)
        codex_image_gen         (HITL_ONLY: public-facing artifact)
        codex_visual_dispatch   (HITL_ONLY: 15-asset bundle)

    Adding a new action requires a deliberate review — this test fails as a guard.
    """
    assert {a.value for a in RequestedAction} == {
        # V1
        "cleanup_log",
        "ack_outbox_event",
        "quarantine_alert",
        "prune_consumed_outbox",
        # V2
        "codex_xhigh_fix",
        "codex_overnight_queue",
        "codex_image_gen",
        "codex_visual_dispatch",
    }


def test_requested_action_excludes_blocked() -> None:
    """cleanup_zombie_plist must NOT be a RequestedAction (P0-3 threat)."""
    assert "cleanup_zombie_plist" not in {a.value for a in RequestedAction}


def test_requested_action_excludes_legacy_hitl_only() -> None:
    """restart_agent is HITL_ONLY but NOT a RequestedAction — separate flow."""
    assert "restart_agent" not in {a.value for a in RequestedAction}


def test_requested_action_v2_includes_codex_capabilities() -> None:
    """V2 adds 4 Codex 5.5 capabilities to the RequestedAction enum.

    All use Codex CLI OAuth (Pro $200) — Golden Rule #13 compliant
    (no ANTHROPIC_API_KEY, no new OPENAI_API_KEY usage).
    """
    enum_values = {a.value for a in RequestedAction}
    assert "codex_xhigh_fix" in enum_values
    assert "codex_overnight_queue" in enum_values
    assert "codex_image_gen" in enum_values
    assert "codex_visual_dispatch" in enum_values


# ---------------------------------------------------------------------------
# FederationAlertMode + ProposalStatus enums coverage
# ---------------------------------------------------------------------------


def test_mode_enum_exact_values() -> None:
    assert {m.value for m in FederationAlertMode} == {
        "observe",
        "dry_deliberate",
        "dry_action",
        "production",
    }


def test_status_enum_exact_values() -> None:
    assert {s.value for s in ProposalStatus} == {
        "received",
        "observed",
        "deliberating",
        "proposed",
        "dry_executing",
        "dry_succeeded",
        "dry_failed",
        "awaiting_approval",
        "executing",
        "completed",
        "failed",
        "quarantined",
        "duplicate",
    }
