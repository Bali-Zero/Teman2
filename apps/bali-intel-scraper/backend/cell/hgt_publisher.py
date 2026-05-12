"""HGT publisher hook for intel-scraper-cell — STRUCTURAL patterns only.

When the scraper successfully discovers a *structural* finding about a
source — e.g. "regulator X publishes a stable RSS feed at /api/v2/news",
"site Y exposes a sitemap-index at /sitemaps/news.xml" — that finding
is a Project-scope skill that benefits sibling cells (mata-garuda,
research-cell future). It is broadcast via
:class:`cell_core.hgt.publisher.HGTPublisher` to the ``cell:skills``
Redis stream.

What is NEVER published:
 * Article content / title / snippet (UU PDP scope — client-facing
   downstream pipeline handles content, the cell layer must not leak it).
 * Author names, byline emails, phone numbers, NIK / NPWP / passport.
 * Any payload that the scraper itself classifies as PII or low-confidence.

Confidence threshold: ≥0.7 (matches HGTPublisher default). Patterns below
that threshold stay in local genome only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from cell_core.hgt.domains import validate_domain
from cell_core.hgt.publisher import HGTPublisher

logger = logging.getLogger("intel_scraper_cell.hgt_publisher")


@dataclass(frozen=True)
class StructuralPattern:
    """A structural discovery suitable for HGT broadcast.

    The fields map onto the skill schema HGTPublisher expects:
    ``id``, ``procedure``, ``precondition``, ``success_criterion``,
    ``confidence``, ``scope``, ``type``, ``domain``.

    ``content`` (the raw article body) is intentionally NOT a field —
    it does not belong in HGT. Add new metadata fields here if needed,
    but never an article body / title field.
    """

    pattern_id: str
    source: str
    procedure: str               # what the pattern says, in plain English
    precondition: str            # when this pattern applies
    success_criterion: str       # how to know the pattern still holds
    confidence: float
    domain: str = "news"         # default domain for intel-scraper findings
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_skill_dict(self, cell_origin: str) -> dict[str, Any]:
        """Render as the dict shape :meth:`HGTPublisher.publish` accepts.

        Always Project-scope, type=skill. The pattern_id is namespaced
        with ``intel.scraper.pattern.`` so consumers can filter on it.
        """
        return {
            "id": f"intel.scraper.pattern.{self.pattern_id}",
            "cell_origin": cell_origin,
            "procedure": self.procedure,
            "precondition": self.precondition,
            "success_criterion": self.success_criterion,
            "confidence": float(self.confidence),
            "scope": "Project",
            "type": "skill",
            "domain": validate_domain(self.domain),
            "_metadata": dict(self.metadata),
        }


class _RedisLike(Protocol):
    """Subset of redis.asyncio.Redis used by HGTPublisher."""

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
    ) -> Any:
        ...


class IntelScraperHGTBridge:
    """Wraps :class:`HGTPublisher` with the cell-specific filters.

    Filters in addition to HGTPublisher's confidence ≥0.7 + scope=Project
    + type≠scar gate:

    * Reject patterns whose ``procedure`` contains any of the PII markers
      (``email``, ``@``, ``+62``, ``NIK``, ``NPWP``, ``passport``).
      This is defense-in-depth; the scraper is supposed to never pass
      such payloads in the first place, but the cell layer must not
      trust upstream to be clean.
    * Reject patterns whose ``confidence`` is exactly 1.0 — that's
      almost always a fixture / test value, not an empirical confidence.
    """

    # Defense-in-depth PII markers. Conservative — matches a handful of
    # case-insensitive substrings. False positives here are acceptable
    # (the pattern stays in local genome instead of being broadcast);
    # false negatives are not.
    _PII_MARKERS = ("email", "@", "+62", "nik:", "npwp:", "passport")

    def __init__(self, publisher: HGTPublisher) -> None:
        self._publisher = publisher
        # Use public cell_name property (Phase 3 TICKET A.0). Falls back to
        # the protected attribute for compatibility with any in-tree shim
        # that may still expose only ``_cell_name``.
        self._cell_origin = getattr(publisher, "cell_name", None) or publisher._cell_name  # type: ignore[attr-defined]

    @classmethod
    def from_redis(
        cls,
        redis_client: _RedisLike | None,
        cell_name: str = "intel-scraper-cell",
        maxlen: int = 1000,
    ) -> "IntelScraperHGTBridge":
        """Build a bridge from a redis client (or ``None`` for a no-op).

        When ``redis_client`` is None, :class:`HGTPublisher` returns
        False immediately on every publish call — the pattern stays
        in local genome, no error propagated to the runner.
        """
        publisher = HGTPublisher(
            redis_client=redis_client,
            cell_name=cell_name,
            maxlen=maxlen,
        )
        return cls(publisher=publisher)

    def _is_pii_tainted(self, pattern: StructuralPattern) -> bool:
        """True if the pattern's procedure/precondition mentions PII markers."""
        haystack = " ".join(
            (pattern.procedure or "", pattern.precondition or "",
             pattern.success_criterion or "")
        ).lower()
        return any(m in haystack for m in self._PII_MARKERS)

    async def publish(self, pattern: StructuralPattern) -> bool:
        """Publish one structural pattern. Returns True iff broadcast.

        Filter order: cell-side filters FIRST, then HGTPublisher's
        threshold checks. We log at INFO when filtered locally so a
        rejected pattern is auditable without a redis transcript.
        """
        if pattern.confidence == 1.0:
            logger.info(
                "intel_scraper.hgt_filtered reason=confidence_eq_1 pattern=%s",
                pattern.pattern_id,
            )
            return False
        if self._is_pii_tainted(pattern):
            logger.warning(
                "intel_scraper.hgt_filtered reason=pii_marker pattern=%s",
                pattern.pattern_id,
            )
            return False

        skill = pattern.to_skill_dict(cell_origin=self._cell_origin)
        published = await self._publisher.publish(skill)
        logger.info(
            "intel_scraper.hgt_publish_attempt pattern=%s confidence=%.2f "
            "published=%s domain=%s ts=%s",
            pattern.pattern_id,
            pattern.confidence,
            published,
            skill["domain"],
            datetime.now(timezone.utc).isoformat(),
        )
        return published


__all__ = [
    "IntelScraperHGTBridge",
    "StructuralPattern",
]
