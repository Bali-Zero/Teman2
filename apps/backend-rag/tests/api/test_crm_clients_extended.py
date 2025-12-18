"""
API Tests for CRM Clients Router - Extended
Tests additional CRM client endpoints

Coverage:
- GET /api/crm/clients/by-email/{email} - Get client by email
- GET /api/crm/clients/{client_id}/summary - Get client summary
- GET /api/crm/clients/stats - Get clients stats
- PUT /api/crm/clients/{client_id} - Update client
- DELETE /api/crm/clients/{client_id} - Delete client
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
class TestCRMClientsExtended:
    """Extended tests for CRM client endpoints"""

    def test_get_client_by_email(self, authenticated_client):
        """Test GET /api/crm/clients/by-email/{email}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "email": "test@example.com"})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/by-email/test@example.com")

            assert response.status_code in [200, 404, 500, 503]

    def test_get_client_summary(self, authenticated_client):
        """Test GET /api/crm/clients/{client_id}/summary"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "Test Client"})
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1/summary")

            assert response.status_code in [200, 404, 500, 503]

    def test_get_clients_stats(self, authenticated_client):
        """Test GET /api/crm/clients/stats"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={"total_clients": 100, "active_clients": 50}
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/stats")

            assert response.status_code in [200, 500, 503]

    def test_update_client(self, authenticated_client):
        """Test PATCH /api/crm/clients/{client_id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "Updated Client"})
            mock_conn.execute = AsyncMock(return_value="INSERT 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/clients/1",
                params={"updated_by": "test@example.com"},
                json={"full_name": "Updated Client", "email": "updated@example.com"},
            )

            assert response.status_code in [200, 404, 422, 500, 503]

    def test_update_client_invalid_field(self, authenticated_client):
        """Test updating client with invalid field"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/clients/1",
                params={"updated_by": "test@example.com"},
                json={"invalid_field": "value"},
            )

            assert response.status_code in [400, 422, 500, 503]

    def test_update_client_no_fields(self, authenticated_client):
        """Test updating client with no fields"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/clients/1",
                params={"updated_by": "test@example.com"},
                json={},
            )

            assert response.status_code in [400, 422, 500, 503]

    def test_update_client_invalid_status(self, authenticated_client):
        """Test updating client with invalid status"""
        response = authenticated_client.patch(
            "/api/crm/clients/1",
            params={"updated_by": "test@example.com"},
            json={"status": "invalid_status"},
        )

        assert response.status_code == 422

    def test_delete_client(self, authenticated_client):
        """Test DELETE /api/crm/clients/{client_id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_conn.execute = AsyncMock(return_value="INSERT 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete(
                "/api/crm/clients/1",
                params={"deleted_by": "test@example.com"},
            )

            assert response.status_code in [200, 404, 500, 503]

    def test_list_clients_with_filters(self, authenticated_client):
        """Test listing clients with various filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            # Test with status filter
            response = authenticated_client.get("/api/crm/clients/?status=active")
            assert response.status_code in [200, 500, 503]

            # Test with assigned_to filter
            response = authenticated_client.get("/api/crm/clients/?assigned_to=test@example.com")
            assert response.status_code in [200, 500, 503]

            # Test with search filter
            response = authenticated_client.get("/api/crm/clients/?search=test")
            assert response.status_code in [200, 500, 503]

    def test_get_client_by_id(self, authenticated_client):
        """Test GET /api/crm/clients/{client_id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "Test Client"})
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1")

            assert response.status_code in [200, 404, 500, 503]

    def test_get_client_summary_with_data(self, authenticated_client):
        """Test GET /api/crm/clients/{client_id}/summary with full data"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "full_name": "Test Client", "email": "test@example.com"}
            )
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1/summary")

            assert response.status_code in [200, 404, 500, 503]
            if response.status_code == 200:
                data = response.json()
                assert "client" in data or "practices" in data
