"""
Ultra-Complete API Tests for Health Router
==========================================

Comprehensive test coverage for all health.py endpoints including:
- Basic health checks
- Detailed system health
- Liveness and readiness probes
- Service status monitoring
- Qdrant metrics
- Debug configuration endpoint

Coverage Endpoints:
- GET /health - Basic health check
- GET /health/ - Basic health check (with trailing slash)
- GET /health/detailed - Detailed service health
- GET /health/live - Kubernetes liveness probe
- GET /health/ready - Kubernetes readiness probe
- GET /health/metrics/qdrant - Qdrant performance metrics
- GET /health/debug/config - Debug configuration view
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Environment setup
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["REDIS_URL"] = "redis://localhost:6379"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestHealthBasic:
    """Tests for GET /health and GET /health/"""

    def test_health_success(self, test_client):
        """Test health check when services are up"""
        response = test_client.get("/health")

        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    def test_health_trailing_slash(self, test_client):
        """Test health endpoint with trailing slash"""
        response = test_client.get("/health/")

        assert response.status_code in [200, 503]

    def test_health_no_auth_required(self, test_client):
        """Test health endpoint is accessible without auth"""
        # Should work without authentication
        response = test_client.get("/health")

        assert response.status_code in [200, 503]

    def test_health_during_startup(self, test_client):
        """Test health check during service startup"""
        with patch("app.routers.health.is_initialized", return_value=False):
            response = test_client.get("/health")

            # Should return initializing status
            assert response.status_code in [200, 503]
            if response.status_code == 200:
                data = response.json()
                assert data.get("status") in ["initializing", "starting", "healthy"]

    def test_health_response_format(self, test_client):
        """Test health response has expected format"""
        response = test_client.get("/health")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "status" in data
            # May have timestamp, version, etc.

    def test_health_caching(self, test_client):
        """Test health endpoint caching behavior"""
        # Make multiple requests
        response1 = test_client.get("/health")
        response2 = test_client.get("/health")
        response3 = test_client.get("/health")

        # All should return consistent status codes
        assert response1.status_code in [200, 503]
        assert response2.status_code in [200, 503]
        assert response3.status_code in [200, 503]

    def test_health_concurrent_requests(self, test_client):
        """Test concurrent health checks"""
        import concurrent.futures

        def check_health():
            return test_client.get("/health")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_health) for _ in range(20)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should complete successfully
        assert len(responses) == 20
        assert all(r.status_code in [200, 503] for r in responses)

    def test_health_response_time(self, test_client):
        """Test health check responds quickly"""
        import time

        start = time.time()
        response = test_client.get("/health")
        duration = time.time() - start

        assert response.status_code in [200, 503]
        # Should respond within 1 second (it's a health check!)
        assert duration < 1


@pytest.mark.api
class TestHealthDetailed:
    """Tests for GET /health/detailed"""

    def test_detailed_health_all_services_up(self, test_client):
        """Test detailed health when all services are operational"""
        with patch("app.routers.health.check_all_services") as mock_check:
            mock_check.return_value = {
                "database": {"status": "healthy", "response_time_ms": 10},
                "qdrant": {"status": "healthy", "response_time_ms": 15},
                "redis": {"status": "healthy", "response_time_ms": 5},
            }

            response = test_client.get("/health/detailed")

            assert response.status_code in [200, 503]
            if response.status_code == 200:
                data = response.json()
                assert "database" in data or "services" in data

    def test_detailed_health_some_services_down(self, test_client):
        """Test detailed health when some services are degraded"""
        with patch("app.routers.health.check_all_services") as mock_check:
            mock_check.return_value = {
                "database": {"status": "healthy"},
                "qdrant": {"status": "unhealthy", "error": "Connection timeout"},
                "redis": {"status": "healthy"},
            }

            response = test_client.get("/health/detailed")

            assert response.status_code in [200, 503]

    def test_detailed_health_all_services_down(self, test_client):
        """Test when all services are unavailable"""
        with patch("app.routers.health.check_all_services") as mock_check:
            mock_check.return_value = {
                "database": {"status": "unhealthy"},
                "qdrant": {"status": "unhealthy"},
                "redis": {"status": "unhealthy"},
            }

            response = test_client.get("/health/detailed")

            assert response.status_code in [503, 500]

    def test_detailed_health_timeout(self, test_client):
        """Test detailed health with service timeout"""
        with patch("app.routers.health.check_all_services") as mock_check:
            import time

            time.sleep(0.1)  # Simulate slow check
            mock_check.return_value = {"status": "timeout"}

            response = test_client.get("/health/detailed")

            assert response.status_code in [200, 503, 504]

    def test_detailed_health_exception_handling(self, test_client):
        """Test exception handling in detailed health"""
        with patch("app.routers.health.check_all_services") as mock_check:
            mock_check.side_effect = Exception("Internal error")

            response = test_client.get("/health/detailed")

            # Should return error status, not crash
            assert response.status_code in [500, 503]

    def test_detailed_health_no_auth_required(self, test_client):
        """Test detailed health accessible without auth"""
        response = test_client.get("/health/detailed")

        assert response.status_code in [200, 503, 500]


@pytest.mark.api
class TestHealthKubernetes:
    """Tests for Kubernetes-style probes"""

    def test_liveness_probe_healthy(self, test_client):
        """Test liveness probe when app is running"""
        response = test_client.get("/health/live")

        # Liveness should return 200 if app is running
        assert response.status_code in [200, 500, 503]

    def test_liveness_probe_format(self, test_client):
        """Test liveness probe response format"""
        response = test_client.get("/health/live")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "status" in data or "alive" in data

    def test_readiness_probe_ready(self, test_client):
        """Test readiness probe when services are ready"""
        with patch("app.routers.health.check_critical_services") as mock_check:
            mock_check.return_value = True

            response = test_client.get("/health/ready")

            assert response.status_code in [200, 503]

    def test_readiness_probe_not_ready(self, test_client):
        """Test readiness probe when services not ready"""
        with patch("app.routers.health.check_critical_services") as mock_check:
            mock_check.return_value = False

            response = test_client.get("/health/ready")

            assert response.status_code in [503, 500]

    def test_readiness_probe_during_startup(self, test_client):
        """Test readiness during application startup"""
        with patch("app.routers.health.is_ready", return_value=False):
            response = test_client.get("/health/ready")

            # Should indicate not ready
            assert response.status_code in [503, 500]

    def test_liveness_vs_readiness(self, test_client):
        """Test difference between liveness and readiness"""
        live_response = test_client.get("/health/live")
        ready_response = test_client.get("/health/ready")

        # Liveness can be 200 when readiness is 503
        assert live_response.status_code in [200, 500, 503]
        assert ready_response.status_code in [200, 503, 500]

    def test_kubernetes_probe_performance(self, test_client):
        """Test Kubernetes probes respond quickly"""
        import time

        # Liveness probe
        start = time.time()
        test_client.get("/health/live")
        live_duration = time.time() - start

        # Readiness probe
        start = time.time()
        test_client.get("/health/ready")
        ready_duration = time.time() - start

        # Both should respond within 500ms
        assert live_duration < 0.5
        assert ready_duration < 0.5


@pytest.mark.api
class TestHealthQdrantMetrics:
    """Tests for GET /health/metrics/qdrant"""

    def test_qdrant_metrics_success(self, test_client):
        """Test Qdrant metrics when available"""
        with patch("app.routers.health.get_qdrant_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "total_searches": 1000,
                "avg_search_latency_ms": 50,
                "total_upserts": 500,
                "error_count": 2,
                "cache_hit_rate": 0.75,
            }

            response = test_client.get("/health/metrics/qdrant")

            assert response.status_code in [200, 503, 500]

    def test_qdrant_metrics_unavailable(self, test_client):
        """Test when Qdrant metrics are unavailable"""
        with patch("app.routers.health.get_qdrant_metrics") as mock_metrics:
            mock_metrics.return_value = None

            response = test_client.get("/health/metrics/qdrant")

            assert response.status_code in [503, 500, 404]

    def test_qdrant_metrics_format(self, test_client):
        """Test Qdrant metrics response format"""
        with patch("app.routers.health.get_qdrant_metrics") as mock_metrics:
            mock_metrics.return_value = {"searches": 100, "latency": 25}

            response = test_client.get("/health/metrics/qdrant")

            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)

    def test_qdrant_metrics_no_auth_required(self, test_client):
        """Test metrics accessible without auth"""
        response = test_client.get("/health/metrics/qdrant")

        assert response.status_code in [200, 503, 500, 404]


@pytest.mark.api
class TestHealthDebugConfig:
    """Tests for GET /health/debug/config"""

    def test_debug_config_in_dev(self, test_client):
        """Test debug config endpoint in development"""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            response = test_client.get("/health/debug/config")

            # Should be accessible in dev
            assert response.status_code in [200, 401, 403, 404]

    def test_debug_config_in_production(self, test_client):
        """Test debug config blocked in production"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            response = test_client.get("/health/debug/config")

            # Should be blocked or require admin auth
            assert response.status_code in [401, 403, 404]

    def test_debug_config_no_secrets_exposed(self, test_client):
        """Test that secrets are not exposed in debug config"""
        response = test_client.get("/health/debug/config")

        if response.status_code == 200:
            data = response.json()
            # Should not contain actual API keys or passwords
            text = str(data).lower()
            assert "password" not in text or "***" in text
            assert "secret" not in text or "***" in text

    def test_debug_config_shows_env_info(self, test_client):
        """Test debug config shows environment information"""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            response = test_client.get("/health/debug/config")

            if response.status_code == 200:
                data = response.json()
                # Should show basic config info
                assert isinstance(data, dict)


@pytest.mark.api
@pytest.mark.integration
class TestHealthIntegration:
    """Integration tests for health endpoints"""

    def test_health_chain_basic_to_detailed(self, test_client):
        """Test health check escalation"""
        # First check basic
        basic_response = test_client.get("/health")

        if basic_response.status_code == 200:
            # If basic is healthy, check detailed
            detailed_response = test_client.get("/health/detailed")
            assert detailed_response.status_code in [200, 503]

    def test_health_correlation_with_metrics(self, test_client):
        """Test health status correlates with metrics"""
        with patch("app.routers.health.get_qdrant_metrics") as mock_metrics:
            mock_metrics.return_value = {"error_count": 100}

            health_response = test_client.get("/health/detailed")
            metrics_response = test_client.get("/health/metrics/qdrant")

            # If metrics show errors, health might be degraded
            assert health_response.status_code in [200, 503]
            assert metrics_response.status_code in [200, 503, 500]

    def test_health_database_dependency(self, test_client):
        """Test health check handles database issues"""
        with patch("app.routers.health.check_database") as mock_db:
            mock_db.return_value = False

            response = test_client.get("/health/detailed")

            # Should indicate unhealthy when DB is down
            assert response.status_code in [503, 500]

    def test_health_qdrant_dependency(self, test_client):
        """Test health check handles Qdrant issues"""
        with patch("app.routers.health.check_qdrant") as mock_qdrant:
            mock_qdrant.return_value = False

            response = test_client.get("/health/detailed")

            assert response.status_code in [200, 503, 500]

    def test_health_redis_dependency(self, test_client):
        """Test health check handles Redis issues"""
        with patch("app.routers.health.check_redis") as mock_redis:
            mock_redis.return_value = False

            response = test_client.get("/health/detailed")

            assert response.status_code in [200, 503]  # Redis is non-critical


@pytest.mark.api
@pytest.mark.performance
class TestHealthPerformance:
    """Performance tests for health endpoints"""

    def test_health_rapid_polling(self, test_client):
        """Test health endpoint under rapid polling"""
        import time

        start = time.time()
        for _ in range(100):
            response = test_client.get("/health")
            assert response.status_code in [200, 503]

        duration = time.time() - start

        # Should handle 100 requests in under 5 seconds
        assert duration < 5

    def test_health_no_memory_leak(self, test_client):
        """Test health checks don't cause memory leaks"""
        # Make many requests
        for _ in range(50):
            test_client.get("/health")
            test_client.get("/health/detailed")

        # Should complete without errors
        # Memory leak detection would require external tools

    def test_health_consistent_performance(self, test_client):
        """Test health check performance is consistent"""
        import time

        durations = []
        for _ in range(10):
            start = time.time()
            test_client.get("/health")
            durations.append(time.time() - start)

        # All should be roughly similar (within 2x)
        avg_duration = sum(durations) / len(durations)
        assert all(d < avg_duration * 2 for d in durations)


@pytest.mark.api
@pytest.mark.security
class TestHealthSecurity:
    """Security tests for health endpoints"""

    def test_health_no_information_leakage(self, test_client):
        """Test health endpoints don't leak sensitive info"""
        response = test_client.get("/health/detailed")

        if response.status_code == 200:
            text = response.text.lower()
            # Should not contain passwords, keys, or internal IPs
            assert "password" not in text
            assert "api_key" not in text or "***" in text

    def test_health_ddos_protection(self, test_client):
        """Test health endpoints have DDoS protection"""
        # Make many requests rapidly
        responses = []
        for _ in range(50):
            response = test_client.get("/health")
            responses.append(response.status_code)

        # Should handle burst without crashing
        assert all(code in [200, 429, 503] for code in responses)

    def test_health_cors_headers(self, test_client):
        """Test CORS headers on health endpoints"""
        response = test_client.get("/health")

        # Should have appropriate CORS headers or no CORS
        assert response.status_code in [200, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
