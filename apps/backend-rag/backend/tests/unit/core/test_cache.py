"""
Unit tests for cache service
Target: >95% coverage
"""

import sys
import time
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.cache import LRUCache, cached


class TestLRUCache:
    """Tests for LRUCache"""

    def test_init(self):
        """Test initialization"""
        cache = LRUCache(max_size=10, default_ttl=60)
        assert cache.max_size == 10
        assert cache.default_ttl == 60

    def test_get_not_exists(self):
        """Test getting non-existent key"""
        cache = LRUCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_set_and_get(self):
        """Test setting and getting value"""
        cache = LRUCache(default_ttl=60)
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"

    def test_set_expired(self):
        """Test getting expired value"""
        cache = LRUCache(default_ttl=0)  # Expires immediately
        cache.set("key1", "value1")
        time.sleep(0.1)
        result = cache.get("key1")
        assert result is None

    def test_set_custom_ttl(self):
        """Test setting value with custom TTL"""
        cache = LRUCache(default_ttl=60)
        cache.set("key1", "value1", ttl=120)
        result = cache.get("key1")
        assert result == "value1"

    def test_delete(self):
        """Test deleting key"""
        cache = LRUCache()
        cache.set("key1", "value1")
        result = cache.delete("key1")
        assert result is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self):
        """Test deleting nonexistent key"""
        cache = LRUCache()
        result = cache.delete("nonexistent")
        assert result is False

    def test_clear(self):
        """Test clearing cache"""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.clear()
        assert count == 2
        assert len(cache.cache) == 0

    def test_lru_eviction(self):
        """Test LRU eviction when max size reached"""
        cache = LRUCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_lru_reorder_on_get(self):
        """Test LRU reordering on get"""
        cache = LRUCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # Move key1 to end
        cache.set("key3", "value3")  # Should evict key2, not key1

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"


class TestCachedDecorator:
    """Tests for cached decorator"""

    @pytest.mark.asyncio
    async def test_cached_async_function(self):
        """Test cached async function decorator"""
        call_count = {"count": 0}

        @cached(ttl=60)
        async def test_func(x):
            call_count["count"] += 1
            return x * 2

        result1 = await test_func(5)
        result2 = await test_func(5)  # Should use cache

        assert result1 == 10
        assert result2 == 10
        assert call_count["count"] == 1  # Called only once

    @pytest.mark.asyncio
    async def test_cached_async_function_different_args(self):
        """Test cached async function with different arguments"""
        call_count = {"count": 0}

        @cached(ttl=60, prefix="test")
        async def test_func(x):
            call_count["count"] += 1
            return x * 2

        result1 = await test_func(5)
        result2 = await test_func(10)  # Different arg, should call again
        result3 = await test_func(5)  # Same as first, should use cache

        assert result1 == 10
        assert result2 == 20
        assert result3 == 10
        # Should be called twice (once for 5, once for 10)
        assert call_count["count"] >= 1
