"""Tests for the client portal router."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.portal as portal_module
from backend.app.dependencies import get_database_pool


@pytest.fixture
def fake_client() -> dict[str, object]:
    return {
        "client_id": 1,
        "user_id": "client-user-1",
        "email": "client@example.com",
        "name": "Portal Client",
    }


@pytest.fixture
def app(mock_db_pool, fake_client: dict[str, object]) -> FastAPI:
    pool, _conn = mock_db_pool
    application = FastAPI()
    application.include_router(portal_module.router)
    application.dependency_overrides[portal_module.get_current_client] = lambda: fake_client
    application.dependency_overrides[get_database_pool] = lambda: pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def portal_service() -> MagicMock:
    service = MagicMock()
    service.get_dashboard = AsyncMock(return_value={"pending_documents": 2})
    service.get_visa_status = AsyncMock(return_value={"visa_type": "KITAS"})
    service.get_documents = AsyncMock(return_value=[{"id": 1, "name": "passport.pdf"}])
    return service


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert portal_module.router.prefix == "/api/portal"
        assert portal_module.router.tags == ["portal"]


class TestPortalEndpoints:
    @pytest.mark.integration
    def test_dashboard_returns_portal_data(
        self,
        app: FastAPI,
        client: TestClient,
        portal_service: MagicMock,
    ) -> None:
        app.dependency_overrides[portal_module.get_portal_service] = lambda: portal_service

        response = client.get("/api/portal/dashboard")

        assert response.status_code == 200
        assert response.json()["data"]["pending_documents"] == 2

    @pytest.mark.integration
    def test_visa_status_returns_portal_data(
        self,
        app: FastAPI,
        client: TestClient,
        portal_service: MagicMock,
    ) -> None:
        app.dependency_overrides[portal_module.get_portal_service] = lambda: portal_service

        response = client.get("/api/portal/visa")

        assert response.status_code == 200
        assert response.json()["data"]["visa_type"] == "KITAS"

    @pytest.mark.integration
    def test_documents_returns_filtered_list(
        self,
        app: FastAPI,
        client: TestClient,
        portal_service: MagicMock,
    ) -> None:
        app.dependency_overrides[portal_module.get_portal_service] = lambda: portal_service

        response = client.get("/api/portal/documents?document_type=passport")

        assert response.status_code == 200
        assert response.json()["data"][0]["name"] == "passport.pdf"
        portal_service.get_documents.assert_awaited_once()
        call = portal_service.get_documents.await_args
        assert call.args == (1,)
        assert call.kwargs["document_type"] == "passport"
        assert call.kwargs["current_user"]["client_id"] == 1

    @pytest.mark.integration
    def test_profile_returns_db_backed_data(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={
            "id": 1,
            "full_name": "Portal Client",
            "email": "client@example.com",
            "phone": "+62812",
            "whatsapp": "+62812",
            "nationality": "Italian",
            "passport_number": "P123",
            "passport_expiry": date(2030, 1, 1),
            "date_of_birth": date(1990, 1, 1),
            "gender": "female",
            "address": "Bali",
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "assigned_to": "agent@balizero.com",
            "assigned_to_name": "Assigned Agent",
            "assigned_to_avatar": "https://example.com/avatar.png",
        })

        response = client.get("/api/portal/profile")

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["full_name"] == "Portal Client"
        assert payload["assigned_to"]["name"] == "Assigned Agent"

    @pytest.mark.integration
    def test_dashboard_denies_unauthenticated_client(self, mock_db_pool) -> None:
        pool, _conn = mock_db_pool
        application = FastAPI()
        application.include_router(portal_module.router)
        application.dependency_overrides[get_database_pool] = lambda: pool
        application.dependency_overrides[portal_module.get_current_client] = (
            lambda: (_ for _ in ()).throw(HTTPException(status_code=401, detail="Authentication required"))
        )
        application.dependency_overrides[portal_module.get_portal_service] = lambda: MagicMock()

        response = TestClient(application, raise_server_exceptions=False).get("/api/portal/dashboard")

        assert response.status_code == 401
