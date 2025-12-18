"""
Unit tests for Legal Ingestion Router
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.legal_ingest import router

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Create FastAPI test client"""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_legal_service():
    """Mock LegalIngestionService"""
    service = AsyncMock()
    service.ingest_legal_document = AsyncMock(
        return_value={
            "success": True,
            "book_title": "Test Legal Document",
            "chunks_created": 50,
            "legal_metadata": {"type": "UU", "number": "1", "year": "2024"},
            "structure": {"bab": 1, "pasal": 10},
            "message": "Successfully ingested legal document",
            "error": None,
        }
    )
    return service


# ============================================================================
# Tests
# ============================================================================


class TestGetLegalService:
    """Test get_legal_service singleton"""

    @patch("app.routers.legal_ingest._legal_service", None)
    @patch("app.routers.legal_ingest.LegalIngestionService")
    def test_get_legal_service_creates_instance(self, mock_service_class):
        """Test that get_legal_service creates a new instance if None"""
        from app.routers.legal_ingest import get_legal_service

        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        result = get_legal_service()

        assert result == mock_instance
        mock_service_class.assert_called_once()

    @patch("app.routers.legal_ingest._legal_service")
    def test_get_legal_service_returns_existing(self, mock_service):
        """Test that get_legal_service returns existing instance"""
        from app.routers.legal_ingest import get_legal_service

        result = get_legal_service()

        assert result == mock_service


class TestIngestLegalDocument:
    """Test /api/legal/ingest endpoint"""

    @patch("app.routers.legal_ingest.get_legal_service")
    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_success(
        self, mock_path_class, mock_get_service, client, mock_legal_service
    ):
        """Test successful legal document ingestion"""
        mock_get_service.return_value = mock_legal_service
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/path/to/document.pdf",
                "title": "Test Document",
                "tier": "S",
                "collection_name": "test_collection",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["book_title"] == "Test Legal Document"
        assert data["chunks_created"] == 50
        call_args = mock_legal_service.ingest_legal_document.call_args
        assert call_args.kwargs["file_path"] == "/path/to/document.pdf"
        assert call_args.kwargs["title"] == "Test Document"
        assert call_args.kwargs["tier_override"] is not None  # Parsed to TierLevel.S
        assert call_args.kwargs["collection_name"] == "test_collection"

    @patch("app.routers.legal_ingest.get_legal_service")
    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_file_not_found(self, mock_path_class, mock_get_service, client):
        """Test ingestion fails when file doesn't exist"""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": "/nonexistent/file.pdf"},
        )

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    @patch("app.routers.legal_ingest.get_legal_service")
    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_invalid_tier(self, mock_path_class, mock_get_service, client):
        """Test ingestion fails with invalid tier"""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": "/path/to/document.pdf", "tier": "INVALID"},
        )

        assert response.status_code == 400
        assert "Invalid tier" in response.json()["detail"]

    @patch("app.routers.legal_ingest.get_legal_service")
    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_service_error(
        self, mock_path_class, mock_get_service, client, mock_legal_service
    ):
        """Test ingestion handles service errors"""
        mock_get_service.return_value = mock_legal_service
        mock_legal_service.ingest_legal_document.side_effect = Exception("Service error")
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": "/path/to/document.pdf"},
        )

        assert response.status_code == 500
        assert "Failed to ingest legal document" in response.json()["detail"]

    @patch("app.routers.legal_ingest.get_legal_service")
    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_with_tier_override(
        self, mock_path_class, mock_get_service, client, mock_legal_service
    ):
        """Test ingestion with tier override"""
        mock_get_service.return_value = mock_legal_service
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": "/path/to/document.pdf", "tier": "A"},
        )

        assert response.status_code == 200
        # Verify tier_override was passed (will be TierLevel.A)
        call_args = mock_legal_service.ingest_legal_document.call_args
        assert call_args.kwargs["tier_override"] is not None


class TestIngestLegalDocumentsBatch:
    """Test /api/legal/ingest-batch endpoint"""

    @patch("app.routers.legal_ingest.get_legal_service")
    def test_ingest_batch_success(self, mock_get_service, client, mock_legal_service):
        """Test successful batch ingestion"""
        mock_get_service.return_value = mock_legal_service

        # FastAPI treats list[str] as body parameter, so we send it directly
        response = client.post(
            "/api/legal/ingest-batch",
            json=["/path/to/doc1.pdf", "/path/to/doc2.pdf"],
            params={"collection_name": "test_collection"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2

    @patch("app.routers.legal_ingest.get_legal_service")
    def test_ingest_batch_with_failures(self, mock_get_service, client, mock_legal_service):
        """Test batch ingestion with some failures"""
        mock_get_service.return_value = mock_legal_service
        # First call succeeds, second fails
        mock_legal_service.ingest_legal_document.side_effect = [
            {
                "success": True,
                "book_title": "Doc1",
                "chunks_created": 10,
                "message": "Success",
                "error": None,
            },
            Exception("Ingestion failed"),
        ]

        # FastAPI treats list[str] as body parameter
        response = client.post(
            "/api/legal/ingest-batch",
            json=["/path/to/doc1.pdf", "/path/to/doc2.pdf"],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert data["results"][0]["success"] is True
        assert data["results"][1]["success"] is False
        assert "error" in data["results"][1]


class TestGetCollectionStats:
    """Test /api/legal/collections/stats endpoint"""

    @patch("app.routers.legal_ingest.get_legal_service")
    def test_get_collection_stats_success(self, mock_get_service, client):
        """Test successful collection stats retrieval"""
        response = client.get("/api/legal/collections/stats?collection_name=test_collection")

        assert response.status_code == 200
        data = response.json()
        assert data["collection_name"] == "test_collection"
        assert "message" in data

    @patch("app.routers.legal_ingest.get_legal_service")
    def test_get_collection_stats_default_collection(self, mock_get_service, client):
        """Test collection stats with default collection name"""
        response = client.get("/api/legal/collections/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["collection_name"] == "legal_unified"

    @patch("app.routers.legal_ingest.get_legal_service")
    def test_get_collection_stats_error(self, mock_get_service, client):
        """Test collection stats handles errors"""
        mock_get_service.side_effect = Exception("Service error")

        response = client.get("/api/legal/collections/stats")

        assert response.status_code == 500
        assert "Failed to get collection stats" in response.json()["detail"]
