"""Tests for the pulse cycle — CELL's heartbeat."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from cell.core.pulse import PulseEngine
from cell.fast.health_triage import HealthStatus


@pytest.fixture
def mock_deps() -> dict:
    return {
        "dna_loader": MagicMock(),
        "safety_gate": AsyncMock(),
        "health_sensor": AsyncMock(),
        "metabolism": MagicMock(),
    }


@pytest.mark.asyncio
async def test_pulse_dna_check_fails(mock_deps: dict) -> None:
    mock_deps["dna_loader"].verify_integrity.return_value = False
    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash")
    result = await engine.single_pulse()
    assert result.halted is True
    assert "dna" in result.halt_reason.lower()


@pytest.mark.asyncio
async def test_pulse_disabled(mock_deps: dict) -> None:
    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = False
    safety_result.reason = "disabled"
    safety_result.detail = "Redis key set"
    mock_deps["safety_gate"].check.return_value = safety_result
    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash")
    result = await engine.single_pulse()
    assert result.skipped is True
    assert result.skip_reason == "disabled"


@pytest.mark.asyncio
async def test_pulse_healthy_system(mock_deps: dict) -> None:
    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = True
    mock_deps["safety_gate"].check.return_value = safety_result
    health_reading = MagicMock()
    health_reading.reachable = True
    health_reading.status_code = 200
    health_reading.response_time_seconds = 0.1
    mock_deps["health_sensor"].read.return_value = health_reading
    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash")
    result = await engine.single_pulse()
    assert result.halted is False
    assert result.skipped is False
    assert result.health_status == HealthStatus.GREEN
    assert result.action_taken is None
