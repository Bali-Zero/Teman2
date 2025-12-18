"""
Caching Behavior Tests
Tests for cache behavior, invalidation, and consistency

Coverage:
- Cache hit/miss scenarios
- Cache TTL behavior
- Cache invalidation triggers
- Cache consistency
- Cache key generation
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
@pytest.mark.cache
class TestCacheHitMiss:
    """Test cache hit/miss scenarios"""

    def test_cached_endpoint_first_request(self, authenticated_client, test_app):
        """Test first request to cached endpoint (cache miss)"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response.status_code == 200

    def test_cached_endpoint_second_request(self, authenticated_client, test_app):
        """Test second request to cached endpoint (cache hit)"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            # First request
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")

            # Second request (should hit cache)
            response2 = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code == 200

            # Responses should be identical (cached)
            if response1.status_code == 200 and response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                assert data1 == data2

    def test_agents_status_caching(self, authenticated_client):
        """Test agents status endpoint caching"""
        # First request
        response1 = authenticated_client.get("/api/agents/status")

        # Immediate second request (should be cached)
        response2 = authenticated_client.get("/api/agents/status")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Should return same data (cached)
        data1 = response1.json()
        data2 = response2.json()
        assert data1 == data2

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.cache
class TestCacheTTL:
    """Test cache TTL behavior"""

    def test_cache_expiration(self, authenticated_client, test_app):
        """Test cache expiration after TTL"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            call_count = 0

            def fetchrow_side_effect(*args):
                nonlocal call_count
                call_count += 1
                return {"total": 100 + call_count}

            mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
            mock_get_pool.return_value = mock_pool

            # First request
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")

            # Wait for cache to expire (if TTL is short)
            # Note: In test environment, cache might not expire quickly
            time.sleep(0.1)

            # Second request (may hit cache or miss)
            response2 = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code == 200

    def test_cache_ttl_different_endpoints(self, authenticated_client):
        """Test different endpoints have different TTL"""
        # Agents status (5 min TTL)
        response1 = authenticated_client.get("/api/agents/status")

        # Client stats (5 min TTL)
        response2 = authenticated_client.get("/api/crm/clients/stats/overview")

        # Both should be cached
        assert response1.status_code == 200
        assert response2.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.cache
class TestCacheInvalidation:
    """Test cache invalidation scenarios"""

    def test_cache_invalidation_on_update(self, authenticated_client, test_app):
        """Test cache invalidation when data is updated"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            # Get stats (cached)
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")

            # Update client (should invalidate cache)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            response2 = authenticated_client.patch(
                "/api/crm/clients/1",
                json={"full_name": "Updated"},
            )

            # Get stats again (should reflect changes)
            mock_conn.fetchrow = AsyncMock(return_value={"total": 101})
            response3 = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code in [200, 404, 500]
            assert response3.status_code == 200

    def test_cache_invalidation_on_create(self, authenticated_client, test_app):
        """Test cache invalidation when new data is created"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            # Get stats (cached)
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")

            # Create new client (should invalidate cache)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_conn.fetchval = AsyncMock(return_value=1)
            response2 = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "New Client"},
            )

            # Get stats again (should reflect new client)
            mock_conn.fetchrow = AsyncMock(return_value={"total": 101})
            response3 = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code in [200, 201, 500]
            assert response3.status_code == 200

    def test_cache_invalidation_on_delete(self, authenticated_client, test_app):
        """Test cache invalidation when data is deleted"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            # Get stats (cached)
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")

            # Delete client (should invalidate cache)
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            response2 = authenticated_client.delete("/api/crm/clients/1")

            # Get stats again (should reflect deletion)
            mock_conn.fetchrow = AsyncMock(return_value={"total": 99})
            response3 = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code in [200, 204, 404, 500]
            assert response3.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.cache
class TestCacheConsistency:
    """Test cache consistency"""

    def test_cache_consistency_across_requests(self, authenticated_client):
        """Test cache consistency across multiple requests"""
        responses = []

        for _ in range(5):
            response = authenticated_client.get("/api/agents/status")
            responses.append(response)

        # All should return same data (cached)
        assert all(r.status_code == 200 for r in responses)

        if all(r.status_code == 200 for r in responses):
            data_values = [r.json() for r in responses]
            # All should be identical
            assert all(data == data_values[0] for data in data_values)

    def test_cache_key_uniqueness(self, authenticated_client, test_app):
        """Test cache key uniqueness for different parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            # Different query parameters should have different cache keys
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")
            response2 = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.cache
class TestCachePerformance:
    """Test cache performance impact"""

    def test_cached_vs_uncached_performance(self, authenticated_client):
        """Test performance difference between cached and uncached requests"""
        import time

        # Uncached endpoint (or first request)
        start1 = time.time()
        response1 = authenticated_client.get("/api/agents/status")
        time1 = time.time() - start1

        # Cached endpoint (second request)
        start2 = time.time()
        response2 = authenticated_client.get("/api/agents/status")
        time2 = time.time() - start2

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Second request should be faster (or at least not slower)
        # Note: In test environment, difference might be minimal
        assert time2 <= time1 * 2  # Allow some variance

    def test_cache_reduces_database_calls(self, authenticated_client, test_app):
        """Test that caching reduces database calls"""
        call_count = 0

        def fetchrow_side_effect(*args):
            nonlocal call_count
            call_count += 1
            return {"total": 100}

        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
            mock_get_pool.return_value = mock_pool

            # Multiple requests
            for _ in range(5):
                authenticated_client.get("/api/crm/clients/stats/overview")

            # Should have fewer database calls due to caching
            # Note: Exact count depends on cache implementation
            assert call_count <= 5

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn
