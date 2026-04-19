"""KGSensor tests — all DB paths mocked."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors.kg_sensor import KGSensor, _KGError


@pytest.mark.asyncio
async def test_missing_db_url_returns_yellow(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reading = await KGSensor().read()
    assert isinstance(reading, SensorReading)
    assert reading.status == "yellow"
    assert reading.metadata["error_code"] == "db_url_missing"
    assert reading.value["node_count"] == 0


@pytest.mark.asyncio
async def test_happy_path_green_with_populated_kg():
    snapshot = {
        "node_count": 108_068,
        "edge_count": 242_827,
        "nodes_by_type": {"undang_undang": 1500, "kbli": 1563, "visa": 40},
        "edges_by_type": {"regulates": 50_000, "requires": 30_000},
        "last_updated_at": datetime(2026, 4, 18, tzinfo=timezone.utc).isoformat(),
    }
    sensor = KGSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_snapshot", return_value=snapshot):
        reading = await sensor.read()
    assert reading.status == "green"
    assert reading.value == snapshot


@pytest.mark.asyncio
async def test_empty_kg_returns_yellow():
    snapshot = {
        "node_count": 0,
        "edge_count": 0,
        "nodes_by_type": {},
        "edges_by_type": {},
        "last_updated_at": None,
    }
    sensor = KGSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_snapshot", return_value=snapshot):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["node_count"] == 0


@pytest.mark.asyncio
async def test_db_error_returns_red():
    sensor = KGSensor(db_url="postgres://fake")
    with patch.object(
        sensor,
        "_fetch_snapshot",
        side_effect=_KGError("db_error", "query failed: relation kg_nodes does not exist"),
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "db_error"


@pytest.mark.asyncio
async def test_unexpected_exception_returns_red():
    sensor = KGSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_snapshot", side_effect=RuntimeError("bang")):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "unexpected"


def test_db_url_override_beats_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "env://one")
    sensor = KGSensor(db_url="constructor://two")
    assert sensor._resolve_db_url() == "constructor://two"


def test_db_url_fallback_to_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "env://one")
    sensor = KGSensor()
    assert sensor._resolve_db_url() == "env://one"
