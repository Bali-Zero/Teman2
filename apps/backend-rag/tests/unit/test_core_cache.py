"""
Unit tests for Core Cache Module - LRUCache & CacheService
Comprehensive coverage for intelligent caching with Redis fallback
"""

import json
import time
from collections import OrderedDict
from unittest.mock import Mock, patch

import pytest

from backend.core.cache import (
    CACHE_KEY_HASH_LENGTH,
    DEFAULT_CACHE_TTL,
    DEFAULT_MAX_MEMORY_CACHE_SIZE,
    CacheService,
    LRUCache,
    cached,
    get_cache_service,
    invalidate_cache,
)


class TestLRUCache:
    """Test suite for LRUCache class"""

    def test_init_default_parameters(self):
        """Test LRUCache initialization with defaults"""
        cache = LRUCache()
        assert cache.max_size == DEFAULT_MAX_MEMORY_CACHE_SIZE
        assert cache.default_ttl == DEFAULT_CACHE_TTL
        assert isinstance(cache.cache, OrderedDict)
        assert len(cache.cache) == 0

    def test_init_custom_parameters(self):
        """Test LRUCache initialization with custom parameters"""
        cache = LRUCache(max_size=100, default_ttl=60)
        assert cache.max_size == 100
        assert cache.default_ttl == 60

    def test_set_and_get_simple(self):
        """Test basic set and get operations"""
        cache = LRUCache(default_ttl=300)
        cache.set("key1", "value1")

        result = cache.get("key1")
        assert result == "value1"

    def test_get_nonexistent_key(self):
        """Test getting non-existent key returns None"""
        cache = LRUCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_set_with_custom_ttl(self):
        """Test setting value with custom TTL"""
        cache = LRUCache(default_ttl=300)
        cache.set("key1", "value1", ttl=60)

        result = cache.get("key1")
        assert result == "value1"

    def test_ttl_expiration(self):
        """Test that expired keys return None"""
        cache = LRUCache()
        cache.set("key1", "value1", ttl=1)  # 1 second TTL

        # Should work immediately
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        # Should return None after expiration
        assert cache.get("key1") is None
        # Key should be deleted from cache
        assert "key1" not in cache.cache

    def test_lru_eviction(self):
        """Test LRU eviction when max_size reached"""
        cache = LRUCache(max_size=3, default_ttl=300)

        # Fill cache to max
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Add one more - should evict key1 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_order_updates_on_get(self):
        """Test that get() updates LRU order"""
        cache = LRUCache(max_size=3, default_ttl=300)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 (moves to end)
        cache.get("key1")

        # Add key4 - should evict key2 (now least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_update_existing_key(self):
        """Test updating existing key moves it to end"""
        cache = LRUCache(max_size=3, default_ttl=300)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Update key1 (should move to end)
        cache.set("key1", "value1_updated")

        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key2

        assert cache.get("key1") == "value1_updated"
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_delete_existing_key(self):
        """Test deleting existing key"""
        cache = LRUCache()
        cache.set("key1", "value1")

        result = cache.delete("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_delete_nonexistent_key(self):
        """Test deleting non-existent key"""
        cache = LRUCache()
        result = cache.delete("nonexistent")
        assert result is False

    def test_clear(self):
        """Test clearing all cache entries"""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        count = cache.clear()

        assert count == 3
        assert len(cache.cache) == 0
        assert cache.get("key1") is None

    def test_clear_pattern(self):
        """Test clearing keys matching pattern"""
        cache = LRUCache()
        cache.set("user:123", "data1")
        cache.set("user:456", "data2")
        cache.set("session:789", "data3")

        count = cache.clear_pattern("user:*")

        assert count == 2
        assert cache.get("user:123") is None
        assert cache.get("user:456") is None
        assert cache.get("session:789") == "data3"

    def test_clear_pattern_no_matches(self):
        """Test clearing pattern with no matches"""
        cache = LRUCache()
        cache.set("key1", "value1")

        count = cache.clear_pattern("nomatch:*")

        assert count == 0
        assert cache.get("key1") == "value1"

    def test_cleanup_expired(self):
        """Test cleanup of expired entries"""
        cache = LRUCache()
        cache.set("key1", "value1", ttl=1)
        cache.set("key2", "value2", ttl=10)
        cache.set("key3", "value3", ttl=1)

        time.sleep(1.1)

        count = cache.cleanup_expired()

        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") is None

    def test_cleanup_expired_no_expired(self):
        """Test cleanup when no entries expired"""
        cache = LRUCache()
        cache.set("key1", "value1", ttl=300)
        cache.set("key2", "value2", ttl=300)

        count = cache.cleanup_expired()

        assert count == 0
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

    def test_set_various_types(self):
        """Test caching various data types"""
        cache = LRUCache()

        cache.set("string", "value")
        cache.set("int", 42)
        cache.set("float", 3.14)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"key": "value"})
        cache.set("bool", True)
        cache.set("none", None)

        assert cache.get("string") == "value"
        assert cache.get("int") == 42
        assert cache.get("float") == 3.14
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"key": "value"}
        assert cache.get("bool") is True
        assert cache.get("none") is None

    def test_zero_ttl(self):
        """Test cache with zero TTL (immediately expired)"""
        cache = LRUCache()
        cache.set("key1", "value1", ttl=0)

        # Should be immediately expired
        assert cache.get("key1") is None


class TestCacheService:
    """Test suite for CacheService class"""

    @patch("app.core.config.settings")
    def test_init_no_redis(self, mock_settings):
        """Test CacheService initialization without Redis"""
        mock_settings.redis_url = None

        cache = CacheService()

        assert cache.redis_available is False
        assert cache.redis_client is None
        assert cache.stats == {"hits": 0, "misses": 0, "errors": 0}
        assert isinstance(cache._memory_cache, LRUCache)

    @patch("app.core.config.settings")
    @patch("redis.from_url")
    def test_init_with_redis_success(self, mock_redis_from_url, mock_settings):
        """Test CacheService initialization with Redis"""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis_client

        cache = CacheService()

        assert cache.redis_available is True
        assert cache.redis_client == mock_redis_client

    @patch("app.core.config.settings")
    @patch("redis.from_url")
    def test_init_with_redis_failure(self, mock_redis_from_url, mock_settings):
        """Test CacheService falls back when Redis fails"""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_from_url.side_effect = Exception("Connection failed")

        cache = CacheService()

        assert cache.redis_available is False
        assert cache.redis_client is None

    @patch("app.core.config.settings")
    def test_generate_key(self, mock_settings):
        """Test cache key generation"""
        mock_settings.redis_url = None
        cache = CacheService()

        key = cache._generate_key("test", "arg1", "arg2", key1="value1")

        assert key.startswith("zantara:test:")
        assert len(key.split(":")[-1]) == CACHE_KEY_HASH_LENGTH

    @patch("app.core.config.settings")
    def test_generate_key_deterministic(self, mock_settings):
        """Test that same args generate same key"""
        mock_settings.redis_url = None
        cache = CacheService()

        key1 = cache._generate_key("test", "arg1", key="value")
        key2 = cache._generate_key("test", "arg1", key="value")

        assert key1 == key2

    @patch("app.core.config.settings")
    def test_generate_key_different_args(self, mock_settings):
        """Test that different args generate different keys"""
        mock_settings.redis_url = None
        cache = CacheService()

        key1 = cache._generate_key("test", "arg1")
        key2 = cache._generate_key("test", "arg2")

        assert key1 != key2

    @patch("app.core.config.settings")
    def test_get_memory_cache_hit(self, mock_settings):
        """Test get() with memory cache hit"""
        mock_settings.redis_url = None
        cache = CacheService()

        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 0

    @patch("app.core.config.settings")
    def test_get_memory_cache_miss(self, mock_settings):
        """Test get() with memory cache miss"""
        mock_settings.redis_url = None
        cache = CacheService()

        result = cache.get("nonexistent")

        assert result is None
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 1

    @patch("app.core.config.settings")
    @patch("redis.from_url")
    def test_get_redis_cache_hit(self, mock_redis_from_url, mock_settings):
        """Test get() with Redis cache hit"""
        mock_settings.redis_url = "redis://localhost"
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = json.dumps("value1")
        mock_redis_from_url.return_value = mock_redis_client

        cache = CacheService()
        result = cache.get("key1")

        assert result == "value1"
        assert cache.stats["hits"] == 1

    @patch("app.core.config.settings")
    @patch("redis.from_url")
    def test_get_redis_cache_miss(self, mock_redis_from_url, mock_settings):
        """Test get() with Redis cache miss"""
        mock_settings.redis_url = "redis://localhost"
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None
        mock_redis_from_url.return_value = mock_redis_client

        cache = CacheService()
        result = cache.get("nonexistent")

        assert result is None
        assert cache.stats["misses"] == 1

    @patch("app.core.config.settings")
    def test_set_memory_cache(self, mock_settings):
        """Test set() with memory cache"""
        mock_settings.redis_url = None
        cache = CacheService()

        result = cache.set("key1", "value1", ttl=300)

        assert result is True
        assert cache.get("key1") == "value1"

    @patch("app.core.config.settings")
    @patch("redis.from_url")
    def test_set_redis_cache(self, mock_redis_from_url, mock_settings):
        """Test set() with Redis cache"""
        mock_settings.redis_url = "redis://localhost"
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis_client

        cache = CacheService()
        result = cache.set("key1", "value1", ttl=300)

        assert result is True
        mock_redis_client.setex.assert_called_once()

    @patch("app.core.config.settings")
    def test_delete_memory_cache(self, mock_settings):
        """Test delete() with memory cache"""
        mock_settings.redis_url = None
        cache = CacheService()

        cache.set("key1", "value1")
        result = cache.delete("key1")

        assert result is True
        assert cache.get("key1") is None

    @patch("app.core.config.settings")
    @patch("redis.from_url")
    def test_delete_redis_cache(self, mock_redis_from_url, mock_settings):
        """Test delete() with Redis cache"""
        mock_settings.redis_url = "redis://localhost"
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_from_url.return_value = mock_redis_client

        cache = CacheService()
        result = cache.delete("key1")

        assert result is True
        mock_redis_client.delete.assert_called_once_with("key1")

    @patch("app.core.config.settings")
    def test_clear_pattern_memory(self, mock_settings):
        """Test clear_pattern() with memory cache"""
        mock_settings.redis_url = None
        cache = CacheService()

        cache.set("user:1", "data1")
        cache.set("user:2", "data2")
        cache.set("session:1", "data3")

        count = cache.clear_pattern("user:*")

        assert count == 2

    @patch("app.core.config.settings")
    def test_get_stats_no_operations(self, mock_settings):
        """Test get_stats() with no operations"""
        mock_settings.redis_url = None
        cache = CacheService()

        stats = cache.get_stats()

        assert stats["backend"] == "memory"
        assert stats["connected"] is False
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["errors"] == 0
        assert stats["hit_rate"] == "0.0%"

    @patch("app.core.config.settings")
    def test_get_stats_with_operations(self, mock_settings):
        """Test get_stats() after cache operations"""
        mock_settings.redis_url = None
        cache = CacheService()

        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "50.0%"

    @patch("app.core.config.settings")
    def test_get_error_handling(self, mock_settings):
        """Test get() error handling"""
        mock_settings.redis_url = None
        cache = CacheService()

        # Force error by breaking memory cache
        cache._memory_cache.get = Mock(side_effect=Exception("Error"))

        result = cache.get("key1")

        assert result is None
        assert cache.stats["errors"] == 1


class TestCacheDecorator:
    """Test suite for @cached decorator"""

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_cached_decorator_first_call(self, mock_settings):
        """Test cached decorator on first call (cache miss)"""
        mock_settings.redis_url = None
        call_count = 0
        test_cache = CacheService()  # Create isolated cache instance

        @cached(ttl=300, prefix="test_first_call", cache_service=test_cache)
        async def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        result = await expensive_function()

        assert result == "result"
        assert call_count == 1

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_cached_decorator_second_call(self, mock_settings):
        """Test cached decorator on second call (cache hit)"""
        mock_settings.redis_url = None
        call_count = 0
        test_cache = CacheService()  # Create isolated cache instance

        @cached(ttl=300, prefix="test", cache_service=test_cache)
        async def expensive_function():
            nonlocal call_count
            call_count += 1
            return "result"

        result1 = await expensive_function()
        result2 = await expensive_function()

        assert result1 == "result"
        assert result2 == "result"
        assert call_count == 1  # Function called only once

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_cached_with_different_args(self, mock_settings):
        """Test cached decorator with different arguments"""
        mock_settings.redis_url = None
        call_count = 0
        test_cache = CacheService()  # Create isolated cache instance

        @cached(ttl=300, prefix="test_diff_args", cache_service=test_cache)
        async def function_with_args(arg1, arg2):
            nonlocal call_count
            call_count += 1
            return f"{arg1}-{arg2}"

        result1 = await function_with_args("a", "b")
        result2 = await function_with_args("a", "b")  # Same args - cache hit
        result3 = await function_with_args("c", "d")  # Different args - cache miss

        assert result1 == "a-b"
        assert result2 == "a-b"
        assert result3 == "c-d"
        assert call_count == 2  # Called for unique arg combinations


class TestUtilityFunctions:
    """Test suite for utility functions"""

    @patch("app.core.config.settings")
    def test_get_cache_service_singleton(self, mock_settings):
        """Test get_cache_service returns singleton"""
        mock_settings.redis_url = None

        # Reset singleton for test isolation
        import backend.core.cache as cache_module

        cache_module._cache_instance = None

        cache1 = get_cache_service()
        cache2 = get_cache_service()

        assert cache1 is cache2

        # Cleanup
        cache_module._cache_instance = None

    @patch("app.core.config.settings")
    def test_invalidate_cache(self, mock_settings):
        """Test invalidate_cache function"""
        mock_settings.redis_url = None
        cache = CacheService()

        cache.set("zantara:test:1", "data1")
        cache.set("zantara:test:2", "data2")
        cache.set("other:key", "data3")

        count = invalidate_cache("zantara:test:*", cache_service=cache)

        assert count == 2
        assert cache.get("zantara:test:1") is None
        assert cache.get("other:key") == "data3"


class TestConstants:
    """Test suite for module constants"""

    def test_constants_defined(self):
        """Test that all constants are defined"""
        assert CACHE_KEY_HASH_LENGTH == 12
        assert DEFAULT_CACHE_TTL == 300
        assert DEFAULT_MAX_MEMORY_CACHE_SIZE == 1000
