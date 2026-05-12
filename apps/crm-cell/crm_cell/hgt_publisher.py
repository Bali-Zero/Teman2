"""HGT bridge for crm-cell — broadcasts STRUCTURAL patterns only.

Phase 3 TICKET A.1 — replaces Sprint 3 W2 sync stub (DELETED) with async
``CrmHGTBridge`` wrapping the canonical ``cell_core.hgt.publisher.HGTPublisher``.

UU PDP discipline: client PII NEVER appears in HGT broadcasts. Only
structural insights — "Brevo template T123 bounces 80%+ for client
segment X" — that other cells can act on without seeing client data.

Confidence floor: read from ``HGTPublisher.CONFIDENCE_THRESHOLD`` (0.7).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from cell_core.hgt.domains import validate_domain
from cell_core.hgt.publisher import HGTPublisher

logger = logging.getLogger("crm_cell.hgt_publisher")


@dataclass(frozen=True)
class StructuralPattern:
    """A structural CRM discovery suitable for HGT broadcast.

    Canonical 6-field shape (Phase 3 TICKET A.1 — mirrors
    :class:`IntelScraperHGTBridge` schema). Maps directly to
    :class:`HGTPublisher`'s 9 xadd fields (with ``cell_origin`` + ``scope`` +
    ``type`` filled by the bridge).

    Client PII NEVER appears in any string field. Use structural identifiers
    (``template_id``, ``segment_id``, ``time_window``) instead.
    """

    pattern_id: str
    procedure: str
    precondition: str
    success_criterion: str
    confidence: float
    domain: str = "crm"


class CrmHGTBridge:
    """CRM-cell HGT bridge — mirrors :class:`IntelScraperHGTBridge`.

    Filters (defense-in-depth, in addition to HGTPublisher's confidence
    + scope=Project + type≠scar gate):

    * Reject patterns whose strings
      (``procedure``/``precondition``/``success_criterion``) contain PII
      markers (defensive — caller is supposed to never pass PII).
    * Reject ``confidence == 1.0`` (fixture pollution guard).

    No ``try/except`` around :meth:`HGTPublisher.publish` — that class catches
    all ``Exception`` in its own xadd block (see ``cell_core.hgt.publisher``
    lines 75-77). The bridge stays simple.
    """

    _PII_MARKERS = (
        "email",
        "@",
        "+62",
        "nik:",
        "npwp:",
        "passport",
        "client_id",
        "kitas_no",
        "ktp:",
    )

    def __init__(self, publisher: HGTPublisher) -> None:
        self._publisher = publisher
        # TICKET A.0 (PR #626) — public property, no protected access.
        self._cell_origin = publisher.cell_name

    @classmethod
    def from_redis(
        cls,
        redis_client: Any | None,
        cell_name: str = "crm-cell",
        maxlen: int = 1000,
    ) -> "CrmHGTBridge":
        """Build a bridge from a redis client (or ``None`` for a no-op).

        When ``redis_client`` is None, :class:`HGTPublisher` returns False
        immediately on every publish call — the pattern stays in local
        genome, no error propagated to the caller.
        """
        publisher = HGTPublisher(
            redis_client=redis_client,
            cell_name=cell_name,
            maxlen=maxlen,
        )
        return cls(publisher=publisher)

    def _is_pii_clean(self, pattern: StructuralPattern) -> bool:
        """True if string fields contain no PII markers (case-insensitive)."""
        haystack = " ".join(
            (
                pattern.procedure or "",
                pattern.precondition or "",
                pattern.success_criterion or "",
            )
        ).lower()
        return not any(m in haystack for m in self._PII_MARKERS)

    async def publish(self, pattern: StructuralPattern) -> bool:
        """Publish one structural pattern. Returns True iff broadcast.

        Filter order: cell-side filters FIRST, then HGTPublisher's gates
        (confidence floor + scope=Project + type≠scar).
        """
        if pattern.confidence < HGTPublisher.CONFIDENCE_THRESHOLD:
            logger.debug(
                "hgt: pattern %s below floor %s (got %s) — discarded",
                pattern.pattern_id,
                HGTPublisher.CONFIDENCE_THRESHOLD,
                pattern.confidence,
            )
            return False
        if pattern.confidence == 1.0:
            logger.info(
                "hgt: pattern %s filtered (confidence=1.0 fixture guard)",
                pattern.pattern_id,
            )
            return False
        if not self._is_pii_clean(pattern):
            logger.warning(
                "hgt: pattern %s blocked — string fields contain PII markers",
                pattern.pattern_id,
            )
            return False

        skill = {
            "id": f"crm.pattern.{pattern.pattern_id}",
            "cell_origin": self._cell_origin,
            "procedure": pattern.procedure,
            "precondition": pattern.precondition,
            "success_criterion": pattern.success_criterion,
            "confidence": float(pattern.confidence),
            "scope": "Project",
            "type": "skill",
            "domain": validate_domain(pattern.domain),
        }
        published = await self._publisher.publish(skill)
        logger.info(
            "hgt: pattern %s published=%s confidence=%.2f domain=%s",
            pattern.pattern_id,
            published,
            pattern.confidence,
            skill["domain"],
        )
        return published


__all__ = [
    "StructuralPattern",
    "CrmHGTBridge",
]
