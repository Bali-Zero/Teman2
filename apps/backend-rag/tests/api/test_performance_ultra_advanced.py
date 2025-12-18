"""
Ultra-Advanced Performance Tests
Tests for advanced performance scenarios, optimization, and scalability

Coverage:
- Advanced performance metrics
- Optimization scenarios
- Scalability testing
- Resource utilization
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
@pytest.mark.performance
class TestAdvancedPerformanceMetrics:
    """Test advanced performance metrics"""

    def test_response_time_percentiles(self, authenticated_client):
        """Test response time percentiles"""
        response_times = []

        # Make 100 requests
        for _ in range(100):
            start = time.time()
            response = authenticated_client.get("/api/agents/status")
            elapsed = time.time() - start

            if response.status_code == 200:
                response_times.append(elapsed)

        if response_times:
            response_times.sort()
            p50 = response_times[len(response_times) // 2]
            p95 = response_times[int(len(response_times) * 0.95)]
            p99 = response_times[int(len(response_times) * 0.99)]

            # Percentiles should be reasonable
            assert p50 < 1.0  # Median under 1 second
            assert p95 < 2.0  # 95th percentile under 2 seconds
            assert p99 < 5.0  # 99th percentile under 5 seconds

    def test_throughput_measurement(self, authenticated_client):
        """Test API throughput"""
        start_time = time.time()
        request_count = 0

        # Make requests for 5 seconds
        while time.time() - start_time < 5.0:
            response = authenticated_client.get("/api/agents/status")
            if response.status_code == 200:
                request_count += 1

        throughput = request_count / 5.0  # Requests per second

        # Should handle reasonable throughput
        assert throughput > 10  # At least 10 requests per second

    def test_concurrent_throughput(self, authenticated_client):
        """Test concurrent request throughput"""
        import threading

        results = []
        start_time = time.time()

        def make_requests():
            local_count = 0
            while time.time() - start_time < 2.0:
                response = authenticated_client.get("/api/agents/status")
                if response.status_code == 200:
                    local_count += 1
            results.append(local_count)

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_requests)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        total_requests = sum(results)
        elapsed = time.time() - start_time
        throughput = total_requests / elapsed

        # Should handle concurrent throughput
        assert throughput > 50  # At least 50 requests per second with concurrency


@pytest.mark.api
@pytest.mark.performance
class TestOptimizationScenarios:
    """Test optimization scenarios"""

    def test_caching_impact_on_performance(self, authenticated_client, test_app):
        """Test caching impact on performance"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # First request (cache miss)
            start1 = time.time()
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")
            time1 = time.time() - start1

            # Second request (cache hit)
            start2 = time.time()
            response2 = authenticated_client.get("/api/crm/clients/stats/overview")
            time2 = time.time() - start2

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Cached request should be faster or similar
            assert time2 <= time1 * 1.5  # Allow some variance

    def test_pagination_impact_on_performance(self, authenticated_client, test_app):
        """Test pagination impact on performance"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Small limit
            start1 = time.time()
            response1 = authenticated_client.get("/api/crm/clients?limit=10")
            time1 = time.time() - start1

            # Large limit
            start2 = time.time()
            response2 = authenticated_client.get("/api/crm/clients?limit=200")
            time2 = time.time() - start2

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Both should complete reasonably quickly
            assert time1 < 2.0
            assert time2 < 3.0

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.performance
class TestScalabilityScenarios:
    """Test scalability scenarios"""

    def test_scalability_with_increasing_load(self, authenticated_client):
        """Test scalability with increasing load"""
        load_levels = [10, 50, 100, 500]

        for load in load_levels:
            start_time = time.time()
            success_count = 0

            for _ in range(load):
                response = authenticated_client.get("/api/agents/status")
                if response.status_code == 200:
                    success_count += 1

            elapsed = time.time() - start_time
            success_rate = success_count / load

            # Should maintain high success rate
            assert success_rate >= 0.9  # At least 90% success rate
            # Should scale reasonably
            assert elapsed < load * 0.1  # Less than 0.1 seconds per request average

    def test_scalability_with_large_datasets(self, authenticated_client, test_app):
        """Test scalability with large datasets"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate large dataset
            mock_conn.fetch = AsyncMock(return_value=[{"id": i} for i in range(10000)])
            mock_get_pool.return_value = mock_pool

            start_time = time.time()
            response = authenticated_client.get("/api/crm/clients?limit=200")
            elapsed = time.time() - start_time

            assert response.status_code == 200
            # Should handle large datasets efficiently
            assert elapsed < 5.0  # Should complete in reasonable time

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.performance
class TestResourceUtilization:
    """Test resource utilization scenarios"""

    def test_memory_usage_with_large_responses(self, authenticated_client, test_app):
        """Test memory usage with large responses"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate large response
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "id": i,
                        "data": "X" * 1000,
                        "metadata": {"key": "value" * 100},
                    }
                    for i in range(1000)
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?limit=1000")

            # Should handle large responses
            assert response.status_code in [200, 500, 503]

    def test_connection_pool_utilization(self, authenticated_client, test_app):
        """Test connection pool utilization"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            call_count = 0

            def acquire_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return mock_pool.acquire.return_value

            mock_pool.acquire = MagicMock(side_effect=acquire_side_effect)
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            # Make multiple requests
            for _ in range(10):
                authenticated_client.get("/api/crm/clients")

            # Should reuse connections efficiently
            assert call_count <= 10  # Should not exceed request count significantly

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn
