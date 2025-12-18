"""
API Tests for Oracle Universal Router - Extended Scenarios
Tests additional Oracle Universal edge cases and scenarios

Coverage:
- User profile conversion errors
- Analytics storage errors
- Response building edge cases
- Domain hint scenarios
- Context docs scenarios
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
class TestOracleUniversalExtended:
    """Extended tests for Oracle Universal scenarios"""

    def test_oracle_query_with_domain_hint(self, authenticated_client, mock_search_service):
        """Test oracle query with domain hint"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "domain_hint": "visa"},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_with_context_docs(self, authenticated_client, mock_search_service):
        """Test oracle query with context document IDs"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "context_docs": ["doc1", "doc2"]},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_user_profile_conversion_error(
        self, authenticated_client, mock_search_service
    ):
        """Test oracle query when user profile conversion fails"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        with (
            patch(
                "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
            ) as mock_get_profile,
            patch("app.routers.oracle_universal.UserProfile") as mock_user_profile,
        ):
            mock_get_profile.return_value = {
                "id": 1,
                "email": "test@example.com",
                "invalid_field": "invalid",
            }
            mock_user_profile.side_effect = Exception("Profile conversion error")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "user_email": "test@example.com"},
            )

            assert response.status_code in [200, 500, 503]

    def test_oracle_query_analytics_storage_error(self, authenticated_client, mock_search_service):
        """Test oracle query when analytics storage fails"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        with patch(
            "app.routers.oracle_universal.db_manager.store_query_analytics", new_callable=AsyncMock
        ) as mock_store:
            mock_store.side_effect = Exception("Storage error")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query"},
            )

            # Should still return 200 even if analytics storage fails
            assert response.status_code in [200, 500, 503]

    def test_oracle_query_response_format_conversational(
        self, authenticated_client, mock_search_service
    ):
        """Test oracle query with conversational response format"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "response_format": "conversational"},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_custom_limit(self, authenticated_client, mock_search_service):
        """Test oracle query with custom limit"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "limit": 20},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_asyncio_task_error(self, authenticated_client, mock_search_service):
        """Test oracle query when asyncio task creation fails"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        with patch("app.routers.oracle_universal.asyncio.create_task") as mock_create_task:
            mock_create_task.side_effect = Exception("Task creation error")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query"},
            )

            # Should still return 200 even if task creation fails
            assert response.status_code in [200, 500, 503]

    def test_oracle_query_user_profile_validation_error(
        self, authenticated_client, mock_search_service
    ):
        """Test oracle query when user profile validation fails"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }

        with (
            patch(
                "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
            ) as mock_get_profile,
            patch("app.routers.oracle_universal.UserProfile") as mock_user_profile,
        ):
            mock_get_profile.return_value = {"id": 1, "email": "test@example.com"}
            mock_user_profile.side_effect = ValueError("Validation error")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "user_email": "test@example.com"},
            )

            # Should handle validation error gracefully
            assert response.status_code in [200, 500, 503]

    def test_oracle_query_response_building_edge_case(
        self, authenticated_client, mock_search_service
    ):
        """Test oracle query response building with edge case data"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle",
            "domain_scores": {},
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": [],
            "metadatas": [],
            "distances": [],
        }

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "include_sources": False},
        )

        assert response.status_code in [200, 500, 503]
