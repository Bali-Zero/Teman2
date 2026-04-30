"""Contract tests for the 1 sensor still stubbed.

Sensors graduated out of stub-land (own test_*_sensor.py):
  - GSCSensor              (Sprint 2)
  - GA4Sensor              (Sprint 2b)
  - WarRoomEventSensor     (Sprint 2c)
  - KGSensor               (Sprint 2d)
  - CompetitorSERPSensor   (Sprint 2e)
  - LeadAttributionSensor  (Sprint 2 — pre_natal gate feeder)

Only CannibalizationSensor remains a stub — per Sprint 2d commit, it
belongs in the thinker layer, not the sensor layer, and will be
relocated or redesigned in Sprint 3.
"""
import pytest

from cell_core.types import SensorReading
from apps.evaluator.seo_cell.sensors import (
    CannibalizationSensor,
    CompetitorSERPSensor,
    GA4Sensor,
    GSCSensor,
    KGSensor,
    LeadAttributionSensor,
    WarRoomEventSensor,
)

STUB_SENSORS = [
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


def test_seven_distinct_sensor_names():
    all_seven = [
        *STUB_SENSORS,
        GSCSensor(),
        GA4Sensor(),
        WarRoomEventSensor(),
        KGSensor(),
        CompetitorSERPSensor(),
        LeadAttributionSensor(),
    ]
    names = {s.name for s in all_seven}
    assert len(names) == 7
    assert names == {
        "gsc",
        "ga4",
        "competitor_serp",
        "kg",
        "war_room_event",
        "cannibalization",
        "lead_attribution",
    }
