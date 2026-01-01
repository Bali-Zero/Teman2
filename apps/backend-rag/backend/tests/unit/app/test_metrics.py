"""
Unit tests for app/metrics.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.metrics import MetricsCollector


class TestMetrics:
    """Tests for metrics module"""

    @pytest.fixture
    def metrics_collector(self):
        """Create MetricsCollector instance"""
        return MetricsCollector()

    def test_init(self):
        """Test initialization"""
        collector = MetricsCollector()
        assert collector.session_count == 0

    def test_update_session_count(self, metrics_collector):
        """Test updating session count"""
        metrics_collector.update_session_count(5)
        assert metrics_collector.session_count == 5

    @pytest.mark.asyncio
    async def test_measure_redis_latency(self, metrics_collector):
        """Test measuring Redis latency"""
        with patch("core.cache.get_cache_service") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.set = MagicMock()
            mock_cache.get = MagicMock(return_value="pong")
            mock_get_cache.return_value = mock_cache
            
            latency = await metrics_collector.measure_redis_latency()
            assert latency >= 0

    @pytest.mark.asyncio
    async def test_measure_redis_latency_error(self, metrics_collector):
        """Test measuring Redis latency with error"""
        with patch("core.cache.get_cache_service", side_effect=Exception("Error")):
            latency = await metrics_collector.measure_redis_latency()
            assert latency == -1

    @pytest.mark.asyncio
    async def test_measure_sse_latency(self, metrics_collector):
        """Test measuring SSE latency"""
        latency = await metrics_collector.measure_sse_latency()
        assert latency == 0  # Initial value

    def test_update_sse_latency(self, metrics_collector):
        """Test updating SSE latency"""
        metrics_collector.update_sse_latency(100.0)
        assert metrics_collector.last_sse_latency == 100.0

    def test_update_system_metrics(self, metrics_collector):
        """Test updating system metrics"""
        with patch("app.metrics.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 50.0
            mock_psutil.virtual_memory.return_value = MagicMock(used=1024*1024*1024)
            
            metrics_collector.update_system_metrics()
            # Should not raise exception

    def test_record_request(self, metrics_collector):
        """Test recording HTTP request"""
        metrics_collector.record_request("GET", "/api/test", 200, 0.1)
        # Should not raise exception

    def test_record_cache_hit(self, metrics_collector):
        """Test recording cache hit"""
        metrics_collector.record_cache_hit()
        # Should not raise exception

    def test_record_cache_miss(self, metrics_collector):
        """Test recording cache miss"""
        metrics_collector.record_cache_miss()
        # Should not raise exception

    def test_record_ai_request(self, metrics_collector):
        """Test recording AI request"""
        metrics_collector.record_ai_request("gemini-3-flash-preview", 0.5, tokens=100)
        # Should not raise exception

    def test_record_rag_query(self, metrics_collector):
        """Test recording RAG query"""
        metrics_collector.record_rag_query("visa_oracle", "keyword", "success")
        # Should not raise exception

