"""Integration test — full pulse cycle with mocked externals."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from cell.core.dna import DNALoader
from cell.core.pulse import PulseEngine
from cell.core.safety import SafetyGate
from cell.fast.health_triage import HealthStatus
from cell.metabolism.tracker import MetabolismTracker
from cell.sensors.health_sensor import HealthSensor

@pytest.mark.asyncio
async def test_full_pulse_cycle_healthy():
    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    safety = SafetyGate(redis=mock_redis)
    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}
    mock_response.elapsed = MagicMock()
    mock_response.elapsed.total_seconds.return_value = 0.1
    mock_http.get = AsyncMock(return_value=mock_response)
    sensor = HealthSensor(client=mock_http, url="http://test/health")
    metabolism = MetabolismTracker(daily_limit=10.0)
    engine = PulseEngine(dna_loader=dna_loader, safety_gate=safety, health_sensor=sensor, metabolism=metabolism, dna_expected_hash=dna_hash)
    result = await engine.single_pulse()
    assert result.halted is False
    assert result.skipped is False
    assert result.health_status == HealthStatus.GREEN
    assert result.action_taken is None

@pytest.mark.asyncio
async def test_full_pulse_cycle_unreachable():
    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    safety = SafetyGate(redis=mock_redis)
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=Exception("Connection refused"))
    sensor = HealthSensor(client=mock_http, url="http://test/health")
    metabolism = MetabolismTracker(daily_limit=10.0)
    engine = PulseEngine(dna_loader=dna_loader, safety_gate=safety, health_sensor=sensor, metabolism=metabolism, dna_expected_hash=dna_hash)
    result = await engine.single_pulse()
    assert result.halted is False
    assert result.health_status == HealthStatus.RED
