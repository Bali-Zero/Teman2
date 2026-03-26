"""Tests for CELL sensors."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from cell.sensors.health_sensor import HealthSensor

@pytest.mark.asyncio
async def test_health_sensor_healthy():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}
    mock_response.elapsed = MagicMock()
    mock_response.elapsed.total_seconds.return_value = 0.15
    mock_client.get = AsyncMock(return_value=mock_response)
    sensor = HealthSensor(client=mock_client, url="http://test/health")
    reading = await sensor.read()
    assert reading.reachable is True
    assert reading.status_code == 200
    assert reading.response_time_seconds == 0.15

@pytest.mark.asyncio
async def test_health_sensor_unreachable():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
    sensor = HealthSensor(client=mock_client, url="http://test/health")
    reading = await sensor.read()
    assert reading.reachable is False
    assert reading.error == "Connection refused"

@pytest.mark.asyncio
async def test_health_sensor_503():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.json.return_value = {"status": "unhealthy"}
    mock_response.elapsed = MagicMock()
    mock_response.elapsed.total_seconds.return_value = 0.5
    mock_client.get = AsyncMock(return_value=mock_response)
    sensor = HealthSensor(client=mock_client, url="http://test/health")
    reading = await sensor.read()
    assert reading.reachable is True
    assert reading.status_code == 503
