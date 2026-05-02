"""Integration tests for IntelScraperCellRunner — all 3 components wired.

These tests exercise the async-context-manager contract end-to-end with:
* a real :class:`Genome` (tmp_path SQLite)
* a stubbed :class:`HGTPublisher` (no Redis)
* an AsyncMock :class:`ObservedShellBus`

Verifies:
1. successful run → status=ok, ≥1 observed_shell_events row written
2. degraded run (some scars + some articles) → status=degraded
3. failed run (sources>0, articles=0, scars>0) → status=failed
4. no-source run → status=failed (e.g. all sources unreachable)
5. exception inside the with-block → status=failed, event still emitted
6. HGT publish counter increments correctly
7. trace_id auto-generated when caller passes None
8. last_summary populated after run
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.cell.event_bridge import IntelScraperEventBridge
from backend.cell.hgt_publisher import (
    IntelScraperHGTBridge,
    StructuralPattern,
)
from backend.cell.runner import IntelScraperCellRunner
from backend.cell.scar_recorder import (
    FailureKind,
    IntelScraperScarRecorder,
)
from cell_core.genome import Genome


@pytest.fixture
def genome(tmp_path) -> Genome:
    return Genome(db_path=str(tmp_path / "runner-genome.db"))


@pytest.fixture
def fake_bus():
    bus = AsyncMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def runner(genome: Genome, fake_bus):
    """Build a runner with all 3 components wired but Redis stubbed off."""
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock(return_value=b"1-0")
    return IntelScraperCellRunner(
        scar_recorder=IntelScraperScarRecorder(genome),
        hgt_bridge=IntelScraperHGTBridge.from_redis(
            fake_redis, cell_name="intel-scraper-cell"
        ),
        event_bridge=IntelScraperEventBridge(fake_bus),
    )


def _last_emit_payload(fake_bus):
    """Helper to extract the last bus.emit() call's payload."""
    assert fake_bus.emit.await_count == 1
    return fake_bus.emit.await_args.kwargs


@pytest.mark.asyncio
async def test_clean_run_emits_status_ok(runner, fake_bus):
    async with runner.run() as session:
        session.note_source_attempted("djp.go.id")
        session.note_source_attempted("imigrasi.go.id")
        session.note_articles_found(7)
        session.note_articles_found(5)
        # success criterion structural pattern
        await session.publish_pattern(StructuralPattern(
            pattern_id="djp_rss_v2",
            source="djp.go.id",
            procedure="djp.go.id RSS at /api/v2/news returns stable JSON",
            precondition="GET /api/v2/news",
            success_criterion="≥1 article",
            confidence=0.9,
        ))

    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["automation_name"] == "intel.scraper.run"
    assert kwargs["status"] == "ok"
    payload = kwargs["payload"]
    assert payload["sources_attempted"] == 2
    assert payload["articles_found"] == 12
    assert payload["scars_added"] == 0
    assert payload["hgt_published_count"] == 1
    assert payload["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_partial_failure_emits_status_degraded(runner, fake_bus):
    async with runner.run() as session:
        session.note_source_attempted("djp.go.id")
        session.note_source_attempted("imigrasi.go.id")
        session.note_articles_found(5)
        session.record_failure(
            "imigrasi.go.id", FailureKind.RATE_LIMIT, "429 Too Many Requests"
        )

    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["status"] == "degraded"
    payload = kwargs["payload"]
    assert payload["scars_added"] == 1
    assert payload["articles_found"] == 5


@pytest.mark.asyncio
async def test_all_sources_failed_emits_status_failed(runner, fake_bus):
    async with runner.run() as session:
        session.note_source_attempted("djp.go.id")
        session.note_source_attempted("imigrasi.go.id")
        session.record_failure("djp.go.id", FailureKind.HTTP_5XX, "503")
        session.record_failure(
            "imigrasi.go.id", FailureKind.CONNECT_TIMEOUT, "timed out"
        )

    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["status"] == "failed"
    payload = kwargs["payload"]
    assert payload["sources_attempted"] == 2
    assert payload["articles_found"] == 0
    assert payload["scars_added"] == 2


@pytest.mark.asyncio
async def test_no_sources_attempted_emits_status_failed(runner, fake_bus):
    """Runner started but no sources attempted (e.g. config empty) → failed."""
    async with runner.run() as session:
        # noop — caller hit a config error before getting to scrape
        _ = session.trace_id
    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["status"] == "failed"
    assert kwargs["payload"]["sources_attempted"] == 0


@pytest.mark.asyncio
async def test_clean_run_with_zero_articles_emits_degraded(runner, fake_bus):
    """All sources OK but every feed empty: not a hard failure but
    operator should investigate. Status=degraded."""
    async with runner.run() as session:
        session.note_source_attempted("bps.go.id")
        # No articles, no scars
    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["status"] == "degraded"
    assert kwargs["payload"]["articles_found"] == 0
    assert kwargs["payload"]["scars_added"] == 0


@pytest.mark.asyncio
async def test_exception_in_block_marks_status_failed_and_emits(runner, fake_bus):
    """Exception inside the with-block: event still emitted with
    status=failed; exception propagates AFTER bus emit."""
    class _BoomException(RuntimeError):
        pass

    with pytest.raises(_BoomException):
        async with runner.run() as session:
            session.note_source_attempted("djp.go.id")
            session.note_articles_found(3)
            raise _BoomException("scraper crashed mid-run")

    # Bus DID receive the event.
    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["status"] == "failed"
    # Counters reflect the partial state.
    assert kwargs["payload"]["sources_attempted"] == 1
    assert kwargs["payload"]["articles_found"] == 3


@pytest.mark.asyncio
async def test_trace_id_auto_generated_when_none(runner, fake_bus):
    async with runner.run(trace_id=None) as session:
        session.note_source_attempted("djp.go.id")
        session.note_articles_found(1)
        # the trace_id must be set on the session and start with the
        # canonical prefix
        assert session.trace_id.startswith("intel-scraper-")
    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["trace_id"].startswith("intel-scraper-")


@pytest.mark.asyncio
async def test_explicit_trace_id_passed_through(runner, fake_bus):
    async with runner.run(trace_id="run-2026-05-02T03:00") as session:
        session.note_source_attempted("djp.go.id")
        session.note_articles_found(1)
    kwargs = _last_emit_payload(fake_bus)
    assert kwargs["trace_id"] == "run-2026-05-02T03:00"


@pytest.mark.asyncio
async def test_last_summary_populated_after_run(runner, fake_bus):
    assert runner.last_summary is None
    async with runner.run() as session:
        session.note_source_attempted("oss.go.id")
        session.note_articles_found(2)
    assert runner.last_summary is not None
    assert runner.last_summary.sources_attempted == 1
    assert runner.last_summary.articles_found == 2


@pytest.mark.asyncio
async def test_hgt_publish_counter_only_increments_on_success(genome, fake_bus):
    """Patterns below confidence threshold do NOT bump hgt_published_count."""
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock(return_value=b"1-0")
    runner = IntelScraperCellRunner(
        scar_recorder=IntelScraperScarRecorder(genome),
        hgt_bridge=IntelScraperHGTBridge.from_redis(
            fake_redis, cell_name="intel-scraper-cell"
        ),
        event_bridge=IntelScraperEventBridge(fake_bus),
    )

    low = StructuralPattern(
        pattern_id="lowconf",
        source="djp.go.id",
        procedure="something",
        precondition="x",
        success_criterion="y",
        confidence=0.5,    # below 0.7 threshold → filtered
    )
    high = StructuralPattern(
        pattern_id="highconf",
        source="djp.go.id",
        procedure="something else",
        precondition="x",
        success_criterion="y",
        confidence=0.95,
    )

    async with runner.run() as session:
        session.note_source_attempted("djp.go.id")
        session.note_articles_found(1)
        ok_low = await session.publish_pattern(low)
        ok_high = await session.publish_pattern(high)
        assert ok_low is False
        assert ok_high is True

    payload = fake_bus.emit.await_args.kwargs["payload"]
    assert payload["hgt_published_count"] == 1


@pytest.mark.asyncio
async def test_runner_swallows_bus_exception(genome):
    """If ObservedShellBus.emit raises (shouldn't normally — it's
    supposed to swallow), the runner must NOT propagate; otherwise the
    parent automation would crash on observability failure."""
    bus = AsyncMock()
    bus.emit = AsyncMock(side_effect=RuntimeError("bus broken"))
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock(return_value=b"1-0")
    runner = IntelScraperCellRunner(
        scar_recorder=IntelScraperScarRecorder(genome),
        hgt_bridge=IntelScraperHGTBridge.from_redis(
            fake_redis, cell_name="intel-scraper-cell"
        ),
        event_bridge=IntelScraperEventBridge(bus),
    )

    # Must complete cleanly even though emit raised.
    async with runner.run() as session:
        session.note_source_attempted("oss.go.id")
        session.note_articles_found(1)
    # Summary still populated.
    assert runner.last_summary is not None
    assert runner.last_summary.sources_attempted == 1


@pytest.mark.asyncio
async def test_scar_recorder_failure_synthesizes_record(genome, fake_bus):
    """If the scar recorder layer raises (e.g. SQLite locked), the
    runner falls back to a synthetic ScarRecord (confidence=0.0)
    and the run continues. This is the Symbiosis Law 4 contract."""
    # We pre-build with a real Genome but stash a stub at the
    # scar_recorder layer that raises.
    class _BoomScarRecorder:
        def record(self, source, kind, detail=""):
            raise RuntimeError("genome locked")

    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock()
    runner = IntelScraperCellRunner(
        scar_recorder=_BoomScarRecorder(),  # type: ignore[arg-type]
        hgt_bridge=IntelScraperHGTBridge.from_redis(
            fake_redis, cell_name="intel-scraper-cell"
        ),
        event_bridge=IntelScraperEventBridge(fake_bus),
    )

    async with runner.run() as session:
        session.note_source_attempted("djp.go.id")
        rec = session.record_failure("djp.go.id", FailureKind.HTTP_5XX, "503")
        # Synthetic record with confidence=0.0
        assert rec.confidence == 0.0
        assert rec.scar_id == "intel.scraper.djp_go_id.http_5xx"

    payload = fake_bus.emit.await_args.kwargs["payload"]
    assert payload["scars_added"] == 1
    # Status: 1 source, 0 articles, 1 scar → failed
    assert fake_bus.emit.await_args.kwargs["status"] == "failed"


@pytest.mark.asyncio
async def test_scars_visible_in_genome_after_run(runner, genome):
    """After a degraded run, the scar must be queryable in the Genome
    so the next run can read it for backoff decisions."""
    async with runner.run() as session:
        session.note_source_attempted("djp.go.id")
        session.note_articles_found(2)
        session.record_failure(
            "djp.go.id", FailureKind.SCHEMA_DRIFT, "missing field 'pubDate'"
        )

    rows = genome.get_active(
        cell="intel-scraper-cell",
        entry_type="scar",
        scope="Personal",
        min_confidence=0.5,
        limit=10,
    )
    assert any(
        r["id"] == "intel.scraper.djp_go_id.schema_drift" for r in rows
    ), rows
