"""HGT publisher for crm-cell — broadcasts STRUCTURAL patterns only.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/crm-cell-design.md
  docs/sprint3/review-synthesis-2026-05-04.md (I5 — stubs landed 2026-05-04)

UU PDP discipline: client PII NEVER appears in HGT broadcasts. Only
structural insights — "Brevo template T123 bounces 80%+ for client
segment X", "WhatsApp message ID with template Y has 95% read-rate when
sent in window 06:00-09:00 WITA" — that other cells (analytics,
retention loop) can act on without seeing the underlying client data.

Confidence floor: 0.7 (per Sprint 1 contract — propose-only quarantine
via Kimi K2.6 OpenClaw agent in cell-core HGT coordinator).

W2 status: STUB. The methods accept the canonical inputs and return
``False`` (not published). Wiring into the cell-core HGT coordinator
lands in Sprint 4.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("crm_cell.hgt_publisher")

CONFIDENCE_FLOOR: float = 0.7


@dataclass(frozen=True)
class StructuralPattern:
    """One structural insight ready for HGT broadcast.

    NEVER carries client PII. ``payload`` MUST be a dict of
    primitive types (no client_id, no email, no name, no phone, no NPWP).
    """

    pattern_kind: str       # e.g. "brevo_template_bounce_rate"
    confidence: float       # 0.0-1.0; ≥ CONFIDENCE_FLOOR to publish
    payload: dict           # structural data (counts, timing, template_id)


class CrmHGTPublisher:
    """Pro-side HGT publisher for the CRM cell.

    Sprint 3 W2 stub. The eventual Sprint 4 implementation will publish
    to the Redis stream consumed by ``packages/cell-core/hgt_coordinator``
    (mirroring intel-scraper-cell pattern).
    """

    def __init__(self, *, hgt_stream=None) -> None:
        # The Redis stream handle is optional in Sprint 3 W2;
        # Sprint 4 will require it.
        self._hgt_stream = hgt_stream

    def publish(self, pattern: StructuralPattern) -> bool:
        """Broadcast a structural pattern to sibling cells.

        Returns True if published, False if filtered by the confidence
        floor or by PII contamination guard. The caller does NOT block on
        the return value — HGT is best-effort.
        """
        if pattern.confidence < CONFIDENCE_FLOOR:
            logger.debug(
                "[STUB] hgt: pattern %s below floor %s (got %s) — discarded",
                pattern.pattern_kind, CONFIDENCE_FLOOR, pattern.confidence,
            )
            return False
        if not self._is_pii_clean(pattern.payload):
            logger.warning(
                "[STUB] hgt: pattern %s blocked — payload contains PII tokens",
                pattern.pattern_kind,
            )
            return False
        logger.info(
            "[STUB] hgt: pattern %s would publish (confidence=%s, payload=%s)",
            pattern.pattern_kind, pattern.confidence, pattern.payload,
        )
        # Sprint 4: call into self._hgt_stream.xadd(...)
        return True

    @staticmethod
    def _is_pii_clean(payload: dict) -> bool:
        """Conservative PII guard — no client identifiers in HGT payload."""
        forbidden_keys = {
            "client_id", "email", "name", "surname", "phone",
            "npwp", "nib", "passport", "kitas_no", "ktp",
        }
        return not (set(payload.keys()) & forbidden_keys)
