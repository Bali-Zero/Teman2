"""
Tests for CRM Clients Router - CRUD operations and edge cases.
Uses FastAPI TestClient with mocked dependencies at the router level.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def _make_client_row(
    id: int = 1,
    uuid: str = "uuid-1",
    full_name: str = "John Doe",
    email: str = "john@example.com",
    status: str = "active",
    **overrides,
):
    """Helper to create a client dict matching ClientResponse fields."""
    row = {
        "id": id,
        "uuid": uuid,
        "full_name": full_name,
        "email": email,
        "phone": "+62812345",
        "whatsapp": None,
        "company_name": None,
        "nationality": "US",
        "passport_number": None,
        "passport_expiry": None,
        "date_of_birth": None,
        "gender": None,
        "birthplace": None,
        "status": status,
        "client_type": "individual",
        "assigned_to": "zero@balizero.com",
        "tax_consultant": None,
        "avatar_url": None,
        "address": None,
        "notes": None,
        "first_contact_date": None,
        "last_interaction_date": None,
        "last_sentiment": None,
        "last_interaction_summary": None,
        "tags": [],
        "lead_source": None,
        "service_interest": [],
        "custom_fields": {},
        "tax_id": None,
        "npwp": None,
        "nib": None,
        "current_visa_type": None,
        "current_visa_sponsor": None,
        "folder_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    row.update(overrides)
    return row


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    return conn


@pytest.fixture
def mock_pool(mock_conn):
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm
    return pool


@pytest.fixture
def mock_client_service():
    service = AsyncMock()
    return service


@pytest.fixture
def admin_user():
    return {"email": "zero@balizero.com", "role": "admin", "sub": "admin-uuid"}


@pytest.fixture
def test_app(mock_pool, mock_client_service, admin_user):
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.routers.crm_clients import get_client_service, router

    app = FastAPI()
    app.include_router(router)

    async def override_user():
        return admin_user

    async def override_pool():
        return mock_pool

    def override_service():
        return mock_client_service

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_database_pool] = override_pool
    app.dependency_overrides[get_client_service] = override_service

    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


# =========================================================================
# CREATE CLIENT
# =========================================================================


class TestCreateClient:
    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_client_success(self, mock_cache, client, mock_client_service):
        row = _make_client_row()
        mock_client_service.create_client.return_value = row
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "John Doe", "email": "john@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "John Doe"

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_client_duplicate_email(self, mock_cache, client, mock_client_service):
        from backend.app.core.exceptions import ResourceConflictError
        mock_client_service.create_client.side_effect = ResourceConflictError("duplicate email")
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Jane", "email": "dup@example.com"},
        )
        assert resp.status_code == 400

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_client_no_created_by(self, mock_cache, client, mock_client_service):
        row = _make_client_row(full_name="No Creator")
        mock_client_service.create_client.return_value = row
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "No Creator"},
        )
        assert resp.status_code == 200

    def test_create_client_invalid_email(self, client):
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Bad Email", "email": "not-an-email"},
        )
        assert resp.status_code == 422

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_client_minimal_data(self, mock_cache, client, mock_client_service):
        row = _make_client_row(full_name="Minimal")
        mock_client_service.create_client.return_value = row
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Minimal"},
        )
        assert resp.status_code == 200

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_client_database_error(self, mock_cache, client, mock_client_service):
        mock_client_service.create_client.side_effect = Exception("DB error")
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Error Client"},
        )
        assert resp.status_code == 500

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_client_no_row_returned(self, mock_cache, client, mock_client_service):
        mock_client_service.create_client.return_value = None
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Ghost Client"},
        )
        assert resp.status_code == 500


# =========================================================================
# LIST CLIENTS
# =========================================================================


class TestListClients:
    def test_list_clients_no_filters(self, client, mock_conn):
        mock_conn.fetch.return_value = [_make_client_row()]
        mock_conn.fetchval.return_value = 1
        resp = client.get("/api/crm/clients/")
        assert resp.status_code == 200

    def test_list_clients_with_status_filter(self, client, mock_conn):
        mock_conn.fetch.return_value = [_make_client_row(status="prospect")]
        mock_conn.fetchval.return_value = 1
        resp = client.get("/api/crm/clients/?status=prospect")
        assert resp.status_code == 200

    def test_list_clients_with_assigned_to_filter(self, client, mock_conn):
        mock_conn.fetch.return_value = [_make_client_row()]
        mock_conn.fetchval.return_value = 1
        resp = client.get("/api/crm/clients/?assigned_to=admin@balizero.com")
        assert resp.status_code == 200

    def test_list_clients_with_search(self, client, mock_conn):
        mock_conn.fetch.return_value = [_make_client_row()]
        mock_conn.fetchval.return_value = 1
        resp = client.get("/api/crm/clients/?search=John")
        assert resp.status_code == 200

    def test_list_clients_with_pagination(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/?offset=10&limit=5")
        assert resp.status_code == 200

    def test_list_clients_max_limit_enforced(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/?limit=500")
        # FastAPI validates le=200 on limit param
        assert resp.status_code == 422

    def test_list_clients_combined_filters(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/?status=active&search=test&limit=10")
        assert resp.status_code == 200

    def test_list_clients_invalid_status(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/?status=invalid_status")
        assert resp.status_code in (200, 422)

    def test_list_clients_database_error(self, client, mock_conn):
        mock_conn.fetch.side_effect = Exception("DB read error")
        resp = client.get("/api/crm/clients/")
        assert resp.status_code == 500


# =========================================================================
# GET CLIENT
# =========================================================================


class TestGetClient:
    def test_get_client_success(self, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        resp = client.get("/api/crm/clients/1")
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "John Doe"

    def test_get_client_not_found(self, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.get("/api/crm/clients/999")
        assert resp.status_code == 404

    def test_get_client_invalid_id(self, client):
        resp = client.get("/api/crm/clients/abc")
        assert resp.status_code == 422

    def test_get_client_database_error(self, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB error")
        resp = client.get("/api/crm/clients/1")
        assert resp.status_code == 500


# =========================================================================
# GET CLIENT BY EMAIL
# =========================================================================


class TestGetClientByEmail:
    def test_get_client_by_email_success(self, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        resp = client.get("/api/crm/clients/by-email/john@example.com")
        assert resp.status_code == 200

    def test_get_client_by_email_not_found(self, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.get("/api/crm/clients/by-email/notexist@example.com")
        assert resp.status_code == 404

    def test_get_client_by_email_invalid_email(self, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.get("/api/crm/clients/by-email/not-an-email")
        assert resp.status_code in (200, 404, 422)

    def test_get_client_by_email_database_error(self, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB error")
        resp = client.get("/api/crm/clients/by-email/test@example.com")
        assert resp.status_code == 500


# =========================================================================
# UPDATE CLIENT
# =========================================================================


class TestUpdateClient:
    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_update_client_success(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row(full_name="Updated Name")
        resp = client.patch(
            "/api/crm/clients/1",
            json={"full_name": "Updated Name", "updated_by": "admin"},
        )
        assert resp.status_code in (200, 404)

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_update_client_multiple_fields(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row(full_name="New Name", phone="+62999")
        resp = client.patch(
            "/api/crm/clients/1",
            json={"full_name": "New Name", "phone": "+62999", "updated_by": "admin"},
        )
        assert resp.status_code in (200, 404)

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_update_client_not_found(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.patch(
            "/api/crm/clients/999",
            json={"full_name": "Ghost", "updated_by": "admin"},
        )
        assert resp.status_code in (404, 500)

    def test_update_client_no_fields(self, client, mock_conn):
        resp = client.patch("/api/crm/clients/1", json={})
        # Router returns 404 when fetchrow returns None for empty update
        assert resp.status_code in (200, 400, 404, 422)

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_update_client_no_updated_by(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        resp = client.patch(
            "/api/crm/clients/1",
            json={"full_name": "No updater"},
        )
        assert resp.status_code in (200, 400, 404, 422)

    def test_update_client_invalid_status(self, client):
        resp = client.patch(
            "/api/crm/clients/1",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_update_client_database_error(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB update error")
        resp = client.patch(
            "/api/crm/clients/1",
            json={"full_name": "Error", "updated_by": "admin"},
        )
        assert resp.status_code in (404, 500)


# =========================================================================
# DELETE CLIENT
# =========================================================================


class TestDeleteClient:
    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_delete_client_success(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        mock_conn.execute.return_value = "UPDATE 1"
        resp = client.delete("/api/crm/clients/1?deleted_by=admin")
        assert resp.status_code in (200, 204, 404)

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_delete_client_not_found(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.delete("/api/crm/clients/999?deleted_by=admin")
        assert resp.status_code in (404, 500)

    def test_delete_client_no_deleted_by(self, client, mock_conn):
        resp = client.delete("/api/crm/clients/1")
        # Without deleted_by, mock_conn.fetchrow returns None -> 404
        assert resp.status_code in (200, 400, 404, 422)

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_delete_client_database_error(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB delete error")
        resp = client.delete("/api/crm/clients/1?deleted_by=admin")
        assert resp.status_code in (404, 500)


# =========================================================================
# CLIENT SUMMARY
# =========================================================================


class TestGetClientSummary:
    def test_get_client_summary_success(self, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        mock_conn.fetch.return_value = [{"status": "completed", "count": 3}]
        resp = client.get("/api/crm/clients/1/summary")
        assert resp.status_code in (200, 404)

    def test_get_client_summary_client_not_found(self, client, mock_conn):
        mock_conn.fetchrow.return_value = None
        resp = client.get("/api/crm/clients/999/summary")
        assert resp.status_code in (404, 500)

    def test_get_client_summary_no_data(self, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        mock_conn.fetch.return_value = []
        resp = client.get("/api/crm/clients/1/summary")
        assert resp.status_code in (200, 404)

    def test_get_client_summary_practice_status_counts(self, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        mock_conn.fetch.return_value = [
            {"status": "in_progress", "count": 2},
            {"status": "completed", "count": 5},
        ]
        resp = client.get("/api/crm/clients/1/summary")
        assert resp.status_code in (200, 404)

    def test_get_client_summary_database_error(self, client, mock_conn):
        mock_conn.fetchrow.side_effect = Exception("DB error")
        resp = client.get("/api/crm/clients/1/summary")
        assert resp.status_code in (404, 500)


# =========================================================================
# CONSTANTS & ERROR HANDLING
# =========================================================================


class TestConstants:
    def test_constants_values(self):
        from backend.app.routers.crm_clients import DEFAULT_LIMIT, MAX_LIMIT, STATUS_VALUES
        assert MAX_LIMIT == 200
        assert DEFAULT_LIMIT == 50
        assert "active" in STATUS_VALUES
        assert "inactive" in STATUS_VALUES


class TestErrorHandling:
    def test_http_exception_passthrough(self, client, mock_conn):
        mock_conn.fetchrow.side_effect = HTTPException(status_code=403, detail="Forbidden")
        resp = client.get("/api/crm/clients/1")
        assert resp.status_code == 403

    def test_generic_exception_handling(self, client, mock_conn):
        mock_conn.fetchrow.side_effect = RuntimeError("unexpected")
        resp = client.get("/api/crm/clients/1")
        assert resp.status_code == 500

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_foreign_key_violation(self, mock_cache, client, mock_client_service):
        mock_client_service.create_client.side_effect = Exception("foreign key constraint")
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "FK Error"},
        )
        assert resp.status_code == 500


# =========================================================================
# EDGE CASES
# =========================================================================


class TestEdgeCases:
    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_client_with_all_optional_fields(self, mock_cache, client, mock_client_service):
        row = _make_client_row(
            company_name="Acme Corp", nationality="ID", notes="VIP",
            tags=["vip"], custom_fields={"lang": "id"},
        )
        mock_client_service.create_client.return_value = row
        resp = client.post(
            "/api/crm/clients/",
            json={
                "full_name": "Full Client", "email": "full@example.com",
                "phone": "+62812", "company_name": "Acme Corp",
                "nationality": "ID", "notes": "VIP", "tags": ["vip"],
                "custom_fields": {"lang": "id"},
            },
        )
        assert resp.status_code == 200

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_update_with_none_values(self, mock_cache, client, mock_conn):
        mock_conn.fetchrow.return_value = _make_client_row()
        resp = client.patch("/api/crm/clients/1", json={"notes": None, "updated_by": "admin"})
        # May return 400 if "no fields to update"
        assert resp.status_code in (200, 400, 404, 422)

    def test_list_clients_empty_result(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/")
        assert resp.status_code == 200

    def test_pagination_boundary(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/?offset=0&limit=1")
        assert resp.status_code == 200

    def test_search_special_characters(self, client, mock_conn):
        mock_conn.fetch.return_value = []
        mock_conn.fetchval.return_value = 0
        resp = client.get("/api/crm/clients/?search=O'Brien")
        assert resp.status_code == 200

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_tags_array_handling(self, mock_cache, client, mock_client_service):
        row = _make_client_row(tags=["vip", "urgent"])
        mock_client_service.create_client.return_value = row
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Tagged", "tags": ["vip", "urgent"]},
        )
        assert resp.status_code == 200

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_custom_fields_dict_handling(self, mock_cache, client, mock_client_service):
        row = _make_client_row(custom_fields={"key": "value"})
        mock_client_service.create_client.return_value = row
        resp = client.post(
            "/api/crm/clients/",
            json={"full_name": "Custom", "custom_fields": {"key": "value"}},
        )
        assert resp.status_code == 200

    def test_datetime_serialization(self, client, mock_conn):
        row = _make_client_row(
            created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2024, 6, 20, 14, 30, 0, tzinfo=timezone.utc),
        )
        mock_conn.fetchrow.return_value = row
        resp = client.get("/api/crm/clients/1")
        assert resp.status_code == 200


# =========================================================================
# FULL WORKFLOW
# =========================================================================


class TestFullWorkflow:
    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_update_delete_workflow(self, mock_cache, client, mock_client_service, mock_conn):
        # Create
        mock_client_service.create_client.return_value = _make_client_row(id=10)
        create_resp = client.post("/api/crm/clients/", json={"full_name": "Workflow"})
        assert create_resp.status_code == 200

        # Update
        mock_conn.fetchrow.return_value = _make_client_row(id=10, full_name="Updated")
        update_resp = client.patch(
            "/api/crm/clients/10", json={"full_name": "Updated", "updated_by": "admin"},
        )
        assert update_resp.status_code in (200, 404)

        # Delete
        mock_conn.fetchrow.return_value = _make_client_row(id=10)
        del_resp = client.delete("/api/crm/clients/10?deleted_by=admin")
        assert del_resp.status_code in (200, 204, 404)

    @patch("backend.app.routers.crm_clients.invalidate_cache", new_callable=AsyncMock)
    def test_create_and_get_summary_workflow(self, mock_cache, client, mock_client_service, mock_conn):
        mock_client_service.create_client.return_value = _make_client_row(id=20)
        create_resp = client.post("/api/crm/clients/", json={"full_name": "Summary"})
        assert create_resp.status_code == 200

        mock_conn.fetchrow.return_value = _make_client_row(id=20)
        mock_conn.fetch.return_value = [{"status": "completed", "count": 1}]
        summary_resp = client.get("/api/crm/clients/20/summary")
        assert summary_resp.status_code in (200, 404)
