"""
Unit tests for Portal Router

Tests cover:
- GET /api/portal/dashboard - Client dashboard
- GET /api/portal/visa - Visa status
- GET /api/portal/companies - Company list
- GET /api/portal/company/{id} - Company detail
- POST /api/portal/company/{id}/select - Set primary company
- GET /api/portal/taxes - Tax overview
- GET /api/portal/documents - Document list
- POST /api/portal/documents/upload - Upload document
- GET /api/portal/messages - Message list
- POST /api/portal/messages - Send message
- POST /api/portal/messages/{id}/read - Mark read
- GET /api/portal/settings - Get preferences
- PATCH /api/portal/settings - Update preferences
- GET /api/portal/timeline - Activity timeline
- GET /api/portal/profile - Client profile
- PATCH /api/portal/profile - Update profile

Authentication: Uses get_current_client which requires role='client' + linked_client_id
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.portal import (
    get_current_client,
    get_portal_service,
    router,
)

# ============================================
# FIXTURES
# ============================================


@pytest.fixture
def mock_portal_client():
    """Mock authenticated portal client."""
    return {
        "client_id": 42,
        "user_id": "client-uuid-456",
        "email": "client@example.com",
        "name": "John Doe",
    }


@pytest.fixture
def mock_portal_service():
    """Mock PortalService with all methods."""
    service = AsyncMock()
    return service


@pytest.fixture
def app(mock_portal_client, mock_portal_service, mock_db_pool):
    """Create FastAPI app with portal dependency overrides."""
    from backend.app.dependencies import get_database_pool

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_client] = lambda: mock_portal_client
    app.dependency_overrides[get_portal_service] = lambda: mock_portal_service
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return app


@pytest.fixture
def client(app):
    """TestClient for portal router."""
    return TestClient(app)


# ============================================
# DASHBOARD TESTS
# ============================================


class TestDashboard:
    """Tests for GET /api/portal/dashboard"""

    def test_dashboard_success(self, client, mock_portal_service):
        """Happy path: return dashboard data."""
        mock_portal_service.get_dashboard.return_value = {
            "active_visa": {"type": "KITAS", "status": "active"},
            "pending_documents": 3,
            "unread_messages": 1,
        }

        response = client.get("/api/portal/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "active_visa" in data["data"]

    def test_dashboard_service_error(self, client, mock_portal_service):
        """Service exception returns 500."""
        mock_portal_service.get_dashboard.side_effect = Exception("DB down")

        response = client.get("/api/portal/dashboard")
        assert response.status_code == 500


# ============================================
# VISA TESTS
# ============================================


class TestVisaStatus:
    """Tests for GET /api/portal/visa"""

    def test_visa_status_success(self, client, mock_portal_service):
        """Return visa information."""
        mock_portal_service.get_visa_status.return_value = {
            "current_visa": {"type": "KITAS", "expiry": "2027-01-15"},
            "history": [],
        }

        response = client.get("/api/portal/visa")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["current_visa"]["type"] == "KITAS"

    def test_visa_status_error(self, client, mock_portal_service):
        """Service error returns 500."""
        mock_portal_service.get_visa_status.side_effect = Exception("Service error")
        response = client.get("/api/portal/visa")
        assert response.status_code == 500


# ============================================
# COMPANY TESTS
# ============================================


class TestCompanies:
    """Tests for company endpoints"""

    def test_list_companies_success(self, client, mock_portal_service):
        """List all client companies."""
        mock_portal_service.get_companies.return_value = [
            {"id": 1, "name": "PT Example"},
            {"id": 2, "name": "CV Other"},
        ]

        response = client.get("/api/portal/companies")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2

    def test_company_detail_success(self, client, mock_portal_service):
        """Get company detail with camelCase mapping."""
        mock_portal_service.get_company_detail.return_value = {
            "id": 1,
            "name": "PT Example",
            "akta_no": "AKT-001",
            "akta_date": "2025-01-15",
            "sk_number": "SK-001",
            "tax_office": "KPP Denpasar",
            "company_status": "ACTIVE",
            "investment_type": "PMA",
            "authorized_capital": 1000000000,
            "ownership": {"is_primary": True},
        }

        response = client.get("/api/portal/company/1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["isPrimary"] is True
        assert data["data"]["aktaNo"] == "AKT-001"
        assert data["data"]["skNumber"] == "SK-001"

    def test_company_detail_not_found(self, client, mock_portal_service):
        """Company not found returns 404."""
        mock_portal_service.get_company_detail.return_value = None

        response = client.get("/api/portal/company/999")
        assert response.status_code == 404

    def test_set_primary_company_success(self, client, mock_portal_service):
        """Set primary company."""
        mock_portal_service.set_primary_company.return_value = {"id": 1, "primary": True}

        response = client.post("/api/portal/company/1/select")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_set_primary_company_invalid(self, client, mock_portal_service):
        """Invalid company raises ValueError -> 400."""
        mock_portal_service.set_primary_company.side_effect = ValueError("Company not linked")

        response = client.post("/api/portal/company/999/select")
        assert response.status_code == 400


# ============================================
# TAX TESTS
# ============================================


class TestTaxOverview:
    """Tests for GET /api/portal/taxes"""

    def test_tax_overview_success(self, client, mock_portal_service):
        """Return tax data."""
        mock_portal_service.get_tax_overview.return_value = {
            "obligations": [],
            "upcoming_deadlines": [],
        }

        response = client.get("/api/portal/taxes")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================
# DOCUMENT TESTS
# ============================================


class TestDocuments:
    """Tests for document endpoints"""

    def test_list_documents_success(self, client, mock_portal_service):
        """List client documents."""
        mock_portal_service.get_documents.return_value = [
            {"id": 1, "type": "passport", "status": "valid"},
        ]

        response = client.get("/api/portal/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1

    def test_list_documents_with_filter(self, client, mock_portal_service):
        """Filter documents by type."""
        mock_portal_service.get_documents.return_value = []

        response = client.get(
            "/api/portal/documents",
            params={"document_type": "passport"},
        )

        assert response.status_code == 200
        mock_portal_service.get_documents.assert_called_once()
        call = mock_portal_service.get_documents.call_args
        assert call.args == (42,)
        assert call.kwargs["document_type"] == "passport"
        assert call.kwargs["current_user"]["client_id"] == 42

    def test_upload_document_no_filename(self, client):
        """Upload without filename returns 400 or 422 depending on validation layer."""
        response = client.post(
            "/api/portal/documents/upload",
            data={"document_type": "passport"},
            files={"file": ("", b"", "application/pdf")},
        )
        # Router returns 400 (HTTPException) but FastAPI may return 422 for form validation
        assert response.status_code in (400, 422)

    def test_upload_document_invalid_extension(self, client):
        """Upload with disallowed extension returns 400."""
        response = client.post(
            "/api/portal/documents/upload",
            data={"document_type": "passport"},
            files={"file": ("malware.exe", b"x" * 100, "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_document_too_large(self, client):
        """Upload exceeding 10MB returns 400."""
        large_content = b"x" * (10 * 1024 * 1024 + 1)
        response = client.post(
            "/api/portal/documents/upload",
            data={"document_type": "passport"},
            files={"file": ("big.pdf", large_content, "application/pdf")},
        )
        assert response.status_code == 400

    def test_upload_document_success(self, client, mock_portal_service):
        """Successful document upload."""
        mock_portal_service.upload_document.return_value = {
            "id": 10,
            "file_name": "passport.pdf",
        }

        response = client.post(
            "/api/portal/documents/upload",
            data={"document_type": "passport"},
            files={"file": ("passport.pdf", b"PDF_CONTENT", "application/pdf")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Document uploaded successfully"


# ============================================
# MESSAGE TESTS
# ============================================


class TestMessages:
    """Tests for message endpoints"""

    def test_get_messages_success(self, client, mock_portal_service):
        """List messages with pagination."""
        mock_portal_service.get_messages.return_value = {
            "messages": [{"id": 1, "content": "Hello"}],
            "total": 1,
        }

        response = client.get("/api/portal/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_send_message_success(self, client, mock_portal_service):
        """Send a message to team."""
        mock_portal_service.send_message.return_value = {
            "id": 5,
            "content": "Need help with visa",
        }

        response = client.post(
            "/api/portal/messages",
            json={"content": "Need help with visa"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Message sent"

    def test_mark_message_read(self, client, mock_portal_service):
        """Mark message as read."""
        mock_portal_service.mark_message_read.return_value = None

        response = client.post("/api/portal/messages/5/read")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================
# SETTINGS TESTS
# ============================================


class TestSettings:
    """Tests for settings endpoints"""

    def test_get_preferences_success(self, client, mock_portal_service):
        """Get client preferences."""
        mock_portal_service.get_preferences.return_value = {
            "email_notifications": True,
            "language": "en",
        }

        response = client.get("/api/portal/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["language"] == "en"

    def test_update_preferences_success(self, client, mock_portal_service):
        """Update preferences."""
        mock_portal_service.update_preferences.return_value = {
            "language": "id",
        }

        response = client.patch(
            "/api/portal/settings",
            json={"language": "id"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_preferences_no_changes(self, client):
        """Empty update returns no-change message."""
        response = client.patch(
            "/api/portal/settings",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No changes to apply"


# ============================================
# TIMELINE TESTS
# ============================================


class TestTimeline:
    """Tests for GET /api/portal/timeline"""

    def test_timeline_success(self, client, mock_portal_service):
        """Return activity timeline."""
        mock_portal_service.get_timeline.return_value = [
            {"type": "message", "content": "New message from team"},
        ]

        response = client.get("/api/portal/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================
# PROFILE TESTS
# ============================================


class TestProfile:
    """Tests for profile endpoints"""

    def test_get_profile_success(self, client, mock_db_pool):
        """Get client profile with all fields."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = {
            "id": 42,
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+62812345678",
            "whatsapp": "+62812345678",
            "nationality": "US",
            "passport_number": "C12345678",
            "passport_expiry": datetime(2028, 6, 15).date(),
            "date_of_birth": datetime(1985, 3, 20).date(),
            "gender": "M",
            "address": "Jl. Sunset Rd, Bali",
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "assigned_to": "agent@balizero.com",
            "assigned_to_name": "Agent Smith",
            "assigned_to_avatar": "https://example.com/avatar.jpg",
        }

        response = client.get("/api/portal/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["full_name"] == "John Doe"
        assert data["data"]["assigned_to"]["email"] == "agent@balizero.com"

    def test_get_profile_not_found(self, client, mock_db_pool):
        """Profile not found returns 404."""
        conn = mock_db_pool._mock_conn
        conn.fetchrow.return_value = None

        response = client.get("/api/portal/profile")
        assert response.status_code == 404

    def test_update_profile_success(self, client, mock_portal_service):
        """Update profile fields."""
        mock_portal_service.update_profile.return_value = {
            "phone": "+62899999999",
        }

        response = client.patch(
            "/api/portal/profile",
            json={"phone": "+62899999999"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
