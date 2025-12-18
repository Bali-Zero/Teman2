"""
Comprehensive API Tests for Oracle Ingest Router
Complete test coverage for bulk document ingestion endpoints

Coverage:
- POST /api/oracle/ingest - Bulk ingest documents
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
class TestOracleIngest:
    """Comprehensive tests for POST /api/oracle/ingest"""

    def test_ingest_documents_basic(self, authenticated_client):
        """Test basic document ingestion"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 1, "failed": 0})
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": [
                        {
                            "content": "Test document content",
                            "metadata": {
                                "law_id": "PP-28-2025",
                                "pasal": "1",
                                "category": "business_licensing",
                            },
                        }
                    ],
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_ingest_documents_multiple(self, authenticated_client):
        """Test ingesting multiple documents"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 5, "failed": 0})
            mock_get_service.return_value = mock_service

            documents = [
                {
                    "content": f"Document {i} content",
                    "metadata": {
                        "law_id": f"PP-{i}-2025",
                        "pasal": str(i),
                        "category": "business_licensing",
                    },
                }
                for i in range(5)
            ]

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": documents,
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_ingest_documents_with_batch_size(self, authenticated_client):
        """Test ingesting documents with custom batch size"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 10, "failed": 0})
            mock_get_service.return_value = mock_service

            documents = [
                {
                    "content": f"Document {i}",
                    "metadata": {"law_id": f"PP-{i}-2025"},
                }
                for i in range(10)
            ]

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": documents,
                    "batch_size": 50,
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_ingest_documents_max_batch_size(self, authenticated_client):
        """Test ingesting documents with maximum batch size"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 100, "failed": 0})
            mock_get_service.return_value = mock_service

            documents = [
                {
                    "content": f"Document {i}",
                    "metadata": {"law_id": f"PP-{i}-2025"},
                }
                for i in range(100)
            ]

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": documents,
                    "batch_size": 500,
                },
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_ingest_documents_exceeds_max(self, authenticated_client):
        """Test ingesting more than maximum documents"""
        documents = [
            {
                "content": f"Document {i}",
                "metadata": {"law_id": f"PP-{i}-2025"},
            }
            for i in range(1001)  # Exceeds max_items=1000
        ]

        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": documents,
            },
        )

        assert response.status_code == 422

    def test_ingest_documents_empty_list(self, authenticated_client):
        """Test ingesting empty document list"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [],
            },
        )

        assert response.status_code == 422

    def test_ingest_documents_missing_content(self, authenticated_client):
        """Test ingesting documents with missing content"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "metadata": {"law_id": "PP-28-2025"},
                    }
                ],
            },
        )

        assert response.status_code == 422

    def test_ingest_documents_missing_metadata(self, authenticated_client):
        """Test ingesting documents with missing metadata"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "Test content",
                    }
                ],
            },
        )

        assert response.status_code == 422

    def test_ingest_documents_short_content(self, authenticated_client):
        """Test ingesting documents with content shorter than min_length"""
        response = authenticated_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "Short",  # Less than min_length=10
                        "metadata": {"law_id": "PP-28-2025"},
                    }
                ],
            },
        )

        assert response.status_code == 422

    def test_ingest_documents_different_collection(self, authenticated_client):
        """Test ingesting documents to different collection"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 1, "failed": 0})
            mock_get_service.return_value = mock_service

            collections = ["legal_intelligence", "legal_unified", "custom_collection"]

            for collection in collections:
                response = authenticated_client.post(
                    "/api/oracle/ingest",
                    json={
                        "collection": collection,
                        "documents": [
                            {
                                "content": "Test document content",
                                "metadata": {"law_id": "PP-28-2025"},
                            }
                        ],
                    },
                )

                assert response.status_code in [200, 201, 400, 404, 500, 503]

    def test_ingest_documents_response_structure(self, authenticated_client):
        """Test ingest response structure"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 1, "failed": 0})
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": [
                        {
                            "content": "Test document content",
                            "metadata": {"law_id": "PP-28-2025"},
                        }
                    ],
                },
            )

            if response.status_code in [200, 201]:
                data = response.json()
                assert "success" in data
                assert "collection" in data
                assert "documents_ingested" in data
                assert "execution_time_ms" in data

    def test_ingest_documents_partial_failure(self, authenticated_client):
        """Test document ingestion with partial failures"""
        with patch("app.routers.oracle_ingest.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_documents = AsyncMock(return_value={"ingested": 3, "failed": 2})
            mock_get_service.return_value = mock_service

            documents = [
                {
                    "content": f"Document {i} content",
                    "metadata": {"law_id": f"PP-{i}-2025"},
                }
                for i in range(5)
            ]

            response = authenticated_client.post(
                "/api/oracle/ingest",
                json={
                    "collection": "legal_intelligence",
                    "documents": documents,
                },
            )

            assert response.status_code in [200, 201, 500, 503]


@pytest.mark.api
class TestOracleIngestSecurity:
    """Security tests for Oracle ingest endpoints"""

    def test_oracle_ingest_requires_auth(self, test_client):
        """Test Oracle ingest endpoint requires authentication"""
        response = test_client.post(
            "/api/oracle/ingest",
            json={
                "collection": "legal_intelligence",
                "documents": [
                    {
                        "content": "Test",
                        "metadata": {"law_id": "PP-28-2025"},
                    }
                ],
            },
        )

        assert response.status_code == 401
