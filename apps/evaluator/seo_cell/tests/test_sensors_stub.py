"""Contract tests for the 4 sensors still stubbed.

GSCSensor (Sprint 2) and GA4Sensor (Sprint 2b) graduated out of stub-
land; see their dedicated test_*_sensor.py files with mocked API paths.
"""
import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors import (
    CannibalizationSensor,
    CompetitorSERPSensor,
    GA4Sensor,
    GSCSensor,
    KGSensor,
    WarRoomEventSensor,
)

# GSC + GA4 omitted — they're real now and would hit live APIs.
STUB_SENSORS = [
    CompetitorSERPSensor(),
    KGSensor(),
    WarRoomEventSensor(),
    CannibalizationSensor(),
]


@pytest.mark.parametrize("sensor", STUB_SENSORS, ids=lambda s: s.name)
@pytest.mark.asyncio
async def test_stub_sensor_returns_reading(sensor):
    reading = await sensor.read()
    assert isinstance(reading, SensorReading)
    assert reading.sensor_name == sensor.name
    assert reading.status in ("green", "yellow", "red")
    assert reading.metadata.get("stub") is True


def test_six_distinct_sensor_names():
    all_six = [*STUB_SENSORS, GSCSensor(), GA4Sensor()]
    names = {s.name for s in all_six}
    assert len(names) == 6
    assert names == {
        "gsc",
        "ga4",
        "competitor_serp",
        "kg",
        "war_room_event",
        "cannibalization",
    }
