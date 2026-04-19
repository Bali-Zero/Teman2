"""Contract tests for the 5 sensors still stubbed in Sprint 2.

GSCSensor graduated out of stub-land in Sprint 2 — see
test_gsc_sensor.py for its dedicated tests with mocked credentials.
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

# GSC omitted — it's real now and would hit the live API.
STUB_SENSORS = [
    GA4Sensor(),
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
    all_six = [*STUB_SENSORS, GSCSensor()]
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
