"""Genome scar recorder for crm-cell.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/crm-cell-design.md
  docs/sprint3/review-synthesis-2026-05-04.md (I5 — stubs landed 2026-05-04)

Records recurring failure patterns from CRM operations (welcome flow
partial-failure per sub-step, drive_poll circuit-breaker open, Brevo
delivery bounce, WhatsApp template rejected) as scars in the cell-core
Genome. Scars are NEVER blocking — record-then-continue is the contract.

Scope: Personal (somatic, never inherited via HGT). Structural patterns
that DO get shared with sibling cells (e.g. "WhatsApp template ID X
reliably bounces for visa-applicant client_segment") go through
:mod:`hgt_publisher`.

Scar id namespace: ``crm.<sub_module>.<failure_kind>``.

W2 status: STUB. The methods accept the canonical inputs and return
``None``. Wiring into welcome_practice_service / drive_poll_service /
crm_automation_engine lands in Sprint 4 once cell-core Genome
integration in backend-rag is finalized (PR #449 ships only the
adapter contract).
"""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("crm_cell.scar_recorder")


class FailureKind(str, enum.Enum):
    """Known CRM failure modes worth tracking as scars."""

    WELCOME_PARTIAL_FAILURE = "welcome_partial_failure"  # 1 of 4 sub-steps failed
    DRIVE_CIRCUIT_OPEN = "drive_circuit_open"            # 3-fail breaker tripped
    BREVO_BOUNCE = "brevo_bounce"                        # email rejected by Brevo
    WHATSAPP_TEMPLATE_REJECTED = "whatsapp_template_rejected"
    WHATSAPP_QUOTA_EXCEEDED = "whatsapp_quota_exceeded"
    TELEGRAM_CHAT_NOT_FOUND = "telegram_chat_not_found"
    PRACTICE_INSERT_RACE = "practice_insert_race"        # concurrent insert collision
    LISTENER_DISCONNECT = "listener_disconnect"          # PG LISTEN reconnect loop


@dataclass(frozen=True)
class CrmScar:
    """One scar instance — what failed, where, when."""

    failure_kind: FailureKind
    sub_module: str
    detail: str
    client_id: int | None = None
    practice_id: int | None = None
    observed_at: datetime | None = None


class CrmScarRecorder:
    """Pro-side scar accumulator for the CRM cell.

    Sprint 3 W2 stub. The eventual Sprint 4 implementation will call
    into ``packages/cell-core`` Genome (mirroring intel-scraper-cell
    pattern). The interface here is stable so callers can already wire
    `record(...)` calls without waiting for the Genome integration.
    """

    def __init__(self, *, genome=None) -> None:
        # The Genome handle is optional in Sprint 3 W2; Sprint 4 will
        # require it. Today the stub logs and discards.
        self._genome = genome

    def record(self, scar: CrmScar) -> None:
        """Record a CRM failure pattern as a scar."""
        if scar.observed_at is None:
            scar = CrmScar(
                failure_kind=scar.failure_kind,
                sub_module=scar.sub_module,
                detail=scar.detail,
                client_id=scar.client_id,
                practice_id=scar.practice_id,
                observed_at=datetime.now(tz=timezone.utc),
            )
        scar_id = f"crm.{scar.sub_module}.{scar.failure_kind.value}"
        logger.info(
            "[STUB] scar recorded id=%s detail=%s client_id=%s practice_id=%s",
            scar_id, scar.detail, scar.client_id, scar.practice_id,
        )
        # Sprint 4: call into self._genome.upsert_scar(scar_id, ...)
