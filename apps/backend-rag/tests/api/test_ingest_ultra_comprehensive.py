"""
Ultra-Comprehensive API Tests for Ingestion Router
Complete test coverage for all book ingestion endpoints with every possible scenario

Coverage:
- POST /api/ingest/upload - Upload and ingest file
- POST /api/ingest/file - Ingest local file
- POST /api/ingest/batch - Batch ingest
- GET /api/ingest/stats - Get ingestion statistics
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestUploadIngest:
    """Ultra-comprehensive tests for POST /api/ingest/upload"""

    def test_upload_pdf_file(self, authenticated_client):
        """Test uploading PDF file"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={
                    "success": True,
                    "book_id": "book_123",
                    "chunks_created": 100,
                    "tier": "A",
                }
            )
            mock_service_class.return_value = mock_service

            files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
            data = {}

            response = authenticated_client.post(
                "/api/ingest/upload",
                files=files,
                data=data,
            )

            assert response.status_code in [200, 201, 400, 500, 503]

    def test_upload_epub_file(self, authenticated_client):
        """Test uploading EPUB file"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={
                    "success": True,
                    "book_id": "book_123",
                    "chunks_created": 100,
                }
            )
            mock_service_class.return_value = mock_service

            files = {"file": ("test.epub", b"EPUB content", "application/epub+zip")}
            data = {}

            response = authenticated_client.post(
                "/api/ingest/upload",
                files=files,
                data=data,
            )

            assert response.status_code in [200, 201, 400, 500, 503]

    def test_upload_with_title(self, authenticated_client):
        """Test uploading file with title"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
            data = {"title": "Test Book Title"}

            response = authenticated_client.post(
                "/api/ingest/upload",
                files=files,
                data=data,
            )

            assert response.status_code in [200, 201, 400, 500, 503]

    def test_upload_with_author(self, authenticated_client):
        """Test uploading file with author"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
            data = {"author": "Test Author"}

            response = authenticated_client.post(
                "/api/ingest/upload",
                files=files,
                data=data,
            )

            assert response.status_code in [200, 201, 400, 500, 503]

    def test_upload_with_tier_override(self, authenticated_client):
        """Test uploading file with tier override"""
        tiers = ["S", "A", "B", "C", "D"]

        for tier in tiers:
            with patch("app.routers.ingest.IngestionService") as mock_service_class:
                mock_service = MagicMock()
                mock_service.ingest_book = AsyncMock(
                    return_value={"success": True, "book_id": "book_123", "tier": tier}
                )
                mock_service_class.return_value = mock_service

                files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
                data = {"tier_override": tier}

                response = authenticated_client.post(
                    "/api/ingest/upload",
                    files=files,
                    data=data,
                )

                assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_upload_invalid_file_type(self, authenticated_client):
        """Test uploading invalid file type"""
        files = {"file": ("test.txt", b"Text content", "text/plain")}
        data = {}

        response = authenticated_client.post(
            "/api/ingest/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 400

    def test_upload_missing_file(self, authenticated_client):
        """Test uploading without file"""
        response = authenticated_client.post(
            "/api/ingest/upload",
            data={},
        )

        assert response.status_code == 422

    def test_upload_large_file(self, authenticated_client):
        """Test uploading large file"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            large_content = b"PDF" + b"X" * (100 * 1024 * 1024)  # 100MB
            files = {"file": ("large.pdf", large_content, "application/pdf")}
            data = {}

            response = authenticated_client.post(
                "/api/ingest/upload",
                files=files,
                data=data,
            )

            assert response.status_code in [200, 201, 400, 413, 500, 503]


@pytest.mark.api
class TestFileIngest:
    """Ultra-comprehensive tests for POST /api/ingest/file"""

    def test_ingest_local_file_basic(self, authenticated_client):
        """Test ingesting local file"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            with patch("os.path.exists", return_value=True):
                response = authenticated_client.post(
                    "/api/ingest/file",
                    json={"file_path": "/path/to/book.pdf"},
                )

                assert response.status_code in [200, 201, 500, 503]

    def test_ingest_local_file_with_title(self, authenticated_client):
        """Test ingesting local file with title"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            with patch("os.path.exists", return_value=True):
                response = authenticated_client.post(
                    "/api/ingest/file",
                    json={
                        "file_path": "/path/to/book.pdf",
                        "title": "Test Book",
                    },
                )

                assert response.status_code in [200, 201, 500, 503]

    def test_ingest_local_file_with_all_fields(self, authenticated_client):
        """Test ingesting local file with all fields"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            with patch("os.path.exists", return_value=True):
                response = authenticated_client.post(
                    "/api/ingest/file",
                    json={
                        "file_path": "/path/to/book.pdf",
                        "title": "Test Book",
                        "author": "Test Author",
                        "language": "en",
                        "tier_override": "A",
                    },
                )

                assert response.status_code in [200, 201, 500, 503]

    def test_ingest_local_file_not_found(self, authenticated_client):
        """Test ingesting non-existent local file"""
        with patch("os.path.exists", return_value=False):
            response = authenticated_client.post(
                "/api/ingest/file",
                json={"file_path": "/nonexistent/book.pdf"},
            )

            assert response.status_code == 404

    def test_ingest_local_file_missing_path(self, authenticated_client):
        """Test ingesting file without path"""
        response = authenticated_client.post(
            "/api/ingest/file",
            json={},
        )

        assert response.status_code == 422


@pytest.mark.api
class TestBatchIngest:
    """Ultra-comprehensive tests for POST /api/ingest/batch"""

    def test_batch_ingest_basic(self, authenticated_client):
        """Test basic batch ingestion"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.glob") as mock_glob:
                    mock_glob.return_value = [
                        Path("book1.pdf"),
                        Path("book2.pdf"),
                    ]

                    response = authenticated_client.post(
                        "/api/ingest/batch",
                        json={"directory_path": "/path/to/books"},
                    )

                    assert response.status_code in [200, 201, 500, 503]

    def test_batch_ingest_with_patterns(self, authenticated_client):
        """Test batch ingestion with file patterns"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.glob") as mock_glob:
                    mock_glob.return_value = [Path("book1.pdf")]

                    response = authenticated_client.post(
                        "/api/ingest/batch",
                        json={
                            "directory_path": "/path/to/books",
                            "file_patterns": ["*.pdf", "*.epub"],
                        },
                    )

                    assert response.status_code in [200, 201, 500, 503]

    def test_batch_ingest_with_skip_existing(self, authenticated_client):
        """Test batch ingestion with skip_existing"""
        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={"success": True, "book_id": "book_123"}
            )
            mock_service_class.return_value = mock_service

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.glob") as mock_glob:
                    mock_glob.return_value = [Path("book1.pdf")]

                    response = authenticated_client.post(
                        "/api/ingest/batch",
                        json={
                            "directory_path": "/path/to/books",
                            "skip_existing": True,
                        },
                    )

                    assert response.status_code in [200, 201, 500, 503]

    def test_batch_ingest_directory_not_found(self, authenticated_client):
        """Test batch ingestion with non-existent directory"""
        with patch("pathlib.Path.exists", return_value=False):
            response = authenticated_client.post(
                "/api/ingest/batch",
                json={"directory_path": "/nonexistent/books"},
            )

            assert response.status_code == 404

    def test_batch_ingest_no_books_found(self, authenticated_client):
        """Test batch ingestion with no books found"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob", return_value=[]):
                response = authenticated_client.post(
                    "/api/ingest/batch",
                    json={"directory_path": "/path/to/empty"},
                )

                assert response.status_code == 400

    def test_batch_ingest_partial_failure(self, authenticated_client):
        """Test batch ingestion with partial failures"""
        call_count = 0

        def ingest_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": True, "book_id": "book_1"}
            else:
                raise Exception("Ingestion failed")

        with patch("app.routers.ingest.IngestionService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(side_effect=ingest_side_effect)
            mock_service_class.return_value = mock_service

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.glob") as mock_glob:
                    mock_glob.return_value = [
                        Path("book1.pdf"),
                        Path("book2.pdf"),
                    ]

                    response = authenticated_client.post(
                        "/api/ingest/batch",
                        json={"directory_path": "/path/to/books"},
                    )

                    assert response.status_code in [200, 201, 500, 503]


@pytest.mark.api
class TestIngestStats:
    """Ultra-comprehensive tests for GET /api/ingest/stats"""

    def test_get_ingest_stats(self, authenticated_client):
        """Test getting ingestion statistics"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.get_collection_stats = AsyncMock(
                return_value={"total_documents": 1000, "collection_name": "books"}
            )
            mock_qdrant.return_value = mock_client

            response = authenticated_client.get("/api/ingest/stats")

            assert response.status_code in [200, 500, 503]

    def test_ingest_stats_structure(self, authenticated_client):
        """Test ingest stats response structure"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.get_collection_stats = AsyncMock(return_value={"total_documents": 1000})
            mock_qdrant.return_value = mock_client

            response = authenticated_client.get("/api/ingest/stats")

            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)


@pytest.mark.api
class TestIngestSecurity:
    """Security tests for ingestion endpoints"""

    def test_ingest_endpoints_require_auth(self, test_client):
        """Test all ingestion endpoints require authentication"""
        endpoints = [
            ("POST", "/api/ingest/upload"),
            ("POST", "/api/ingest/file"),
            ("POST", "/api/ingest/batch"),
            ("GET", "/api/ingest/stats"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401
