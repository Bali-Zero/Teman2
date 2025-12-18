"""
Unit tests for CacheService Dependency Injection
Tests isolation and DI patterns
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.cache import CacheService, cached, get_cache_service

# ============================================================================
# Tests for Instance Isolation
# ============================================================================


@patch("app.core.config.settings.redis_url", None)
def test_cache_service_instances_are_isolated():
    """Test that different CacheService instances have isolated memory caches"""
    cache1 = CacheService()
    cache2 = CacheService()

    # They should be different instances
    assert cache1 is not cache2

    # Set value in cache1
    cache1.set("test_key", "value1", ttl=60)

    # cache2 should not have this value (isolated)
    assert cache2.get("test_key") is None

    # cache1 should still have it
    assert cache1.get("test_key") == "value1"


def test_singleton_pattern_still_works():
    """Test that get_cache_service() returns singleton"""
    cache1 = get_cache_service()
    cache2 = get_cache_service()

    # Should be same instance (singleton)
    assert cache1 is cache2

    # Set value in cache1
    cache1.set("singleton_key", "value", ttl=60)

    # cache2 should have it (same instance)
    assert cache2.get("singleton_key") == "value"


def test_cache_service_memory_cache_is_instance_level():
    """Test that _memory_cache is instance-level, not module-level"""
    cache1 = CacheService()
    cache2 = CacheService()

    # Verify they have separate memory caches
    assert cache1._memory_cache is not cache2._memory_cache

    # Set in cache1
    cache1._memory_cache.set("test", "value1", ttl=60)

    # cache2 should not have it
    assert cache2._memory_cache.get("test") is None


# ============================================================================
# Tests for Dependency Injection
# ============================================================================


@pytest.mark.asyncio
@patch("app.core.config.settings.redis_url", None)
async def test_cached_decorator_with_di():
    """Test @cached decorator works with dependency injection"""
    # Create isolated cache for testing
    test_cache = CacheService()

    call_count = 0

    @cached(ttl=60, prefix="test", cache_service=test_cache)
    async def expensive_operation(x: int):
        nonlocal call_count
        call_count += 1
        return x * 2

    # First call - should execute function
    result1 = await expensive_operation(5)
    assert result1 == 10
    assert call_count == 1

    # Second call - should use cache
    result2 = await expensive_operation(5)
    assert result2 == 10
    assert call_count == 1  # Should not increment

    # Different argument - should execute again
    result3 = await expensive_operation(10)
    assert result3 == 20
    assert call_count == 2


@pytest.mark.asyncio
@patch("app.core.config.settings.redis_url", None)
async def test_cached_decorator_without_di_uses_singleton():
    """Test @cached decorator without cache_service uses singleton"""
    call_count = 0

    @cached(ttl=60, prefix="test_singleton")
    async def expensive_operation(x: int):
        nonlocal call_count
        call_count += 1
        return x * 2

    # First call
    result1 = await expensive_operation(5)
    assert result1 == 10
    assert call_count == 1

    # Second call - should use cache (singleton)
    result2 = await expensive_operation(5)
    assert result2 == 10
    assert call_count == 1


@pytest.mark.asyncio
@patch("app.core.config.settings.redis_url", None)
async def test_cached_decorator_isolation():
    """Test that different cache instances don't share cached values"""
    cache1 = CacheService()
    cache2 = CacheService()

    call_count_1 = 0
    call_count_2 = 0

    @cached(ttl=60, prefix="test", cache_service=cache1)
    async def func1(x: int):
        nonlocal call_count_1
        call_count_1 += 1
        return f"cache1_{x}"

    @cached(ttl=60, prefix="test", cache_service=cache2)
    async def func2(x: int):
        nonlocal call_count_2
        call_count_2 += 1
        return f"cache2_{x}"

    # Call func1
    result1 = await func1(5)
    assert result1 == "cache1_5"
    assert call_count_1 == 1

    # Call func2 with same argument - should execute (different cache)
    result2 = await func2(5)
    assert result2 == "cache2_5"
    assert call_count_2 == 1

    # Call func1 again - should use cache
    result1_2 = await func1(5)
    assert result1_2 == "cache1_5"
    assert call_count_1 == 1  # Should not increment


# ============================================================================
# Tests for FastAPI Dependency Injection Pattern
# ============================================================================


def test_get_cache_service_returns_singleton():
    """Test that get_cache_service() follows singleton pattern"""
    cache1 = get_cache_service()
    cache2 = get_cache_service()

    assert cache1 is cache2


def test_cache_service_can_be_mocked():
    """Test that CacheService can be easily mocked for testing"""
    mock_cache = MagicMock(spec=CacheService)
    mock_cache.get.return_value = "mocked_value"
    mock_cache.set.return_value = True

    # Can be used in place of real cache
    assert mock_cache.get("key") == "mocked_value"
    assert mock_cache.set("key", "value", ttl=60) is True


# ============================================================================
# Tests for Memory Cache Isolation
# ============================================================================


@patch("app.core.config.settings.redis_url", None)
def test_memory_cache_cleanup():
    """Test that memory cache cleanup works per instance"""
    cache = CacheService()

    # Set some values
    cache.set("key1", "value1", ttl=60)
    cache.set("key2", "value2", ttl=60)

    # Clear pattern
    count = cache.clear_pattern("key1")
    assert count == 1

    # key1 should be gone
    assert cache.get("key1") is None

    # key2 should still be there
    assert cache.get("key2") == "value2"


@patch("app.core.config.settings.redis_url", None)
def test_memory_cache_stats_per_instance():
    """Test that stats are per-instance"""
    cache1 = CacheService()
    cache2 = CacheService()

    # Use cache1
    cache1.set("key1", "value1", ttl=60)
    cache1.get("key1")

    # Use cache2
    cache2.set("key2", "value2", ttl=60)
    cache2.get("key2")

    stats1 = cache1.get_stats()
    stats2 = cache2.get_stats()

    # Stats should be independent
    assert stats1["hits"] == 1
    assert stats2["hits"] == 1

    # They should be separate instances
    assert cache1 is not cache2










