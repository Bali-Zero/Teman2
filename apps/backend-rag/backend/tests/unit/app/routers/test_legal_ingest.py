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

from app.routers.legal_ingest import get_legal_service, router
from services.ingestion.legal_ingestion_service import LegalIngestionService


@pytest.fixture
def mock_legal_service():
    """Mock LegalIngestionService"""
    service = MagicMock(spec=LegalIngestionService)
    service.ingest_legal_document = AsyncMock(return_value={
        "success": True,
        "book_title": "Test Document",
        "chunks_created": 10,
        "legal_metadata": {},
        "structure": {}
    })
    return service


@pytest.fixture
def app(mock_legal_service):
    """Create FastAPI app with router and dependency overrides"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_legal_service] = lambda: mock_legal_service
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestLegalIngestRouter:
    """Tests for legal_ingest router"""

    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_success(self, mock_path, client, mock_legal_service):
        """Test ingesting legal document successfully"""
        mock_path.return_value.exists.return_value = True

        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/test/document.pdf",
                "title": "Test Document"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["book_title"] == "Test Document"

    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_file_not_found(self, mock_path, client):
        """Test ingesting legal document with file not found"""
        mock_path.return_value.exists.return_value = False

        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/nonexistent/document.pdf"
            }
        )
        assert response.status_code == 404

    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_with_tier(self, mock_path, client, mock_legal_service):
        """Test ingesting legal document with tier override"""
        mock_path.return_value.exists.return_value = True

        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/test/document.pdf",
                "tier": "A"
            }
        )
        assert response.status_code == 200

    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_invalid_tier(self, mock_path, client):
        """Test ingesting legal document with invalid tier"""
        mock_path.return_value.exists.return_value = True

        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/test/document.pdf",
                "tier": "INVALID"
            }
        )
        assert response.status_code == 400

    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_with_collection(self, mock_path, client, mock_legal_service):
        """Test ingesting legal document with collection override"""
        mock_path.return_value.exists.return_value = True

        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/test/document.pdf",
                "collection_name": "custom_collection"
            }
        )
        assert response.status_code == 200

    @patch("app.routers.legal_ingest.Path")
    def test_ingest_legal_document_error(self, mock_path, client, mock_legal_service):
        """Test ingesting legal document with service error"""
        mock_path.return_value.exists.return_value = True
        mock_legal_service.ingest_legal_document = AsyncMock(side_effect=Exception("Service error"))

        # The endpoint catches exceptions and returns 200 with error in response
        response = client.post(
            "/api/legal/ingest",
            json={
                "file_path": "/test/document.pdf"
            }
        )
        # Check that error is in response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

