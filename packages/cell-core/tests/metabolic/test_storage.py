"""Tests for MetabolicStore — SQLite persistence."""
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from cell_core.metabolic.definitions import (
    METRIC_AUTONOMY_INDEX,
    METRIC_ESCALATION_FREQ,
    METRIC_ONTOLOGY_DENSITY,
    METRIC_TTR,
    MetabolicSnapshot,
    MetricValue,
)
from cell_core.metabolic.storage import MetabolicStore


def _make_metric(metric_type: str, value: float | None = 1.0) -> MetricValue:
    return MetricValue(
        metric_type=metric_type, value=value,
        calculated_at="2026-04-16T12:00:00+00:00", metadata={},
    )


def _make_snapshot(ts: str = "2026-04-16T12:00:00+00:00", ttr=3.0, do=2.2, ia=0.17, fe=0.65) -> MetabolicSnapshot:
    return MetabolicSnapshot(
        ttr=MetricValue(METRIC_TTR, ttr, ts, {"episodes_count": 2}),
        ontology_density=MetricValue(METRIC_ONTOLOGY_DENSITY, do, ts, {"nodes": 100, "edges": 220}),
        autonomy_index=MetricValue(METRIC_AUTONOMY_INDEX, ia, ts, {"endogenous": {"cron": 10}, "exogenous": {"sessions": 49}}),
        escalation_freq=MetricValue(METRIC_ESCALATION_FREQ, fe, ts, {"raw_count": 38, "total_actions": 59}),
        calculated_at=ts,
    )


@pytest.fixture
def store(tmp_path):
    return MetabolicStore(db_path=str(tmp_path / "test_metrics.db"))


def test_store_and_latest(store):
    snap = _make_snapshot()
    rowid = store.store(snap)
    assert rowid > 0
    results = store.latest(1)
    assert len(results) == 1
    assert results[0].ttr.value == 3.0
    assert results[0].ontology_density.value == 2.2


def test_latest_ordering(store):
    store.store(_make_snapshot(ts="2026-04-14T12:00:00+00:00", ttr=1.0))
    store.store(_make_snapshot(ts="2026-04-15T12:00:00+00:00", ttr=2.0))
    store.store(_make_snapshot(ts="2026-04-16T12:00:00+00:00", ttr=3.0))
    results = store.latest(2)
    assert len(results) == 2
    assert results[0].ttr.value == 3.0  # newest first
    assert results[1].ttr.value == 2.0


def test_range_query(store):
    for day in range(10, 17):
        store.store(_make_snapshot(ts=f"2026-04-{day:02d}T12:00:00+00:00", ttr=float(day)))
    results = store.range("2026-04-12T00:00:00", "2026-04-14T23:59:59")
    assert len(results) == 3
    assert results[0].ttr.value == 12.0  # oldest first
    assert results[2].ttr.value == 14.0


def test_metric_series(store):
    for day in range(10, 17):
        store.store(_make_snapshot(ts=f"2026-04-{day:02d}T12:00:00+00:00", ttr=float(day)))
    series = store.metric_series(METRIC_TTR, n=5)
    assert len(series) == 5
    assert series[0][1] == 16.0  # newest first
    assert series[4][1] == 12.0


def test_stats(store):
    store.store(_make_snapshot(ts="2026-04-15T12:00:00+00:00"))
    store.store(_make_snapshot(ts="2026-04-16T12:00:00+00:00"))
    st = store.stats()
    assert st["total_snapshots"] == 2
    assert st["first_snapshot"] == "2026-04-15T12:00:00+00:00"
    assert st["last_snapshot"] == "2026-04-16T12:00:00+00:00"
    assert st["db_file_size"] > 0


def test_schema_created_on_init(tmp_path):
    """Fresh DB has the metabolic_snapshots table."""
    import sqlite3
    db_path = str(tmp_path / "fresh.db")
    MetabolicStore(db_path=db_path)
    conn = sqlite3.connect(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='metabolic_snapshots'"
    ).fetchall()
    conn.close()
    assert len(tables) == 1


def test_concurrent_writes(tmp_path):
    """Multiple threads writing simultaneously should not corrupt the DB."""
    store = MetabolicStore(db_path=str(tmp_path / "concurrent.db"))

    def write_one(i: int) -> int:
        snap = _make_snapshot(ts=f"2026-04-{i+1:02d}T12:00:00+00:00", ttr=float(i))
        return store.store(snap)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(write_one, i) for i in range(10)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 10
    assert store.stats()["total_snapshots"] == 10


def test_none_values_stored(store):
    """Snapshot with None metrics stores and retrieves correctly."""
    snap = MetabolicSnapshot(
        ttr=MetricValue(METRIC_TTR, None, "2026-04-16T12:00:00+00:00", {"error": "pg_down"}),
        ontology_density=MetricValue(METRIC_ONTOLOGY_DENSITY, None, "2026-04-16T12:00:00+00:00", {}),
        autonomy_index=MetricValue(METRIC_AUTONOMY_INDEX, 0.15, "2026-04-16T12:00:00+00:00", {}),
        escalation_freq=MetricValue(METRIC_ESCALATION_FREQ, 0.5, "2026-04-16T12:00:00+00:00", {}),
        calculated_at="2026-04-16T12:00:00+00:00",
    )
    store.store(snap)
    results = store.latest(1)
    assert results[0].ttr.value is None
    assert results[0].ttr.metadata == {"error": "pg_down"}
    assert results[0].autonomy_index.value == 0.15


def test_schema_v2_migration_idempotent(tmp_path):
    """_ensure_schema is idempotent: re-open store, columns still present, no error."""
    import sqlite3
    db_path = str(tmp_path / "v2_idempotent.db")

    # First open: creates + migrates
    store1 = MetabolicStore(db_path=db_path)
    store1.store(_make_snapshot(), collector_host="pro", metric_scope="host")
    del store1

    # Second open: migration re-runs, must not raise "duplicate column"
    store2 = MetabolicStore(db_path=db_path)
    store2.store(_make_snapshot(ts="2026-04-17T12:00:00+00:00"), collector_host="air", metric_scope="global")

    conn = sqlite3.connect(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(metabolic_snapshots)")}
    conn.close()
    assert "collector_host" in cols
    assert "metric_scope" in cols
    assert store2.stats()["total_snapshots"] == 2


def test_store_with_collector_host_and_scope(store):
    """store() persists collector_host + metric_scope; queryable via raw SQL."""
    import sqlite3
    store.store(_make_snapshot(ts="2026-04-17T12:00:00+00:00"), collector_host="pro", metric_scope="host")
    store.store(_make_snapshot(ts="2026-04-17T12:00:01+00:00"), collector_host="air", metric_scope="global")
    store.store(_make_snapshot(ts="2026-04-17T12:00:02+00:00"), collector_host="air", metric_scope="host")

    conn = sqlite3.connect(store._db_path)
    pro_host = conn.execute(
        "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='pro' AND metric_scope='host'"
    ).fetchone()[0]
    air_global = conn.execute(
        "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='air' AND metric_scope='global'"
    ).fetchone()[0]
    air_host = conn.execute(
        "SELECT COUNT(*) FROM metabolic_snapshots WHERE collector_host='air' AND metric_scope='host'"
    ).fetchone()[0]
    conn.close()

    assert pro_host == 1
    assert air_global == 1
    assert air_host == 1


def test_store_legacy_call_without_scope_still_works(store):
    """Legacy callers (no collector_host/metric_scope) still persist (backcompat)."""
    store.store(_make_snapshot())
    results = store.latest(1)
    assert results[0].ttr.value == 3.0
