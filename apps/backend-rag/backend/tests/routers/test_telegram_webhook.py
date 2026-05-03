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
        with patch("backend.app.routers.telegram_webhook.handle_intel_callback", AsyncMock(return_value=True)):
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

