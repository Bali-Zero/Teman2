"""
Unit tests for Cache Service
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.cache import CacheService, cached, invalidate_cache

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    with patch("app.core.config.settings") as mock:
        mock.redis_url = None
        yield mock


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    mock_client.delete.return_value = 1
    mock_client.keys.return_value = []
    return mock_client


@pytest.fixture
def cache_service_no_redis():
    """Create CacheService without Redis"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = None
        with patch("core.cache.logger"):
            service = CacheService()
            return service


@pytest.fixture
def cache_service_with_redis(mock_redis_client):
    """Create CacheService with Redis"""
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis_client

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            with patch("core.cache.logger"):
                service = CacheService()
                return service


@pytest.fixture
def clear_memory_cache(cache_service_no_redis):
    """Clear memory cache before and after test (instance-level)"""
    cache_service_no_redis._memory_cache.clear()
    yield
    cache_service_no_redis._memory_cache.clear()


# ============================================================================
# Tests for CacheService.__init__
# ============================================================================


def test_init_without_redis_url():
    """Test initialization without Redis URL"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = None
        with patch("core.cache.logger") as mock_logger:
            service = CacheService()
            assert service.redis_available is False
            assert service.redis_client is None
            assert service.stats == {"hits": 0, "misses": 0, "errors": 0}
            mock_logger.info.assert_called_once()


def test_init_with_redis_url_success(mock_redis_client):
    """Test initialization with Redis URL and successful connection"""
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis_client

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            with patch("core.cache.logger") as mock_logger:
                service = CacheService()
                assert service.redis_available is True
                assert service.redis_client == mock_redis_client
                mock_redis_module.from_url.assert_called_once_with(
                    "redis://localhost:6379", decode_responses=True
                )
                mock_redis_client.ping.assert_called_once()
                mock_logger.info.assert_called_once()


def test_init_with_redis_connection_error():
    """Test initialization when Redis connection fails"""
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.side_effect = Exception("Connection refused")

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            with patch("core.cache.logger") as mock_logger:
                service = CacheService()
                assert service.redis_available is False
                assert service.redis_client is None
                mock_logger.warning.assert_called_once()


def test_init_with_redis_ping_error(mock_redis_client):
    """Test initialization when Redis ping fails"""
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis_client
    mock_redis_client.ping.side_effect = Exception("Ping failed")

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            with patch("core.cache.logger") as mock_logger:
                service = CacheService()
                assert service.redis_available is False
                mock_logger.warning.assert_called_once()


# ============================================================================
# Tests for _generate_key
# ============================================================================


def test_generate_key_with_args(cache_service_no_redis):
    """Test key generation with positional arguments"""
    key = cache_service_no_redis._generate_key("test", "arg1", "arg2")
    assert key.startswith("zantara:test:")
    assert len(key.split(":")[2]) == 12  # MD5 hash truncated to 12 chars


def test_generate_key_with_kwargs(cache_service_no_redis):
    """Test key generation with keyword arguments"""
    key1 = cache_service_no_redis._generate_key("test", key1="value1", key2="value2")
    key2 = cache_service_no_redis._generate_key("test", key2="value2", key1="value1")
    # Should be deterministic (same order after sort_keys=True)
    assert key1 == key2


def test_generate_key_with_mixed_args(cache_service_no_redis):
    """Test key generation with mixed args and kwargs"""
    key = cache_service_no_redis._generate_key("test", "arg1", key1="value1")
    assert key.startswith("zantara:test:")
    assert len(key) > 0


def test_generate_key_filters_self(cache_service_no_redis):
    """Test that 'self' is filtered from args"""

    class TestClass:
        pass

    obj = TestClass()
    key = cache_service_no_redis._generate_key("test", obj, "arg1")
    # Should not include obj in the hash
    assert key.startswith("zantara:test:")


# ============================================================================
# Tests for get method
# ============================================================================


def test_get_from_redis_hit(cache_service_with_redis, mock_redis_client):
    """Test get from Redis with cache hit"""
    mock_redis_client.get.return_value = '{"key": "value"}'
    result = cache_service_with_redis.get("test_key")
    assert result == {"key": "value"}
    assert cache_service_with_redis.stats["hits"] == 1
    assert cache_service_with_redis.stats["misses"] == 0
    mock_redis_client.get.assert_called_once_with("test_key")


def test_get_from_redis_miss(cache_service_with_redis, mock_redis_client):
    """Test get from Redis with cache miss"""
    mock_redis_client.get.return_value = None
    result = cache_service_with_redis.get("test_key")
    assert result is None
    assert cache_service_with_redis.stats["hits"] == 0
    assert cache_service_with_redis.stats["misses"] == 1


def test_get_from_memory_hit(cache_service_no_redis, clear_memory_cache):
    """Test get from memory cache with cache hit"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("test_key", {"key": "value"}, ttl=60)
    result = cache_service_no_redis.get("test_key")
    assert result == {"key": "value"}
    assert cache_service_no_redis.stats["hits"] == 1
    assert cache_service_no_redis.stats["misses"] == 0


def test_get_from_memory_miss(cache_service_no_redis, clear_memory_cache):
    """Test get from memory cache with cache miss"""
    result = cache_service_no_redis.get("test_key")
    assert result is None
    assert cache_service_no_redis.stats["hits"] == 0
    assert cache_service_no_redis.stats["misses"] == 1


def test_get_redis_error(cache_service_with_redis, mock_redis_client):
    """Test get when Redis raises exception"""
    mock_redis_client.get.side_effect = Exception("Redis error")
    with patch("core.cache.logger") as mock_logger:
        result = cache_service_with_redis.get("test_key")
        assert result is None
        assert cache_service_with_redis.stats["errors"] == 1
        mock_logger.error.assert_called_once()


def test_get_invalid_json(cache_service_with_redis, mock_redis_client):
    """Test get with invalid JSON from Redis"""
    mock_redis_client.get.return_value = "invalid json"
    with patch("core.cache.logger") as mock_logger:
        result = cache_service_with_redis.get("test_key")
        # Exception should be caught and None returned
        assert result is None
        assert cache_service_with_redis.stats["errors"] == 1
        mock_logger.error.assert_called_once()


# ============================================================================
# Tests for set method
# ============================================================================


def test_set_to_redis(cache_service_with_redis, mock_redis_client):
    """Test set to Redis"""
    result = cache_service_with_redis.set("test_key", {"key": "value"}, ttl=600)
    assert result is True
    mock_redis_client.setex.assert_called_once_with("test_key", 600, '{"key": "value"}')


def test_set_to_memory(cache_service_no_redis, clear_memory_cache):
    """Test set to memory cache"""
    result = cache_service_no_redis.set("test_key", {"key": "value"}, ttl=600)
    assert result is True
    # Verify in instance-level memory cache
    cached_value = cache_service_no_redis._memory_cache.get("test_key")
    assert cached_value == {"key": "value"}


def test_set_redis_error(cache_service_with_redis, mock_redis_client):
    """Test set when Redis raises exception"""
    mock_redis_client.setex.side_effect = Exception("Redis error")
    with patch("core.cache.logger") as mock_logger:
        result = cache_service_with_redis.set("test_key", {"key": "value"})
        assert result is False
        assert cache_service_with_redis.stats["errors"] == 1
        mock_logger.error.assert_called_once()


def test_set_default_ttl(cache_service_with_redis, mock_redis_client):
    """Test set with default TTL"""
    cache_service_with_redis.set("test_key", {"key": "value"})
    mock_redis_client.setex.assert_called_once_with("test_key", 300, '{"key": "value"}')


# ============================================================================
# Tests for delete method
# ============================================================================


def test_delete_from_redis(cache_service_with_redis, mock_redis_client):
    """Test delete from Redis"""
    result = cache_service_with_redis.delete("test_key")
    assert result is True
    mock_redis_client.delete.assert_called_once_with("test_key")


def test_delete_from_memory(cache_service_no_redis, clear_memory_cache):
    """Test delete from memory cache"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("test_key", {"key": "value"}, ttl=60)
    result = cache_service_no_redis.delete("test_key")
    assert result is True
    assert cache_service_no_redis._memory_cache.get("test_key") is None


def test_delete_nonexistent_memory(cache_service_no_redis, clear_memory_cache):
    """Test delete non-existent key from memory cache"""
    result = cache_service_no_redis.delete("nonexistent_key")
    # LRUCache.delete() returns False if key doesn't exist
    assert result is False


def test_delete_redis_error(cache_service_with_redis, mock_redis_client):
    """Test delete when Redis raises exception"""
    mock_redis_client.delete.side_effect = Exception("Redis error")
    with patch("core.cache.logger") as mock_logger:
        result = cache_service_with_redis.delete("test_key")
        assert result is False
        mock_logger.error.assert_called_once()


# ============================================================================
# Tests for clear_pattern method
# ============================================================================


def test_clear_pattern_redis_with_keys(cache_service_with_redis, mock_redis_client):
    """Test clear_pattern with Redis and matching keys"""
    mock_redis_client.keys.return_value = ["key1", "key2", "key3"]
    mock_redis_client.delete.return_value = 3
    result = cache_service_with_redis.clear_pattern("zantara:test:*")
    assert result == 3
    mock_redis_client.keys.assert_called_once_with("zantara:test:*")
    mock_redis_client.delete.assert_called_once_with("key1", "key2", "key3")


def test_clear_pattern_redis_no_keys(cache_service_with_redis, mock_redis_client):
    """Test clear_pattern with Redis and no matching keys"""
    mock_redis_client.keys.return_value = []
    result = cache_service_with_redis.clear_pattern("zantara:test:*")
    assert result == 0
    mock_redis_client.delete.assert_not_called()


def test_clear_pattern_memory(cache_service_no_redis, clear_memory_cache):
    """Test clear_pattern with memory cache"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("zantara:test:key1", "value1", ttl=60)
    cache_service_no_redis._memory_cache.set("zantara:test:key2", "value2", ttl=60)
    cache_service_no_redis._memory_cache.set("zantara:other:key3", "value3", ttl=60)
    result = cache_service_no_redis.clear_pattern("zantara:test:*")
    assert result == 2
    assert cache_service_no_redis._memory_cache.get("zantara:test:key1") is None
    assert cache_service_no_redis._memory_cache.get("zantara:test:key2") is None
    assert cache_service_no_redis._memory_cache.get("zantara:other:key3") == "value3"


def test_clear_pattern_memory_no_match(cache_service_no_redis, clear_memory_cache):
    """Test clear_pattern with memory cache and no matches"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("zantara:other:key", "value", ttl=60)
    result = cache_service_no_redis.clear_pattern("zantara:test:*")
    assert result == 0
    assert cache_service_no_redis._memory_cache.get("zantara:other:key") == "value"


def test_clear_pattern_redis_error(cache_service_with_redis, mock_redis_client):
    """Test clear_pattern when Redis raises exception"""
    mock_redis_client.keys.side_effect = Exception("Redis error")
    with patch("core.cache.logger") as mock_logger:
        result = cache_service_with_redis.clear_pattern("zantara:test:*")
        assert result == 0
        mock_logger.error.assert_called_once()


# ============================================================================
# Tests for get_stats method
# ============================================================================


def test_get_stats_with_hits_and_misses(cache_service_no_redis):
    """Test get_stats with hits and misses"""
    cache_service_no_redis.stats = {"hits": 10, "misses": 5, "errors": 0}
    stats = cache_service_no_redis.get_stats()
    assert stats["hits"] == 10
    assert stats["misses"] == 5
    assert stats["errors"] == 0
    assert stats["hit_rate"] == "66.7%"
    assert stats["backend"] == "memory"
    assert stats["connected"] is False


def test_get_stats_redis_backend(cache_service_with_redis):
    """Test get_stats with Redis backend"""
    cache_service_with_redis.stats = {"hits": 8, "misses": 2, "errors": 0}
    stats = cache_service_with_redis.get_stats()
    assert stats["backend"] == "redis"
    assert stats["connected"] is True
    assert stats["hit_rate"] == "80.0%"


def test_get_stats_no_requests(cache_service_no_redis):
    """Test get_stats with no requests"""
    stats = cache_service_no_redis.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["hit_rate"] == "0.0%"


def test_get_stats_with_errors(cache_service_no_redis):
    """Test get_stats with errors"""
    cache_service_no_redis.stats = {"hits": 5, "misses": 3, "errors": 2}
    stats = cache_service_no_redis.get_stats()
    assert stats["errors"] == 2


# ============================================================================
# Tests for cached decorator
# ============================================================================


@pytest.mark.asyncio
async def test_cached_decorator_cache_hit(cache_service_no_redis, clear_memory_cache):
    """Test cached decorator with cache hit"""
    call_count = 0

    # Explicitly pass the cache service instance
    @cached(ttl=300, prefix="test", cache_service=cache_service_no_redis)
    async def test_function(arg1, arg2):
        nonlocal call_count
        call_count += 1
        return {"result": arg1 + arg2}

    # First call - cache miss
    result1 = await test_function("a", "b")
    assert result1 == {"result": "ab"}
    assert call_count == 1

    # Second call - cache hit
    result2 = await test_function("a", "b")
    assert result2 == {"result": "ab"}
    assert call_count == 1  # Function not called again


@pytest.mark.asyncio
async def test_cached_decorator_cache_miss(cache_service_no_redis, clear_memory_cache):
    """Test cached decorator with cache miss"""
    call_count = 0

    # Explicitly pass the cache service instance
    @cached(ttl=300, prefix="test", cache_service=cache_service_no_redis)
    async def test_function(arg):
        nonlocal call_count
        call_count += 1
        return {"result": arg}

    # Different arguments = cache miss
    await test_function("a")
    await test_function("b")
    assert call_count == 2


@pytest.mark.asyncio
async def test_cached_decorator_custom_ttl(mock_redis_client):
    """Test cached decorator with custom TTL"""
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis_client

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            with patch("core.cache.logger"):
                # Create cache service with mocked redis
                cache_service = CacheService()
                cache_service.redis_available = True
                cache_service.redis_client = mock_redis_client

                @cached(ttl=600, prefix="test", cache_service=cache_service)
                async def test_function():
                    return {"result": "test"}

                await test_function()
                # Verify TTL was used
                call_args = mock_redis_client.setex.call_args
                assert call_args is not None
                assert call_args[0][1] == 600  # TTL parameter


@pytest.mark.asyncio
async def test_cached_decorator_custom_prefix(cache_service_no_redis, clear_memory_cache):
    """Test cached decorator with custom prefix"""
    # Use cache service instance
    cache_service_no_redis.redis_available = False
    cache_service_no_redis.redis_client = None

    @cached(ttl=300, prefix="custom", cache_service=cache_service_no_redis)
    async def test_function():
        return {"result": "test"}

    await test_function()
    # Check that key starts with custom prefix (instance-level cache)
    keys = list(cache_service_no_redis._memory_cache.cache.keys())
    assert len(keys) == 1
    assert keys[0].startswith("zantara:custom:")


@pytest.mark.asyncio
async def test_cached_decorator_with_kwargs(cache_service_no_redis, clear_memory_cache):
    """Test cached decorator with keyword arguments"""
    call_count = 0

    # Explicitly pass the cache service instance
    @cached(ttl=300, prefix="test", cache_service=cache_service_no_redis)
    async def test_function(**kwargs):
        nonlocal call_count
        call_count += 1
        return kwargs

    result1 = await test_function(key1="value1", key2="value2")
    result2 = await test_function(key2="value2", key1="value1")  # Same, different order
    assert result1 == result2
    assert call_count == 1  # Should be cached


# ============================================================================
# Tests for invalidate_cache function
# ============================================================================


def test_invalidate_cache_with_pattern(cache_service_no_redis, clear_memory_cache):
    """Test invalidate_cache function"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("zantara:test:key1", "value1", ttl=60)
    cache_service_no_redis._memory_cache.set("zantara:test:key2", "value2", ttl=60)
    cache_service_no_redis._memory_cache.set("zantara:other:key3", "value3", ttl=60)

    with patch("core.cache.logger") as mock_logger:
        count = invalidate_cache("zantara:test:*", cache_service=cache_service_no_redis)
        assert count == 2
        mock_logger.info.assert_called_once()


def test_invalidate_cache_default_pattern(cache_service_no_redis, clear_memory_cache):
    """Test invalidate_cache with default pattern"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("zantara:test:key1", "value1", ttl=60)
    cache_service_no_redis._memory_cache.set("zantara:test:key2", "value2", ttl=60)

    with patch("core.cache.logger"):
        count = invalidate_cache(cache_service=cache_service_no_redis)
        assert count == 2


def test_invalidate_cache_no_matches(cache_service_no_redis, clear_memory_cache):
    """Test invalidate_cache with no matching keys"""
    # Use instance-level memory cache
    cache_service_no_redis._memory_cache.set("zantara:other:key", "value", ttl=60)

    with patch("core.cache.logger"):
        count = invalidate_cache("zantara:test:*", cache_service=cache_service_no_redis)
        assert count == 0


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


def test_redis_unavailable_fallback(cache_service_with_redis, mock_redis_client):
    """Test that Redis errors fall back to memory cache"""
    # Simulate Redis becoming unavailable
    cache_service_with_redis.redis_available = False
    cache_service_with_redis.redis_client = None

    result = cache_service_with_redis.set("test_key", {"key": "value"})
    assert result is True
    # Should use instance-level memory cache
    assert cache_service_with_redis._memory_cache.get("test_key") == {"key": "value"}


def test_memory_cache_isolation(cache_service_no_redis, clear_memory_cache):
    """Test that memory cache is isolated per service instance"""
    # Set value in first instance
    cache_service_no_redis._memory_cache.set("persistent_key", "persistent_value", ttl=60)

    # Create second instance (should be isolated)
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = None
        with patch("core.cache.logger"):
            service2 = CacheService()
            result = service2.get("persistent_key")
            # Should be None (isolated instances)
            assert result is None

    # First instance should still have it
    assert cache_service_no_redis.get("persistent_key") == "persistent_value"


def test_stats_independence():
    """Test that stats are independent per service instance"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = None
        with patch("core.cache.logger"):
            service1 = CacheService()
            service2 = CacheService()

            service1.get("key1")
            service2.get("key2")

            assert service1.stats["misses"] == 1
            assert service2.stats["misses"] == 1
            # Stats should be independent
            assert service1.stats is not service2.stats


def test_generate_key_with_complex_types(cache_service_no_redis):
    """Test key generation with complex types"""
    key = cache_service_no_redis._generate_key("test", [1, 2, 3], {"nested": {"key": "value"}})
    assert key.startswith("zantara:test:")
    assert len(key.split(":")[2]) == 12
