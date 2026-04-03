"""
Unit tests for CRM Enhanced Router

Tests cover:
- GET /api/crm/clients/{id}/profile - Enhanced client profile
- PATCH /api/crm/clients/{id}/profile - Update client profile
- GET /api/crm/companies/by-client/{id} - Companies by client
- GET /api/crm/companies/{id}/documents - Company documents
- GET /api/crm/clients/{id}/family - Family members list
- POST /api/crm/clients/{id}/family - Create family member
- PATCH /api/crm/clients/{id}/family/{member_id} - Update family member
- DELETE /api/crm/clients/{id}/family/{member_id} - Delete family member
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.crm_enhanced import router


# ============================================
# FIXTURES
# ============================================


@pytest.fixture
def app(mock_current_user, mock_db_pool):
    """Create FastAPI app with CRM dependency overrides."""
    from backend.app.dependencies import get_current_user, get_database_pool

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return app


@pytest.fixture
def client(app):
    """TestClient for CRM enhanced router."""
    return TestClient(app)


@pytest.fixture
def sample_client_row():
    """Mock client database row."""
    return {
        "id": 42,
        "uuid": "uuid-42",
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+62812345678",
        "whatsapp": "+62812345678",
        "nationality": "US",
        "passport_number": "C12345678",
        "passport_expiry": datetime(2028, 6, 15).date(),
        "date_of_birth": datetime(1985, 3, 20).date(),
        "gender": "M",
        "avatar_url": None,
        "company_name": "PT Example",
        "google_drive_folder_id": "folder-123",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "agent@balizero.com",
        "address": "Jl. Sunset Rd, Bali",
        "notes": "VIP client",
        "tags": ["vip"],
        "custom_fields": {},
        "first_contact_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_interaction_date": datetime(2026, 3, 15, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 15, tzinfo=timezone.utc),
        "visa_expiry_date": datetime(2027, 1, 15).date(),
        "current_visa_type": "KITAS",
        "current_visa_sponsor": "PT Sponsor",
        "passport_ocr_data": None,
        "birthplace": "New York",
    }


# ============================================
# CLIENT PROFILE TESTS
# ============================================


class TestGetClientProfile:
    """Tests for GET /api/crm/clients/{client_id}/profile"""

    def test_get_profile_success(self, client, mock_db_pool, sample_client_row):
        """Happy path: retrieve enhanced client profile."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = sample_client_row
        conn.fetch.return_value = []  # family members, documents, etc.
        conn.fetchval.return_value = 0  # counts

        response = client.get("/api/crm/clients/42/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_profile_not_found(self, client, mock_db_pool):
        """Client not found returns 404."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None

        response = client.get("/api/crm/clients/999/profile")
        assert response.status_code == 404


class TestUpdateClientProfile:
    """Tests for PATCH /api/crm/clients/{client_id}/profile"""

    def test_update_profile_success(self, client, mock_db_pool):
        """Update client profile fields."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = {"id": 42}  # Client exists
        conn.execute.return_value = "UPDATE 1"

        response = client.patch(
            "/api/crm/clients/42/profile",
            json={
                "avatar_url": "https://example.com/avatar.png",
                "date_of_birth": "1985-03-20",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_profile_no_fields(self, client, mock_db_pool):
        """No fields provided should still work (empty update)."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = {"id": 42}

        response = client.patch(
            "/api/crm/clients/42/profile",
            json={},
        )

        # Should either succeed or return appropriate response
        assert response.status_code in (200, 422)


# ============================================
# COMPANIES BY CLIENT TESTS
# ============================================


class TestCompaniesByClient:
    """Tests for GET /api/crm/companies/by-client/{client_id}"""

    def test_companies_by_client_success(self, client, mock_db_pool):
        """List companies linked to a client."""
        conn = mock_db_pool._mock_conn
        conn.fetch.return_value = [
            {
                "id": 1,
                "company_name": "PT Example",
                "nib": "12345",
                "is_primary": True,
                "investment_type": "PMA",
                "company_status": "ACTIVE",
            },
        ]

        response = client.get("/api/crm/companies/by-client/42")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_companies_by_client_empty(self, client, mock_db_pool):
        """Client with no companies returns empty list."""
        conn = mock_db_pool._mock_conn
        conn.fetch.return_value = []

        response = client.get("/api/crm/companies/by-client/42")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================
# COMPANY DOCUMENTS TESTS
# ============================================


class TestCompanyDocuments:
    """Tests for GET /api/crm/companies/{company_id}/documents"""

    def test_company_documents_success(self, client, mock_db_pool):
        """List documents for a company."""
        conn = mock_db_pool._mock_conn
        conn.fetch.return_value = [
            {
                "id": 1,
                "document_type": "nib",
                "file_name": "nib.pdf",
                "status": "valid",
            },
        ]

        response = client.get("/api/crm/companies/1/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================
# FAMILY MEMBER TESTS
# ============================================


class TestFamilyMembers:
    """Tests for family member CRUD endpoints"""

    def test_list_family_members_success(self, client, mock_db_pool):
        """List family members for a client."""
        conn = mock_db_pool._mock_conn
        conn.fetch.return_value = [
            {
                "id": 1,
                "full_name": "Jane Doe",
                "relationship": "spouse",
                "nationality": "US",
                "passport_number": "D98765",
                "passport_expiry": datetime(2029, 1, 1).date(),
                "date_of_birth": datetime(1987, 5, 10).date(),
                "current_visa_type": "KITAS",
                "visa_expiry": datetime(2027, 1, 15).date(),
                "email": "jane@example.com",
                "phone": "+62811111111",
                "notes": None,
                "created_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
        ]

        response = client.get("/api/crm/clients/42/family")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_create_family_member_success(self, client, mock_db_pool):
        """Create a new family member."""
        conn = mock_db_pool._mock_conn
        conn.fetchval.return_value = 10  # New member ID

        response = client.post(
            "/api/crm/clients/42/family",
            json={
                "full_name": "Baby Doe",
                "relationship": "child",
                "date_of_birth": "2023-05-15",
                "nationality": "US",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_create_family_member_missing_name(self, client):
        """Missing required full_name fails validation."""
        response = client.post(
            "/api/crm/clients/42/family",
            json={
                "relationship": "child",
            },
        )

        assert response.status_code == 422

    def test_update_family_member_success(self, client, mock_db_pool):
        """Update existing family member."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = {"id": 1}  # Member exists
        conn.execute.return_value = "UPDATE 1"

        response = client.patch(
            "/api/crm/clients/42/family/1",
            json={
                "passport_number": "E99999",
                "passport_expiry": "2030-01-01",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_family_member_not_found(self, client, mock_db_pool):
        """Update non-existent member returns 404."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None

        response = client.patch(
            "/api/crm/clients/42/family/999",
            json={"full_name": "Nobody"},
        )

        assert response.status_code == 404

    def test_delete_family_member_success(self, client, mock_db_pool):
        """Delete family member."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = {"id": 1}
        conn.execute.return_value = "DELETE 1"

        response = client.delete("/api/crm/clients/42/family/1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_family_member_not_found(self, client, mock_db_pool):
        """Delete non-existent member returns 404."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None

        response = client.delete("/api/crm/clients/42/family/999")

        assert response.status_code == 404
