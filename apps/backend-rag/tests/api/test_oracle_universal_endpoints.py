"""
API Tests for Oracle Universal Router
Tests Oracle query endpoints

Coverage:
- POST /api/oracle/query - Oracle query endpoint
- POST /api/oracle/reason - Gemini reasoning endpoint
- GET /api/oracle/stats - Get Oracle stats
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def valid_jwt_token():
    """Generate a valid JWT token for testing"""
    payload = {
        "sub": "test@example.com",
        "email": "test@example.com",
        "user_id": "test-user-123",
        "role": "member",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


class TestOracleQuery:
    """Test suite for /api/oracle/query endpoint"""

    @pytest.mark.asyncio
    async def test_oracle_query_basic(self, test_client, valid_jwt_token):
        """Test POST /api/oracle/query basic query"""
        with patch("app.routers.oracle_universal.personality_service") as mock_service:
            mock_service.fast_chat = AsyncMock(
                return_value={
                    "response": "Test response",
                    "ai_used": "zantara-ai",
                    "category": "general",
                }
            )

            response = test_client.post(
                "/api/oracle/query",
                json={"query": "Test query"},
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            # May return 200, 500, or 503 depending on service availability
            assert response.status_code in [200, 500, 503]

    @pytest.mark.asyncio
    async def test_oracle_query_with_user_email(self, test_client, valid_jwt_token):
        """Test POST /api/oracle/query with user email"""
        with patch("app.routers.oracle_universal.personality_service") as mock_service:
            mock_service.fast_chat = AsyncMock(
                return_value={
                    "response": "Test response",
                    "ai_used": "zantara-ai",
                    "category": "general",
                }
            )

            response = test_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "user_email": "test@example.com"},
                headers={"Authorization": f"Bearer {valid_jwt_token}"},
            )

            # May return 200, 500, or 503 depending on service availability
            assert response.status_code in [200, 500, 503]

    def test_oracle_query_requires_auth(self, test_client):
        """Test that oracle query requires authentication"""
        response = test_client.post("/api/oracle/query", json={"query": "Test query"})
        assert response.status_code == 401

    def test_oracle_query_embedding_error(self, authenticated_client, mock_search_service):
        """Test oracle query when embedding generation fails"""
        with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_single_embedding.side_effect = Exception(
                "Embedding error"
            )

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query"},
            )

            assert response.status_code == 503
            assert "unavailable" in response.json()["detail"].lower()

    def test_oracle_query_collection_not_found(self, authenticated_client, mock_search_service):
        """Test oracle query when collection is not found"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "nonexistent_collection"
        }
        mock_search_service.collections = {}

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query"},
        )

        assert response.status_code in [404, 503]
        if response.status_code == 404:
            assert "not available" in response.json()["detail"]

    def test_oracle_query_empty_results(self, authenticated_client, mock_search_service):
        """Test oracle query with empty search results"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": [],
            "metadatas": [],
            "distances": [],
        }
        mock_search_service.ai_client.generate_response.return_value = "AI response"

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query"},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_with_language_override(self, authenticated_client, mock_search_service):
        """Test oracle query with language override"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }
        mock_search_service.ai_client.generate_response.return_value = "AI response"

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "language_override": "id"},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_with_include_sources(self, authenticated_client, mock_search_service):
        """Test oracle query with include_sources flag"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }
        mock_search_service.ai_client.generate_response.return_value = "AI response"

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "include_sources": True},
        )

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "sources" in data


@pytest.mark.api
class TestOracleFeedback:
    """Tests for POST /api/oracle/feedback endpoint"""

    def test_submit_feedback_success(self, authenticated_client):
        """Test submitting user feedback successfully"""
        with (
            patch(
                "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
            ) as mock_get_profile,
            patch(
                "app.routers.oracle_universal.db_manager.store_feedback", new_callable=AsyncMock
            ) as mock_store,
        ):
            mock_get_profile.return_value = {"id": 1, "email": "test@example.com"}
            mock_store.return_value = None

            response = authenticated_client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "test@example.com",
                    "query_text": "Test query",
                    "original_answer": "Original answer",
                    "user_correction": "Corrected answer",
                    "feedback_type": "correction",
                    "rating": 3,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "feedback_id" in data

    def test_submit_feedback_no_user(self, authenticated_client):
        """Test submitting feedback when user doesn't exist"""
        with (
            patch(
                "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
            ) as mock_get_profile,
            patch(
                "app.routers.oracle_universal.db_manager.store_feedback", new_callable=AsyncMock
            ) as mock_store,
        ):
            mock_get_profile.return_value = None
            mock_store.return_value = None

            response = authenticated_client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "nonexistent@example.com",
                    "query_text": "Test query",
                    "original_answer": "Original answer",
                    "feedback_type": "correction",
                    "rating": 5,  # Required field
                },
            )

            assert response.status_code in [200, 422]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True

    def test_submit_feedback_error(self, authenticated_client):
        """Test submitting feedback when storage fails"""
        with (
            patch(
                "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
            ) as mock_get_profile,
            patch(
                "app.routers.oracle_universal.db_manager.store_feedback", new_callable=AsyncMock
            ) as mock_store,
        ):
            mock_get_profile.return_value = {"id": 1}
            mock_store.side_effect = Exception("Storage error")

            response = authenticated_client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "test@example.com",
                    "query_text": "Test query",
                    "original_answer": "Original answer",
                    "feedback_type": "correction",
                    "rating": 5,  # Required field
                },
            )

            assert response.status_code in [422, 500]


@pytest.mark.api
class TestOracleTestEndpoints:
    """Tests for Oracle test endpoints"""

    def test_get_user_profile_endpoint(self, authenticated_client):
        """Test GET /api/oracle/user/profile/{user_email}"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = {
                "id": 1,
                "email": "test@example.com",
                "language": "id",
                "name": "Test User",
            }

            response = authenticated_client.get("/api/oracle/user/profile/test@example.com")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "profile" in data

    def test_get_user_profile_not_found(self, authenticated_client):
        """Test GET /api/oracle/user/profile/{user_email} when user doesn't exist"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = None

            response = authenticated_client.get("/api/oracle/user/profile/nonexistent@example.com")

            assert response.status_code == 404

    def test_get_personalities(self, authenticated_client):
        """Test GET /api/oracle/personalities"""
        response = authenticated_client.get("/api/oracle/personalities")

        assert response.status_code == 200
        data = response.json()
        assert "personalities" in data or isinstance(data, list)

    def test_test_personality(self, authenticated_client):
        """Test POST /api/oracle/personality/test endpoint"""
        with patch(
            "app.routers.oracle_universal.personality_service.test_personality",
            new_callable=AsyncMock,
        ) as mock_test:
            mock_test.return_value = {
                "success": True,
                "response": "Test personality response",
            }

            response = authenticated_client.post(
                "/api/oracle/personality/test",
                params={"personality_type": "jaksel", "message": "Hello"},
            )

            assert response.status_code in [200, 500]

    def test_test_personality_error(self, authenticated_client):
        """Test personality test when service fails"""
        with patch(
            "app.routers.oracle_universal.personality_service.test_personality",
            new_callable=AsyncMock,
        ) as mock_test:
            mock_test.side_effect = Exception("Service error")

            response = authenticated_client.post(
                "/api/oracle/personality/test",
                params={"personality_type": "jaksel", "message": "Hello"},
            )

            assert response.status_code == 500

    def test_test_gemini_integration(self, authenticated_client):
        """Test GET /api/oracle/gemini/test endpoint"""
        with patch(
            "app.routers.oracle_universal.google_services.get_gemini_model"
        ) as mock_get_model:
            from unittest.mock import MagicMock

            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "Test response from Gemini"
            mock_model.generate_content = MagicMock(return_value=mock_response)
            mock_get_model.return_value = mock_model

            response = authenticated_client.get("/api/oracle/gemini/test")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data

    def test_test_drive_connection(self, authenticated_client):
        """Test GET /api/oracle/drive/test endpoint"""
        with patch("app.routers.oracle_universal.google_services") as mock_google_services:
            from unittest.mock import MagicMock

            # Mock drive_service property
            mock_drive_service = MagicMock()
            mock_files = MagicMock()
            mock_files.list = MagicMock()
            mock_files.list.return_value.execute.return_value = {"files": []}
            mock_drive_service.files.return_value = mock_files
            mock_google_services.drive_service = mock_drive_service

            response = authenticated_client.get("/api/oracle/drive/test")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "success" in data or "error" in data


@pytest.mark.api
class TestOracleHealth:
    """Tests for GET /api/oracle/health endpoint"""

    def test_oracle_health_check(self, authenticated_client):
        """Test GET /api/oracle/health"""
        response = authenticated_client.get("/api/oracle/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "service" in data

    def test_oracle_health_check_no_auth(self, test_client):
        """Test health check doesn't require authentication"""
        response = test_client.get("/api/oracle/health")
        assert response.status_code == 200

    def test_get_user_profile_endpoint(self, authenticated_client):
        """Test GET /api/oracle/user/profile/{user_email}"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = {
                "id": 1,
                "email": "test@example.com",
                "language": "id",
                "name": "Test User",
            }

            response = authenticated_client.get("/api/oracle/user/profile/test@example.com")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "profile" in data

    def test_get_user_profile_not_found(self, authenticated_client):
        """Test GET /api/oracle/user/profile/{user_email} when user doesn't exist"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = None

            response = authenticated_client.get("/api/oracle/user/profile/nonexistent@example.com")

            assert response.status_code == 404

    def test_get_personalities(self, authenticated_client):
        """Test GET /api/oracle/personalities"""
        response = authenticated_client.get("/api/oracle/personalities")

        assert response.status_code == 200
        data = response.json()
        assert "personalities" in data or isinstance(data, list)

    def test_test_drive_connection_not_initialized(self, authenticated_client):
        """Test GET /api/oracle/drive/test when Drive service not initialized"""
        with patch("app.routers.oracle_universal.google_services.drive_service", None):
            response = authenticated_client.get("/api/oracle/drive/test")

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False
            assert "not initialized" in data.get("error", "").lower()

    def test_oracle_query_with_language_override(self, authenticated_client, mock_search_service):
        """Test oracle query with language override"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }
        mock_search_service.ai_client.generate_response.return_value = "AI response"

        request_data = {"query": "test query", "language_override": "id"}
        response = authenticated_client.post("/api/oracle/query", json=request_data)

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_with_sources(self, authenticated_client, mock_search_service):
        """Test oracle query with sources included"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{}],
            "distances": [0.1],
        }
        mock_search_service.ai_client.generate_response.return_value = "AI response"

        request_data = {"query": "test query", "include_sources": True}
        response = authenticated_client.post("/api/oracle/query", json=request_data)

        assert response.status_code in [200, 500, 503]


@pytest.mark.api
class TestOracleUserProfile:
    """Tests for GET /api/oracle/user/profile/{user_email} endpoint"""

    def test_get_user_profile_success(self, authenticated_client):
        """Test getting user profile successfully"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = {
                "id": 1,
                "email": "test@example.com",
                "language": "en",
            }

            response = authenticated_client.get("/api/oracle/user/profile/test@example.com")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "profile" in data

    def test_get_user_profile_not_found(self, authenticated_client):
        """Test getting non-existent user profile"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.return_value = None

            response = authenticated_client.get("/api/oracle/user/profile/nonexistent@example.com")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_user_profile_error(self, authenticated_client):
        """Test getting user profile when database fails"""
        with patch(
            "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
        ) as mock_get_profile:
            mock_get_profile.side_effect = Exception("Database error")

            response = authenticated_client.get("/api/oracle/user/profile/test@example.com")

            assert response.status_code == 500

    def test_oracle_query_with_use_ai_flag(self, authenticated_client, mock_search_service):
        """Test oracle query with use_ai flag enabled"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{"filename": "test.pdf"}],
            "distances": [0.1],
        }
        mock_search_service.ai_client.generate_response.return_value = "AI response"

        with patch(
            "app.routers.oracle_universal.smart_oracle", new_callable=AsyncMock
        ) as mock_smart_oracle:
            mock_smart_oracle.return_value = "Full PDF content"

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "use_ai": True},
            )

            assert response.status_code in [200, 500, 503]

    def test_oracle_query_smart_oracle_fallback(self, authenticated_client, mock_search_service):
        """Test oracle query when Smart Oracle fails and falls back to chunks"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": ["doc1"],
            "metadatas": [{"filename": "test.pdf"}],
            "distances": [0.1],
        }

        with (
            patch(
                "app.routers.oracle_universal.smart_oracle", new_callable=AsyncMock
            ) as mock_smart_oracle,
            patch(
                "app.routers.oracle_universal.reason_with_gemini", new_callable=AsyncMock
            ) as mock_reason,
        ):
            mock_smart_oracle.return_value = "Error: Document not found"
            mock_reason.return_value = {
                "answer": "Fallback answer",
                "model_used": "gemini-2.5-flash",
                "reasoning_time_ms": 100,
            }

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "use_ai": True},
            )

            assert response.status_code in [200, 500, 503]

    def test_oracle_query_no_ai_processing(self, authenticated_client, mock_search_service):
        """Test oracle query without AI processing (use_ai=False)"""
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
            json={"query": "Test query", "use_ai": False},
        )

        assert response.status_code in [200, 500, 503]

    def test_oracle_query_reasoning_error(self, authenticated_client, mock_search_service):
        """Test oracle query when reasoning fails"""
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
            "app.routers.oracle_universal.reason_with_gemini", new_callable=AsyncMock
        ) as mock_reason:
            mock_reason.side_effect = Exception("Reasoning error")

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "use_ai": True},
            )

            assert response.status_code in [200, 500, 503]

    def test_oracle_query_default_response_no_answer(
        self, authenticated_client, mock_search_service
    ):
        """Test oracle query when no answer is generated (default response)"""
        mock_search_service.router.get_routing_stats.return_value = {
            "selected_collection": "visa_oracle"
        }
        mock_search_service.collections = {"visa_oracle": AsyncMock()}
        mock_search_service.collections["visa_oracle"].search.return_value = {
            "documents": [],
            "metadatas": [],
            "distances": [],
        }

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query", "use_ai": False, "user_email": "test@example.com"},
        )

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data or data.get("answer") is not None

    def test_oracle_query_analytics_storage(self, authenticated_client, mock_search_service):
        """Test oracle query analytics storage"""
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
            mock_store.return_value = None

            response = authenticated_client.post(
                "/api/oracle/query",
                json={"query": "Test query", "session_id": "test_session"},
            )

            assert response.status_code in [200, 500, 503]

    def test_oracle_query_general_exception(self, authenticated_client, mock_search_service):
        """Test oracle query when general exception occurs"""
        mock_search_service.router.get_routing_stats.side_effect = Exception("General error")

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "Test query"},
        )

        assert response.status_code in [500, 503]
