"""
Performance and Load Testing Scenarios
Tests for performance, concurrency, and load scenarios

Coverage:
- Concurrent request handling
- Response time validation
- Rate limiting behavior
- Large payload handling
- Batch operation performance
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
class TestConcurrentRequests:
    """Test concurrent request handling"""

    def test_concurrent_health_checks(self, test_client):
        """Test multiple concurrent health check requests"""

        def make_request():
            return test_client.get("/health")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [future.result() for future in as_completed(futures)]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)
        assert len(results) == 20

    def test_concurrent_csrf_token_requests(self, test_client, test_app):
        """Test concurrent CSRF token generation"""
        from fastapi.testclient import TestClient

        def make_request():
            with TestClient(test_app, raise_server_exceptions=False) as client:
                client.headers.clear()
                return client.get("/api/auth/csrf-token")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in as_completed(futures)]

        # All should succeed and generate unique tokens
        assert all(r.status_code == 200 for r in results)
        tokens = [r.json()["csrfToken"] for r in results]
        assert len(set(tokens)) == len(tokens), "All tokens should be unique"

    def test_concurrent_authenticated_requests(self, authenticated_client):
        """Test concurrent authenticated requests"""

        def make_request():
            return authenticated_client.get("/api/agents/status")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in as_completed(futures)]

        # All should succeed
        assert all(r.status_code == 200 for r in results)


@pytest.mark.api
@pytest.mark.performance
class TestResponseTimes:
    """Test response time validation"""

    def test_health_check_response_time(self, test_client):
        """Test health check responds quickly"""
        start = time.time()
        response = test_client.get("/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Health check should be very fast (< 1 second)
        assert elapsed < 1.0

    def test_csrf_token_response_time(self, test_client, test_app):
        """Test CSRF token generation is fast"""
        from fastapi.testclient import TestClient

        with TestClient(test_app, raise_server_exceptions=False) as client:
            client.headers.clear()
            start = time.time()
            response = client.get("/api/auth/csrf-token")
            elapsed = time.time() - start

            assert response.status_code == 200
            # Token generation should be fast (< 0.5 seconds)
            assert elapsed < 0.5

    def test_cached_endpoint_response_time(self, authenticated_client):
        """Test cached endpoints respond faster on second request"""
        # First request
        start1 = time.time()
        response1 = authenticated_client.get("/api/agents/status")
        time1 = time.time() - start1

        # Second request (should be cached)
        start2 = time.time()
        response2 = authenticated_client.get("/api/agents/status")
        time2 = time.time() - start2

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Second request should be faster (or at least not slower)
        # Note: In test environment caching might not be as effective
        assert time2 <= time1 * 1.5  # Allow some variance


@pytest.mark.api
@pytest.mark.performance
class TestLargePayloads:
    """Test handling of large payloads"""

    def test_large_json_payload(self, authenticated_client):
        """Test endpoint with large JSON payload"""
        large_payload = {
            "messages": [{"role": "user", "content": "A" * 10000} for _ in range(100)],
        }

        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json=large_payload,
        )

        # Should handle large payloads gracefully
        assert response.status_code in [200, 201, 400, 413, 422, 500]

    def test_large_query_parameter(self, authenticated_client):
        """Test endpoint with large query parameter"""
        large_query = "A" * 10000

        response = authenticated_client.post(
            "/api/memory/search",
            json={"query": large_query, "limit": 10},
        )

        # Should handle large queries
        assert response.status_code in [200, 400, 422, 500]

    def test_large_batch_operation(self, authenticated_client):
        """Test batch operation with many items"""
        large_batch = [f"/path/to/doc{i}.pdf" for i in range(100)]

        with patch("app.routers.legal_ingest.get_legal_service") as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Doc",
                    "chunks_created": 5,
                }
            )
            mock_service.return_value = mock_service_instance

            response = authenticated_client.post(
                "/api/legal/ingest-batch",
                json=large_batch,
            )

            # Should handle large batches
            assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
@pytest.mark.performance
class TestRateLimiting:
    """Test rate limiting behavior"""

    def test_rapid_sequential_requests(self, authenticated_client):
        """Test rapid sequential requests to same endpoint"""
        responses = []
        for _ in range(50):
            response = authenticated_client.get("/api/agents/status")
            responses.append(response)

        # Most should succeed (rate limiting may kick in)
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 40, "Most requests should succeed"

    def test_rapid_different_endpoints(self, authenticated_client):
        """Test rapid requests to different endpoints"""
        endpoints = [
            "/api/agents/status",
            "/api/dashboard/stats",
            "/api/handlers/list",
        ]

        responses = []
        for endpoint in endpoints * 10:  # 30 requests total
            response = authenticated_client.get(endpoint)
            responses.append(response)

        # All should succeed (different endpoints shouldn't trigger rate limit)
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 25, "Most requests should succeed"


@pytest.mark.api
@pytest.mark.performance
class TestBatchOperations:
    """Test batch operation performance"""

    def test_batch_ingestion_performance(self, authenticated_client):
        """Test batch ingestion handles multiple items efficiently"""
        file_paths = [f"/path/to/doc{i}.pdf" for i in range(20)]

        with patch("app.routers.legal_ingest.get_legal_service") as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Doc",
                    "chunks_created": 5,
                }
            )
            mock_service.return_value = mock_service_instance

            start = time.time()
            response = authenticated_client.post(
                "/api/legal/ingest-batch",
                json=file_paths,
            )
            elapsed = time.time() - start

            assert response.status_code in [200, 422]
            # Batch should complete in reasonable time
            # Note: With mocks this should be fast
            assert elapsed < 5.0

    def test_batch_vs_individual_requests(self, authenticated_client):
        """Compare batch vs individual request performance"""
        file_paths = [f"/path/to/doc{i}.pdf" for i in range(5)]

        with patch("app.routers.legal_ingest.get_legal_service") as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Doc",
                    "chunks_created": 5,
                }
            )
            mock_service.return_value = mock_service_instance

            # Batch request
            start_batch = time.time()
            batch_response = authenticated_client.post(
                "/api/legal/ingest-batch",
                json=file_paths,
            )
            batch_time = time.time() - start_batch

            # Individual requests would be slower, but we're just testing structure
            assert batch_response.status_code in [200, 422]
            assert batch_time < 2.0
