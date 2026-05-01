import pytest
from pathlib import Path
from cell_observatory.storage import Storage


@pytest.fixture
async def storage(tmp_path):
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    await s.init()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_init_creates_schema(storage):
    rows = await storage._fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r["name"] for r in rows}
    assert "pulse_events" in table_names
    assert "pulse_classifications" in table_names
    assert "pulse_daily_rollup" in table_names
    assert "pulse_classifications_fts" in table_names
    assert "schema_version" in table_names


@pytest.mark.asyncio
async def test_wal_mode_enabled(storage):
    rows = await storage._fetchall("PRAGMA journal_mode")
    assert rows[0]["journal_mode"].lower() == "wal"


@pytest.mark.asyncio
async def test_insert_pulse_event_idempotent(storage):
    payload = {
        "outbox_id": 1, "event_version": "v1", "cell_id": "organism",
        "cell_kind": "test", "pulse_id": "01ABC",
        "pulse_timestamp": "2026-05-01T00:00:00.000Z",
        "phase": "homeostatic",
        "sensors": [], "pulse_result": {"classifier_self": "green"},
        "homeostatic_state": {}, "scar_signals": [], "metadata": {},
    }
    inserted_first = await storage.insert_pulse_event(payload)
    inserted_second = await storage.insert_pulse_event(payload)
    assert inserted_first is True
    assert inserted_second is False  # already exists, skipped


@pytest.mark.asyncio
async def test_classification_upsert(storage):
    """Backfill must overwrite existing classification — A1 fix."""
    pulse = {"outbox_id": 1, "event_version": "v1", "cell_id": "x", "cell_kind": "x",
             "pulse_id": "x", "pulse_timestamp": "2026-05-01T00:00:00.000Z",
             "phase": "x", "sensors": [], "pulse_result": {"classifier_self": "green"},
             "homeostatic_state": {}, "scar_signals": [], "metadata": {}}
    await storage.insert_pulse_event(pulse)

    cls1 = {"outbox_id": 1, "label": "normal", "confidence": 0.9, "reasoning": "calm",
            "label_diff": "agree", "model": "minimax-m2", "model_version": None,
            "cost_usd": 0.0001, "latency_ms": 100, "error": None}
    cls2 = {**cls1, "label": "anomaly", "confidence": 0.6, "reasoning": "rethink"}

    await storage.upsert_classification(cls1)
    await storage.upsert_classification(cls2)

    rows = await storage._fetchall("SELECT label, confidence FROM pulse_classifications WHERE outbox_id=1")
    assert len(rows) == 1
    assert rows[0]["label"] == "anomaly"  # second won
    assert rows[0]["confidence"] == 0.6
