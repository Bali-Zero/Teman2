"""Tests for the auth router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.auth as auth_module
from backend.app.dependencies import get_database_pool
from backend.app.setup.route_walk import iter_leaf_routes
from backend.services.pii.violation_store import hash_subject


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
        paths = {route.path for route in iter_leaf_routes(auth_module.router)}
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
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            ("client", "/portal"),
            ("partner", "/portal/partner/dashboard"),
            ("team", "/dashboard"),
            ("admin", "/dashboard"),
        ],
    )
    def test_post_auth_redirect_is_role_scoped(self, role: str, expected: str) -> None:
        assert auth_module._redirect_for_role(role) == expected

    @pytest.mark.unit
    def test_login_request_accepts_password_alias(self) -> None:
        request = auth_module.LoginRequest.model_validate(
            {"email": "user@example.com", "password": "654321"},
        )
        assert request.credentials == "654321"


class TestLoginEndpoint:
    @pytest.mark.integration
    def test_blocked_login_logs_only_pseudonymous_subjects(
        self,
        client: TestClient,
    ) -> None:
        audit_service = MagicMock()
        audit_service.pool = object()

        brute_force_detector = MagicMock()
        brute_force_detector.is_blocked = AsyncMock(return_value=True)

        redis_manager = MagicMock()
        redis_manager.get_async_client.return_value = AsyncMock()

        synthetic_email = "blocked-user@example.com"
        with (
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance",
                return_value=redis_manager,
            ),
            patch("backend.app.routers.auth.logger") as mock_logger,
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": synthetic_email, "pin": "123456"},
            )

        assert response.status_code == 429
        call = mock_logger.warning.call_args
        rendered = call.args[0] % call.args[1:]
        assert synthetic_email not in rendered
        assert "testclient" not in rendered
        assert hash_subject(synthetic_email) in rendered
        assert hash_subject("testclient") in rendered

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
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance", return_value=redis_manager
            ),
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
    def test_login_does_not_spawn_autoclockin_for_a_service_account(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        """PANOPTICON caller gate: a service-role login must not even spawn the
        auto-clock-in task. Before this, the gate was `role != "client"`, which
        is true for role="monitoring" — the login-healthcheck probe would spawn
        a coroutine every 5 minutes that the callee's own guard then discarded.
        This asserts the caller now agrees with the callee instead of relying
        on it to catch what the caller let through.
        """
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_user_row(role="monitoring"))
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
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance", return_value=redis_manager
            ),
            patch("backend.app.routers.auth.verify_password", return_value=True),
            patch("backend.app.routers.auth.spawn") as mock_spawn,
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "123456"},
            )

        assert response.status_code == 200
        mock_spawn.assert_not_called()

    @pytest.mark.integration
    def test_login_spawns_autoclockin_for_a_real_job_title(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        """Innocence: the service-account exclusion above must not exclude a
        real colleague. This column holds free-text job titles, not a fixed
        enum — 'Tax Care' is a real role in this system, not a placeholder.
        """
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=_user_row(role="Tax Care"))
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
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance", return_value=redis_manager
            ),
            patch("backend.app.routers.auth.verify_password", return_value=True),
            patch("backend.app.routers.auth.spawn") as mock_spawn,
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "123456"},
            )

        assert response.status_code == 200
        mock_spawn.assert_called_once()

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
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance", return_value=redis_manager
            ),
            patch("backend.app.routers.auth.verify_password", return_value=False),
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "bad"},
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or PIN"

    @pytest.mark.integration
    def test_client_login_returns_and_signs_authoritative_client_id(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value=_user_row(
                role="client",
                linked_client_id=42,
                portal_access=True,
            ),
        )
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
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance",
                return_value=redis_manager,
            ),
            patch("backend.app.routers.auth.verify_password", return_value=True),
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "123456"},
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user"]["client_id"] == 42
        assert data["user"]["portal_access"] is True
        token_payload = auth_module.jwt.decode(
            data["token"],
            auth_module.JWT_SECRET_KEY,
            algorithms=[auth_module.JWT_ALGORITHM],
        )
        assert token_payload["client_id"] == 42

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "eligibility_override",
        [
            {"portal_access": False, "linked_client_id": 42},
            {"portal_access": True, "linked_client_id": None},
        ],
        ids=["portal-access-disabled", "client-link-missing"],
    )
    def test_client_login_denies_portal_ineligible_accounts_without_session(
        self,
        client: TestClient,
        mock_db_pool,
        eligibility_override: dict[str, object],
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value=_user_row(
                role="client",
                **eligibility_override,
            ),
        )
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
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=audit_service,
            ),
            patch(
                "backend.services.security.brute_force.BruteForceDetector",
                return_value=brute_force_detector,
            ),
            patch(
                "backend.core.redis_manager.RedisManager.get_instance",
                return_value=redis_manager,
            ),
            patch("backend.app.routers.auth.verify_password", return_value=True),
            patch("backend.app.routers.auth.create_access_token") as token_mock,
            patch("backend.app.routers.auth.set_auth_cookies") as cookie_mock,
        ):
            response = client.post(
                "/api/auth/login",
                json={"email": "test@balizero.com", "pin": "123456"},
            )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Portal access is not available for this account",
        }
        assert response.cookies.get("nz_access_token") is None
        assert response.cookies.get("nz_csrf_token") is None
        conn.execute.assert_not_awaited()
        brute_force_detector.clear_on_success.assert_not_awaited()
        token_mock.assert_not_called()
        cookie_mock.assert_not_called()
        assert audit_service.log_auth_event.await_args.kwargs["failure_reason"] == (
            "Portal access unavailable"
        )

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
    def test_logout_revokes_current_jti_until_expiry(self, client: TestClient) -> None:
        token = auth_module.create_access_token(
            {"sub": "1", "email": "test@balizero.com", "role": "admin"},
            expires_delta=auth_module.timedelta(minutes=30),
        )
        redis_client = MagicMock()
        redis_client.setex = AsyncMock(return_value=True)
        redis_manager = MagicMock()
        redis_manager.get_async_client.return_value = redis_client

        with patch(
            "backend.core.redis_manager.RedisManager.get_instance",
            return_value=redis_manager,
        ):
            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        redis_client.setex.assert_awaited_once()
        key, ttl_seconds, reason = redis_client.setex.await_args.args
        assert key.startswith("revoked:")
        assert 1 <= ttl_seconds <= 30 * 60
        assert reason == "logout"

    @pytest.mark.integration
    def test_logout_fails_closed_when_revocation_store_is_unavailable(
        self,
        client: TestClient,
    ) -> None:
        token = auth_module.create_access_token(
            {"sub": "1", "email": "test@balizero.com", "role": "admin"},
        )
        redis_manager = MagicMock()
        redis_manager.get_async_client.return_value = None

        with patch(
            "backend.core.redis_manager.RedisManager.get_instance",
            return_value=redis_manager,
        ):
            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 503
        assert response.json()["detail"] == ("Session revocation service temporarily unavailable")

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
        application.dependency_overrides[auth_module.get_current_user] = lambda: (
            _ for _ in ()
        ).throw(HTTPException(status_code=401, detail="Unauthorized"))

        response = TestClient(application, raise_server_exceptions=False).get("/api/auth/profile")

        assert response.status_code == 401


def _audit_mock() -> MagicMock:
    audit = MagicMock()
    audit.pool = object()
    audit.connect = AsyncMock()
    audit.log_auth_event = AsyncMock()
    return audit


class TestMagicLink:
    @pytest.mark.unit
    def test_router_exposes_magic_link_routes(self) -> None:
        paths = {route.path for route in iter_leaf_routes(auth_module.router)}
        assert "/api/auth/request-magic-link" in paths
        assert "/api/auth/verify-magic/{token}" in paths

    @pytest.mark.integration
    def test_request_magic_link_is_enumeration_safe(self, client: TestClient) -> None:
        """The response body is generic and identical regardless of account."""
        svc = MagicMock()
        svc.request_magic_link = AsyncMock(return_value={"token": None, "is_client": False})

        with (
            patch(
                "backend.services.portal.magic_link_service.MagicLinkService",
                return_value=svc,
            ),
            patch("backend.app.routers.auth.spawn") as spawn_mock,
        ):
            response = client.post(
                "/api/auth/request-magic-link",
                json={"email": "stranger@example.com"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
        # No email dispatched for a non-client.
        spawn_mock.assert_not_called()

    @pytest.mark.integration
    def test_request_magic_link_dispatches_email_for_client(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.request_magic_link = AsyncMock(
            return_value={
                "token": "raw-token-xyz",
                "is_client": True,
                "email": "client@example.com",
                "name": "Client One",
            }
        )

        with (
            patch(
                "backend.services.portal.magic_link_service.MagicLinkService",
                return_value=svc,
            ),
            patch("backend.app.routers.auth.spawn") as spawn_mock,
            patch("backend.app.routers.auth._send_magic_link_email", new=AsyncMock()),
        ):

            def close_spawned_coroutine(coroutine, **_kwargs) -> None:
                coroutine.close()

            spawn_mock.side_effect = close_spawned_coroutine
            response = client.post(
                "/api/auth/request-magic-link",
                json={"email": "client@example.com"},
            )

        assert response.status_code == 200
        # Generic body — never reveals the account exists.
        assert "account exists" in response.json()["message"].lower()
        spawn_mock.assert_called_once()

    @pytest.mark.integration
    def test_request_magic_link_validates_email(self, client: TestClient) -> None:
        response = client.post("/api/auth/request-magic-link", json={"email": "not-an-email"})
        assert response.status_code == 422

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("recipient", "endpoint", "expected"),
        [
            (
                "portal-active@example.com",
                "http://127.0.0.1:18181/api/notifications/send-email",
                True,
            ),
            (
                "portal-active@example.com",
                "http://localhost/api/notifications/send-email",
                False,
            ),
            (
                "client@balizero.com",
                "https://nuzantara-rag.fly.dev/api/notifications/send-email",
                True,
            ),
        ],
    )
    def test_magic_link_email_endpoint_safety_contract(
        self, recipient: str, endpoint: str, expected: bool
    ) -> None:
        assert auth_module._synthetic_email_endpoint_is_safe(recipient, endpoint) is expected

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_synthetic_magic_link_refuses_non_loopback_email_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "INTERNAL_EMAIL_API_URL",
            "https://nuzantara-rag.fly.dev/api/notifications/send-email",
        )
        monkeypatch.setenv("NUZANTARA_API_KEY", "synthetic-test-key")

        with patch("httpx.AsyncClient") as http_client:
            sent = await auth_module._send_magic_link_email(
                "portal-active@example.com",
                "Synthetic Client",
                "http://127.0.0.1:3101/portal/magic?token=synthetic-token",
            )

        assert sent is False
        http_client.assert_not_called()

    @pytest.mark.integration
    def test_verify_magic_link_success_sets_cookies(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.verify_magic_link = AsyncMock(
            return_value={
                "id": "7",
                "email": "client@example.com",
                "name": "Client One",
                "role": "client",
                "client_id": 42,
                "portal_access": True,
            }
        )

        with (
            patch(
                "backend.services.portal.magic_link_service.MagicLinkService",
                return_value=svc,
            ),
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=_audit_mock(),
            ),
            patch(
                "backend.app.routers.auth.create_access_token",
                return_value="synthetic-access-token",
            ) as token_mock,
        ):
            response = client.get("/api/auth/verify-magic/raw-token-xyz")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["data"]["user"]["email"] == "client@example.com"
        assert payload["data"]["user"]["client_id"] == 42
        assert payload["data"]["user"]["portal_access"] is True
        assert payload["data"]["redirectTo"] == "/portal"
        assert token_mock.call_args.kwargs["data"]["client_id"] == 42
        assert response.cookies.get("nz_access_token")
        assert response.cookies.get("nz_csrf_token")

    @pytest.mark.integration
    def test_verify_magic_link_rejects_invalid_token(self, client: TestClient) -> None:
        svc = MagicMock()
        svc.verify_magic_link = AsyncMock(return_value=None)

        with (
            patch(
                "backend.services.portal.magic_link_service.MagicLinkService",
                return_value=svc,
            ),
            patch(
                "backend.services.monitoring.audit_service.get_audit_service",
                return_value=_audit_mock(),
            ),
        ):
            response = client.get("/api/auth/verify-magic/bad-token")

        assert response.status_code == 401
        assert "invalid or expired" in response.json()["detail"].lower()

        assert response.status_code == 401
