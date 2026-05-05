"""Pydantic models for Federation Alert Dispatcher proposals.

Mirrors the schema in migration 147. Strict typing here means the
daemon, dispatcher, and webhook handlers cannot drift from the DB
constraints (every CHECK in the migration has a corresponding Enum
or validator below).

Usage:
    alert = AlertInput(
        proposal_id="...",
        run_id="...",
        idempotency_key=hash_alert(payload),
        mode=FederationAlertMode.OBSERVE,
        alert_type="cron_failure",
        severity=AlertSeverity.HIGH,
        compact_payload={"v": 1, ...},
        full_payload={...},
    )
    row = await repo.create_from_alert(alert)
    # ... daemon picks up via LISTEN, advances status through SM
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# pg_notify hard limit is 8000 bytes; FAD compact_payload target keeps
# 10× headroom so a single event never trips the safety net.
PG_NOTIFY_HARD_LIMIT_BYTES = 8000
FAD_COMPACT_PAYLOAD_MAX_BYTES = 500


class FederationAlertMode(str, Enum):
    """Dispatcher operating mode. Env var can only DOWNGRADE from DB value."""

    OBSERVE = "observe"
    DRY_DELIBERATE = "dry_deliberate"
    DRY_ACTION = "dry_action"
    PRODUCTION = "production"


_MODE_ORDER: dict[str, int] = {
    FederationAlertMode.OBSERVE.value: 0,
    FederationAlertMode.DRY_DELIBERATE.value: 1,
    FederationAlertMode.DRY_ACTION.value: 2,
    FederationAlertMode.PRODUCTION.value: 3,
}


def effective_mode(db_mode: str, env_mode: str | None) -> str:
    """Take the SAFER (lower) of DB and env. Env can only DOWNGRADE."""
    if env_mode is None:
        return db_mode
    if env_mode not in _MODE_ORDER:
        # Defensive: unknown env value falls back to DB
        return db_mode
    return min((db_mode, env_mode), key=lambda m: _MODE_ORDER[m])


class ProposalStatus(str, Enum):
    """Proposal state machine. See spec for transitions."""

    RECEIVED = "received"
    OBSERVED = "observed"
    DELIBERATING = "deliberating"
    PROPOSED = "proposed"
    DRY_EXECUTING = "dry_executing"
    DRY_SUCCEEDED = "dry_succeeded"
    DRY_FAILED = "dry_failed"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    DUPLICATE = "duplicate"


_TERMINAL_STATUSES: frozenset[str] = frozenset({
    ProposalStatus.OBSERVED.value,
    ProposalStatus.DRY_SUCCEEDED.value,
    ProposalStatus.DRY_FAILED.value,
    ProposalStatus.COMPLETED.value,
    ProposalStatus.FAILED.value,
    ProposalStatus.QUARANTINED.value,
    ProposalStatus.DUPLICATE.value,
})


def is_terminal_status(status: str) -> bool:
    return status in _TERMINAL_STATUSES


class AlertSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class RequestedAction(str, Enum):
    """FAD whitelist — actions safe enough to be proposed by Consiglio + executed.

    Whitelist V1 (PR #393) — 4 idempotent maintenance ops on local resources:
        CLEANUP_LOG, ACK_OUTBOX_EVENT, QUARANTINE_ALERT, PRUNE_CONSUMED_OUTBOX

    Whitelist V2 (this PR) — 4 Codex 5.5 capabilities (OAuth Pro $200, no API key):
        CODEX_XHIGH_FIX        — HITL_ONLY: deep agentic fix via Codex gpt-5.5 xhigh
        CODEX_OVERNIGHT_QUEUE  — ALLOWED_L2: enqueue task for overnight runner
                                 (non-destructive: queue write only; runner has
                                 its own safeguards)
        CODEX_IMAGE_GEN        — HITL_ONLY: single-image gpt-image-2 OAuth
        CODEX_VISUAL_DISPATCH  — HITL_ONLY: 15-asset bundle for BZ dispatch

    BLOCKED:
        cleanup_zombie_plist — replicates P0-3 threat model (2026-04-29
                               51/54 plist corruption, producer unidentified).
    HITL_ONLY (requires approval even in production):
        restart_agent        — organism restart loop amplification risk.
        codex_xhigh_fix      — deep code edit with potential blast radius.
        codex_image_gen      — public-facing artifact, editorial gate.
        codex_visual_dispatch — public-facing bundle, editorial gate.
    """

    CLEANUP_LOG = "cleanup_log"
    ACK_OUTBOX_EVENT = "ack_outbox_event"
    QUARANTINE_ALERT = "quarantine_alert"
    PRUNE_CONSUMED_OUTBOX = "prune_consumed_outbox"
    # Whitelist V2 — Codex 5.5 capabilities (OAuth, no API key)
    CODEX_XHIGH_FIX = "codex_xhigh_fix"
    CODEX_OVERNIGHT_QUEUE = "codex_overnight_queue"
    CODEX_IMAGE_GEN = "codex_image_gen"
    CODEX_VISUAL_DISPATCH = "codex_visual_dispatch"


class AlertInput(BaseModel):
    """Payload to create a new proposal from an inbound alert.

    The repository's ON CONFLICT (idempotency_key) DO UPDATE keeps this
    a safe upsert — same alert fingerprint within the dedup window
    returns the existing row instead of creating a duplicate.
    """

    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    proposal_id: str = Field(..., min_length=1, max_length=128)
    run_id: str = Field(..., min_length=1, max_length=128)
    idempotency_key: str = Field(..., min_length=1, max_length=128)

    source_outbox_id: int | None = None
    source_channel: str = Field(default="federation_alert", max_length=64)
    source_ref: str | None = Field(default=None, max_length=256)

    mode: FederationAlertMode
    alert_type: str = Field(..., min_length=1, max_length=128)
    severity: AlertSeverity = AlertSeverity.MEDIUM
    risk_level: RiskLevel = RiskLevel.L2

    requested_action: RequestedAction | None = None
    target_file: str | None = Field(default=None, max_length=512)

    action_payload: dict[str, Any] = Field(default_factory=dict)
    compact_payload: dict[str, Any] = Field(default_factory=dict)
    full_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("compact_payload")
    @classmethod
    def _enforce_compact_payload_size(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        """compact_payload is what travels over pg_notify.

        DB enforces octet_length(compact_payload::text) < 500. We mirror
        that constraint here so encoding errors surface at API boundary,
        not at COMMIT time.
        """
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        size = len(encoded.encode("utf-8"))
        if size >= FAD_COMPACT_PAYLOAD_MAX_BYTES:
            raise ValueError(
                f"compact_payload too large: {size}B "
                f"(max {FAD_COMPACT_PAYLOAD_MAX_BYTES}B). "
                "Move large fields into full_payload (DB row only)."
            )
        if size >= PG_NOTIFY_HARD_LIMIT_BYTES:
            # Belt-and-suspenders; should be unreachable given the
            # FAD_COMPACT_PAYLOAD_MAX_BYTES guard above.
            raise ValueError(
                f"pg_notify hard limit exceeded: {size}B"
            )
        return value


class ProposalRow(BaseModel):
    """Row projection of federation_alert_proposals for daemon/handlers.

    Includes all fields the daemon needs to process a proposal — the
    full payload is fetched from this row, not from the pg_notify
    (which carries only a reference + minimal metadata).
    """

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
    )

    id: int
    proposal_id: str
    run_id: str
    idempotency_key: str

    source_outbox_id: int | None = None
    source_channel: str
    source_ref: str | None = None

    mode: FederationAlertMode
    status: ProposalStatus
    alert_type: str
    severity: AlertSeverity
    risk_level: RiskLevel

    requested_action: RequestedAction | None = None
    target_file: str | None = None

    action_payload: dict[str, Any] = Field(default_factory=dict)
    compact_payload: dict[str, Any] = Field(default_factory=dict)
    full_payload: dict[str, Any] = Field(default_factory=dict)
    dispatch_plan: dict[str, Any] = Field(default_factory=dict)
    deliberation_result: dict[str, Any] = Field(default_factory=dict)
    votes: dict[str, Any] = Field(default_factory=dict)
    gate_6_passes: bool | None = None

    requires_approval: bool = False
    approval_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_message_id: int | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None

    action_idempotency_key: str | None = None
    quarantine_token: str | None = None
    quarantine_reason: str | None = None
    quarantined_at: datetime | None = None

    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime

    last_error: str | None = None
    last_error_at: datetime | None = None
    artifact_uri: str | None = None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    def is_terminal(self) -> bool:
        return is_terminal_status(self.status if isinstance(self.status, str) else self.status.value)
