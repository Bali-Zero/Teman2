"""
API Tests for Oracle Universal - Error Scenarios
Tests comprehensive error handling paths

Coverage:
- Error analytics storage
- Error response building
- Exception handling paths
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestOracleUniversalErrorScenarios:
    """Tests for Oracle Universal error scenarios"""

    def test_oracle_query_error_analytics_storage(self, authenticated_client, mock_search_service):
        """Test error analytics storage when exception occurs"""
        mock_search_service.router.get_routing_stats.side_effect = Exception("Test error")

        with patch(
            "app.routers.oracle_universal.db_manager.store_query_analytics", new_callable=AsyncMock
        ) as mock_store:
            mock_store.return_value = None

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query"},
            )

            assert response.status_code in [500, 503]
            if response.status_code == 500:
                data = response.json()
                assert data["success"] is False
                assert "error" in data

    def test_oracle_query_error_response_structure(self, authenticated_client, mock_search_service):
        """Test error response structure"""
        mock_search_service.router.get_routing_stats.side_effect = Exception("Test error")

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "user_email": "test@example.com"},
        )

        assert response.status_code in [500, 503]
        if response.status_code == 500:
            data = response.json()
            assert "success" in data
            assert data["success"] is False
            assert "query" in data
            assert "execution_time_ms" in data

    def test_oracle_query_error_with_user_profile(self, authenticated_client, mock_search_service):
        """Test error handling when user profile exists"""
        mock_search_service.router.get_routing_stats.side_effect = Exception("Test error")

        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = {"id": 1, "email": "test@example.com"}

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "user_email": "test@example.com"},
            )

            assert response.status_code in [500, 503]
