"""Contract tests for the 3 sensors still stubbed.

Sensors graduated out of stub-land (have their own test_*_sensor.py):
  - GSCSensor    (Sprint 2)
  - GA4Sensor    (Sprint 2b)
  - WarRoomEventSensor (Sprint 2c)
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

STUB_SENSORS = [
    CompetitorSERPSensor(),
    KGSensor(),
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
    all_six = [*STUB_SENSORS, GSCSensor(), GA4Sensor(), WarRoomEventSensor()]
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
