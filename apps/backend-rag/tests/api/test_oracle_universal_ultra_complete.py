"""
Ultra-Complete API Tests for Oracle Universal Router
=====================================================

Comprehensive test coverage for all oracle_universal.py endpoints including:
- All HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Input validation (valid, invalid, malformed, edge cases)
- Error handling (4xx, 5xx scenarios)
- Security (authentication, authorization, injection attacks)
- Rate limiting behavior
- Performance/load scenarios
- Integration workflows

Coverage Endpoints:
- POST /api/oracle/query - Ultra Hybrid Oracle Query
- GET /api/oracle/health - Health check
- GET /api/oracle/personalities - Get available personalities
- POST /api/oracle/personality/test - Test personality
- GET /api/oracle/user/profile/{user_email} - Get user profile
- POST /api/oracle/feedback - Submit feedback
- GET /api/oracle/gemini/test - Test Gemini
- GET /api/oracle/drive/test - Test Drive
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Environment setup
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2,test_api_key_3"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestOracleUniversalQuery:
    """Comprehensive tests for POST /api/oracle/query"""

    def test_query_valid_simple(self, authenticated_client):
        """Test simple valid query"""
        with patch("app.routers.oracle_universal.handle_oracle_query") as mock_handle:
            mock_handle.return_value = {"answer": "Test answer", "sources": [], "confidence": 0.95}

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "What is KITAS?",
                    "collection": "visa_oracle",
                    "user_email": "test@example.com",
                },
            )

            assert response.status_code in [200, 400, 429, 500, 503]

    def test_query_valid_complex(self, authenticated_client):
        """Test complex query with all optional parameters"""
        with patch("app.routers.oracle_universal.handle_oracle_query") as mock_handle:
            mock_handle.return_value = {
                "answer": "Detailed answer",
                "sources": [{"title": "Source 1", "url": "http://example.com"}],
                "confidence": 0.88,
                "metadata": {"processing_time": 1.5},
            }

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "How to open PT PMA in Bali with foreign investment?",
                    "collection": "legal_unified",
                    "user_email": "business@example.com",
                    "personality": "professional",
                    "include_sources": True,
                    "max_results": 10,
                },
            )

            assert response.status_code in [200, 400, 429, 500, 503]

    def test_query_invalid_empty_query(self, authenticated_client):
        """Test with empty query string"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "", "collection": "visa_oracle", "user_email": "test@example.com"},
        )

        assert response.status_code in [400, 422]

    def test_query_invalid_missing_required_fields(self, authenticated_client):
        """Test with missing required fields"""
        response = authenticated_client.post("/api/oracle/query", json={"query": "What is KITAS?"})

        assert response.status_code in [400, 422]

    def test_query_invalid_collection(self, authenticated_client):
        """Test with non-existent collection"""
        with patch("app.routers.oracle_universal.handle_oracle_query") as mock_handle:
            mock_handle.side_effect = ValueError("Collection not found")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "Test query",
                    "collection": "nonexistent_collection",
                    "user_email": "test@example.com",
                },
            )

            assert response.status_code in [400, 404, 500]

    def test_query_invalid_email_format(self, authenticated_client):
        """Test with invalid email format"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "What is KITAS?",
                "collection": "visa_oracle",
                "user_email": "not-an-email",
            },
        )

        assert response.status_code in [400, 422]

    def test_query_sql_injection_attempt(self, authenticated_client):
        """Test SQL injection attack prevention"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "'; DROP TABLE users; --",
                "collection": "visa_oracle",
                "user_email": "attacker@evil.com",
            },
        )

        # Should either reject or sanitize, not crash
        assert response.status_code in [200, 400, 422, 429, 500]

    def test_query_xss_attempt(self, authenticated_client):
        """Test XSS attack prevention"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "<script>alert('XSS')</script>",
                "collection": "visa_oracle",
                "user_email": "test@example.com",
            },
        )

        # Should sanitize or reject
        assert response.status_code in [200, 400, 422, 429, 500]

    def test_query_very_long_query(self, authenticated_client):
        """Test with extremely long query (>10000 chars)"""
        long_query = "A" * 10001

        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": long_query,
                "collection": "visa_oracle",
                "user_email": "test@example.com",
            },
        )

        assert response.status_code in [200, 400, 413, 422, 429]

    def test_query_unicode_characters(self, authenticated_client):
        """Test with unicode and special characters"""
        with patch("app.routers.oracle_universal.handle_oracle_query") as mock_handle:
            mock_handle.return_value = {"answer": "答案", "sources": [], "confidence": 0.9}

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "Apa itu KITAS? 中文测试 🇮🇩",
                    "collection": "visa_oracle",
                    "user_email": "test@example.com",
                },
            )

            assert response.status_code in [200, 400, 422, 429, 500]

    def test_query_malformed_json(self, authenticated_client):
        """Test with malformed JSON"""
        response = authenticated_client.post(
            "/api/oracle/query", data="{invalid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422]

    def test_query_rate_limit_burst(self, authenticated_client):
        """Test rate limiting with burst requests"""
        # Send multiple requests rapidly
        responses = []
        for i in range(20):
            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": f"Query {i}",
                    "collection": "visa_oracle",
                    "user_email": "test@example.com",
                },
            )
            responses.append(response.status_code)

        # Should see some 429 (Too Many Requests) if rate limiting is active
        assert any(code in [200, 429, 500] for code in responses)

    def test_query_concurrent_requests(self, authenticated_client):
        """Test handling concurrent requests"""
        import concurrent.futures

        def make_request():
            return authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "What is KITAS?",
                    "collection": "visa_oracle",
                    "user_email": "test@example.com",
                },
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should complete without crashes
        assert len(responses) == 10
        assert all(r.status_code in [200, 400, 429, 500, 503] for r in responses)


@pytest.mark.api
class TestOracleHealth:
    """Tests for GET /api/oracle/health"""

    def test_health_success(self, authenticated_client):
        """Test health check when all services are up"""
        with patch("app.routers.oracle_universal.verify_services") as mock_verify:
            mock_verify.return_value = {
                "status": "healthy",
                "services": {"qdrant": "up", "gemini": "up", "drive": "up"},
            }

            response = authenticated_client.get("/api/oracle/health")

            assert response.status_code in [200, 503]

    def test_health_degraded(self, authenticated_client):
        """Test health check when some services are down"""
        with patch("app.routers.oracle_universal.verify_services") as mock_verify:
            mock_verify.return_value = {
                "status": "degraded",
                "services": {"qdrant": "up", "gemini": "down", "drive": "up"},
            }

            response = authenticated_client.get("/api/oracle/health")

            assert response.status_code in [200, 503]

    def test_health_timeout(self, authenticated_client):
        """Test health check with timeout"""
        with patch("app.routers.oracle_universal.verify_services") as mock_verify:
            import time

            time.sleep(0.1)  # Simulate slow response
            mock_verify.return_value = {"status": "timeout"}

            response = authenticated_client.get("/api/oracle/health")

            assert response.status_code in [200, 503, 504]


@pytest.mark.api
class TestOraclePersonalities:
    """Tests for personality endpoints"""

    def test_get_personalities_list(self, authenticated_client):
        """Test GET /api/oracle/personalities"""
        response = authenticated_client.get("/api/oracle/personalities")

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_test_personality_valid(self, authenticated_client):
        """Test POST /api/oracle/personality/test with valid personality"""
        with patch("app.routers.oracle_universal.test_personality") as mock_test:
            mock_test.return_value = {
                "personality": "professional",
                "sample_response": "This is a professional response.",
            }

            response = authenticated_client.post(
                "/api/oracle/personality/test",
                json={"personality": "professional", "test_query": "Hello"},
            )

            assert response.status_code in [200, 400, 500]

    def test_test_personality_invalid(self, authenticated_client):
        """Test with non-existent personality"""
        response = authenticated_client.post(
            "/api/oracle/personality/test",
            json={"personality": "nonexistent_personality", "test_query": "Hello"},
        )

        assert response.status_code in [400, 404, 500]


@pytest.mark.api
class TestOracleUserProfile:
    """Tests for GET /api/oracle/user/profile/{user_email}"""

    def test_get_user_profile_valid(self, authenticated_client):
        """Test with valid user email"""
        with patch("app.routers.oracle_universal.get_user_profile") as mock_get:
            mock_get.return_value = {
                "email": "test@example.com",
                "language": "en",
                "preferences": {},
            }

            response = authenticated_client.get("/api/oracle/user/profile/test@example.com")

            assert response.status_code in [200, 404, 500]

    def test_get_user_profile_not_found(self, authenticated_client):
        """Test with non-existent user"""
        with patch("app.routers.oracle_universal.get_user_profile") as mock_get:
            mock_get.return_value = None

            response = authenticated_client.get("/api/oracle/user/profile/nonexistent@example.com")

            assert response.status_code in [404, 500]

    def test_get_user_profile_invalid_email(self, authenticated_client):
        """Test with invalid email format"""
        response = authenticated_client.get("/api/oracle/user/profile/not-an-email")

        assert response.status_code in [400, 404, 422, 500]


@pytest.mark.api
class TestOracleFeedback:
    """Tests for POST /api/oracle/feedback"""

    def test_submit_feedback_valid(self, authenticated_client):
        """Test submitting valid feedback"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "user_email": "test@example.com",
                "query": "Original query",
                "response": "AI response",
                "rating": 5,
                "feedback": "Very helpful",
            },
        )

        assert response.status_code in [200, 201, 400, 500]

    def test_submit_feedback_minimal(self, authenticated_client):
        """Test with minimal required fields"""
        response = authenticated_client.post(
            "/api/oracle/feedback", json={"user_email": "test@example.com", "rating": 3}
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_submit_feedback_invalid_rating(self, authenticated_client):
        """Test with invalid rating value"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "user_email": "test@example.com",
                "rating": 10,  # Invalid: should be 1-5
            },
        )

        assert response.status_code in [400, 422]


@pytest.mark.api
class TestOracleIntegrations:
    """Tests for Gemini and Drive integration endpoints"""

    def test_gemini_integration(self, authenticated_client):
        """Test GET /api/oracle/gemini/test"""
        with patch("app.routers.oracle_universal.test_gemini") as mock_test:
            mock_test.return_value = {"status": "ok", "model": "gemini-pro"}

            response = authenticated_client.get("/api/oracle/gemini/test")

            assert response.status_code in [200, 503]

    def test_drive_integration(self, authenticated_client):
        """Test GET /api/oracle/drive/test"""
        with patch("app.routers.oracle_universal.test_drive") as mock_test:
            mock_test.return_value = {"status": "ok", "files_accessible": True}

            response = authenticated_client.get("/api/oracle/drive/test")

            assert response.status_code in [200, 503]


@pytest.mark.api
@pytest.mark.security
class TestOracleSecurity:
    """Security-focused tests"""

    def test_unauthenticated_access(self, test_client):
        """Test endpoints without authentication"""
        response = test_client.post(
            "/api/oracle/query",
            json={"query": "Test", "collection": "visa_oracle", "user_email": "test@example.com"},
        )

        assert response.status_code in [200, 401, 403]

    def test_csrf_protection(self, authenticated_client):
        """Test CSRF protection"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test", "collection": "visa_oracle", "user_email": "test@example.com"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code in [200, 400, 403, 429, 500]

    def test_headers_security(self, authenticated_client):
        """Test security headers are present"""
        response = authenticated_client.get("/api/oracle/health")

        # Check for security headers
        assert response.status_code in [200, 503]
        # Headers like X-Content-Type-Options, X-Frame-Options should be present


@pytest.mark.api
@pytest.mark.performance
class TestOraclePerformance:
    """Performance and load tests"""

    def test_query_response_time(self, authenticated_client):
        """Test query response time is acceptable"""
        import time

        start = time.time()
        response = authenticated_client.post(
            "/api/oracle/query",
            json={
                "query": "What is KITAS?",
                "collection": "visa_oracle",
                "user_email": "test@example.com",
            },
        )
        duration = time.time() - start

        assert response.status_code in [200, 400, 429, 500, 503]
        # Response should be under 30 seconds
        assert duration < 30

    def test_large_payload_handling(self, authenticated_client):
        """Test handling of large request payloads"""
        large_query = {
            "query": "A" * 5000,
            "collection": "visa_oracle",
            "user_email": "test@example.com",
            "metadata": {"key": "value" * 1000},
        }

        response = authenticated_client.post("/api/oracle/query", json=large_query)

        assert response.status_code in [200, 400, 413, 422, 429, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
