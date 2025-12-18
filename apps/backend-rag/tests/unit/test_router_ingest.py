"""
Unit tests for Ingest Router
100% coverage target with comprehensive mocking
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

from app.routers.ingest import router

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
def mock_ingestion_service():
    """Mock IngestionService"""
    service = AsyncMock()
    service.ingest_book = AsyncMock(
        return_value={
            "success": True,
            "book_title": "Test Book",
            "book_author": "Test Author",
            "tier": "S",
            "chunks_created": 100,
            "message": "Successfully ingested Test Book",
            "error": None,
        }
    )
    return service


@pytest.fixture
def mock_file():
    """Mock uploaded file"""
    file = MagicMock()
    file.filename = "test.pdf"
    file.read = AsyncMock(return_value=b"PDF content")
    return file


# ============================================================================
# Tests for upload_and_ingest endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_upload_and_ingest_success(client, mock_ingestion_service):
    """Test upload_and_ingest successful"""
    with (
        patch("app.routers.ingest.IngestionService", return_value=mock_ingestion_service),
        patch("builtins.open", create=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=True),
        patch("os.remove"),
    ):
        files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
        response = client.post(
            "/api/ingest/upload", files=files, data={"title": "Test Book", "author": "Test Author"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_upload_and_ingest_invalid_file_type(client):
    """Test upload_and_ingest with invalid file type"""
    files = {"file": ("test.txt", b"Text content", "text/plain")}
    response = client.post("/api/ingest/upload", files=files)

    assert response.status_code == 400
    assert "PDF and EPUB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_and_ingest_exception(client, mock_ingestion_service):
    """Test upload_and_ingest handles exception"""
    mock_ingestion_service.ingest_book.side_effect = Exception("Ingestion error")

    with (
        patch("app.routers.ingest.IngestionService", return_value=mock_ingestion_service),
        patch("builtins.open", create=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=True),
        patch("os.remove"),
    ):
        files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
        response = client.post("/api/ingest/upload", files=files)

        assert response.status_code == 500


# ============================================================================
# Tests for ingest_local_file endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_ingest_local_file_success(client, mock_ingestion_service):
    """Test ingest_local_file successful"""
    with (
        patch("app.routers.ingest.IngestionService", return_value=mock_ingestion_service),
        patch("os.path.exists", return_value=True),
    ):
        response = client.post(
            "/api/ingest/file",
            json={
                "file_path": "data/books/test.pdf",
                "title": "Test Book",
                "author": "Test Author",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_ingest_local_file_not_found(client, mock_ingestion_service):
    """Test ingest_local_file with file not found"""
    with (
        patch("app.routers.ingest.IngestionService", return_value=mock_ingestion_service),
        patch("os.path.exists", return_value=False),
    ):
        response = client.post(
            "/api/ingest/file", json={"file_path": "nonexistent.pdf", "title": "Test"}
        )

        assert response.status_code == 404


# ============================================================================
# Tests for batch_ingest endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_batch_ingest_success(client, mock_ingestion_service):
    """Test batch_ingest successful"""
    mock_ingestion_service.ingest_book = AsyncMock(
        return_value={
            "success": True,
            "book_title": "Test Book",
            "book_author": "Test Author",
            "tier": "S",
            "chunks_created": 100,
            "message": "Successfully ingested Test Book",
            "error": None,
        }
    )

    with (
        patch("app.routers.ingest.IngestionService", return_value=mock_ingestion_service),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.glob", return_value=[Path("book1.pdf"), Path("book2.pdf")]),
    ):
        response = client.post(
            "/api/ingest/batch",
            json={
                "directory_path": "/test/books",
                "file_patterns": ["*.pdf"],
                "skip_existing": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "successful" in data
        assert data["total_books"] == 2


# ============================================================================
# Tests for get_stats endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_stats_success(client):
    """Test get_stats successful"""
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info = AsyncMock(return_value={"points_count": 1000})

    with patch("app.routers.ingest.QdrantClient", return_value=mock_qdrant):
        response = client.get("/api/ingest/stats")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
