"""
Integration Tests for Metrics Module
Tests Prometheus metrics collection and reporting
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestMetricsIntegration:
    """Comprehensive integration tests for metrics module"""

    @pytest.fixture
    def metrics_collector(self):
        """Create MetricsCollector instance"""
        from app.metrics import MetricsCollector

        return MetricsCollector()

    def test_initialization(self, metrics_collector):
        """Test metrics collector initialization"""
        assert metrics_collector is not None
        assert metrics_collector.session_count == 0
        assert metrics_collector.last_redis_check == 0
        assert metrics_collector.last_sse_latency == 0

    def test_update_session_count(self, metrics_collector):
        """Test updating session count"""
        metrics_collector.update_session_count(10)
        assert metrics_collector.session_count == 10

    @pytest.mark.asyncio
    async def test_measure_redis_latency_success(self, metrics_collector):
        """Test measuring Redis latency successfully"""
        with patch("app.metrics.get_cache_service") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.set = MagicMock()
            mock_cache.get = MagicMock(return_value="pong")
            mock_get_cache.return_value = mock_cache

            latency = await metrics_collector.measure_redis_latency()

            assert latency >= 0
            assert metrics_collector.last_redis_check >= 0

    @pytest.mark.asyncio
    async def test_measure_redis_latency_failure(self, metrics_collector):
        """Test measuring Redis latency when cache fails"""
        with patch("app.metrics.get_cache_service", side_effect=Exception("Cache error")):
            latency = await metrics_collector.measure_redis_latency()

            assert latency == -1

    def test_measure_sse_latency(self, metrics_collector):
        """Test measuring SSE latency"""
        metrics_collector.last_sse_latency = 50.0
        latency = metrics_collector.measure_sse_latency()

        assert latency == 50.0

    def test_update_sse_latency(self, metrics_collector):
        """Test updating SSE latency"""
        metrics_collector.update_sse_latency(100.0)
        assert metrics_collector.last_sse_latency == 100.0

    def test_update_system_metrics(self, metrics_collector):
        """Test updating system metrics"""
        metrics_collector.update_system_metrics()
        # Should not raise exception

    def test_record_request(self, metrics_collector):
        """Test recording HTTP request metrics"""
        metrics_collector.record_request("GET", "/api/test", 200, 0.5)
        # Should not raise exception

    def test_record_cache_hit(self, metrics_collector):
        """Test recording cache hit"""
        metrics_collector.record_cache_hit()
        # Should not raise exception

    def test_record_cache_miss(self, metrics_collector):
        """Test recording cache miss"""
        metrics_collector.record_cache_miss()
        # Should not raise exception

    def test_record_cache_set(self, metrics_collector):
        """Test recording cache set operation"""
        metrics_collector.record_cache_set()
        # Should not raise exception

    def test_record_ai_request(self, metrics_collector):
        """Test recording AI request metrics"""
        metrics_collector.record_ai_request("gpt-4", 1.5, tokens=100)
        # Should not raise exception

    def test_record_ai_request_no_tokens(self, metrics_collector):
        """Test recording AI request without tokens"""
        metrics_collector.record_ai_request("gpt-4", 1.5)
        # Should not raise exception

    def test_update_db_connections(self, metrics_collector):
        """Test updating database connection count"""
        metrics_collector.update_db_connections(5)
        # Should not raise exception

    def test_record_db_query(self, metrics_collector):
        """Test recording database query duration"""
        metrics_collector.record_db_query(0.1)
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_get_active_sessions_count(self):
        """Test getting active sessions count"""
        from app.metrics import get_active_sessions_count

        count = await get_active_sessions_count()
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_collect_all_metrics(self):
        """Test collecting all metrics"""
        from app.metrics import collect_all_metrics

        with patch("app.metrics.metrics_collector.measure_redis_latency", new_callable=AsyncMock):
            metrics_output = await collect_all_metrics()

            assert metrics_output is not None
            assert isinstance(metrics_output, bytes)

    def test_get_metrics_middleware(self):
        """Test getting metrics middleware"""
        from unittest.mock import AsyncMock

        from app.metrics import get_metrics_middleware

        middleware = get_metrics_middleware()
        assert middleware is not None
        assert callable(middleware)

        # Test middleware execution
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_call_next = AsyncMock(return_value=mock_response)

        import asyncio

        result = asyncio.run(middleware(mock_request, mock_call_next))
        assert result == mock_response

    def test_global_metrics_collector(self):
        """Test global metrics collector instance"""
        from app.metrics import metrics_collector

        assert metrics_collector is not None
        assert hasattr(metrics_collector, "update_session_count")
