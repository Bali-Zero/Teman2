"""Genome scar recorder for intel-scraper-cell.

Each known failure pattern hit during a scrape (rate limit, paywall,
robots.txt block, DNS fail, schema drift) lands as a scar in the cell-core
Genome. Scars are NEVER blocking — record-then-continue is the contract.
Cross-run learning later reads them to compute backoff / quarantine windows.

Scope: Personal (somatic, never inherited via HGT). The structural patterns
that DO get shared with sibling cells go through :mod:`hgt_publisher`.

Scar id namespace: ``intel.scraper.<source_slug>.<failure_kind>``.

This module imports :class:`Genome` lazily so import does not require
SQLite schema setup at process start (``Genome.__init__`` runs DDL on
the SQLite file). The scraper passes a Genome instance built once per
process to :class:`IntelScraperScarRecorder`.
"""
from __future__ import annotations

import enum
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger("intel_scraper_cell.scar_recorder")


class FailureKind(str, enum.Enum):
    """Known failure pattern classes for intel scraper sources.

    Each value maps to a stable scar id suffix. Add new kinds here as
    they're identified — never reuse an existing kind for a different
    semantics, or you'll merge two unrelated scars.
    """

    RATE_LIMIT = "rate_limit"             # HTTP 429 / Retry-After observed
    PAYWALL = "paywall"                   # HTTP 402 / 403 with paywall body markers
    ROBOTS_BLOCKED = "robots_blocked"     # robots.txt forbids the path
    DNS_FAIL = "dns_fail"                 # NXDOMAIN / SERVFAIL
    CONNECT_TIMEOUT = "connect_timeout"
    READ_TIMEOUT = "read_timeout"
    SCHEMA_DRIFT = "schema_drift"         # parser hit unexpected layout
    HTTP_5XX = "http_5xx"                 # upstream server error
    EMPTY_FEED = "empty_feed"             # 200 OK but no articles


# `source` slugs are arbitrary lowercase strings (e.g. domain or feed id).
# We sanitize them so the scar id stays grep-friendly and SQLite-safe.
_SOURCE_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def _slugify(source: str) -> str:
    """Lowercase + collapse non-[a-z0-9_] runs into single underscores."""
    s = _SOURCE_SLUG_RE.sub("_", source.strip().lower()).strip("_")
    return s or "unknown"


@dataclass(frozen=True)
class ScarRecord:
    """Immutable record of one scar that was just recorded.

    Returned from :meth:`IntelScraperScarRecorder.record` so the runner
    can include it in the run summary without re-reading the DB.
    """

    scar_id: str
    source: str
    kind: FailureKind
    detail: str
    confidence: float
    recorded_at: str   # ISO 8601 UTC


class _GenomeLike(Protocol):
    """Subset of :class:`cell_core.genome.Genome` used by the recorder.

    Allows tests to pass a stub without instantiating SQLite.
    """

    def record_scar(
        self,
        cell: str,
        scar_id: str,
        procedure: str,
        precondition: str = "",
    ) -> str:
        ...

    def use_skill(self, skill_id: str) -> None:
        ...


class IntelScraperScarRecorder:
    """Record-then-continue scar emitter for intel-scraper-cell.

    Confidence stays at the Genome default for scars (0.9, see
    ``Genome.record_scar``). Each call to :meth:`record` either inserts
    a new row or bumps the existing scar's ``uses`` counter via
    ``Genome.use_skill`` — the second call is the cross-run signal that
    "domain X has been rate-limiting us 5x in 24h" without us writing
    a custom counter table.
    """

    CELL_NAME = "intel-scraper-cell"
    SCAR_NAMESPACE = "intel.scraper"

    def __init__(self, genome: _GenomeLike) -> None:
        self._genome = genome

    @staticmethod
    def make_scar_id(source: str, kind: FailureKind) -> str:
        """Stable scar id: ``intel.scraper.<source_slug>.<failure_kind>``.

        >>> IntelScraperScarRecorder.make_scar_id("imigrasi.go.id", FailureKind.RATE_LIMIT)
        'intel.scraper.imigrasi_go_id.rate_limit'
        """
        return f"intel.scraper.{_slugify(source)}.{kind.value}"

    def record(
        self,
        source: str,
        kind: FailureKind,
        detail: str = "",
    ) -> ScarRecord:
        """Record one scar. Idempotent at the (source, kind) level.

        On the first call: inserts a Personal-scope scar via
        ``Genome.record_scar``. On subsequent calls with the same id:
        ``Genome.record_scar`` upserts (keeps max confidence) and we
        bump ``uses`` separately via ``use_skill`` so the cross-run
        signal is observable.
        """
        scar_id = self.make_scar_id(source, kind)
        # detail is kept under 500 chars to avoid pathological growth
        # if upstream throws a giant traceback as the failure detail.
        clipped_detail = (detail or "")[:500]
        procedure = (
            f"intel-scraper hit {kind.value} on '{source}': {clipped_detail}. "
            f"Back off this source on next run; if scar uses ≥5 in 24h, "
            f"quarantine for 2h before retry."
        )
        precondition = f"target source = {source}"

        # First record_scar does the insert OR upsert.
        self._genome.record_scar(
            cell=self.CELL_NAME,
            scar_id=scar_id,
            procedure=procedure,
            precondition=precondition,
        )
        # Then bump uses + last_used so cross-run accumulation is visible.
        # use_skill is a no-op on a freshly-inserted row except for
        # uses=1 + last_used=now, which is exactly what we want.
        self._genome.use_skill(scar_id)

        recorded_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "intel_scraper.scar_recorded source=%s kind=%s scar_id=%s",
            source,
            kind.value,
            scar_id,
        )
        return ScarRecord(
            scar_id=scar_id,
            source=source,
            kind=kind,
            detail=clipped_detail,
            confidence=0.9,
            recorded_at=recorded_at,
        )


__all__ = [
    "FailureKind",
    "IntelScraperScarRecorder",
    "ScarRecord",
]
