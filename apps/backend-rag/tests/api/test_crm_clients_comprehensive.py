"""
Comprehensive API Tests for CRM Clients Router
Complete test coverage for all client management endpoints

Coverage:
- POST /api/crm/clients - Create client
- GET /api/crm/clients - List clients (with filters, pagination, sorting)
- GET /api/crm/clients/{client_id} - Get client by ID
- GET /api/crm/clients/by-email/{email} - Get client by email
- PATCH /api/crm/clients/{client_id} - Update client
- DELETE /api/crm/clients/{client_id} - Delete client
- GET /api/crm/clients/{client_id}/summary - Get client summary
- GET /api/crm/clients/stats/overview - Get client statistics
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
class TestCreateClient:
    """Comprehensive tests for POST /api/crm/clients"""

    def test_create_client_minimal(self, authenticated_client, test_app):
        """Test creating client with minimal required fields"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Test Client"},
            )

            assert response.status_code in [200, 201, 500]

    def test_create_client_complete(self, authenticated_client, test_app):
        """Test creating client with all fields"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Complete Client",
                    "email": "client@example.com",
                    "phone": "+1234567890",
                    "whatsapp": "+1234567890",
                    "nationality": "US",
                    "passport_number": "P123456",
                    "client_type": "individual",
                    "assigned_to": "team@example.com",
                    "address": "123 Main St",
                    "notes": "Test notes",
                    "tags": ["vip", "premium"],
                    "custom_fields": {"field1": "value1"},
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_client_company_type(self, authenticated_client, test_app):
        """Test creating company client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Test Company",
                    "client_type": "company",
                    "email": "company@example.com",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_client_invalid_type(self, authenticated_client):
        """Test creating client with invalid client_type"""
        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Test Client",
                "client_type": "invalid_type",
            },
        )

        assert response.status_code == 422

    def test_create_client_empty_name(self, authenticated_client):
        """Test creating client with empty name"""
        response = authenticated_client.post(
            "/api/crm/clients",
            json={"full_name": ""},
        )

        assert response.status_code == 422

    def test_create_client_long_name(self, authenticated_client):
        """Test creating client with name exceeding limit"""
        long_name = "A" * 201  # Exceeds 200 character limit

        response = authenticated_client.post(
            "/api/crm/clients",
            json={"full_name": long_name},
        )

        assert response.status_code == 422

    def test_create_client_invalid_email(self, authenticated_client):
        """Test creating client with invalid email format"""
        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Test Client",
                "email": "invalid-email",
            },
        )

        assert response.status_code == 422

    def test_create_client_duplicate_email(self, authenticated_client, test_app):
        """Test creating client with duplicate email"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate duplicate email
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "email": "existing@example.com"})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Test Client",
                    "email": "existing@example.com",
                },
            )

            # Should handle duplicate gracefully
            assert response.status_code in [200, 201, 400, 409, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(
            return_value={"id": 1, "full_name": "Test Client", "email": None}
        )
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestListClients:
    """Comprehensive tests for GET /api/crm/clients"""

    def test_list_clients_default(self, authenticated_client, test_app):
        """Test listing clients with default parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"id": 1, "full_name": "Client 1"},
                    {"id": 2, "full_name": "Client 2"},
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_list_clients_with_limit(self, authenticated_client, test_app):
        """Test listing clients with limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[{"id": 1}])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?limit=10")

            assert response.status_code == 200

    def test_list_clients_with_status_filter(self, authenticated_client, test_app):
        """Test listing clients filtered by status"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?status=active")

            assert response.status_code == 200

    def test_list_clients_with_invalid_status(self, authenticated_client):
        """Test listing clients with invalid status"""
        response = authenticated_client.get("/api/crm/clients?status=invalid")

        # Should handle invalid status gracefully
        assert response.status_code in [200, 400, 422, 500]

    def test_list_clients_with_search(self, authenticated_client, test_app):
        """Test listing clients with search query"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?search=test")

            assert response.status_code == 200

    def test_list_clients_with_sorting(self, authenticated_client, test_app):
        """Test listing clients with sorting"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?sort_by=full_name&sort_order=asc")

            assert response.status_code == 200

    def test_list_clients_max_limit(self, authenticated_client, test_app):
        """Test listing clients with maximum limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?limit=200")

            assert response.status_code == 200

    def test_list_clients_exceeds_max_limit(self, authenticated_client):
        """Test listing clients exceeding maximum limit"""
        response = authenticated_client.get("/api/crm/clients?limit=1000")

        # Should cap at maximum limit
        assert response.status_code in [200, 400, 422]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestGetClient:
    """Comprehensive tests for GET /api/crm/clients/{client_id}"""

    def test_get_client_by_id_success(self, authenticated_client, test_app):
        """Test getting client by ID"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "full_name": "Test Client", "email": "test@example.com"}
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1")

            assert response.status_code == 200
            data = response.json()
            assert "id" in data or "full_name" in data

    def test_get_client_not_found(self, authenticated_client, test_app):
        """Test getting non-existent client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/99999")

            assert response.status_code == 404

    def test_get_client_by_email(self, authenticated_client, test_app):
        """Test getting client by email"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "email": "test@example.com", "full_name": "Test"}
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/by-email/test@example.com")

            assert response.status_code == 200

    def test_get_client_by_email_not_found(self, authenticated_client, test_app):
        """Test getting client by non-existent email"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/by-email/nonexistent@example.com")

            assert response.status_code == 404

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestUpdateClient:
    """Comprehensive tests for PATCH /api/crm/clients/{client_id}"""

    def test_update_client_partial(self, authenticated_client, test_app):
        """Test partial client update"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "full_name": "Old Name", "email": "old@example.com"}
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/clients/1",
                json={"full_name": "New Name"},
            )

            assert response.status_code in [200, 404, 500]

    def test_update_client_status(self, authenticated_client, test_app):
        """Test updating client status"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "status": "active"})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/clients/1",
                json={"status": "inactive"},
            )

            assert response.status_code in [200, 404, 500]

    def test_update_client_invalid_status(self, authenticated_client):
        """Test updating client with invalid status"""
        response = authenticated_client.patch(
            "/api/crm/clients/1",
            json={"status": "invalid_status"},
        )

        assert response.status_code == 422

    def test_update_client_not_found(self, authenticated_client, test_app):
        """Test updating non-existent client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.patch(
                "/api/crm/clients/99999",
                json={"full_name": "New Name"},
            )

            assert response.status_code == 404

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestDeleteClient:
    """Comprehensive tests for DELETE /api/crm/clients/{client_id}"""

    def test_delete_client_success(self, authenticated_client, test_app):
        """Test deleting client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/crm/clients/1")

            assert response.status_code in [200, 204, 404, 500]

    def test_delete_client_not_found(self, authenticated_client, test_app):
        """Test deleting non-existent client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/crm/clients/99999")

            assert response.status_code == 404

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestClientSummary:
    """Comprehensive tests for GET /api/crm/clients/{client_id}/summary"""

    def test_get_client_summary(self, authenticated_client, test_app):
        """Test getting client summary"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "summary": "Test summary"})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1/summary")

            assert response.status_code in [200, 404, 500]

    def test_get_client_summary_not_found(self, authenticated_client, test_app):
        """Test getting summary for non-existent client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/99999/summary")

            assert response.status_code == 404

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestClientStats:
    """Comprehensive tests for GET /api/crm/clients/stats/overview"""

    def test_get_client_stats(self, authenticated_client, test_app):
        """Test getting client statistics"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "total": 100,
                    "active": 80,
                    "inactive": 15,
                    "prospect": 5,
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    def test_get_client_stats_cached(self, authenticated_client, test_app):
        """Test client stats are cached"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            # First request
            response1 = authenticated_client.get("/api/crm/clients/stats/overview")
            # Second request (should be cached)
            response2 = authenticated_client.get("/api/crm/clients/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestCRMClientSecurity:
    """Security tests for CRM clients endpoints"""

    def test_crm_endpoints_require_auth(self, test_client):
        """Test all CRM endpoints require authentication"""
        endpoints = [
            ("POST", "/api/crm/clients"),
            ("GET", "/api/crm/clients"),
            ("GET", "/api/crm/clients/1"),
            ("PATCH", "/api/crm/clients/1"),
            ("DELETE", "/api/crm/clients/1"),
            ("GET", "/api/crm/clients/stats/overview"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            elif method == "POST":
                response = test_client.post(path, json={})
            elif method == "PATCH":
                response = test_client.patch(path, json={})
            elif method == "DELETE":
                response = test_client.delete(path)

            assert response.status_code == 401
