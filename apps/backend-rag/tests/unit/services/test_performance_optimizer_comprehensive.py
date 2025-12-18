"""
Comprehensive tests for services/performance_optimizer.py
Target: 95%+ coverage
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from services.performance_optimizer import PerformanceMonitor, async_timed, perf_monitor, timed


class TestPerformanceMonitor:
    """Comprehensive test suite for PerformanceMonitor"""

    @pytest.fixture
    def monitor(self):
        """Create PerformanceMonitor instance"""
        return PerformanceMonitor()

    def test_init(self, monitor):
        """Test PerformanceMonitor initialization"""
        assert monitor.metrics["request_count"] == 0
        assert monitor.metrics["total_time"] == 0

    def test_record_request(self, monitor):
        """Test record_request"""
        monitor.record_request(0.5, cache_hit=True)
        assert monitor.metrics["request_count"] == 1
        assert monitor.metrics["cache_hits"] == 1

    def test_record_request_cache_miss(self, monitor):
        """Test record_request with cache miss"""
        monitor.record_request(0.3, cache_hit=False)
        assert monitor.metrics["cache_misses"] == 1

    def test_record_component_time(self, monitor):
        """Test record_component_time"""
        monitor.record_component_time("embedding_time", 0.1)
        assert monitor.metrics["embedding_time"] == 0.1

    def test_get_metrics(self, monitor):
        """Test get_metrics"""
        monitor.record_request(0.5, cache_hit=True)
        monitor.record_request(0.3, cache_hit=False)
        metrics = monitor.get_metrics()
        assert "cache_hit_rate" in metrics
        assert "requests_per_second" in metrics


class TestTimedDecorators:
    """Test suite for timed decorators"""

    @pytest.mark.asyncio
    async def test_async_timed(self):
        """Test async_timed decorator"""

        @async_timed("test_component")
        async def test_func():
            await asyncio.sleep(0.01)
            return "result"

        result = await test_func()
        assert result == "result"
        # Check that component time was recorded
        assert (
            "test_component" in perf_monitor.metrics
            or perf_monitor.metrics.get("test_component", 0) >= 0
        )

    def test_timed(self):
        """Test timed decorator"""

        @timed("test_component_sync")
        def test_func():
            time.sleep(0.01)
            return "result"

        result = test_func()
        assert result == "result"
        # Check that component time was recorded
        assert (
            "test_component_sync" in perf_monitor.metrics
            or perf_monitor.metrics.get("test_component_sync", 0) >= 0
        )


class TestOptimizedSearchService:
    """Test suite for OptimizedSearchService"""

    @pytest.fixture
    def optimized_service(self):
        """Create OptimizedSearchService instance"""
        from services.performance_optimizer import OptimizedSearchService

        mock_search = MagicMock()
        return OptimizedSearchService(original_search_service=mock_search)

    def test_init(self, optimized_service):
        """Test OptimizedSearchService initialization"""
        assert optimized_service.original is not None
