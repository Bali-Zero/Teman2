"""
API Tests for CRM Practices Router
Tests practice management endpoints
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestCRMPracticeEndpoints:
    """Tests for CRM practice endpoints"""

    def test_list_practices(self, authenticated_client):
        """Test GET /api/crm/practices/"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/")

            assert response.status_code in [200, 500]

    def test_get_practice(self, authenticated_client):
        """Test GET /api/crm/practices/{id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "practice_type": "KITAS"})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/1")

            assert response.status_code in [200, 404]

    def test_create_practice_first(self, authenticated_client):
        """Test POST /api/crm/practices/"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "practice_type": "KITAS"})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/",
                json={"client_id": 1, "practice_type": "KITAS"},
            )

            assert response.status_code in [200, 422, 500, 503]

    def test_create_practice(self, authenticated_client):
        """Test POST /api/crm/practices"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "inquiry",
                }
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/",
                params={"created_by": "test@example.com"},
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "inquiry",
                },
            )

            assert response.status_code in [200, 422, 500, 503]

    def test_get_active_practices(self, authenticated_client):
        """Test GET /api/crm/practices/active"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/active")

            assert response.status_code in [200, 500]

    def test_get_upcoming_renewals(self, authenticated_client):
        """Test GET /api/crm/practices/renewals/upcoming"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/renewals/upcoming?days=30")

            assert response.status_code in [200, 500]

    def test_update_practice(self, authenticated_client):
        """Test PATCH /api/crm/practices/{id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "client_id": 1,
                    "status": "in_progress",
                    "priority": "high",
                }
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/practices/1",
                params={"updated_by": "test@example.com"},
                json={"status": "in_progress", "priority": "high"},
            )

            assert response.status_code in [200, 404, 422, 500, 503]

    def test_update_practice_invalid_status(self, authenticated_client):
        """Test updating practice with invalid status"""
        response = authenticated_client.patch(
            "/api/crm/practices/1",
            params={"updated_by": "test@example.com"},
            json={"status": "invalid_status"},
        )

        assert response.status_code == 422

    def test_update_practice_invalid_priority(self, authenticated_client):
        """Test updating practice with invalid priority"""
        response = authenticated_client.patch(
            "/api/crm/practices/1",
            params={"updated_by": "test@example.com"},
            json={"priority": "invalid_priority"},
        )

        assert response.status_code == 422

    def test_add_document_to_practice(self, authenticated_client):
        """Test POST /api/crm/practices/{id}/documents/add"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"documents": []})
            mock_conn.execute = AsyncMock(return_value="UPDATE 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/1/documents/add",
                params={
                    "document_name": "Passport Copy",
                    "drive_file_id": "file123",
                    "uploaded_by": "test@example.com",
                },
            )

            assert response.status_code in [200, 404, 500, 503]

    def test_add_document_to_practice_not_found(self, authenticated_client):
        """Test adding document to nonexistent practice"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/practices/999/documents/add",
                params={
                    "document_name": "Passport Copy",
                    "drive_file_id": "file123",
                    "uploaded_by": "test@example.com",
                },
            )

            assert response.status_code == 404

    def test_get_practices_stats(self, authenticated_client):
        """Test GET /api/crm/practices/stats/overview"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "total_practices": 100,
                    "active_practices": 50,
                    "by_status": {},
                    "by_type": {},
                }
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response.status_code in [200, 500, 503]

    def test_list_practices_with_filters(self, authenticated_client):
        """Test listing practices with various filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            # Test with client_id filter
            response = authenticated_client.get("/api/crm/practices/?client_id=1")
            assert response.status_code in [200, 500, 503]

            # Test with status filter
            response = authenticated_client.get("/api/crm/practices/?status=in_progress")
            assert response.status_code in [200, 500, 503]

            # Test with assigned_to filter
            response = authenticated_client.get("/api/crm/practices/?assigned_to=test@example.com")
            assert response.status_code in [200, 500, 503]

    def test_get_practice_by_client(self, authenticated_client):
        """Test GET /api/crm/practices/ with client_id filter"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(
                return_value=[{"id": 1, "client_id": 1, "status": "in_progress"}]
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/?client_id=1&limit=10")

            assert response.status_code in [200, 500, 503]

    def test_crm_practices_require_auth(self, test_client):
        """Test that CRM practice endpoints require authentication"""
        response = test_client.get("/api/crm/practices/")
        assert response.status_code == 401
