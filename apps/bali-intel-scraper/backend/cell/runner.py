"""Orchestrator that ties scar recorder + HGT publisher + event bridge together.

A scraper adapter integrates the cell with three calls per run:

    runner = IntelScraperCellRunner(scar_recorder, hgt_bridge, event_bridge)
    async with runner.run(trace_id=...) as session:
        # for each source attempted:
        session.note_source_attempted("imigrasi.go.id")
        try:
            articles = await scrape_source("imigrasi.go.id")
            session.note_articles_found(len(articles))
            for pattern in extract_structural_patterns(articles):
                await session.publish_pattern(pattern)
        except RateLimit as exc:
            session.record_failure("imigrasi.go.id",
                                    FailureKind.RATE_LIMIT, str(exc))
        except Exception as exc:
            session.record_failure("imigrasi.go.id",
                                    FailureKind.HTTP_5XX, repr(exc))

    # On exit the runner emits one observed_shell row with the
    # accumulated counters and computed status.

The status computation is deterministic:

* 0 sources_attempted        → "failed"  (pipeline never started)
* ≥1 source_attempted but 0 articles AND ≥1 scars        → "failed"
* articles_found > 0 AND scars_added == 0                → "ok"
* articles_found > 0 AND scars_added > 0                 → "degraded"
* articles_found == 0 AND scars_added == 0               → "degraded"
  (e.g. scrape ran clean but every feed was empty — operator should
  inspect, but it's not a hard failure)

The runner never raises on bus / publisher errors — those degrade to
JSONL or in-memory drop respectively. Caller exceptions propagate.
"""
from __future__ import annotations

import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import AsyncIterator

from .event_bridge import IntelScraperEventBridge
from .hgt_publisher import IntelScraperHGTBridge, StructuralPattern
from .scar_recorder import FailureKind, IntelScraperScarRecorder, ScarRecord

logger = logging.getLogger("intel_scraper_cell.runner")


@dataclass
class RunSummary:
    """Counters + identifiers for one scraper run.

    Mutated in place by :class:`_RunSession`. ``finish_run`` reads it
    to populate the observed_shell row.
    """

    trace_id: str
    started_at: str
    sources_attempted: int = 0
    articles_found: int = 0
    scars: list[ScarRecord] = field(default_factory=list)
    hgt_published_count: int = 0
    finished_at: str = ""
    duration_ms: int = 0

    @property
    def scars_added(self) -> int:
        return len(self.scars)


class _RunSession:
    """The per-run object returned by ``IntelScraperCellRunner.run``.

    It exposes only the four mutator methods the scraper needs. The
    runner controls finalization (status computation + bus emit).
    """

    def __init__(
        self,
        summary: RunSummary,
        scar_recorder: IntelScraperScarRecorder,
        hgt_bridge: IntelScraperHGTBridge,
    ) -> None:
        self._summary = summary
        self._scar_recorder = scar_recorder
        self._hgt_bridge = hgt_bridge

    @property
    def trace_id(self) -> str:
        return self._summary.trace_id

    def note_source_attempted(self, source: str) -> None:
        """Record one source attempt — counters only, no I/O."""
        self._summary.sources_attempted += 1
        logger.debug("intel_scraper.source_attempted source=%s", source)

    def note_articles_found(self, count: int) -> None:
        """Increment the articles_found counter by `count` (clipped ≥0)."""
        if count < 0:
            count = 0
        self._summary.articles_found += int(count)

    def record_failure(
        self,
        source: str,
        kind: FailureKind,
        detail: str = "",
    ) -> ScarRecord:
        """Record a failure scar via the scar recorder.

        Best-effort: a Genome failure (e.g. SQLite locked) is logged
        and a synthetic ScarRecord is returned with ``confidence=0.0``
        so the run summary still reflects the attempt. The run
        continues — Symbiosis Law 4.
        """
        try:
            scar = self._scar_recorder.record(
                source=source, kind=kind, detail=detail
            )
        except Exception as exc:  # noqa: BLE001  (defense in depth)
            logger.error(
                "intel_scraper.scar_recorder_failed source=%s kind=%s err=%r",
                source,
                kind.value,
                exc,
            )
            scar = ScarRecord(
                scar_id=IntelScraperScarRecorder.make_scar_id(source, kind),
                source=source,
                kind=kind,
                detail=(detail or "")[:500],
                confidence=0.0,
                recorded_at=datetime.now(timezone.utc).isoformat(),
            )
        self._summary.scars.append(scar)
        return scar

    async def publish_pattern(self, pattern: StructuralPattern) -> bool:
        """Publish one structural pattern via HGT. Returns True iff broadcast.

        Best-effort: bridge / Redis errors are swallowed; the pattern
        stays in local genome (caller is responsible for genome-side
        recording — the bridge is broadcast-only).
        """
        try:
            published = await self._hgt_bridge.publish(pattern)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "intel_scraper.hgt_publish_failed pattern=%s err=%r",
                pattern.pattern_id,
                exc,
            )
            return False
        if published:
            self._summary.hgt_published_count += 1
        return published


def _compute_status(summary: RunSummary) -> str:
    """Deterministic status mapping. See module docstring for rules."""
    if summary.sources_attempted == 0:
        return "failed"
    if summary.articles_found == 0 and summary.scars_added > 0:
        return "failed"
    if summary.articles_found > 0 and summary.scars_added == 0:
        return "ok"
    return "degraded"


class IntelScraperCellRunner:
    """Top-level cell wrapper. One instance per process.

    Holds references to the genome scar recorder, HGT bridge, and event
    bridge. Each call to :meth:`run` allocates a new :class:`_RunSession`
    + :class:`RunSummary`. The runner is async-context-manager-shaped
    via :meth:`run` so the bus emit happens deterministically on exit
    (including on exception — the run is still recorded as failed).
    """

    def __init__(
        self,
        scar_recorder: IntelScraperScarRecorder,
        hgt_bridge: IntelScraperHGTBridge,
        event_bridge: IntelScraperEventBridge,
    ) -> None:
        self._scar_recorder = scar_recorder
        self._hgt_bridge = hgt_bridge
        self._event_bridge = event_bridge
        self._last_summary: RunSummary | None = None

    @property
    def last_summary(self) -> RunSummary | None:
        """Most recent finished run's summary — for monitoring / tests."""
        return self._last_summary

    @contextlib.asynccontextmanager
    async def run(
        self,
        trace_id: str | None = None,
    ) -> AsyncIterator[_RunSession]:
        """Async context manager that scopes one scraper run.

        On enter: creates the summary, emits no event yet.
        On exit (success OR exception): computes status from counters,
        emits exactly one ``intel.scraper.run`` row via the event
        bridge. Exceptions raised inside the ``with`` block re-raise
        AFTER the event is emitted (status='failed' if the block
        recorded ≥1 source but threw, 'failed' is also the case when
        the block threw before recording any source).
        """
        tid = trace_id or f"intel-scraper-{uuid.uuid4()}"
        started_dt = datetime.now(timezone.utc)
        started_perf = time.perf_counter()
        summary = RunSummary(
            trace_id=tid,
            started_at=started_dt.isoformat(),
        )
        session = _RunSession(
            summary=summary,
            scar_recorder=self._scar_recorder,
            hgt_bridge=self._hgt_bridge,
        )
        threw = False
        try:
            yield session
        except Exception:
            threw = True
            raise
        finally:
            duration_ms = int((time.perf_counter() - started_perf) * 1000)
            finished_dt = datetime.now(timezone.utc)
            summary.duration_ms = duration_ms
            summary.finished_at = finished_dt.isoformat()
            status = "failed" if threw else _compute_status(summary)

            try:
                await self._event_bridge.emit_run(
                    trace_id=summary.trace_id,
                    status=status,
                    sources_attempted=summary.sources_attempted,
                    articles_found=summary.articles_found,
                    scars_added=summary.scars_added,
                    hgt_published_count=summary.hgt_published_count,
                    duration_ms=summary.duration_ms,
                    started_at=summary.started_at,
                    finished_at=summary.finished_at,
                )
            except Exception as exc:  # noqa: BLE001
                # ObservedShellBus is supposed to swallow everything,
                # so reaching here means the bridge layer raised. Log
                # and continue — the parent must NOT cascade.
                logger.error(
                    "intel_scraper.event_bridge_failed trace_id=%s err=%r",
                    summary.trace_id,
                    exc,
                )
            self._last_summary = summary


__all__ = [
    "IntelScraperCellRunner",
    "RunSummary",
]
