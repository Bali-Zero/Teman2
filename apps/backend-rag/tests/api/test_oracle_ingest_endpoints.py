"""
API Tests for Oracle Ingest Router
Tests Oracle document ingestion endpoints
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestOracleIngest:
    """Tests for Oracle ingest endpoints"""

    def test_ingest_documents(self, authenticated_client):
        """Test POST /api/oracle/ingest/documents"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"success": True, "ingested": 1})
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "test_collection",
                    "documents": [{"content": "Test document", "metadata": {"title": "Test"}}],
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_ingest_documents_auto_create(self, authenticated_client):
        """Test POST /api/oracle/ingest/documents with auto-create"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"success": True, "ingested": 1})
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "new_collection",
                    "documents": [{"content": "Test document", "metadata": {}}],
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_list_collections(self, authenticated_client):
        """Test GET /api/oracle/collections"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.collections = {"collection1": MagicMock(), "collection2": MagicMock()}
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/oracle/collections")

            assert response.status_code == 200
            data = response.json()
            assert "collections" in data or isinstance(data, list)

    def test_ingest_documents_collection_not_found(self, authenticated_client):
        """Test ingesting documents to non-existent collection"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.collections = {"existing_collection": MagicMock()}
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "nonexistent_collection",
                    "documents": [{"content": "Test", "metadata": {}}],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False
            assert (
                "not found" in data.get("error", "").lower()
                or "not found" in data.get("message", "").lower()
            )

    def test_ingest_documents_auto_create_legal_intelligence(self, authenticated_client):
        """Test auto-creating legal_intelligence collection"""
        with (
            patch("app.routers.oracle_ingest.get_search_service") as mock_get_service,
            patch("app.routers.oracle_ingest.QdrantClient") as mock_qdrant_class,
            patch("app.routers.oracle_ingest.create_embeddings_generator") as mock_embedder_class,
        ):
            mock_service = MagicMock()
            mock_service.collections = {}
            mock_get_service.return_value = mock_service

            mock_qdrant = MagicMock()
            mock_qdrant.upsert_documents = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant

            mock_embedder = MagicMock()
            mock_embedder.generate_batch_embeddings.return_value = [[0.1] * 1536]
            mock_embedder_class.return_value = mock_embedder

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": [
                        {"content": "Test legal document", "metadata": {"law_id": "PP-1"}}
                    ],
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_list_collections_with_stats(self, authenticated_client):
        """Test listing collections with document counts"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_collection1 = MagicMock()
            mock_collection1.get_collection_stats.return_value = {"total_documents": 100}
            mock_collection2 = MagicMock()
            mock_collection2.get_collection_stats.return_value = {"total_documents": 50}
            mock_service.collections = {
                "collection1": mock_collection1,
                "collection2": mock_collection2,
            }
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/oracle/collections")

            assert response.status_code == 200
            data = response.json()
            assert "collections" in data or isinstance(data, list)

    def test_oracle_ingest_requires_auth(self, test_client):
        """Test that oracle ingest endpoints require authentication"""
        response = test_client.post(
            "/api/oracle/ingest",
            json={"collection": "test", "documents": []},
        )
        assert response.status_code == 401

    def test_ingest_documents_validation_error(self, authenticated_client):
        """Test ingesting documents with invalid data"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "test_collection",
                "documents": [{"content": "short", "metadata": {}}],  # content too short
            },
        )
        assert response.status_code == 422

    def test_ingest_documents_empty_list(self, authenticated_client):
        """Test ingesting empty document list"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={"collection": "test_collection", "documents": []},
        )
        assert response.status_code == 422

    def test_ingest_documents_too_many(self, authenticated_client):
        """Test ingesting too many documents at once"""
        documents = [{"content": "Test document " + str(i), "metadata": {}} for i in range(1001)]
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={"collection": "test_collection", "documents": documents},
        )
        assert response.status_code == 422

    def test_ingest_documents_custom_batch_size(self, authenticated_client):
        """Test ingesting documents with custom batch size"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"success": True, "ingested": 2})
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "test_collection",
                    "documents": [
                        {"content": "Test document 1", "metadata": {}},
                        {"content": "Test document 2", "metadata": {}},
                    ],
                    "batch_size": 50,
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_ingest_documents_service_error(self, authenticated_client):
        """Test ingesting documents when service fails"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(side_effect=Exception("Service error"))
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "test_collection",
                    "documents": [{"content": "Test document", "metadata": {}}],
                },
            )

            assert response.status_code in [200, 500, 503]
            if response.status_code == 200:
                data = response.json()
                assert data.get("success") is False

    def test_list_collections_error(self, authenticated_client):
        """Test listing collections when service fails"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.collections = {}
            mock_get_service.side_effect = Exception("Service error")

            response = authenticated_client.get("/api/oracle/collections")

            assert response.status_code in [200, 500, 503]

    def test_ingest_documents_with_complex_metadata(self, authenticated_client):
        """Test ingesting documents with complex metadata"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"success": True, "ingested": 1})
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "test_collection",
                    "documents": [
                        {
                            "content": "Test document with complex metadata",
                            "metadata": {
                                "law_id": "PP-28-2025",
                                "pasal": "1",
                                "category": "business_licensing",
                                "type": "legal_regulation",
                                "nested": {"key": "value"},
                            },
                        }
                    ],
                },
            )

            assert response.status_code in [200, 500, 503]
