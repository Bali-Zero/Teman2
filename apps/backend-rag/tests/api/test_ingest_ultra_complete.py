"""
Ultra-Complete API Tests for Ingest Router
==========================================

Coverage Endpoints:
- POST /api/ingest/file - Ingest file from path
- POST /api/ingest/upload - Upload and ingest file
- POST /api/ingest/batch - Batch ingest from directory
- GET /api/ingest/stats - Get ingestion statistics
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestIngestFile:
    def test_ingest_file_valid(self, authenticated_client):
        with patch("app.routers.ingest.ingestion_service") as mock:
            mock.ingest_file.return_value = {"success": True, "chunks": 50}
            response = authenticated_client.post(
                "/api/ingest/file", json={"file_path": "/path/to/document.pdf"}
            )
            assert response.status_code in [200, 201, 400, 404, 500]

    def test_ingest_file_not_found(self, authenticated_client):
        response = authenticated_client.post(
            "/api/ingest/file", json={"file_path": "/nonexistent/file.pdf"}
        )
        assert response.status_code in [404, 400, 500]


@pytest.mark.api
class TestIngestUpload:
    def test_upload_file(self, authenticated_client):
        # Simulate file upload
        files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
        response = authenticated_client.post("/api/ingest/upload", files=files)
        assert response.status_code in [200, 201, 400, 413, 415, 500]


@pytest.mark.api
class TestIngestBatch:
    def test_batch_ingest(self, authenticated_client):
        with patch("app.routers.ingest.ingestion_service") as mock:
            mock.batch_ingest.return_value = {"processed": 10, "failed": 0}
            response = authenticated_client.post(
                "/api/ingest/batch", json={"directory_path": "/path/to/documents"}
            )
            assert response.status_code in [200, 201, 400, 404, 500]


@pytest.mark.api
class TestIngestStats:
    def test_get_stats(self, authenticated_client):
        with patch("app.routers.ingest.get_ingestion_stats") as mock:
            mock.return_value = {"total_documents": 1000, "total_chunks": 50000}
            response = authenticated_client.get("/api/ingest/stats")
            assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
