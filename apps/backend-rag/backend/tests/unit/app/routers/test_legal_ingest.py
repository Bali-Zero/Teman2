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

from backend.app.dependencies import get_current_user
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
        },
    )
    return service


@pytest.fixture
def app():
    """Create FastAPI app with router.

    Legal ingest endpoints are admin-gated (Case OS R3): override
    get_current_user with an admin identity so the router's
    _require_ingest_admin gate passes and these tests exercise the
    ingest logic rather than the auth layer.
    """
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"role": "admin"}
    return app


@pytest.fixture(autouse=True)
def allowed_root(tmp_path, monkeypatch):
    """A real, allow-listed directory holding a real document.

    These tests used to `@patch("...legal_ingest.Path")` so that `.exists()` returned
    True for a made-up `/test/document.pdf`. The router now confines the caller-supplied
    path first (`resolve_ingest_path`) and calls `.exists()` on the RESOLVED value, so
    patching the router's `Path` no longer intercepts anything — and `/test/...` is
    outside every allowed root, which is exactly the refusal the guard exists for.
    Using a real file instead keeps each test's intent and drops a mock that was
    standing in for the filesystem.
    """
    root = tmp_path / "legal"
    root.mkdir()
    (root / "document.pdf").write_bytes(b"%PDF-1.4 test")
    monkeypatch.setenv("INGEST_ALLOWED_ROOTS", str(root))
    return root


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestLegalIngestRouter:
    """Tests for legal_ingest router"""

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    def test_ingest_legal_document_success(self, mock_get_service, client, allowed_root):
        """Test ingesting legal document successfully"""

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
            },
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": str(allowed_root / "document.pdf"), "title": "Test Document"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["book_title"] == "Test Document"
        assert data["message"] == "Document ingested successfully"

    def test_ingest_legal_document_file_not_found(self, client, allowed_root):
        """Test ingesting legal document with file not found"""

        response = client.post("/api/legal/ingest", json={"file_path": str(allowed_root / "missing.pdf")})
        assert response.status_code == 404

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    def test_ingest_legal_document_with_tier(self, mock_get_service, client, allowed_root):
        """Test ingesting legal document with tier override"""

        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(
            return_value={
                "success": True,
                "book_title": "Test Document",
                "chunks_created": 10,
                "legal_metadata": {},
                "structure": {},
                "message": "Document ingested successfully",
            },
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": str(allowed_root / "document.pdf"), "tier": "A"},
        )
        assert response.status_code == 200

    def test_ingest_legal_document_invalid_tier(self, client, allowed_root):
        """Test ingesting legal document with invalid tier"""

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": str(allowed_root / "document.pdf"), "tier": "INVALID"},
        )
        assert response.status_code == 400

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    def test_ingest_legal_document_with_collection(self, mock_get_service, client, allowed_root):
        """Test ingesting legal document with collection override"""

        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(
            return_value={
                "success": True,
                "book_title": "Test Document",
                "chunks_created": 10,
                "legal_metadata": {},
                "structure": {},
                "message": "Document ingested successfully",
            },
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/legal/ingest",
            json={"file_path": str(allowed_root / "document.pdf"), "collection_name": "custom_collection"},
        )
        assert response.status_code == 200

    @patch("backend.app.routers.legal_ingest.get_legal_service")
    def test_ingest_legal_document_error(self, mock_get_service, client, allowed_root):
        """Test ingesting legal document with service error"""

        mock_service = MagicMock()
        mock_service.ingest_legal_document = AsyncMock(side_effect=Exception("Service error"))
        mock_get_service.return_value = mock_service

        # The endpoint raises HTTPException on error which returns 500
        response = client.post("/api/legal/ingest", json={"file_path": str(allowed_root / "document.pdf")})
        # The router catches exceptions and returns 500
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
