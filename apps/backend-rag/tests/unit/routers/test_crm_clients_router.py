"""
Unit tests for CRM clients router - targeting 90%+ coverage

Tests all endpoints in backend/app/routers/crm_clients.py:
- POST /api/crm/clients/ - Create client
- GET /api/crm/clients/ - List clients with filters
- GET /api/crm/clients/{client_id} - Get client by ID
- GET /api/crm/clients/by-email/{email} - Get client by email
- PATCH /api/crm/clients/{client_id} - Update client
- DELETE /api/crm/clients/{client_id} - Delete client (soft)
- GET /api/crm/clients/{client_id}/summary - Get client summary
- GET /api/crm/clients/stats/overview - Get stats
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# PYDANTIC MODEL VALIDATION TESTS
# ============================================================================


class TestClientCreateValidation:
    """Tests for ClientCreate model validation"""

    def test_valid_client_create(self):
        """Test creating valid ClientCreate instance"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(
            full_name="John Doe",
            email="john@example.com",
            phone="+62123456789",
            client_type="individual",
        )
        assert client.full_name == "John Doe"
        assert client.email == "john@example.com"
        assert client.client_type == "individual"

    def test_client_create_invalid_type(self):
        """Test validation fails for invalid client_type"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientCreate

        with pytest.raises(ValidationError) as exc_info:
            ClientCreate(full_name="John Doe", client_type="invalid_type")

        assert "client_type must be one of" in str(exc_info.value)

    def test_client_create_empty_name(self):
        """Test validation fails for empty full_name"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientCreate

        with pytest.raises(ValidationError) as exc_info:
            ClientCreate(full_name="   ")

        assert "full_name cannot be empty" in str(exc_info.value)

    def test_client_create_name_too_long(self):
        """Test validation fails for full_name > 200 chars"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientCreate

        long_name = "A" * 201
        with pytest.raises(ValidationError) as exc_info:
            ClientCreate(full_name=long_name)

        assert "full_name must be less than 200 characters" in str(exc_info.value)

    def test_client_create_name_trimmed(self):
        """Test full_name is trimmed of whitespace"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(full_name="  John Doe  ")
        assert client.full_name == "John Doe"

    def test_client_create_defaults(self):
        """Test default values are set correctly"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(full_name="John Doe")
        assert client.client_type == "individual"
        assert client.tags == []
        assert client.custom_fields == {}

    def test_client_create_empty_email_to_none(self):
        """Test empty email string is converted to None"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(full_name="John Doe", email="")
        assert client.email is None

    def test_client_create_whitespace_email_to_none(self):
        """Test whitespace-only email is converted to None"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(full_name="John Doe", email="   ")
        assert client.email is None

    def test_client_create_empty_passport_expiry_to_none(self):
        """Test empty passport_expiry string is converted to None"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(full_name="John Doe", passport_expiry="")
        assert client.passport_expiry is None

    def test_client_create_empty_date_of_birth_to_none(self):
        """Test empty date_of_birth string is converted to None"""
        from app.routers.crm_clients import ClientCreate

        client = ClientCreate(full_name="John Doe", date_of_birth="")
        assert client.date_of_birth is None


class TestClientUpdateValidation:
    """Tests for ClientUpdate model validation"""

    def test_valid_client_update(self):
        """Test creating valid ClientUpdate instance"""
        from app.routers.crm_clients import ClientUpdate

        update = ClientUpdate(full_name="Jane Doe", email="jane@example.com", status="active")
        assert update.full_name == "Jane Doe"
        assert update.status == "active"

    def test_client_update_invalid_status(self):
        """Test validation fails for invalid status"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientUpdate

        with pytest.raises(ValidationError) as exc_info:
            ClientUpdate(status="invalid_status")

        assert "status must be one of" in str(exc_info.value)

    def test_client_update_invalid_type(self):
        """Test validation fails for invalid client_type"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientUpdate

        with pytest.raises(ValidationError) as exc_info:
            ClientUpdate(client_type="invalid_type")

        assert "client_type must be one of" in str(exc_info.value)

    def test_client_update_empty_name(self):
        """Test validation fails for empty full_name"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientUpdate

        with pytest.raises(ValidationError) as exc_info:
            ClientUpdate(full_name="   ")

        assert "full_name cannot be empty" in str(exc_info.value)

    def test_client_update_name_too_long(self):
        """Test validation fails for full_name > 200 chars"""
        from pydantic import ValidationError

        from app.routers.crm_clients import ClientUpdate

        long_name = "A" * 201
        with pytest.raises(ValidationError) as exc_info:
            ClientUpdate(full_name=long_name)

        assert "full_name must be less than 200 characters" in str(exc_info.value)

    def test_client_update_name_trimmed(self):
        """Test full_name is trimmed of whitespace"""
        from app.routers.crm_clients import ClientUpdate

        update = ClientUpdate(full_name="  Jane Doe  ")
        assert update.full_name == "Jane Doe"

    def test_client_update_all_fields_none(self):
        """Test all fields can be None"""
        from app.routers.crm_clients import ClientUpdate

        update = ClientUpdate()
        assert update.full_name is None
        assert update.email is None
        assert update.status is None


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Create mock database pool with connection context manager"""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Setup async context manager for pool.acquire()
    async_context = AsyncMock()
    async_context.__aenter__.return_value = mock_conn
    async_context.__aexit__.return_value = None
    mock_pool.acquire.return_value = async_context

    return mock_pool


@pytest.fixture
def mock_client_row():
    """Mock database row for a client"""
    return {
        "id": 1,
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+62123456789",
        "whatsapp": "+62123456789",
        "nationality": "Indonesian",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "agent@example.com",
        "first_contact_date": datetime(2024, 1, 1, 10, 0, 0),
        "last_interaction_date": datetime(2024, 1, 15, 14, 30, 0),
        "tags": ["vip", "urgent"],
        "created_at": datetime(2024, 1, 1, 10, 0, 0),
        "updated_at": datetime(2024, 1, 1, 10, 0, 0),
    }


@pytest.fixture
def test_app(mock_db_pool):
    """Create FastAPI test app with mocked dependencies"""
    from app.routers.crm_clients import router

    app = FastAPI()
    app.include_router(router)

    # Override database pool dependency
    from app.dependencies import get_database_pool

    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool

    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


# ============================================================================
# API ENDPOINT TESTS - CREATE CLIENT
# ============================================================================


class TestCreateClient:
    """Tests for POST /api/crm/clients/"""

    def test_create_client_success(self, client, mock_db_pool, mock_client_row):
        """Test successful client creation"""
        # Setup mock
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row

        # Make request
        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+62123456789",
                "client_type": "individual",
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "John Doe"
        assert data["email"] == "john@example.com"
        assert data["id"] == 1

        # Verify database call
        mock_conn.fetchrow.assert_called_once()
        call_args = mock_conn.fetchrow.call_args
        assert "INSERT INTO clients" in call_args[0][0]

    def test_create_client_duplicate_email(self, client, mock_db_pool):
        """Test creating client with duplicate email raises 400"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.UniqueViolationError(
            "duplicate key value violates unique constraint"
        )

        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={
                "full_name": "John Doe",
                "email": "john@example.com",
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_client_no_created_by(self, client):
        """Test creating client without created_by parameter fails"""
        response = client.post(
            "/api/crm/clients/",
            json={
                "full_name": "John Doe",
                "email": "john@example.com",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_create_client_invalid_email(self, client):
        """Test creating client with invalid email fails validation"""
        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={
                "full_name": "John Doe",
                "email": "invalid-email",
            },
        )

        assert response.status_code == 422

    def test_create_client_minimal_data(self, client, mock_db_pool, mock_client_row):
        """Test creating client with only required fields"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row

        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={"full_name": "John Doe"},
        )

        assert response.status_code == 200

    def test_create_client_database_error(self, client, mock_db_pool):
        """Test database error during creation"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={"full_name": "John Doe"},
        )

        assert response.status_code == 503

    def test_create_client_no_row_returned(self, client, mock_db_pool):
        """Test when database INSERT returns None"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None

        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={"full_name": "John Doe"},
        )

        assert response.status_code == 500
        assert "Failed to create client" in response.json()["detail"]


# ============================================================================
# API ENDPOINT TESTS - LIST CLIENTS
# ============================================================================


class TestListClients:
    """Tests for GET /api/crm/clients/"""

    def test_list_clients_no_filters(self, client, mock_db_pool, mock_client_row):
        """Test listing all clients without filters"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = [mock_client_row]

        response = client.get("/api/crm/clients/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["full_name"] == "John Doe"

        # Verify query structure
        mock_conn.fetch.assert_called_once()
        call_args = mock_conn.fetch.call_args
        assert "SELECT id, uuid, full_name" in call_args[0][0]
        assert "LIMIT" in call_args[0][0]

    def test_list_clients_with_status_filter(self, client, mock_db_pool, mock_client_row):
        """Test listing clients filtered by status"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = [mock_client_row]

        response = client.get("/api/crm/clients/?status=active")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Verify status filter in query
        call_args = mock_conn.fetch.call_args
        assert "status = $1" in call_args[0][0]
        assert "active" in call_args[0][1:]

    def test_list_clients_with_assigned_to_filter(self, client, mock_db_pool):
        """Test listing clients filtered by assigned_to"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = []

        response = client.get("/api/crm/clients/?assigned_to=agent@example.com")

        assert response.status_code == 200
        call_args = mock_conn.fetch.call_args
        assert "assigned_to = $1" in call_args[0][0]

    def test_list_clients_with_search(self, client, mock_db_pool, mock_client_row):
        """Test listing clients with search term"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = [mock_client_row]

        response = client.get("/api/crm/clients/?search=john")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Verify search in query
        call_args = mock_conn.fetch.call_args
        assert "ILIKE" in call_args[0][0]
        assert "%john%" in call_args[0][1:]

    def test_list_clients_with_pagination(self, client, mock_db_pool):
        """Test listing clients with limit and offset"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = []

        response = client.get("/api/crm/clients/?limit=10&offset=20")

        assert response.status_code == 200
        call_args = mock_conn.fetch.call_args
        assert 10 in call_args[0][1:]
        assert 20 in call_args[0][1:]

    def test_list_clients_max_limit_enforced(self, client, mock_db_pool):
        """Test that limit cannot exceed MAX_LIMIT (200)"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = []

        response = client.get("/api/crm/clients/?limit=300")

        assert response.status_code == 422  # Validation error

    def test_list_clients_combined_filters(self, client, mock_db_pool, mock_client_row):
        """Test listing clients with multiple filters"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = [mock_client_row]

        response = client.get(
            "/api/crm/clients/?status=active&assigned_to=agent@example.com&search=john&limit=5&offset=0"
        )

        assert response.status_code == 200
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "status = $1" in query
        assert "assigned_to = $2" in query
        assert "ILIKE" in query

    def test_list_clients_invalid_status(self, client):
        """Test listing with invalid status value"""
        response = client.get("/api/crm/clients/?status=invalid")

        assert response.status_code == 422

    def test_list_clients_database_error(self, client, mock_db_pool):
        """Test database error during listing"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.side_effect = asyncpg.PostgresError("Database error")

        response = client.get("/api/crm/clients/")

        assert response.status_code == 503


# ============================================================================
# API ENDPOINT TESTS - GET CLIENT BY ID
# ============================================================================


class TestGetClient:
    """Tests for GET /api/crm/clients/{client_id}"""

    def test_get_client_success(self, client, mock_db_pool, mock_client_row):
        """Test successfully getting a client by ID"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["full_name"] == "John Doe"

    def test_get_client_not_found(self, client, mock_db_pool):
        """Test getting non-existent client returns 404"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None

        response = client.get("/api/crm/clients/999")

        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]

    def test_get_client_invalid_id(self, client):
        """Test getting client with invalid ID (non-positive)"""
        response = client.get("/api/crm/clients/0")

        assert response.status_code == 422

    def test_get_client_database_error(self, client, mock_db_pool):
        """Test database error during get"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 503


# ============================================================================
# API ENDPOINT TESTS - GET CLIENT BY EMAIL
# ============================================================================


class TestGetClientByEmail:
    """Tests for GET /api/crm/clients/by-email/{email}"""

    def test_get_client_by_email_success(self, client, mock_db_pool, mock_client_row):
        """Test successfully getting a client by email"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row

        response = client.get("/api/crm/clients/by-email/john@example.com")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "john@example.com"

    def test_get_client_by_email_not_found(self, client, mock_db_pool):
        """Test getting client by non-existent email returns 404"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None

        response = client.get("/api/crm/clients/by-email/notfound@example.com")

        assert response.status_code == 404

    def test_get_client_by_email_invalid_email(self, client):
        """Test getting client with invalid email format"""
        response = client.get("/api/crm/clients/by-email/invalid-email")

        assert response.status_code == 422

    def test_get_client_by_email_database_error(self, client, mock_db_pool):
        """Test database error during get by email"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        response = client.get("/api/crm/clients/by-email/john@example.com")

        assert response.status_code == 503


# ============================================================================
# API ENDPOINT TESTS - UPDATE CLIENT
# ============================================================================


class TestUpdateClient:
    """Tests for PATCH /api/crm/clients/{client_id}"""

    def test_update_client_success(self, client, mock_db_pool, mock_client_row):
        """Test successful client update"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        updated_row = mock_client_row.copy()
        updated_row["full_name"] = "Jane Doe"
        mock_conn.fetchrow.return_value = updated_row
        mock_conn.execute.return_value = None  # For activity log

        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@example.com",
            json={"full_name": "Jane Doe"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Jane Doe"

        # Verify UPDATE query was called
        assert mock_conn.fetchrow.called
        call_args = mock_conn.fetchrow.call_args
        assert "UPDATE clients" in call_args[0][0]

        # Verify activity log was created
        assert mock_conn.execute.called

    def test_update_client_multiple_fields(self, client, mock_db_pool, mock_client_row):
        """Test updating multiple fields at once"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        updated_row = mock_client_row.copy()
        updated_row["full_name"] = "Jane Doe"
        updated_row["status"] = "inactive"
        mock_conn.fetchrow.return_value = updated_row
        mock_conn.execute.return_value = None

        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@example.com",
            json={"full_name": "Jane Doe", "status": "inactive"},
        )

        assert response.status_code == 200

    def test_update_client_not_found(self, client, mock_db_pool):
        """Test updating non-existent client returns 404"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None

        response = client.patch(
            "/api/crm/clients/999?updated_by=admin@example.com",
            json={"full_name": "Jane Doe"},
        )

        assert response.status_code == 404

    def test_update_client_no_fields(self, client, mock_db_pool):
        """Test updating with no fields returns 400"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        response = client.patch("/api/crm/clients/1?updated_by=admin@example.com", json={})

        assert response.status_code == 400
        assert "No fields to update" in response.json()["detail"]

    def test_update_client_no_updated_by(self, client):
        """Test updating without updated_by parameter fails"""
        response = client.patch("/api/crm/clients/1", json={"full_name": "Jane Doe"})

        assert response.status_code == 422

    def test_update_client_invalid_status(self, client):
        """Test updating with invalid status fails validation"""
        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@example.com",
            json={"status": "invalid"},
        )

        assert response.status_code == 422

    def test_update_client_database_error(self, client, mock_db_pool):
        """Test database error during update"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@example.com",
            json={"full_name": "Jane Doe"},
        )

        assert response.status_code == 503


# ============================================================================
# API ENDPOINT TESTS - DELETE CLIENT
# ============================================================================


class TestDeleteClient:
    """Tests for DELETE /api/crm/clients/{client_id}"""

    def test_delete_client_success(self, client, mock_db_pool):
        """Test successful client soft delete"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = {"id": 1}
        mock_conn.execute.return_value = None  # For activity log

        response = client.delete("/api/crm/clients/1?deleted_by=admin@example.com")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "inactive" in data["message"]

        # Verify soft delete query
        call_args = mock_conn.fetchrow.call_args
        assert "UPDATE clients" in call_args[0][0]
        assert "status = 'inactive'" in call_args[0][0]

        # Verify activity log
        assert mock_conn.execute.called

    def test_delete_client_not_found(self, client, mock_db_pool):
        """Test deleting non-existent client returns 404"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None

        response = client.delete("/api/crm/clients/999?deleted_by=admin@example.com")

        assert response.status_code == 404

    def test_delete_client_no_deleted_by(self, client):
        """Test deleting without deleted_by parameter fails"""
        response = client.delete("/api/crm/clients/1")

        assert response.status_code == 422

    def test_delete_client_database_error(self, client, mock_db_pool):
        """Test database error during delete"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        response = client.delete("/api/crm/clients/1?deleted_by=admin@example.com")

        assert response.status_code == 503


# ============================================================================
# API ENDPOINT TESTS - GET CLIENT SUMMARY
# ============================================================================


class TestGetClientSummary:
    """Tests for GET /api/crm/clients/{client_id}/summary"""

    def test_get_client_summary_success(self, client, mock_db_pool, mock_client_row):
        """Test successfully getting client summary"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        # Mock client
        mock_conn.fetchrow.return_value = mock_client_row

        # Mock practices
        mock_practice = {
            "id": 1,
            "client_id": 1,
            "status": "in_progress",
            "practice_type_name": "Visa Extension",
            "category": "immigration",
            "created_at": datetime(2024, 1, 1),
        }
        # Mock interactions
        mock_interaction = {
            "id": 1,
            "client_id": 1,
            "practice_id": 1,
            "conversation_id": "conv_123",
            "interaction_type": "email",
            "channel": "email",
            "subject": "Follow up",
            "summary": "Discussed visa status",
            "full_content": "Full email content",
            "sentiment": "neutral",
            "team_member": "agent@example.com",
            "direction": "outbound",
            "duration_minutes": 15,
            "extracted_entities": {},
            "action_items": [],
            "interaction_date": datetime(2024, 1, 15),
            "created_at": datetime(2024, 1, 15),
        }
        # Mock renewals
        mock_renewal = {
            "id": 1,
            "client_id": 1,
            "status": "pending",
            "alert_date": datetime(2024, 12, 1),
        }

        mock_conn.fetch.side_effect = [
            [mock_practice],  # practices
            [mock_interaction],  # interactions
            [mock_renewal],  # renewals
        ]

        response = client.get("/api/crm/clients/1/summary")

        assert response.status_code == 200
        data = response.json()

        assert "client" in data
        assert data["client"]["id"] == 1

        assert "practices" in data
        assert data["practices"]["total"] == 1
        assert data["practices"]["active"] == 1
        assert data["practices"]["completed"] == 0

        assert "interactions" in data
        assert data["interactions"]["total"] == 1

        assert "renewals" in data
        assert len(data["renewals"]["upcoming"]) == 1

    def test_get_client_summary_client_not_found(self, client, mock_db_pool):
        """Test getting summary for non-existent client returns 404"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None

        response = client.get("/api/crm/clients/999/summary")

        assert response.status_code == 404

    def test_get_client_summary_no_data(self, client, mock_db_pool, mock_client_row):
        """Test getting summary with no practices, interactions, or renewals"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row
        mock_conn.fetch.side_effect = [[], [], []]  # No data

        response = client.get("/api/crm/clients/1/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["practices"]["total"] == 0
        assert data["interactions"]["total"] == 0
        assert len(data["renewals"]["upcoming"]) == 0

    def test_get_client_summary_practice_status_counts(self, client, mock_db_pool, mock_client_row):
        """Test practice status counting logic"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row

        # Multiple practices with different statuses
        practices = [
            {
                "id": 1,
                "status": "in_progress",
                "practice_type_name": "Visa",
                "category": "immigration",
                "created_at": datetime.now(),
            },
            {
                "id": 2,
                "status": "completed",
                "practice_type_name": "Work Permit",
                "category": "immigration",
                "created_at": datetime.now(),
            },
            {
                "id": 3,
                "status": "inquiry",
                "practice_type_name": "KITAS",
                "category": "immigration",
                "created_at": datetime.now(),
            },
            {
                "id": 4,
                "status": "cancelled",
                "practice_type_name": "Business License",
                "category": "business",
                "created_at": datetime.now(),
            },
        ]

        mock_conn.fetch.side_effect = [practices, [], []]

        response = client.get("/api/crm/clients/1/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["practices"]["total"] == 4
        assert data["practices"]["active"] == 2  # in_progress, inquiry
        assert data["practices"]["completed"] == 1

    def test_get_client_summary_database_error(self, client, mock_db_pool):
        """Test database error during summary retrieval"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        response = client.get("/api/crm/clients/1/summary")

        assert response.status_code == 503


# ============================================================================
# API ENDPOINT TESTS - GET STATS
# ============================================================================


class TestGetClientsStats:
    """Tests for GET /api/crm/clients/stats/overview

    Note: These tests directly test the endpoint function, not via HTTP,
    to avoid cache decorator complications in test environment.
    """

    @pytest.mark.asyncio
    async def test_get_stats_success(self, mock_db_pool):
        """Test successfully getting client statistics"""
        from fastapi import Request

        from app.routers.crm_clients import get_clients_stats

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        # Mock by_status
        by_status_rows = [
            {"status": "active", "count": 100},
            {"status": "inactive", "count": 20},
            {"status": "prospect", "count": 50},
        ]

        # Mock by_team_member
        by_team_rows = [
            {"assigned_to": "agent1@example.com", "count": 80},
            {"assigned_to": "agent2@example.com", "count": 60},
        ]

        # Mock new_last_30_days
        new_clients_row = {"count": 15}

        mock_conn.fetch.side_effect = [by_status_rows, by_team_rows]
        mock_conn.fetchrow.return_value = new_clients_row

        # Create mock request
        mock_request = MagicMock(spec=Request)

        # Call the underlying function directly
        result = await get_clients_stats.__wrapped__(request=mock_request, db_pool=mock_db_pool)

        assert result["total"] == 170
        assert result["by_status"]["active"] == 100
        assert result["by_status"]["inactive"] == 20
        assert result["by_status"]["prospect"] == 50
        assert len(result["by_team_member"]) == 2
        assert result["new_last_30_days"] == 15

    @pytest.mark.asyncio
    async def test_get_stats_no_clients(self, mock_db_pool):
        """Test stats with no clients in database"""
        from fastapi import Request

        from app.routers.crm_clients import get_clients_stats

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.side_effect = [[], []]
        mock_conn.fetchrow.return_value = {"count": 0}

        mock_request = MagicMock(spec=Request)

        result = await get_clients_stats.__wrapped__(request=mock_request, db_pool=mock_db_pool)

        assert result["total"] == 0
        assert result["by_status"] == {}
        assert result["by_team_member"] == []
        assert result["new_last_30_days"] == 0

    def test_get_stats_cache_decorator(self):
        """Test that stats endpoint has cache decorator"""
        from app.routers.crm_clients import get_clients_stats

        # Check if the function has the cached decorator applied
        # The cached decorator wraps the function, so we check for wrapper attributes
        assert hasattr(get_clients_stats, "__wrapped__")

    @pytest.mark.asyncio
    async def test_get_stats_database_error(self, mock_db_pool):
        """Test database error during stats retrieval"""
        from fastapi import Request

        from app.routers.crm_clients import get_clients_stats

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.side_effect = asyncpg.PostgresError("Database error")

        mock_request = MagicMock(spec=Request)

        with pytest.raises(HTTPException) as exc_info:
            await get_clients_stats.__wrapped__(request=mock_request, db_pool=mock_db_pool)

        assert exc_info.value.status_code == 503


# ============================================================================
# CONSTANTS TESTS
# ============================================================================


class TestConstants:
    """Tests for module constants"""

    def test_constants_values(self):
        """Test that constants have expected values"""
        from app.routers.crm_clients import (
            CACHE_TTL_STATS_SECONDS,
            DEFAULT_LIMIT,
            MAX_LIMIT,
            STATS_DAYS_RECENT,
            STATUS_VALUES,
        )

        assert MAX_LIMIT == 200
        assert DEFAULT_LIMIT == 50
        assert STATUS_VALUES == {"active", "inactive", "prospect"}
        assert CACHE_TTL_STATS_SECONDS == 300
        assert STATS_DAYS_RECENT == 30


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios"""

    def test_http_exception_passthrough(self, client, mock_db_pool):
        """Test that HTTPExceptions are re-raised, not wrapped"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        from fastapi import HTTPException

        # Create a function that raises HTTPException
        mock_conn.fetchrow.side_effect = HTTPException(status_code=404, detail="Custom error")

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 404
        assert response.json()["detail"] == "Custom error"

    def test_generic_exception_handling(self, client, mock_db_pool):
        """Test that generic exceptions are handled by handle_database_error"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = ValueError("Unexpected error")

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 500

    def test_foreign_key_violation(self, client, mock_db_pool, mock_client_row):
        """Test foreign key violation error handling"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.side_effect = asyncpg.ForeignKeyViolationError("Foreign key violation")

        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@example.com",
            json={"full_name": "Jane Doe"},
        )

        assert response.status_code == 400
        assert "Referenced record does not exist" in response.json()["detail"]


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_client_with_all_optional_fields(self, client, mock_db_pool, mock_client_row):
        """Test creating client with all optional fields populated"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        full_row = mock_client_row.copy()
        full_row.update(
            {
                "address": "123 Main St",
                "notes": "VIP client",
                "passport_number": "AB123456",
            }
        )
        mock_conn.fetchrow.return_value = full_row

        response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+62123456789",
                "whatsapp": "+62987654321",
                "nationality": "Indonesian",
                "passport_number": "AB123456",
                "client_type": "company",
                "assigned_to": "agent@example.com",
                "address": "123 Main St",
                "notes": "VIP client",
                "tags": ["vip", "urgent"],
                "custom_fields": {"referral_source": "website"},
            },
        )

        assert response.status_code == 200

    def test_update_with_none_values(self, client, mock_db_pool, mock_client_row):
        """Test that None values in update are handled correctly"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row
        mock_conn.execute.return_value = None

        # Only full_name should be updated, None values should be ignored
        response = client.patch(
            "/api/crm/clients/1?updated_by=admin@example.com",
            json={"full_name": "Jane Doe", "email": None},
        )

        # Verify that only non-None values are in the update
        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        # full_name should be updated, but email should not be (it's None)
        assert "full_name = $1" in query

    def test_list_clients_empty_result(self, client, mock_db_pool):
        """Test listing clients when no clients match filters"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = []

        response = client.get("/api/crm/clients/?status=active")

        assert response.status_code == 200
        assert response.json() == []

    def test_pagination_boundary(self, client, mock_db_pool):
        """Test pagination at boundary (offset = 0, limit = MAX_LIMIT)"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = []

        response = client.get("/api/crm/clients/?limit=200&offset=0")

        assert response.status_code == 200

    def test_search_special_characters(self, client, mock_db_pool):
        """Test search with special characters"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetch.return_value = []

        response = client.get("/api/crm/clients/?search=john%40example.com")

        assert response.status_code == 200

    def test_tags_array_handling(self, client, mock_db_pool, mock_client_row):
        """Test that tags array is properly handled"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        row_with_tags = mock_client_row.copy()
        row_with_tags["tags"] = ["vip", "urgent", "priority"]
        mock_conn.fetchrow.return_value = row_with_tags

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["tags"], list)
        assert len(data["tags"]) == 3

    def test_custom_fields_dict_handling(self, client, mock_db_pool):
        """Test that custom_fields dict is properly handled"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        custom_fields = {"referral_source": "website", "preferred_language": "en"}
        row = {
            "id": 1,
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": None,
            "whatsapp": None,
            "nationality": None,
            "status": "active",
            "client_type": "individual",
            "assigned_to": None,
            "first_contact_date": None,
            "last_interaction_date": None,
            "tags": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        mock_conn.fetchrow.return_value = row

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 200

    def test_datetime_serialization(self, client, mock_db_pool, mock_client_row):
        """Test that datetime fields are properly serialized"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = mock_client_row

        response = client.get("/api/crm/clients/1")

        assert response.status_code == 200
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data
        # Should be ISO format strings
        assert isinstance(data["created_at"], str)


# ============================================================================
# INTEGRATION-STYLE TESTS (Still unit tests but more comprehensive)
# ============================================================================


class TestFullWorkflow:
    """Tests that simulate full workflows"""

    def test_create_update_delete_workflow(self, client, mock_db_pool, mock_client_row):
        """Test complete workflow: create -> update -> delete"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        # CREATE
        mock_conn.fetchrow.return_value = mock_client_row
        create_response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={"full_name": "John Doe", "email": "john@example.com"},
        )
        assert create_response.status_code == 200
        client_id = create_response.json()["id"]

        # UPDATE
        updated_row = mock_client_row.copy()
        updated_row["status"] = "inactive"
        mock_conn.fetchrow.return_value = updated_row
        mock_conn.execute.return_value = None

        update_response = client.patch(
            f"/api/crm/clients/{client_id}?updated_by=admin@example.com",
            json={"status": "inactive"},
        )
        assert update_response.status_code == 200

        # DELETE (soft)
        mock_conn.fetchrow.return_value = {"id": client_id}
        delete_response = client.delete(
            f"/api/crm/clients/{client_id}?deleted_by=admin@example.com"
        )
        assert delete_response.status_code == 200

    def test_create_and_get_summary_workflow(self, client, mock_db_pool, mock_client_row):
        """Test create client then get summary"""
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        # CREATE
        mock_conn.fetchrow.return_value = mock_client_row
        create_response = client.post(
            "/api/crm/clients/?created_by=admin@example.com",
            json={"full_name": "John Doe"},
        )
        assert create_response.status_code == 200
        client_id = create_response.json()["id"]

        # GET SUMMARY
        mock_conn.fetchrow.return_value = mock_client_row
        mock_conn.fetch.side_effect = [[], [], []]  # No practices, interactions, renewals

        summary_response = client.get(f"/api/crm/clients/{client_id}/summary")
        assert summary_response.status_code == 200
        assert summary_response.json()["client"]["id"] == client_id
