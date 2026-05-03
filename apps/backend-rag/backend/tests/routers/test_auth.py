"""Tests for the auth router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.auth as auth_module
from backend.app.dependencies import get_database_pool


def _user_row(**overrides: object) -> dict[str, object]:
    return {
        "id": 1,
        "email": "test@balizero.com",
        "name": "Test User",
        "password_hash": "hashed-pin",
        "role": "admin",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "active": True,
        "avatar": None,
        "linked_client_id": None,
        "portal_access": False,
        **overrides,
    }


@pytest.fixture
def fake_user() -> dict[str, object]:
    return {
        "id": "1",
        "email": "test@balizero.com",
        "name": "Test User",
        "role": "admin",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "avatar": None,
    }


@pytest.fixture
def app(mock_db_pool, fake_user: dict[str, object]) -> FastAPI:
    pool, _conn = mock_db_pool
    application = FastAPI()
    application.include_router(auth_module.router)
    application.dependency_overrides[get_database_pool] = lambda: pool
    application.dependency_overrides[auth_module.get_current_user] = lambda: fake_user
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert auth_module.router.prefix == "/api/auth"
        assert auth_module.router.tags == ["authentication"]

    @pytest.mark.unit
    def test_router_exposes_expected_routes(self) -> None:
        paths = {route.path for route in auth_module.router.routes}
        assert "/api/auth/login" in paths
        assert "/api/auth/profile" in paths
        assert "/api/auth/logout" in paths
        assert "/api/auth/refresh" in paths


class TestModels:
    @pytest.mark.unit
    def test_login_request_accepts_pin(self) -> None:
        request = auth_module.LoginRequest.model_validate(
            {"email": "user@example.com", "pin": "123456"},
        )
        assert request.credentials == "123456"

    @pytest.mark.unit
    def test_login_request_accepts_password_alias(self) -> None:
        request = auth_module.LoginRequest.model_validate(
            {"email": "user@example.com", "password": "654321"},
        )
        assert request.credentials == "654321"


class TestLoginEndpoint:
    @pytest.mark.integration
    def test_login_success_sets_auth_cookies(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_user_row())
        conn.execute = AsyncMock(return_value="UPDATE 1")

        audit_service = MagicMock()
        audit_service.pool = object()
        audit_service.connect = AsyncMock()
        audit_service.log_auth_event = AsyncMock()

        brute_force_detector = MagicMock()
        brute_force_detector.is_blocked = AsyncMock(return_value=False)
        brute_force_detector.clear_on_success = AsyncMock()
        brute_force_detector.record_failure = AsyncMock()

        redis_manager = MagicMock()
        redis_manager.get_async_client.return_value = AsyncMock()

        with (
            patch("backend.services.monitoring.audit_service.get_audit_service", return_value=audit_service),
            patch("backend.services.security.brute_force.BruteForceDetector", return_value=brute_force_detector),
            patch("backend.core.redis_manager.RedisManager.get_instance", return_value=redis_manager),
            patch("backend.app.routers.auth.verify_password", return_value=True),
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "123456"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["user"]["email"] == "test@balizero.com"
        assert payload["data"]["redirectTo"] == "/dashboard"
        assert response.cookies.get("nz_access_token")
        assert response.cookies.get("nz_csrf_token")
        audit_service.log_auth_event.assert_awaited()
        conn.execute.assert_awaited_once()

    @pytest.mark.integration
    def test_login_rejects_bad_credentials(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_user_row())

        audit_service = MagicMock()
        audit_service.pool = object()
        audit_service.connect = AsyncMock()
        audit_service.log_auth_event = AsyncMock()

        brute_force_detector = MagicMock()
        brute_force_detector.is_blocked = AsyncMock(return_value=False)
        brute_force_detector.record_failure = AsyncMock()

        redis_manager = MagicMock()
        redis_manager.get_async_client.return_value = AsyncMock()

        with (
            patch("backend.services.monitoring.audit_service.get_audit_service", return_value=audit_service),
            patch("backend.services.security.brute_force.BruteForceDetector", return_value=brute_force_detector),
            patch("backend.core.redis_manager.RedisManager.get_instance", return_value=redis_manager),
            patch("backend.app.routers.auth.verify_password", return_value=False),
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "bad"},
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or PIN"

    @pytest.mark.integration
    def test_login_validates_request_body(self, client: TestClient) -> None:
        response = client.post("/api/auth/login", json={"email": "invalid"})
        assert response.status_code == 422


class TestSessionEndpoints:
    @pytest.mark.integration
    def test_profile_returns_current_user(self, client: TestClient) -> None:
        response = client.get("/api/auth/profile")
        assert response.status_code == 200
        assert response.json()["email"] == "test@balizero.com"

    @pytest.mark.integration
    def test_logout_clears_auth_cookies(self, client: TestClient) -> None:
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        cookies = response.headers.get("set-cookie", "")
        assert "nz_access_token=" in cookies
        assert "Max-Age=0" in cookies or "expires=" in cookies.lower()

    @pytest.mark.integration
    def test_refresh_token_returns_new_session_payload(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_user_row(id="1"))

        response = client.post("/api/auth/refresh")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["user"]["id"] == "1"
        assert payload["data"]["redirectTo"] == "/dashboard"
        assert response.cookies.get("nz_access_token")

    @pytest.mark.integration
    def test_refresh_token_returns_401_for_missing_user(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=None)

        response = client.post("/api/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "User not found or inactive"

    @pytest.mark.integration
    def test_profile_denies_unauthenticated_request(self, mock_db_pool) -> None:
        pool, _conn = mock_db_pool
        application = FastAPI()
        application.include_router(auth_module.router)
        application.dependency_overrides[get_database_pool] = lambda: pool
        application.dependency_overrides[auth_module.get_current_user] = (
            lambda: (_ for _ in ()).throw(HTTPException(status_code=401, detail="Unauthorized"))
        )

        response = TestClient(application, raise_server_exceptions=False).get("/api/auth/profile")

        assert response.status_code == 401

