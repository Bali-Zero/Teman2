"""Unit tests for intel-scraper-cell scar_recorder.

Tests use both:

* a real :class:`cell_core.genome.Genome` against an in-memory SQLite
  (``:memory:``) — exercises the round-trip insert/upsert/use_skill path.
* a stub :class:`_StubGenome` for fault-injection (e.g. SQLite locked).

Running:

    PYTHONPATH=packages/cell-core:apps/bali-intel-scraper \\
        pytest apps/bali-intel-scraper/tests/unit/cell/test_scar_recorder.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.cell.scar_recorder import (
    FailureKind,
    IntelScraperScarRecorder,
    ScarRecord,
    _slugify,
)
from cell_core.genome import Genome


@pytest.fixture
def genome(tmp_path) -> Genome:
    """Real Genome on a tmp_path SQLite (NOT :memory: — SQLite WAL pragmas
    don't fully apply to memory DBs across threads).
    """
    return Genome(db_path=str(tmp_path / "genome-test.db"))


def test_slugify_handles_dots_and_uppercase() -> None:
    assert _slugify("imigrasi.go.id") == "imigrasi_go_id"
    assert _slugify("BPS.Go.ID") == "bps_go_id"
    assert _slugify("bali-tribunnews.com") == "bali_tribunnews_com"
    assert _slugify("") == "unknown"
    assert _slugify("   ") == "unknown"


def test_make_scar_id_format() -> None:
    sid = IntelScraperScarRecorder.make_scar_id(
        "imigrasi.go.id", FailureKind.RATE_LIMIT
    )
    assert sid == "intel.scraper.imigrasi_go_id.rate_limit"
    sid2 = IntelScraperScarRecorder.make_scar_id(
        "bali.tribunnews.com", FailureKind.SCHEMA_DRIFT
    )
    assert sid2 == "intel.scraper.bali_tribunnews_com.schema_drift"


def test_record_inserts_scar_into_genome(genome: Genome) -> None:
    rec = IntelScraperScarRecorder(genome)
    out = rec.record(
        source="djp.go.id",
        kind=FailureKind.HTTP_5XX,
        detail="upstream returned 503",
    )
    assert isinstance(out, ScarRecord)
    assert out.scar_id == "intel.scraper.djp_go_id.http_5xx"
    assert out.kind == FailureKind.HTTP_5XX
    assert out.confidence == 0.9
    # Genome row exists, type=scar, scope=Personal
    rows = genome.get_active(
        cell="intel-scraper-cell",
        entry_type="scar",
        scope="Personal",
        min_confidence=0.5,
        limit=10,
    )
    assert any(r["id"] == out.scar_id for r in rows), rows


def test_record_upsert_increments_uses_across_runs(genome: Genome) -> None:
    """Cross-run signal: 5 failures of the same (source, kind) bumps
    the existing scar's uses counter to 5."""
    rec = IntelScraperScarRecorder(genome)
    for i in range(5):
        rec.record(
            source="oss.go.id",
            kind=FailureKind.RATE_LIMIT,
            detail=f"hit #{i}",
        )
    rows = genome.get_active(
        cell="intel-scraper-cell",
        entry_type="scar",
        min_confidence=0.5,
        limit=10,
    )
    matched = [r for r in rows if r["id"] == "intel.scraper.oss_go_id.rate_limit"]
    assert len(matched) == 1
    # uses bumped 5 times
    assert matched[0]["uses"] == 5


def test_record_clips_long_detail(genome: Genome) -> None:
    """A 10K-character traceback must NOT bloat the scar row."""
    long_detail = "x" * 10_000
    rec = IntelScraperScarRecorder(genome)
    out = rec.record(
        source="bps.go.id",
        kind=FailureKind.SCHEMA_DRIFT,
        detail=long_detail,
    )
    assert len(out.detail) == 500  # clipped at the dataclass level


def test_recorded_at_is_iso_utc(genome: Genome) -> None:
    rec = IntelScraperScarRecorder(genome)
    out = rec.record(
        source="bali.tribunnews.com", kind=FailureKind.PAYWALL, detail=""
    )
    parsed = datetime.fromisoformat(out.recorded_at)
    assert parsed.tzinfo is not None
    # within the last few seconds
    delta = (datetime.now(timezone.utc) - parsed).total_seconds()
    assert -1 < delta < 30


# ── Fault injection: Genome stub that raises ───────────────────────────


class _StubGenome:
    """Stub matching :class:`_GenomeLike` protocol used by the recorder."""

    def __init__(self, raise_on_record: Exception | None = None,
                 raise_on_use: Exception | None = None) -> None:
        self.raise_on_record = raise_on_record
        self.raise_on_use = raise_on_use
        self.recorded: list[tuple[str, str]] = []
        self.used: list[str] = []

    def record_scar(self, cell: str, scar_id: str, procedure: str,
                    precondition: str = "") -> str:
        if self.raise_on_record:
            raise self.raise_on_record
        self.recorded.append((cell, scar_id))
        return "inserted"

    def use_skill(self, skill_id: str) -> None:
        if self.raise_on_use:
            raise self.raise_on_use
        self.used.append(skill_id)


def test_record_propagates_genome_exception() -> None:
    """The recorder itself does NOT swallow Genome errors — the runner
    layer is responsible for graceful degradation. This protects us
    from masking a corrupted DB during cross-run analysis."""
    stub = _StubGenome(raise_on_record=RuntimeError("sqlite locked"))
    rec = IntelScraperScarRecorder(stub)
    with pytest.raises(RuntimeError, match="sqlite locked"):
        rec.record(source="x.com", kind=FailureKind.DNS_FAIL, detail="")
    assert stub.recorded == []
