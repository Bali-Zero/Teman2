"""Additional current-contract coverage for CRM portal integration routes."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.deps.crm_access import get_crm_user_filter
from backend.app.routers import crm_portal_integration as crm_router

TEAM_USER = {
    "email": "qa.team@example.test",
    "user_id": "qa-team-user",
    "name": "QA Team",
    "role": "team",
    "permissions": [],
}
CLIENT_USER = {
    "email": "qa.client@example.test",
    "user_id": "qa-client-user",
    "name": "QA Client",
    "role": "client",
    "permissions": [],
}


class _Acquire:
    def __init__(self, connection: AsyncMock) -> None:
        self._connection = connection

    async def __aenter__(self) -> AsyncMock:
        return self._connection

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.fixture
def harness() -> SimpleNamespace:
    connection = AsyncMock()
    db_pool = MagicMock()
    db_pool.acquire.side_effect = lambda: _Acquire(connection)
    invite_service = AsyncMock()
    portal_service = AsyncMock()

    app = FastAPI()
    app.include_router(crm_router.router)
    app.dependency_overrides[get_current_user] = lambda: TEAM_USER
    app.dependency_overrides[get_database_pool] = lambda: db_pool
    app.dependency_overrides[crm_router.get_invite_service] = lambda: invite_service
    app.dependency_overrides[crm_router.get_portal_service] = lambda: portal_service
    app.dependency_overrides[get_crm_user_filter] = lambda: None

    with TestClient(app) as client:
        yield SimpleNamespace(
            app=app,
            client=client,
            connection=connection,
            invite_service=invite_service,
            portal_service=portal_service,
        )

    app.dependency_overrides.clear()


@pytest.fixture
def allow_client_access(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    access_check = AsyncMock()
    monkeypatch.setattr(crm_router, "verify_client_access", access_check)
    return access_check


@pytest.mark.integration
class TestCRMPortalIntegrationAdditionalContracts:
    def test_get_portal_status_with_active_portal_user(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        created_at = datetime(2026, 8, 6, 9, 0, tzinfo=timezone.utc)
        harness.connection.fetchrow.side_effect = [
            {"id": 9, "email": "qa.client@example.com", "last_login": created_at},
            None,
        ]

        response = harness.client.get("/api/crm/portal/clients/42/status")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "has_portal_access": True,
            "portal_user_id": 9,
            "portal_email": "qa.client@example.com",
            "last_login": created_at.isoformat(),
            "pending_invite": False,
            "invite_expires_at": None,
        }
        allow_client_access.assert_awaited_once()

    def test_get_portal_status_with_pending_invitation(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        expires_at = datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc)
        harness.connection.fetchrow.side_effect = [None, {"expires_at": expires_at}]

        response = harness.client.get("/api/crm/portal/clients/42/status")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "has_portal_access": False,
            "portal_user_id": None,
            "portal_email": None,
            "last_login": None,
            "pending_invite": True,
            "invite_expires_at": expires_at.isoformat(),
        }
        allow_client_access.assert_awaited_once()

    def test_send_portal_invite_requires_client_email(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        harness.connection.fetchrow.return_value = None

        response = harness.client.post("/api/crm/portal/clients/42/invite", json={})

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Client has no email address. Please provide one.",
        }
        harness.invite_service.create_invitation.assert_not_awaited()
        allow_client_access.assert_awaited_once()

    def test_get_portal_preview_uses_authorized_impersonation_context(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        harness.portal_service.get_dashboard.return_value = {"status": "active"}
        harness.portal_service.get_visa_status.return_value = {"visas": []}
        harness.portal_service.get_companies.return_value = {"companies": []}
        harness.portal_service.get_tax_overview.return_value = {"taxes": []}

        response = harness.client.get("/api/crm/portal/clients/42/preview")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "dashboard": {"status": "active"},
            "visa": {"visas": []},
            "companies": {"companies": []},
            "taxes": {"taxes": []},
        }
        for method_name in (
            "get_dashboard",
            "get_visa_status",
            "get_companies",
            "get_tax_overview",
        ):
            call = getattr(harness.portal_service, method_name).await_args
            assert call.args == (42,)
            assert call.kwargs["current_user"]["client_id"] == 42
            assert call.kwargs["current_user"]["impersonating"] is True
        allow_client_access.assert_awaited_once()

    def test_client_role_is_forbidden_before_database_access(
        self,
        harness: SimpleNamespace,
    ) -> None:
        harness.app.dependency_overrides[get_current_user] = lambda: CLIENT_USER

        response = harness.client.get("/api/crm/portal/clients/42/status")

        assert response.status_code == 403
        assert response.json() == {
            "detail": "This endpoint is only accessible to team members",
        }
        harness.connection.fetchrow.assert_not_awaited()
