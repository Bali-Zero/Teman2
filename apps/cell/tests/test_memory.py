"""Tests for CELL memory systems."""
import json
import pytest
from unittest.mock import AsyncMock
from cell.memory.short_term import ShortTermMemory, Observation

@pytest.fixture
def mock_redis():
    client = AsyncMock()
    client.set = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.keys = AsyncMock(return_value=[])
    client.info = AsyncMock(return_value={"used_memory": 1024})
    return client

@pytest.mark.asyncio
async def test_store_observation(mock_redis):
    mem = ShortTermMemory(redis=mock_redis, ttl_seconds=86400, max_bytes=5_000_000)
    obs = Observation(event_type="health_check", data={"status": "green"})
    await mem.store(obs)
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args.kwargs.get("ex") == 86400

@pytest.mark.asyncio
async def test_retrieve_recent(mock_redis):
    stored = json.dumps({"event_type": "health_check", "data": {"status": "green"}, "timestamp": "2026-03-26T10:00:00Z"})
    mock_redis.keys = AsyncMock(return_value=[b"cell:stm:1:health_check"])
    mock_redis.get = AsyncMock(return_value=stored.encode())
    mem = ShortTermMemory(redis=mock_redis, ttl_seconds=86400, max_bytes=5_000_000)
    results = await mem.recent(event_type="health_check", limit=10)
    assert len(results) == 1

@pytest.mark.asyncio
async def test_memory_budget_check(mock_redis):
    mock_redis.info = AsyncMock(return_value={"used_memory": 4_500_000})
    mem = ShortTermMemory(redis=mock_redis, ttl_seconds=86400, max_bytes=5_000_000)
    assert await mem.within_budget() is True
    mock_redis.info = AsyncMock(return_value={"used_memory": 5_500_000})
    assert await mem.within_budget() is False
