"""Tests for CELL safety mechanisms."""
import pytest
from unittest.mock import AsyncMock
from cell.core.safety import SafetyGate

@pytest.fixture
def mock_redis():
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    return client

@pytest.mark.asyncio
async def test_safety_gate_all_clear(mock_redis):
    gate = SafetyGate(redis=mock_redis, disable_file="/tmp/cell_test_nonexistent")
    result = await gate.check()
    assert result.can_proceed is True

@pytest.mark.asyncio
async def test_safety_gate_redis_disabled(mock_redis):
    mock_redis.get = AsyncMock(side_effect=lambda k: b"operator" if k == "cell:disabled" else None)
    gate = SafetyGate(redis=mock_redis, disable_file="/tmp/cell_test_nonexistent")
    result = await gate.check()
    assert result.can_proceed is False
    assert result.reason == "disabled"

@pytest.mark.asyncio
async def test_safety_gate_maintenance_mode(mock_redis):
    mock_redis.get = AsyncMock(side_effect=lambda k: b"alembic migration" if k == "cell:maintenance" else None)
    gate = SafetyGate(redis=mock_redis, disable_file="/tmp/cell_test_nonexistent")
    result = await gate.check()
    assert result.can_proceed is False
    assert result.reason == "maintenance"

@pytest.mark.asyncio
async def test_safety_gate_file_disabled(mock_redis, tmp_path):
    disable_file = tmp_path / "cell.disabled"
    disable_file.write_text("manual stop")
    gate = SafetyGate(redis=mock_redis, disable_file=str(disable_file))
    result = await gate.check()
    assert result.can_proceed is False
    assert result.reason == "disabled"
