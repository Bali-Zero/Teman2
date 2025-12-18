"""
Integration Tests for Metrics Service
Tests Prometheus metrics collection and reporting
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="function")
def metrics_collector():
    """Create MetricsCollector instance"""
    from app.metrics import MetricsCollector

    return MetricsCollector()


@pytest.mark.integration
class TestMetricsIntegration:
    """Comprehensive integration tests for Metrics"""

    def test_update_session_count(self, metrics_collector):
        """Test updating active sessions count"""
        metrics_collector.update_session_count(10)
        assert metrics_collector.session_count == 10

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
        metrics_collector.record_ai_request("gpt-4", latency=1.5, tokens=1000)
        # Should not raise exception

    def test_update_db_connections(self, metrics_collector):
        """Test updating database connection count"""
        metrics_collector.update_db_connections(5)
        # Should not raise exception

    def test_record_db_query(self, metrics_collector):
        """Test recording database query duration"""
        metrics_collector.record_db_query(0.1)
        # Should not raise exception

    def test_update_system_metrics(self, metrics_collector):
        """Test updating system-level metrics"""
        metrics_collector.update_system_metrics()
        # Should not raise exception

    def test_update_sse_latency(self, metrics_collector):
        """Test updating SSE latency"""
        metrics_collector.update_sse_latency(50.0)
        assert metrics_collector.last_sse_latency == 50.0

    @pytest.mark.asyncio
    async def test_measure_redis_latency_success(self, metrics_collector):
        """Test measuring Redis latency when Redis is available"""
        with patch("app.metrics.get_cache_service") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.set = AsyncMock()
            mock_cache.get = AsyncMock(return_value="pong")
            mock_get_cache.return_value = mock_cache

            latency = await metrics_collector.measure_redis_latency()
            assert latency >= 0

    @pytest.mark.asyncio
    async def test_measure_redis_latency_failure(self, metrics_collector):
        """Test measuring Redis latency when Redis fails"""
        with patch("app.metrics.get_cache_service", side_effect=Exception("Redis unavailable")):
            latency = await metrics_collector.measure_redis_latency()
            assert latency == -1

    @pytest.mark.asyncio
    async def test_get_active_sessions_count(self):
        """Test getting active sessions count"""
        from app.metrics import get_active_sessions_count

        count = await get_active_sessions_count()
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_collect_all_metrics(self):
        """Test collecting all metrics for Prometheus"""
        from app.metrics import collect_all_metrics

        metrics_output = await collect_all_metrics()
        assert metrics_output is not None
        assert isinstance(metrics_output, bytes)
        assert len(metrics_output) > 0

    def test_metrics_middleware(self):
        """Test metrics middleware creation"""
        from app.metrics import get_metrics_middleware

        middleware = get_metrics_middleware()
        assert callable(middleware)

    @pytest.mark.asyncio
    async def test_metrics_middleware_execution(self):
        """Test metrics middleware execution"""

        from fastapi import Request

        from app.metrics import get_metrics_middleware

        middleware = get_metrics_middleware()

        # Mock request and response
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        # Execute middleware
        response = await middleware(mock_request, mock_call_next)
        assert response == mock_response

    def test_multiple_metrics_operations(self, metrics_collector):
        """Test multiple metrics operations in sequence"""
        # Update various metrics
        metrics_collector.update_session_count(5)
        metrics_collector.record_request("POST", "/api/chat", 200, 1.2)
        metrics_collector.record_cache_hit()
        metrics_collector.record_ai_request("gpt-4", latency=2.0, tokens=500)
        metrics_collector.update_db_connections(3)
        metrics_collector.record_db_query(0.05)

        # Should not raise exceptions
        assert metrics_collector.session_count == 5

    def test_system_metrics_update(self, metrics_collector):
        """Test system metrics update includes CPU and memory"""
        # Update system metrics multiple times
        for _ in range(3):
            metrics_collector.update_system_metrics()
            time.sleep(0.1)

        # Should not raise exceptions
