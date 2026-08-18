"""Tests for the Telegram webhook router."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.telegram_webhook as telegram_webhook_module
from backend.app.dependencies import get_channel_router


@pytest.fixture
def channel_router() -> AsyncMock:
    router = AsyncMock()
    router.route_message = AsyncMock()
    return router


@pytest.fixture
def app(channel_router: AsyncMock) -> FastAPI:
    application = FastAPI()
    application.include_router(telegram_webhook_module.router)
    application.dependency_overrides[get_channel_router] = lambda: channel_router
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert telegram_webhook_module.router.prefix == "/webhook"
        assert telegram_webhook_module.router.tags == ["telegram"]


class TestWebhookEndpoints:
    @pytest.mark.integration
    def test_valid_webhook_payload_routes_message(
        self,
        client: TestClient,
        channel_router: AsyncMock,
    ) -> None:
        response = client.post(
            "/webhook/telegram",
            json={"update_id": 1, "message": {"chat": {"id": 123}, "text": "hello"}},
        )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        channel_router.route_message.assert_awaited_once()

    @pytest.mark.integration
    def test_missing_update_id_returns_error(self, client: TestClient) -> None:
        response = client.post("/webhook/telegram", json={"message": {"text": "hello"}})
        assert response.status_code == 200
        assert response.json()["error"] == "Missing update_id"

    @pytest.mark.integration
    def test_callback_query_short_circuits_when_handled(self, client: TestClient) -> None:
        with patch(
            "backend.app.routers.telegram_webhook.handle_intel_callback",
            AsyncMock(return_value=True),
        ):
            response = client.post(
                "/webhook/telegram",
                json={"update_id": 2, "callback_query": {"data": "intel:approve:news:item-1"}},
            )

        assert response.status_code == 200
        assert response.json()["type"] == "callback_query"

    @pytest.mark.integration
    def test_route_errors_return_ok_false(
        self,
        client: TestClient,
        channel_router: AsyncMock,
    ) -> None:
        channel_router.route_message = AsyncMock(side_effect=RuntimeError("boom"))

        response = client.post(
            "/webhook/telegram",
            json={"update_id": 3, "message": {"chat": {"id": 123}, "text": "hello"}},
        )

        assert response.status_code == 200
        assert response.json()["ok"] is False

    @pytest.mark.integration
    def test_health_endpoint(self, client: TestClient) -> None:
        response = client.get("/webhook/telegram/health")
        assert response.status_code == 200
        assert response.json()["channel"] == "telegram"


class TestWebhookSecretVerification:
    """PROOF-OF-ARMED for the fail-closed X-Telegram-Bot-Api-Secret-Token guard.

    Ledger line (PENDING-ARMS.md, opened 2026-08-01, `/webhook/telegram is a
    PUBLIC endpoint ... and verifies no Telegram secret token`) prescribes exactly
    this shape: a forged POST without the secret header returns 401/403 in prod,
    and a probe WITH the correct header does not — a guard proven only by its
    refusals is a guard that may be refusing everything.
    """

    FAKE_SECRET = "unit-test-telegram-webhook-secret-not-real"  # noqa: S105

    @pytest.mark.unit
    def test_unconfigured_secret_skips_verification(
        self,
        client: TestClient,
        channel_router: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No TELEGRAM_WEBHOOK_SECRET configured (local/dev) — request proceeds."""
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)

        response = client.post(
            "/webhook/telegram",
            json={"update_id": 10, "message": {"chat": {"id": 1}, "text": "hi"}},
        )

        assert response.status_code == 200
        channel_router.route_message.assert_awaited_once()

    @pytest.mark.unit
    def test_configured_secret_missing_header_returns_401(
        self,
        client: TestClient,
        channel_router: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Forged update, no header at all — fails closed BEFORE ack-first persist."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", self.FAKE_SECRET)

        response = client.post(
            "/webhook/telegram",
            json={"update_id": 11, "message": {"chat": {"id": 1}, "text": "hi"}},
        )

        assert response.status_code == 401
        channel_router.route_message.assert_not_awaited()

    @pytest.mark.unit
    def test_configured_secret_wrong_header_returns_401(
        self,
        client: TestClient,
        channel_router: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", self.FAKE_SECRET)

        response = client.post(
            "/webhook/telegram",
            json={"update_id": 12, "message": {"chat": {"id": 1}, "text": "hi"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-value"},
        )

        assert response.status_code == 401
        channel_router.route_message.assert_not_awaited()

    @pytest.mark.unit
    def test_configured_secret_correct_header_is_not_401(
        self,
        client: TestClient,
        channel_router: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Positive control: the correct header must NOT be rejected."""
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", self.FAKE_SECRET)

        response = client.post(
            "/webhook/telegram",
            json={"update_id": 13, "message": {"chat": {"id": 1}, "text": "hi"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": self.FAKE_SECRET},
        )

        assert response.status_code != 401
        assert response.status_code == 200
        channel_router.route_message.assert_awaited_once()

    @pytest.mark.unit
    def test_verification_failure_never_logs_the_secret_or_header_value(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", self.FAKE_SECRET)

        with caplog.at_level("WARNING"):
            client.post(
                "/webhook/telegram",
                json={"update_id": 14, "message": {"chat": {"id": 1}, "text": "hi"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "attacker-guess-12345"},
            )

        rendered = "\n".join(record.getMessage() for record in caplog.records)
        assert self.FAKE_SECRET not in rendered
        assert "attacker-guess-12345" not in rendered
