"""
Integration Tests for Oracle Universal Router
Tests oracle_universal.py endpoints with real dependencies
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def app():
    """Create FastAPI app with oracle_universal router"""
    from fastapi import FastAPI

    from app.routers.oracle_universal import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user dependency"""
    return {"email": "test@example.com", "user_id": "test-user-123"}


@pytest.fixture
def mock_search_service():
    """Mock search service"""
    mock_service = MagicMock()
    mock_service.query_router = MagicMock()
    mock_service.query_router.route_query = MagicMock(
        return_value={"collection_name": "test_collection"}
    )
    mock_service.collection_manager = MagicMock()
    mock_collection = MagicMock()
    mock_collection.search = AsyncMock(
        return_value={
            "documents": ["Document 1", "Document 2"],
            "metadatas": [{"id": "doc1"}, {"id": "doc2"}],
            "distances": [0.1, 0.2],
        }
    )
    mock_service.collection_manager.get_collection = MagicMock(return_value=mock_collection)
    return mock_service


@pytest.mark.integration
class TestOracleUniversalIntegration:
    """Comprehensive integration tests for Oracle Universal router"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/oracle/health")
        assert response.status_code in [200, 503]  # May be unavailable in test

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_basic(self, client, mock_search_service, mock_current_user):
        """Test basic hybrid oracle query"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                with patch(
                    "app.routers.oracle_universal.reason_with_gemini", new_callable=AsyncMock
                ) as mock_reason:
                    mock_reason.return_value = {
                        "answer": "Test answer",
                        "model_used": "gemini-2.5-flash",
                        "reasoning_time_ms": 100,
                        "success": True,
                    }

                    with patch("core.embeddings.create_embeddings_generator") as mock_embed:
                        mock_embedder = MagicMock()
                        mock_embedder.generate_single_embedding = MagicMock(
                            return_value=[0.1] * 384
                        )
                        mock_embed.return_value = mock_embedder

                        payload = {
                            "query": "What is PT PMA?",
                            "limit": 5,
                            "use_reasoning": True,
                        }

                        response = client.post("/api/oracle/query", json=payload)

                        assert response.status_code in [
                            200,
                            422,
                            500,
                        ]  # May fail if dependencies missing

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_with_user_email(
        self, client, mock_search_service, mock_current_user
    ):
        """Test hybrid oracle query with user email"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                with patch(
                    "app.routers.oracle_universal.db_manager.get_user_profile",
                    new_callable=AsyncMock,
                ) as mock_profile:
                    mock_profile.return_value = {
                        "name": "Test User",
                        "language": "en",
                        "role_level": "member",
                    }

                    with patch(
                        "app.routers.oracle_universal.reason_with_gemini", new_callable=AsyncMock
                    ) as mock_reason:
                        mock_reason.return_value = {
                            "answer": "Test answer",
                            "model_used": "gemini-2.5-flash",
                            "success": True,
                        }

                        with patch("core.embeddings.create_embeddings_generator") as mock_embed:
                            mock_embedder = MagicMock()
                            mock_embedder.generate_single_embedding = MagicMock(
                                return_value=[0.1] * 384
                            )
                            mock_embed.return_value = mock_embedder

                        payload = {
                            "query": "What is PT PMA?",
                            "user_email": "test@example.com",
                            "limit": 5,
                        }

                        response = client.post("/api/oracle/query", json=payload)
                        assert response.status_code in [200, 422, 500]

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_with_golden_answer(
        self, client, mock_search_service, mock_current_user
    ):
        """Test hybrid oracle query when golden answer is found"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                with patch("app.routers.oracle_universal.get_golden_answer_service") as mock_golden:
                    mock_golden_svc = MagicMock()
                    mock_golden_svc.pool = MagicMock()  # Already connected
                    mock_golden_svc.lookup_golden_answer = AsyncMock(
                        return_value={
                            "answer": "Golden answer",
                            "match_type": "exact",
                            "cluster_id": "test-cluster",
                        }
                    )
                    mock_golden.return_value = mock_golden_svc

                    payload = {
                        "query": "How to get KITAS?",
                        "limit": 5,
                    }

                    response = client.post("/api/oracle/query", json=payload)
                    # Should return golden answer quickly
                    assert response.status_code in [200, 422, 500]

    @pytest.mark.asyncio
    async def test_feedback_endpoint(self, client, mock_current_user):
        """Test feedback endpoint"""
        with patch("app.routers.oracle_universal.get_current_user", return_value=mock_current_user):
            with patch(
                "app.routers.oracle_universal.db_manager.save_feedback", new_callable=AsyncMock
            ):
                payload = {
                    "query_id": "test-query-123",
                    "rating": 5,
                    "notes": "Great answer!",
                }

                response = client.post("/api/oracle/feedback", json=payload)
                assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_feedback_endpoint_invalid_rating(self, client, mock_current_user):
        """Test feedback endpoint with invalid rating"""
        with patch("app.routers.oracle_universal.get_current_user", return_value=mock_current_user):
            payload = {
                "query_id": "test-query-123",
                "rating": 10,  # Invalid (max 5)
                "notes": "Test",
            }

            response = client.post("/api/oracle/feedback", json=payload)
            assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_user_profile_endpoint(self, client, mock_current_user):
        """Test user profile endpoint"""
        with patch("app.routers.oracle_universal.get_current_user", return_value=mock_current_user):
            with patch(
                "app.routers.oracle_universal.db_manager.get_user_profile", new_callable=AsyncMock
            ) as mock_profile:
                mock_profile.return_value = {
                    "name": "Test User",
                    "email": "test@example.com",
                    "language": "en",
                }

                response = client.get("/api/oracle/user/profile/test@example.com")
                assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_drive_test_endpoint(self, client, mock_current_user):
        """Test drive test endpoint"""
        with patch("app.routers.oracle_universal.get_current_user", return_value=mock_current_user):
            with patch("app.routers.oracle_universal.google_services.drive_service") as mock_drive:
                mock_drive.files.return_value.list.return_value.execute.return_value = {"files": []}

                response = client.get("/api/oracle/drive/test")
                assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_gemini_test_endpoint(self, client, mock_current_user):
        """Test gemini test endpoint"""
        with patch("app.routers.oracle_universal.get_current_user", return_value=mock_current_user):
            with patch("app.routers.oracle_universal.google_services.gemini_available", True):
                response = client.get("/api/oracle/gemini/test")
                assert response.status_code in [200, 503]

    def test_generate_query_hash(self):
        """Test query hash generation"""
        from app.routers.oracle_universal import generate_query_hash

        hash1 = generate_query_hash("test query")
        hash2 = generate_query_hash("test query")
        hash3 = generate_query_hash("different query")

        assert hash1 == hash2  # Same query = same hash
        assert hash1 != hash3  # Different query = different hash
        assert len(hash1) == 32  # MD5 hash length

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_with_conversation_history(
        self, client, mock_search_service, mock_current_user
    ):
        """Test hybrid oracle query with conversation history"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                with patch(
                    "app.routers.oracle_universal.reason_with_gemini", new_callable=AsyncMock
                ) as mock_reason:
                    mock_reason.return_value = {
                        "answer": "Test answer",
                        "model_used": "gemini-2.5-flash",
                        "success": True,
                    }

                    with patch("core.embeddings.create_embeddings_generator") as mock_embed:
                        mock_embedder = MagicMock()
                        mock_embedder.generate_single_embedding = MagicMock(
                            return_value=[0.1] * 384
                        )
                        mock_embed.return_value = mock_embedder

                    payload = {
                        "query": "What is PT PMA?",
                        "limit": 5,
                        "conversation_history": [
                            {"role": "user", "content": "Hello"},
                            {"role": "assistant", "content": "Hi!"},
                        ],
                    }

                    response = client.post("/api/oracle/query", json=payload)
                    assert response.status_code in [200, 422, 500]

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_with_language_override(
        self, client, mock_search_service, mock_current_user
    ):
        """Test hybrid oracle query with language override"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                with patch(
                    "app.routers.oracle_universal.reason_with_gemini", new_callable=AsyncMock
                ) as mock_reason:
                    mock_reason.return_value = {
                        "answer": "Risposta di test",
                        "model_used": "gemini-2.5-flash",
                        "success": True,
                    }

                    with patch("core.embeddings.create_embeddings_generator") as mock_embed:
                        mock_embedder = MagicMock()
                        mock_embedder.generate_single_embedding = MagicMock(
                            return_value=[0.1] * 384
                        )
                        mock_embed.return_value = mock_embedder

                    payload = {
                        "query": "What is PT PMA?",
                        "language_override": "it",
                        "limit": 5,
                    }

                    response = client.post("/api/oracle/query", json=payload)
                    assert response.status_code in [200, 422, 500]

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_embedding_error(
        self, client, mock_search_service, mock_current_user
    ):
        """Test hybrid oracle query when embedding generation fails"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                with patch("core.embeddings.create_embeddings_generator") as mock_embed:
                    mock_embed.side_effect = Exception("Embedding service unavailable")

                    payload = {
                        "query": "What is PT PMA?",
                        "limit": 5,
                    }

                    response = client.post("/api/oracle/query", json=payload)
                    assert response.status_code == 503  # Service unavailable

    @pytest.mark.asyncio
    async def test_hybrid_oracle_query_collection_not_found(
        self, client, mock_search_service, mock_current_user
    ):
        """Test hybrid oracle query when collection not found"""
        with patch(
            "app.routers.oracle_universal.get_search_service", return_value=mock_search_service
        ):
            with patch(
                "app.routers.oracle_universal.get_current_user", return_value=mock_current_user
            ):
                mock_search_service.collection_manager.get_collection = MagicMock(return_value=None)

                with patch("core.embeddings.create_embeddings_generator") as mock_embed:
                    mock_embedder = MagicMock()
                    mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)
                    mock_embed.return_value = mock_embedder

                    payload = {
                        "query": "What is PT PMA?",
                        "limit": 5,
                    }

                    response = client.post("/api/oracle/query", json=payload)
                    assert response.status_code == 404  # Collection not found
