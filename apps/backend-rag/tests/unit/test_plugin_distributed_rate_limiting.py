"""
Unit tests for Distributed Rate Limiting with Redis
Tests Redis-based rate limiting in PluginExecutor
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.plugins.executor import PluginExecutor
from core.plugins.plugin import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput
from core.plugins.registry import PluginRegistry


class MockRateLimitedPlugin(Plugin):
    """Mock plugin with rate limit"""

    def __init__(self, config=None):
        self._rate_limit = 5
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="rate.limited.plugin",
            description="Rate limited plugin",
            category=PluginCategory.SYSTEM,
            version="1.0.0",
            rate_limit=self._rate_limit,
        )

    @property
    def input_schema(self) -> type[PluginInput]:
        return PluginInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return PluginOutput

    async def execute(self, input_data: PluginInput) -> PluginOutput:
        return PluginOutput(success=True, data={"result": "success"})


@pytest.mark.asyncio
async def test_rate_limiting_with_redis():
    """Test rate limiting using Redis"""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)

    executor = PluginExecutor(redis_client=mock_redis)
    registry = PluginRegistry()

    plugin = MockRateLimitedPlugin()
    await registry.register(MockRateLimitedPlugin)

    with patch("core.plugins.executor.registry", registry):
        # First call should succeed
        result = await executor.execute("rate.limited.plugin", {})
        assert result.success is True

        # Verify Redis was called
        mock_redis.incr.assert_called()
        mock_redis.expire.assert_called()


@pytest.mark.asyncio
async def test_rate_limiting_redis_exceeds_limit():
    """Test rate limiting blocks when Redis counter exceeds limit"""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=6)  # Exceeds limit of 5
    mock_redis.expire = AsyncMock(return_value=True)

    executor = PluginExecutor(redis_client=mock_redis)
    registry = PluginRegistry()

    await registry.register(MockRateLimitedPlugin)

    with patch("core.plugins.executor.registry", registry):
        result = await executor.execute("rate.limited.plugin", {})

        assert result.success is False
        assert "Rate limit exceeded" in result.error


@pytest.mark.asyncio
async def test_rate_limiting_redis_fallback_to_memory():
    """Test rate limiting falls back to memory if Redis fails"""
    # Mock Redis client that fails
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(side_effect=Exception("Redis connection failed"))

    executor = PluginExecutor(redis_client=mock_redis)
    registry = PluginRegistry()

    await registry.register(MockRateLimitedPlugin)

    with patch("core.plugins.executor.registry", registry):
        # Should fall back to memory-based rate limiting
        result = await executor.execute("rate.limited.plugin", {})

        # Should still work (fallback to memory)
        assert result.success is True


@pytest.mark.asyncio
async def test_rate_limiting_per_user_with_redis():
    """Test per-user rate limiting with Redis"""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)

    executor = PluginExecutor(redis_client=mock_redis)
    registry = PluginRegistry()

    await registry.register(MockRateLimitedPlugin)

    with patch("core.plugins.executor.registry", registry):
        # User1 makes request
        result1 = await executor.execute("rate.limited.plugin", {}, user_id="user1")
        assert result1.success is True

        # User2 makes request (should have separate rate limit)
        result2 = await executor.execute("rate.limited.plugin", {}, user_id="user2")
        assert result2.success is True

        # Verify Redis keys are user-specific
        calls = mock_redis.incr.call_args_list
        assert len(calls) == 2
        # Keys should include user_id
        assert "user1" in str(calls[0]) or "user1" in str(calls[0].args[0])
        assert "user2" in str(calls[1]) or "user2" in str(calls[1].args[0])


@pytest.mark.asyncio
async def test_rate_limiting_memory_fallback():
    """Test rate limiting uses memory when Redis not available"""
    # No Redis client
    executor = PluginExecutor(redis_client=None)
    registry = PluginRegistry()

    await registry.register(MockRateLimitedPlugin)

    with patch("core.plugins.executor.registry", registry):
        # Make requests within limit
        for i in range(3):
            result = await executor.execute("rate.limited.plugin", {}, user_id="user1")
            assert result.success is True

        # Should use memory-based rate limiting
        assert "rate.limited.plugin:user1" in executor._rate_limits


@pytest.mark.asyncio
async def test_rate_limiting_redis_expiration():
    """Test Redis rate limit expiration"""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)

    executor = PluginExecutor(redis_client=mock_redis)
    registry = PluginRegistry()

    await registry.register(MockRateLimitedPlugin)

    with patch("core.plugins.executor.registry", registry):
        await executor.execute("rate.limited.plugin", {})

        # Verify expire was called with 60 seconds
        mock_redis.expire.assert_called()
        expire_call = mock_redis.expire.call_args
        assert expire_call[0][1] == 60  # 60 seconds expiration










