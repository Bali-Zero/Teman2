"""
Unit tests for legal_ingest router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.legal_ingest import router
from backend.services.ingestion.legal_ingestion_service import LegalIngestionService


@pytest.fixture
def mock_legal_service():
    """Mock LegalIngestionService"""
    service = MagicMock(spec=LegalIngestionService)
    service.ingest_legal_document = AsyncMock(
        return_value={
            "success": True,
            "book_title": "Test Document",
            "chunks_created": 10,
            "legal_metadata": {},
            "structure": {},
            "message": "Document ingested successfully",
        }
    )
    return service


@pytest.fixture
def app():
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestLegalIngestRouter:
    """Tests for legal_ingest router"""

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    @patch("backend.app.routers.legal_ingest.Path")
    def test_ingest_legal_document_success(self, mock_path, mock_get_service, client):
        """Test ingesting legal document successfully"""
        mock_path.return_value.exists.return_value = True

        # Mock the service returned by get_legal_service
        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(
            return_value={
                "success": True,
                "book_title": "Test Document",
                "chunks_created": 10,
                "legal_metadata": {},
                "structure": {},
                "message": "Document ingested successfully",
            }
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/legal/ingest", json={"file_path": "/test/document.pdf", "title": "Test Document"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["book_title"] == "Test Document"
        assert data["message"] == "Document ingested successfully"

    @patch("backend.app.routers.legal_ingest.Path")
    def test_ingest_legal_document_file_not_found(self, mock_path, client):
        """Test ingesting legal document with file not found"""
        mock_path.return_value.exists.return_value = False

        response = client.post("/api/legal/ingest", json={"file_path": "/nonexistent/document.pdf"})
        assert response.status_code == 404

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    @patch("backend.app.routers.legal_ingest.Path")
    def test_ingest_legal_document_with_tier(self, mock_path, mock_get_service, client):
        """Test ingesting legal document with tier override"""
        mock_path.return_value.exists.return_value = True

        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(
            return_value={
                "success": True,
                "book_title": "Test Document",
                "chunks_created": 10,
                "legal_metadata": {},
                "structure": {},
                "message": "Document ingested successfully",
            }
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/legal/ingest", json={"file_path": "/test/document.pdf", "tier": "A"}
        )
        assert response.status_code == 200

    @patch("backend.app.routers.legal_ingest.Path")
    def test_ingest_legal_document_invalid_tier(self, mock_path, client):
        """Test ingesting legal document with invalid tier"""
        mock_path.return_value.exists.return_value = True

        response = client.post(
            "/api/legal/ingest", json={"file_path": "/test/document.pdf", "tier": "INVALID"}
        )
        assert response.status_code == 400

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    @patch("backend.app.routers.legal_ingest.Path")
    def test_ingest_legal_document_with_collection(self, mock_path, mock_get_service, client):
        """Test ingesting legal document with collection override"""
        mock_path.return_value.exists.return_value = True

        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(
            return_value={
                "success": True,
                "book_title": "Test Document",
                "chunks_created": 10,
                "legal_metadata": {},
                "structure": {},
                "message": "Document ingested successfully",
            }
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": "/test/document.pdf", "collection_name": "custom_collection"},
        )
        assert response.status_code == 200

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    @patch("backend.app.routers.legal_ingest.Path")
    def test_ingest_legal_document_error(self, mock_path, mock_get_service, client):
        """Test ingesting legal document with service error"""
        mock_path.return_value.exists.return_value = True

        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(side_effect=Exception("Service error"))
        mock_get_service.return_value = mock_service

        # The endpoint raises HTTPException on error which returns 500
        response = client.post("/api/legal/ingest", json={"file_path": "/test/document.pdf"})
        # The router catches exceptions and returns 500
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
