"""WarRoomEventSensor tests — all DB paths mocked."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors.war_room_event_sensor import (
    WarRoomEventSensor,
    _WarRoomEventError,
)


def _fake_rows(n_blog: int, n_carousel: int) -> list[dict]:
    rows = []
    now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    for i in range(n_blog):
        rows.append(
            {
                "draft_id": 1000 + i,
                "platform": "blog",
                "published_at": now,
                "post_url": f"https://balizero.com/blog/post-{i}",
                "register": "editorial",
            }
        )
    for i in range(n_carousel):
        rows.append(
            {
                "draft_id": 2000 + i,
                "platform": "carousel",
                "published_at": now,
                "post_url": f"https://instagram.com/p/fake-{i}",
                "register": "social",
            }
        )
    return rows


@pytest.mark.asyncio
async def test_missing_db_url_returns_yellow(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reading = await WarRoomEventSensor().read()
    assert isinstance(reading, SensorReading)
    assert reading.status == "yellow"
    assert reading.metadata["error_code"] == "db_url_missing"
    assert reading.value["event_count"] == 0


@pytest.mark.asyncio
async def test_happy_path_aggregates_by_platform():
    sensor = WarRoomEventSensor(window_hours=24, db_url="postgres://fake")
    with patch.object(sensor, "_fetch_posts", return_value=_fake_rows(7, 3)):
        reading = await sensor.read()
    assert reading.status == "green"
    assert reading.value["event_count"] == 10
    assert reading.value["by_platform"] == {"blog": 7, "carousel": 3}
    # Top 50 truncation doesn't kick in with only 10 rows
    assert len(reading.value["recent_posts"]) == 10
    # Row shape: published_at serialized as ISO string
    assert all(isinstance(p["published_at"], str) for p in reading.value["recent_posts"])


@pytest.mark.asyncio
async def test_empty_window_returns_yellow():
    sensor = WarRoomEventSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_posts", return_value=[]):
        reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.value["event_count"] == 0
    assert reading.value["by_platform"] == {}


@pytest.mark.asyncio
async def test_db_error_returns_red():
    sensor = WarRoomEventSensor(db_url="postgres://fake")
    with patch.object(
        sensor,
        "_fetch_posts",
        side_effect=_WarRoomEventError("db_error", "connect failed: timeout"),
    ):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "db_error"
    assert "timeout" in reading.metadata["error"]


@pytest.mark.asyncio
async def test_unexpected_exception_returns_red():
    sensor = WarRoomEventSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_posts", side_effect=RuntimeError("bang")):
        reading = await sensor.read()
    assert reading.status == "red"
    assert reading.metadata["error_code"] == "unexpected"


@pytest.mark.asyncio
async def test_recent_posts_capped_at_50():
    sensor = WarRoomEventSensor(db_url="postgres://fake")
    with patch.object(sensor, "_fetch_posts", return_value=_fake_rows(60, 0)):
        reading = await sensor.read()
    assert reading.value["event_count"] == 60
    assert len(reading.value["recent_posts"]) == 50


def test_db_url_override_beats_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "env://one")
    sensor = WarRoomEventSensor(db_url="constructor://two")
    assert sensor._resolve_db_url() == "constructor://two"


def test_db_url_fallback_to_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "env://one")
    sensor = WarRoomEventSensor()
    assert sensor._resolve_db_url() == "env://one"
