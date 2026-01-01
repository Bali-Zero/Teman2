"""
Unit tests for core/cache.py
Target: >95% coverage
"""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.cache import CacheService, LRUCache, get_cache_service


class TestLRUCache:
    """Tests for LRUCache"""

    def test_init(self):
        """Test initialization"""
        cache = LRUCache(max_size=100, default_ttl=300)
        assert cache.max_size == 100
        assert cache.default_ttl == 300

    def test_init_with_maxsize_alias(self):
        """Test initialization with maxsize alias"""
        cache = LRUCache(maxsize=50)
        assert cache.max_size == 50

    def test_get_missing_key(self):
        """Test getting missing key"""
        cache = LRUCache()
        assert cache.get("missing") is None

    def test_set_and_get(self):
        """Test setting and getting value"""
        cache = LRUCache(default_ttl=3600)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_expired(self):
        """Test getting expired value"""
        cache = LRUCache(default_ttl=0)  # Expires immediately
        cache.set("key1", "value1")
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_set_with_custom_ttl(self):
        """Test setting with custom TTL"""
        cache = LRUCache(default_ttl=1)
        cache.set("key1", "value1", ttl=2)
        assert cache.get("key1") == "value1"
        time.sleep(2.1)
        assert cache.get("key1") is None

    def test_delete_existing(self):
        """Test deleting existing key"""
        cache = LRUCache()
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_missing(self):
        """Test deleting missing key"""
        cache = LRUCache()
        assert cache.delete("missing") is False

    def test_clear(self):
        """Test clearing cache"""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.clear()
        assert count == 2
        assert cache.get("key1") is None

    def test_eviction_when_full(self):
        """Test LRU eviction when cache is full"""
        cache = LRUCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_move_to_end_on_get(self):
        """Test that get moves item to end"""
        cache = LRUCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # Move key1 to end
        cache.set("key3", "value3")  # Should evict key2, not key1
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None


class TestCacheService:
    """Tests for CacheService"""

    def test_init(self):
        """Test initialization"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            assert service.redis_available is False
            assert isinstance(service.stats, dict)

    def test_get_missing(self):
        """Test getting missing key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            result = service.get("missing")
            assert result is None

    def test_get_found_memory(self):
        """Test getting found key from memory cache"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            service.set("key1", "value1")
            result = service.get("key1")
            assert result == "value1"

    def test_set(self):
        """Test setting value"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            result = service.set("key1", "value1")
            assert result is True
            assert service.get("key1") == "value1"

    def test_set_with_ttl(self):
        """Test setting value with TTL"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            result = service.set("key1", "value1", ttl=300)
            assert result is True

    def test_delete(self):
        """Test deleting key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            service.set("key1", "value1")
            result = service.delete("key1")
            assert result is True
            assert service.get("key1") is None

    def test_delete_missing(self):
        """Test deleting missing key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            result = service.delete("missing")
            assert result is False

    def test_get_stats(self):
        """Test getting cache statistics"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            service = CacheService()
            stats = service.get_stats()
            assert "hits" in stats
            assert "misses" in stats
            assert "errors" in stats

    def test_get_cache_service_singleton(self):
        """Test get_cache_service returns singleton"""
        service1 = get_cache_service()
        service2 = get_cache_service()
        assert service1 is service2

