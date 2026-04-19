"""Sprint 1 contract tests for all 6 sensors.

Each sensor must return a SensorReading with a recognizable
`metadata.stub == True` marker and status in {"green","yellow","red"}.
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


SENSORS = [
    GSCSensor(),
    GA4Sensor(),
    CompetitorSERPSensor(),
    KGSensor(),
    WarRoomEventSensor(),
    CannibalizationSensor(),
]


@pytest.mark.parametrize("sensor", SENSORS, ids=lambda s: s.name)
@pytest.mark.asyncio
async def test_sensor_returns_reading(sensor):
    reading = await sensor.read()
    assert isinstance(reading, SensorReading)
    assert reading.sensor_name == sensor.name
    assert reading.status in ("green", "yellow", "red")
    # Sprint 1: all sensors are stubs
    assert reading.metadata.get("stub") is True


@pytest.mark.asyncio
async def test_gsc_sensor_exposes_query_count():
    """Thinker relies on value.query_count to evaluate pre_natal gate."""
    reading = await GSCSensor().read()
    assert "query_count" in reading.value
    assert isinstance(reading.value["query_count"], int)


def test_six_distinct_sensor_names():
    names = {s.name for s in SENSORS}
    assert len(names) == 6
    assert names == {
        "gsc",
        "ga4",
        "competitor_serp",
        "kg",
        "war_room_event",
        "cannibalization",
    }
