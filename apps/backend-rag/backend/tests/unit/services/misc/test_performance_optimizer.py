"""
Unit tests for Performance Optimizer
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.performance_optimizer import PerformanceMonitor, perf_monitor, async_timed, timed


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

