"""
Tests for CRM Clients Router
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import EmailStr

from app.setup.app_factory import create_app
from app.dependencies import get_database_pool


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    from contextlib import asynccontextmanager
    
    pool = AsyncMock()
    conn = AsyncMock()
    
    @asynccontextmanager
    async def acquire():
        yield conn
    
    pool.acquire = acquire
    return pool, conn


@pytest.fixture
def test_app(mock_db_pool):
    """Create test app without auth middleware"""
    from fastapi import FastAPI
    from app.routers import crm_clients
    
    # Create minimal app
    app = FastAPI()
    
    # Include router
    app.include_router(crm_clients.router)
    
    # Override database dependency
    pool, conn = mock_db_pool
    def override_get_database_pool():
        return pool
    
    app.dependency_overrides[get_database_pool] = override_get_database_pool
    
    return app


@pytest.fixture
def client(test_app):
    """Test client fixture"""
    return TestClient(test_app)


@pytest.fixture
def sample_client_data():
    """Sample client data for testing"""
    return {
        "id": 1,
        "uuid": "test-uuid-123",
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "whatsapp": "+1234567890",
        "nationality": "US",
        "passport_number": "AB123456",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "team@example.com",
        "first_contact_date": datetime.now(),
        "last_interaction_date": None,
        "tags": ["vip"],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


class TestCreateClient:
    """Tests for POST /api/crm/clients"""

    def test_create_client_success(self, client, mock_db_pool, sample_client_data):
        """Test successful client creation"""
        pool, conn = mock_db_pool

        # Create mock row that supports both dict access and attribute access
        mock_row = self._create_mock_row(sample_client_data)
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock()

        response = client.post(
            "/api/crm/clients/?created_by=test@example.com",
            json={
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "whatsapp": "+1234567890",
                "nationality": "US",
                "passport_number": "AB123456",
                "client_type": "individual",
                "assigned_to": "team@example.com",
                "tags": ["vip"],
            },
        )

        assert response.status_code == 200
        assert response.json()["full_name"] == "John Doe"
        assert response.json()["email"] == "john@example.com"
    
    @staticmethod
    def _create_mock_row(data):
        """Helper to create mock row with dict access"""
        mock_row = MagicMock()
        for key, value in data.items():
            setattr(mock_row, key, value)
        mock_row.__getitem__ = lambda self, key: data[key]
        mock_row.keys = lambda: data.keys()
        mock_row.values = lambda: data.values()
        mock_row.items = lambda: data.items()
        return mock_row

    def test_create_client_duplicate_email(self, client, mock_db_pool):
        """Test creating client with duplicate email"""
        import asyncpg

        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(
            side_effect=asyncpg.UniqueViolationError("duplicate key value")
        )

        response = client.post(
            "/api/crm/clients/?created_by=test@example.com",
            json={
                "full_name": "John Doe",
                "email": "existing@example.com",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()


class TestListClients:
    """Tests for GET /api/crm/clients"""

    def test_list_clients_success(self, client, mock_db_pool, sample_client_data):
        """Test successful client listing"""
        pool, conn = mock_db_pool

        mock_row = TestCreateClient._create_mock_row(sample_client_data)
        conn.fetch = AsyncMock(return_value=[mock_row])

        response = client.get("/api/crm/clients/")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["full_name"] == "John Doe"

    def test_list_clients_with_filters(self, client, mock_db_pool, sample_client_data):
        """Test listing clients with status filter"""
        pool, conn = mock_db_pool

        mock_row = TestCreateClient._create_mock_row(sample_client_data)
        conn.fetch = AsyncMock(return_value=[mock_row])

        response = client.get("/api/crm/clients/?status=active&limit=10&offset=0")

        assert response.status_code == 200
        conn.fetch.assert_called_once()

    def test_list_clients_with_search(self, client, mock_db_pool, sample_client_data):
        """Test listing clients with search query"""
        pool, conn = mock_db_pool

        mock_row = TestCreateClient._create_mock_row(sample_client_data)
        conn.fetch = AsyncMock(return_value=[mock_row])

        response = client.get("/api/crm/clients/?search=John")

        assert response.status_code == 200


class TestGetClient:
    """Tests for GET /api/crm/clients/{client_id}"""

    def test_get_client_success(self, client, mock_db_pool, sample_client_data):
        """Test successful client retrieval"""
        pool, conn = mock_db_pool

        mock_row = TestCreateClient._create_mock_row(sample_client_data)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["full_name"] == "John Doe"

    def test_get_client_not_found(self, client, mock_db_pool):
        """Test getting non-existent client"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(return_value=None)

        response = client.get("/api/crm/clients/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetClientByEmail:
    """Tests for GET /api/crm/clients/by-email/{email}"""

    def test_get_client_by_email_success(self, client, mock_db_pool, sample_client_data):
        """Test successful client retrieval by email"""
        pool, conn = mock_db_pool

        mock_row = TestCreateClient._create_mock_row(sample_client_data)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        response = client.get("/api/crm/clients/by-email/john@example.com")

        assert response.status_code == 200
        assert response.json()["email"] == "john@example.com"

    def test_get_client_by_email_not_found(self, client, mock_db_pool):
        """Test getting client by non-existent email"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(return_value=None)

        response = client.get("/api/crm/clients/by-email/nonexistent@example.com")

        assert response.status_code == 404


class TestUpdateClient:
    """Tests for PATCH /api/crm/clients/{client_id}"""

    def test_update_client_success(self, client, mock_db_pool, sample_client_data):
        """Test successful client update"""
        pool, conn = mock_db_pool

        updated_data = sample_client_data.copy()
        updated_data["full_name"] = "Jane Doe"
        updated_data["phone"] = "+9876543210"

        mock_row = TestCreateClient._create_mock_row(updated_data)
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock()

        response = client.patch(
            "/api/crm/clients/1?updated_by=test@example.com",
            json={
                "full_name": "Jane Doe",
                "phone": "+9876543210",
            },
        )

        assert response.status_code == 200
        assert response.json()["full_name"] == "Jane Doe"

    def test_update_client_not_found(self, client, mock_db_pool):
        """Test updating non-existent client"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(return_value=None)

        response = client.patch(
            "/api/crm/clients/999?updated_by=test@example.com",
            json={"full_name": "Jane Doe"},
        )

        assert response.status_code == 404

    def test_update_client_no_fields(self, client, mock_db_pool):
        """Test updating client with no fields"""
        pool, conn = mock_db_pool

        response = client.patch(
            "/api/crm/clients/1?updated_by=test@example.com",
            json={},
        )

        assert response.status_code == 400
        assert "no fields" in response.json()["detail"].lower()


class TestDeleteClient:
    """Tests for DELETE /api/crm/clients/{client_id}"""

    def test_delete_client_success(self, client, mock_db_pool):
        """Test successful client deletion (soft delete)"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 1}[key]

        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock()

        response = client.delete("/api/crm/clients/1?deleted_by=test@example.com")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_client_not_found(self, client, mock_db_pool):
        """Test deleting non-existent client"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(return_value=None)

        response = client.delete("/api/crm/clients/999?deleted_by=test@example.com")

        assert response.status_code == 404


class TestGetClientSummary:
    """Tests for GET /api/crm/clients/{client_id}/summary"""

    def test_get_client_summary_success(self, client, mock_db_pool, sample_client_data):
        """Test successful client summary retrieval"""
        pool, conn = mock_db_pool

        mock_client_row = TestCreateClient._create_mock_row(sample_client_data)
        conn.fetchrow = AsyncMock(return_value=mock_client_row)
        conn.fetch = AsyncMock(return_value=[])

        response = client.get("/api/crm/clients/1/summary")

        assert response.status_code == 200
        assert "client" in response.json()
        assert "practices" in response.json()
        assert "interactions" in response.json()
        assert "renewals" in response.json()

    def test_get_client_summary_not_found(self, client, mock_db_pool):
        """Test getting summary for non-existent client"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(return_value=None)

        response = client.get("/api/crm/clients/999/summary")

        assert response.status_code == 404


class TestGetClientsStats:
    """Tests for GET /api/crm/clients/stats/overview"""

    def test_get_clients_stats_success(self, client, mock_db_pool):
        """Test successful clients stats retrieval"""
        pool, conn = mock_db_pool

        mock_status_row = TestCreateClient._create_mock_row({"status": "active", "count": 10})
        mock_team_row = TestCreateClient._create_mock_row({"assigned_to": "team@example.com", "count": 5})
        mock_count_row = TestCreateClient._create_mock_row({"count": 3})

        conn.fetch = AsyncMock(side_effect=[[mock_status_row], [mock_team_row]])
        conn.fetchrow = AsyncMock(return_value=mock_count_row)

        response = client.get("/api/crm/clients/stats/overview")

        assert response.status_code == 200
        assert "total" in response.json()
        assert "by_status" in response.json()
        assert "by_team_member" in response.json()
        assert "new_last_30_days" in response.json()

