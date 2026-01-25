"""
Unit tests for Cache Service
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.article_composer.cache import CacheService


@pytest.fixture
def cache_service():
    """Create cache service instance"""
    return CacheService()


class TestCacheService:
    """Test cache service functionality"""

    @pytest.mark.asyncio
    async def test_initialize_with_redis(self, cache_service):
        """Test cache initialization with Redis available"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch("redis.asyncio.from_url", return_value=mock_redis):
            await cache_service.initialize()

            # Verify Redis client was set and enabled after ping
            assert cache_service.redis_client is not None
            # The initialize method calls ping() and sets enabled=True if successful
            assert cache_service.enabled is True

    @pytest.mark.asyncio
    async def test_initialize_without_redis(self, cache_service):
        """Test cache initialization without Redis (graceful degradation)"""
        with patch("redis.asyncio.from_url", side_effect=Exception("Redis unavailable")):
            await cache_service.initialize()

            assert cache_service.enabled is False
            assert cache_service.redis_client is None

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_service):
        """Test getting cached value"""
        cache_service.enabled = True
        cache_service.redis_client = AsyncMock()
        cache_service.redis_client.get = AsyncMock(return_value='{"result": "cached_data"}')

        result = await cache_service.get("test_key")

        assert result == {"result": "cached_data"}
        cache_service.redis_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service):
        """Test cache miss returns None"""
        cache_service.enabled = True
        cache_service.redis_client = AsyncMock()
        cache_service.redis_client.get = AsyncMock(return_value=None)

        result = await cache_service.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_disabled(self, cache_service):
        """Test get returns None when cache is disabled"""
        cache_service.enabled = False

        result = await cache_service.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_cache(self, cache_service):
        """Test setting cache value"""
        cache_service.enabled = True
        cache_service.redis_client = AsyncMock()
        cache_service.redis_client.setex = AsyncMock()

        await cache_service.set("test_key", {"data": "value"}, ttl=3600)

        cache_service.redis_client.setex.assert_called_once()
        call_args = cache_service.redis_client.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 3600

    @pytest.mark.asyncio
    async def test_set_cache_disabled(self, cache_service):
        """Test set does nothing when cache is disabled"""
        cache_service.enabled = False

        # Should not raise
        await cache_service.set("test_key", {"data": "value"})

    @pytest.mark.asyncio
    async def test_delete_cache(self, cache_service):
        """Test deleting cache key"""
        cache_service.enabled = True
        cache_service.redis_client = AsyncMock()
        cache_service.redis_client.delete = AsyncMock()

        await cache_service.delete("test_key")

        cache_service.redis_client.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_compose_cache(self, cache_service):
        """Test getting compose cache"""
        cache_service.enabled = True
        cache_service.get = AsyncMock(return_value={"article": {}, "api_cost_cents": 3.5})

        result = await cache_service.get_compose_cache("Test Title", "Test content", "business")

        assert result is not None
        assert "article" in result
        cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_compose_cache(self, cache_service):
        """Test setting compose cache"""
        cache_service.enabled = True
        cache_service.set = AsyncMock()

        cache_data = {"article": {}, "api_cost_cents": 3.5}
        await cache_service.set_compose_cache("Test Title", "Test content", "business", cache_data)

        cache_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, cache_service):
        """Test closing cache connection"""
        cache_service.redis_client = AsyncMock()
        cache_service.redis_client.close = AsyncMock()

        await cache_service.close()

        cache_service.redis_client.close.assert_called_once()
