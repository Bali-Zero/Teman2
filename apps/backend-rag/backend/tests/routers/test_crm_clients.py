"""Tests for the CRM clients router."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.crm_clients as crm_clients_module
from backend.app.dependencies import get_current_user, get_database_pool


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _client_row(**overrides: object) -> dict[str, object]:
    return {
        "id": 1,
        "uuid": "11111111-1111-1111-1111-111111111111",
        "full_name": "Alice Example",
        "email": "alice@example.com",
        "phone": "+628123456789",
        "whatsapp": "+628123456789",
        "company_name": None,
        "nationality": "Italian",
        "passport_number": "P123456",
        "passport_expiry": "2030-01-01",
        "date_of_birth": "1990-01-01",
        "gender": None,
        "birthplace": None,
        "status": "active",
        "client_type": "individual",
        "assigned_to": "test@balizero.com",
        "tax_consultant": None,
        "avatar_url": None,
        "address": "Bali",
        "notes": "Important client",
        "first_contact_date": None,
        "last_interaction_date": None,
        "last_sentiment": "positive",
        "last_interaction_summary": "Follow-up complete",
        "tags": ["vip"],
        "lead_source": "referral",
        "service_interest": ["kitas"],
        "custom_fields": {},
        "tax_id": None,
        "npwp": None,
        "nib": None,
        "current_visa_type": None,
        "current_visa_sponsor": None,
        "created_at": _ts(),
        "updated_at": _ts(),
        "created_by": "test@balizero.com",
        **overrides,
    }


@pytest.fixture
def fake_user() -> dict[str, str]:
    return {"id": "1", "email": "test@balizero.com", "role": "admin"}


@pytest.fixture
def app(mock_db_pool, fake_user: dict[str, str]) -> FastAPI:
    pool, _conn = mock_db_pool
    application = FastAPI()
    application.include_router(crm_clients_module.router)
    application.dependency_overrides[get_current_user] = lambda: fake_user
    application.dependency_overrides[get_database_pool] = lambda: pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_routes(self) -> None:
        assert crm_clients_module.router.prefix == "/api/crm/clients"
        paths = {route.path for route in crm_clients_module.router.routes}
        assert "/api/crm/clients/" in paths
        assert "/api/crm/clients/{client_id}" in paths

    @pytest.mark.unit
    def test_client_create_model_validation(self) -> None:
        payload = crm_clients_module.ClientCreate.model_validate(
            {"full_name": "Alice", "email": "alice@example.com"},
        )
        assert payload.full_name == "Alice"


class TestCreateClient:
    @pytest.mark.integration
    def test_create_client_success_triggers_portal_hook(
        self,
        client: TestClient,
        mock_db_pool,
        app: FastAPI,
    ) -> None:
        pool, _conn = mock_db_pool
        created = _client_row()
        client_service = MagicMock()
        client_service.create_client = AsyncMock(return_value=created)
        app.dependency_overrides[crm_clients_module.get_client_service] = lambda: client_service

        drive_service = MagicMock()
        drive_service.create_client_folder = AsyncMock()
        portal_profile_service = MagicMock()
        portal_profile_service.ensure_portal_profile = AsyncMock()

        with (
            patch("backend.app.routers.crm_clients.invalidate_cache", AsyncMock()),
            patch("backend.services.integrations.service_account_drive_service.ServiceAccountDriveService", return_value=drive_service),
            patch("backend.services.crm.welcome.welcome_whatsapp_service.send_client_welcome", AsyncMock()),
            patch("backend.services.crm.welcome.welcome_email_service.schedule_client_welcome_email", AsyncMock()),
            patch("backend.services.portal.portal_profile_service.PortalProfileService", return_value=portal_profile_service),
        ):
            response = client.post(
                "/api/crm/clients/",
                json={"full_name": "Alice Example", "email": "alice@example.com"},
            )

        assert response.status_code == 200
        assert response.json()["email"] == "alice@example.com"
        client_service.create_client.assert_awaited_once()
        assert portal_profile_service.ensure_portal_profile.await_count == 1


class TestListClients:
    @pytest.mark.integration
    def test_list_clients_returns_rows(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[_client_row()])

        with (
            patch("backend.app.routers.crm_clients.get_crm_user_filter", return_value=None),
            patch("backend.app.routers.crm_clients.is_crm_admin", return_value=True),
        ):
            response = client.get("/api/crm/clients/?search=alice")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["full_name"] == "Alice Example"
        fetch_args = conn.fetch.await_args.args
        assert "%alice%" in fetch_args

    @pytest.mark.integration
    def test_list_clients_requires_authenticated_email(self, mock_db_pool) -> None:
        pool, _conn = mock_db_pool
        application = FastAPI()
        application.include_router(crm_clients_module.router)
        application.dependency_overrides[get_database_pool] = lambda: pool
        application.dependency_overrides[get_current_user] = lambda: {"id": "1", "role": "admin"}

        response = TestClient(application, raise_server_exceptions=False).get("/api/crm/clients/")

        assert response.status_code == 401


class TestGetClient:
    @pytest.mark.integration
    def test_get_client_by_id_success(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_client_row())

        with patch("backend.app.routers.crm_clients.verify_client_access", AsyncMock()):
            response = client.get("/api/crm/clients/1")

        assert response.status_code == 200
        assert response.json()["id"] == 1

    @pytest.mark.integration
    def test_get_client_by_id_returns_404(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("backend.app.routers.crm_clients.verify_client_access", AsyncMock()):
            response = client.get("/api/crm/clients/999")

        assert response.status_code == 404


class TestUpdateClient:
    @pytest.mark.integration
    def test_update_client_success(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_client_row(full_name="Updated Name"))
        conn.execute = AsyncMock(return_value="OK")

        notification_service = MagicMock()
        notification_service.notify_profile_updated = AsyncMock()

        with (
            patch("backend.app.routers.crm_clients.verify_client_access", AsyncMock()),
            patch("backend.services.portal.portal_notification_service.PortalNotificationService", return_value=notification_service),
            patch("backend.app.routers.crm_clients.spawn", MagicMock()),
        ):
            response = client.patch("/api/crm/clients/1", json={"full_name": "Updated Name"})

        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"
        assert conn.execute.await_count >= 1

    @pytest.mark.integration
    def test_update_client_rejects_empty_payload(self, client: TestClient, mock_db_pool) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_client_row())

        with patch("backend.app.routers.crm_clients.verify_client_access", AsyncMock()):
            response = client.patch("/api/crm/clients/1", json={})
        assert response.status_code == 400
