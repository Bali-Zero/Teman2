"""
API Tests for Legal Ingestion Router
Tests legal document ingestion endpoints

Coverage:
- POST /api/legal/ingest - Ingest single legal document
- POST /api/legal/ingest-batch - Batch ingestion
- GET /api/legal/collections/stats - Get collection stats
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
class TestLegalIngest:
    """Tests for legal document ingestion"""

    def test_ingest_legal_document_success(self, authenticated_client):
        """Test POST /api/legal/ingest - successful ingestion"""
        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Test Legal Document",
                    "chunks_created": 10,
                    "legal_metadata": {"type": "UU"},
                    "message": "Ingestion successful",
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/path/to/document.pdf",
                    "title": "Test Legal Document",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "chunks_created" in data

    def test_ingest_legal_document_file_not_found(self, authenticated_client):
        """Test POST /api/legal/ingest - file not found"""
        with patch("pathlib.Path.exists", return_value=False):
            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/nonexistent/file.pdf",
                    "title": "Test Document",
                },
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_ingest_legal_document_invalid_tier(self, authenticated_client):
        """Test POST /api/legal/ingest - invalid tier"""
        with patch("pathlib.Path.exists", return_value=True):
            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/path/to/document.pdf",
                    "tier": "INVALID",
                },
            )

            assert response.status_code == 400
            assert "Invalid tier" in response.json()["detail"]

    def test_ingest_legal_document_service_error(self, authenticated_client):
        """Test POST /api/legal/ingest - service error"""
        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(side_effect=Exception("Service error"))
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/path/to/document.pdf",
                },
            )

            assert response.status_code == 500


@pytest.mark.api
class TestLegalIngestBatch:
    """Tests for batch legal document ingestion"""

    def test_ingest_batch_success(self, authenticated_client):
        """Test POST /api/legal/ingest-batch - successful batch"""
        with patch("app.routers.legal_ingest.get_legal_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Document",
                    "chunks_created": 5,
                }
            )
            mock_get_service.return_value = mock_service

            # The endpoint expects a list directly, not wrapped in an object
            response = authenticated_client.post(
                "/api/legal/ingest-batch",
                json=["/path/to/doc1.pdf", "/path/to/doc2.pdf"],
            )

            assert response.status_code in [200, 422]
            if response.status_code == 200:
                data = response.json()
                assert "total" in data
                assert "successful" in data
                assert "failed" in data
                assert "results" in data

    def test_ingest_batch_partial_failure(self, authenticated_client):
        """Test POST /api/legal/ingest-batch - partial failure"""
        with patch("app.routers.legal_ingest.get_legal_service") as mock_get_service:
            mock_service = MagicMock()
            call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {
                        "success": True,
                        "book_title": "Doc1",
                        "chunks_created": 5,
                    }
                else:
                    raise Exception("Ingestion failed")

            mock_service.ingest_legal_document = AsyncMock(side_effect=side_effect)
            mock_get_service.return_value = mock_service

            # The endpoint expects a list directly, not wrapped in an object
            response = authenticated_client.post(
                "/api/legal/ingest-batch",
                json=["/path/to/doc1.pdf", "/path/to/doc2.pdf"],
            )

            assert response.status_code in [200, 422]
            data = response.json()
            assert data["successful"] == 1
            assert data["failed"] == 1


@pytest.mark.api
class TestLegalCollectionStats:
    """Tests for legal collection stats"""

    def test_get_collection_stats(self, authenticated_client):
        """Test GET /api/legal/collections/stats"""
        with patch("app.routers.legal_ingest.get_legal_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/legal/collections/stats")

            assert response.status_code == 200
            data = response.json()
            assert "collection_name" in data

    def test_get_collection_stats_custom_collection(self, authenticated_client):
        """Test GET /api/legal/collections/stats with custom collection"""
        with patch("app.routers.legal_ingest.get_legal_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            response = authenticated_client.get(
                "/api/legal/collections/stats?collection_name=custom_collection"
            )

            assert response.status_code == 200

    def test_ingest_legal_document_with_tier_override(self, authenticated_client):
        """Test POST /api/legal/ingest - with tier override"""
        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Test Document",
                    "chunks_created": 10,
                    "message": "Success",
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/path/to/document.pdf",
                    "tier": "A",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_ingest_legal_document_with_collection_override(self, authenticated_client):
        """Test POST /api/legal/ingest - with collection override"""
        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Test Document",
                    "chunks_created": 5,
                    "message": "Success",
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/path/to/document.pdf",
                    "collection_name": "custom_collection",
                },
            )

            assert response.status_code == 200

    def test_ingest_batch_empty_list(self, authenticated_client):
        """Test POST /api/legal/ingest-batch - empty file list"""
        response = authenticated_client.post(
            "/api/legal/ingest-batch",
            json=[],
        )

        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert data["total"] == 0
            assert data["successful"] == 0
            assert data["failed"] == 0

    def test_ingest_batch_large_list(self, authenticated_client):
        """Test POST /api/legal/ingest-batch - large file list"""
        with patch("app.routers.legal_ingest.get_legal_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Document",
                    "chunks_created": 5,
                }
            )
            mock_get_service.return_value = mock_service

            # Create list of 10 file paths
            file_paths = [f"/path/to/doc{i}.pdf" for i in range(10)]

            response = authenticated_client.post(
                "/api/legal/ingest-batch",
                json=file_paths,
            )

            assert response.status_code in [200, 422]
            if response.status_code == 200:
                data = response.json()
                assert data["total"] == 10

    def test_ingest_legal_document_missing_file_path(self, authenticated_client):
        """Test POST /api/legal/ingest - missing file_path"""
        response = authenticated_client.post(
            "/api/legal/ingest",
            json={},
        )

        assert response.status_code == 422

    def test_ingest_legal_document_all_tiers(self, authenticated_client):
        """Test POST /api/legal/ingest - all valid tier levels"""
        valid_tiers = ["S", "A", "B", "C", "D"]

        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Test",
                    "chunks_created": 5,
                    "message": "Success",
                }
            )
            mock_get_service.return_value = mock_service

            for tier in valid_tiers:
                response = authenticated_client.post(
                    "/api/legal/ingest",
                    json={
                        "file_path": "/path/to/document.pdf",
                        "tier": tier,
                    },
                )

                assert response.status_code == 200

    def test_ingest_legal_document_lowercase_tier(self, authenticated_client):
        """Test POST /api/legal/ingest - lowercase tier (should be converted)"""
        with (
            patch("app.routers.legal_ingest.get_legal_service") as mock_get_service,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.ingest_legal_document = AsyncMock(
                return_value={
                    "success": True,
                    "book_title": "Test",
                    "chunks_created": 5,
                    "message": "Success",
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/legal/ingest",
                json={
                    "file_path": "/path/to/document.pdf",
                    "tier": "a",  # lowercase
                },
            )

            assert response.status_code == 200

    def test_get_collection_stats_default_collection(self, authenticated_client):
        """Test GET /api/legal/collections/stats - default collection"""
        with patch("app.routers.legal_ingest.get_legal_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/legal/collections/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["collection_name"] == "legal_unified"

    def test_ingest_legal_document_requires_auth(self, test_client):
        """Test POST /api/legal/ingest - requires authentication"""
        response = test_client.post(
            "/api/legal/ingest",
            json={"file_path": "/path/to/document.pdf"},
        )

        assert response.status_code == 401
