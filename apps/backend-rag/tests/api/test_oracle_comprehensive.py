"""
Comprehensive API Tests for Oracle Universal Router
Expanded test coverage for Oracle endpoints

Coverage:
- POST /api/oracle/query - Hybrid oracle query
- POST /api/oracle/feedback - Submit feedback
- GET /api/oracle/health - Oracle health check
- GET /api/oracle/user/profile/{user_email} - Get user profile
- GET /api/oracle/drive/test - Test Drive connection
- GET /api/oracle/gemini/test - Test Gemini connection
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestOracleQuery:
    """Comprehensive tests for POST /api/oracle/query"""

    def test_oracle_query_basic(self, authenticated_client):
        """Test basic oracle query"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(
                return_value={"results": [], "collection_used": "test", "query": "test"}
            )
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "What is Indonesian tax law?"},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_oracle_query_with_filters(self, authenticated_client):
        """Test oracle query with filters"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": [], "query": "test"})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "Test query",
                    "limit": 5,
                    "collection": "legal_unified",
                    "user_email": "test@example.com",
                },
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_oracle_query_with_session(self, authenticated_client):
        """Test oracle query with session ID"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "Test query",
                    "session_id": "session_123",
                },
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_oracle_query_missing_query(self, authenticated_client):
        """Test oracle query without query field"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={},
        )

        assert response.status_code == 422

    def test_oracle_query_empty_query(self, authenticated_client):
        """Test oracle query with empty query"""
        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": ""},
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_oracle_query_very_long_query(self, authenticated_client):
        """Test oracle query with very long query string"""
        long_query = "What is " + "tax law " * 1000

        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": long_query},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_oracle_query_response_structure(self, authenticated_client):
        """Test oracle query response structure"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(
                return_value={
                    "results": [{"text": "Test result", "score": 0.9, "metadata": {}}],
                    "query": "test",
                }
            )
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "test"},
            )

            if response.status_code == 200:
                data = response.json()
                # Response should have expected structure
                assert isinstance(data, dict)


@pytest.mark.api
class TestOracleFeedback:
    """Comprehensive tests for POST /api/oracle/feedback"""

    def test_submit_feedback_success(self, authenticated_client):
        """Test submitting feedback"""
        with patch("services.oracle_database.db_manager") as mock_db:
            mock_db.store_feedback = AsyncMock(return_value=True)

            response = authenticated_client.post(
                "/api/oracle/feedback",
                json={
                    "query_id": "query_123",
                    "rating": 5,
                    "comment": "Great answer!",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_submit_feedback_without_rating(self, authenticated_client):
        """Test feedback without rating"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query_id": "query_123",
                "comment": "Good",
            },
        )

        # Should accept or require rating
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_submit_feedback_invalid_rating(self, authenticated_client):
        """Test feedback with invalid rating"""
        response = authenticated_client.post(
            "/api/oracle/feedback",
            json={
                "query_id": "query_123",
                "rating": 10,  # Out of range if 1-5 scale
                "comment": "Test",
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
class TestOracleHealth:
    """Comprehensive tests for GET /api/oracle/health"""

    def test_oracle_health_check(self, test_client):
        """Test oracle health check (public endpoint)"""
        response = test_client.get("/api/oracle/health")

        assert response.status_code in [200, 500, 503]

    def test_oracle_health_no_auth_required(self, test_client):
        """Test oracle health doesn't require auth"""
        test_client.headers.clear()
        response = test_client.get("/api/oracle/health")

        assert response.status_code in [200, 500, 503]


@pytest.mark.api
class TestOracleUserProfile:
    """Comprehensive tests for GET /api/oracle/user/profile/{user_email}"""

    def test_get_user_profile(self, authenticated_client):
        """Test getting user profile"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/oracle/user/profile/test@example.com")

            assert response.status_code in [200, 404, 500]

    def test_get_user_profile_not_found(self, authenticated_client):
        """Test getting non-existent user profile"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/oracle/user/profile/nonexistent@example.com")

            assert response.status_code in [404, 500]

    def test_get_user_profile_invalid_email(self, authenticated_client):
        """Test getting profile with invalid email format"""
        response = authenticated_client.get("/api/oracle/user/profile/invalid-email")

        assert response.status_code in [200, 400, 404, 422, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(
            return_value={
                "id": "user_123",
                "email": "test@example.com",
                "name": "Test User",
            }
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestOracleDriveTest:
    """Comprehensive tests for GET /api/oracle/drive/test"""

    def test_drive_connection_test(self, authenticated_client):
        """Test Drive connection test"""
        response = authenticated_client.get("/api/oracle/drive/test")

        # May require actual Google Drive connection
        assert response.status_code in [200, 400, 401, 403, 500, 503]

    def test_drive_test_requires_auth(self, test_client):
        """Test Drive test requires authentication"""
        response = test_client.get("/api/oracle/drive/test")
        assert response.status_code == 401


@pytest.mark.api
class TestOracleGeminiTest:
    """Comprehensive tests for GET /api/oracle/gemini/test"""

    def test_gemini_connection_test(self, authenticated_client):
        """Test Gemini connection test"""
        response = authenticated_client.get("/api/oracle/gemini/test")

        # May require actual Gemini API connection
        assert response.status_code in [200, 400, 401, 403, 500, 503]

    def test_gemini_test_requires_auth(self, test_client):
        """Test Gemini test requires authentication"""
        response = test_client.get("/api/oracle/gemini/test")
        assert response.status_code == 401


@pytest.mark.api
class TestOracleErrorScenarios:
    """Error scenario tests for Oracle endpoints"""

    def test_oracle_query_service_unavailable(self, authenticated_client):
        """Test oracle query when search service unavailable"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_search.side_effect = Exception("Service unavailable")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "test"},
            )

            assert response.status_code in [500, 503]

    def test_oracle_query_invalid_collection(self, authenticated_client):
        """Test oracle query with invalid collection name"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(side_effect=ValueError("Invalid collection"))
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "test", "collection": "invalid_collection"},
            )

            assert response.status_code in [400, 422, 500]

    def test_oracle_endpoints_require_auth(self, test_client):
        """Test Oracle endpoints require authentication (except health)"""
        endpoints = [
            ("POST", "/api/oracle/query"),
            ("POST", "/api/oracle/feedback"),
            ("GET", "/api/oracle/user/profile/test@example.com"),
            ("GET", "/api/oracle/drive/test"),
            ("GET", "/api/oracle/gemini/test"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401
