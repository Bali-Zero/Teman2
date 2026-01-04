"""
Unit tests for Performance Optimizer
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.performance_optimizer import (
    AsyncLRUCache,
    BatchProcessor,
    ConnectionPool,
    MemoryOptimizer,
    PerformanceMonitor,
    async_timed,
    timed,
)


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor"""

    def test_init(self):
        """Test initialization"""
        monitor = PerformanceMonitor()
        assert monitor.metrics["request_count"] == 0
        assert monitor.metrics["total_time"] == 0

    def test_record_request(self):
        """Test recording request"""
        monitor = PerformanceMonitor()
        monitor.record_request(0.5, cache_hit=True)
        assert monitor.metrics["request_count"] == 1
        assert monitor.metrics["cache_hits"] == 1

    def test_record_request_cache_miss(self):
        """Test recording request with cache miss"""
        monitor = PerformanceMonitor()
        monitor.record_request(0.5, cache_hit=False)
        assert monitor.metrics["cache_misses"] == 1

    def test_record_component_time(self):
        """Test recording component time"""
        monitor = PerformanceMonitor()
        monitor.record_component_time("embedding_time", 0.1)
        assert monitor.metrics["embedding_time"] == 0.1

    def test_get_metrics(self):
        """Test getting metrics"""
        monitor = PerformanceMonitor()
        monitor.record_request(0.5, cache_hit=True)
        monitor.record_request(0.3, cache_hit=False)
        metrics = monitor.get_metrics()
        assert "cache_hit_rate" in metrics
        assert "requests_per_second" in metrics


class TestAsyncTimed:
    """Tests for async_timed decorator"""

    @pytest.mark.asyncio
    async def test_async_timed(self):
        """Test async_timed decorator"""

        @async_timed("test_component")
        async def test_func():
            return "result"

        result = await test_func()
        assert result == "result"


class TestTimed:
    """Tests for timed decorator"""

    def test_timed(self):
        """Test timed decorator"""

        @timed("test_component")
        def test_func():
            return "result"

        result = test_func()
        assert result == "result"


class TestAsyncLRUCache:
    """Tests for AsyncLRUCache"""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test initialization"""
        cache = AsyncLRUCache(maxsize=10, ttl=60)
        assert cache.maxsize == 10
        assert cache.ttl == 60

    @pytest.mark.asyncio
    async def test_get_set(self):
        """Test get and set operations"""
        cache = AsyncLRUCache(maxsize=10, ttl=300)

        # Set value
        await cache.set("key1", "value1")

        # Get value
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting nonexistent key"""
        cache = AsyncLRUCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL expiration"""
        cache = AsyncLRUCache(maxsize=10, ttl=0)  # Immediate expiration

        await cache.set("key1", "value1")
        # Wait a tiny bit to ensure expiration
        import asyncio

        await asyncio.sleep(0.01)

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when maxsize reached"""
        cache = AsyncLRUCache(maxsize=2, ttl=300)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")  # Should evict oldest

        # key1 should be evicted
        result1 = await cache.get("key1")
        assert result1 is None

        # key2 and key3 should still be there
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing cache"""
        cache = AsyncLRUCache()
        await cache.set("key1", "value1")
        await cache.clear()

        result = await cache.get("key1")
        assert result is None


class TestConnectionPool:
    """Tests for ConnectionPool"""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test initialization"""
        pool = ConnectionPool(max_connections=5)
        assert pool.max_connections == 5

    @pytest.mark.asyncio
    async def test_get_connection(self):
        """Test getting connection from pool"""
        pool = ConnectionPool(max_connections=2)
        conn = await pool.get_connection()
        assert conn is not None

    @pytest.mark.asyncio
    async def test_return_connection(self):
        """Test returning connection to pool"""
        pool = ConnectionPool(max_connections=2)
        conn = await pool.get_connection()
        await pool.return_connection(conn)
        # Should not raise exception


class TestBatchProcessor:
    """Tests for BatchProcessor"""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test initialization"""
        processor = BatchProcessor(batch_size=5, max_wait=0.1)
        assert processor.batch_size == 5
        assert processor.max_wait == 0.1

    @pytest.mark.asyncio
    async def test_add_request(self):
        """Test adding request to batch"""
        processor = BatchProcessor(batch_size=1, max_wait=0.01)

        result = await processor.add_request({"test": "data"})
        assert "Processed" in result


class TestMemoryOptimizer:
    """Tests for MemoryOptimizer"""

    def test_optimize_chroma_settings(self):
        """Test optimize_chroma_settings"""
        settings = MemoryOptimizer.optimize_chroma_settings()
        assert isinstance(settings, dict)
        assert "anonymized_telemetry" in settings

    def test_optimize_embedding_model(self):
        """Test optimize_embedding_model"""
        settings = MemoryOptimizer.optimize_embedding_model()
        assert isinstance(settings, dict)
        assert "device" in settings
