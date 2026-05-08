"""Tests for the channel health router."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.channel_health as channel_health_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(channel_health_module.router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestChannelClassification:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("queue_depth", "expected"),
        [(0, "ok"), (20, "ok"), (21, "degraded"), (100, "degraded"), (101, "fail")],
    )
    def test_classify_thresholds(self, queue_depth: int, expected: str) -> None:
        assert channel_health_module._classify(queue_depth) == expected


class TestChannelHealthEndpoint:
    @pytest.mark.integration
    def test_unknown_channel_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/channels/email/health")

        assert response.status_code == 404
        assert response.json()["detail"] == "unknown channel: email"

    @pytest.mark.integration
    def test_known_channel_returns_default_health_without_db(self, app: FastAPI, client: TestClient) -> None:
        app.dependency_overrides[channel_health_module.get_optional_database_pool] = lambda: None

        response = client.get("/api/channels/whatsapp/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["channel"] == "whatsapp"
        assert body["queue_depth"] == 0
        assert body["last_event_seen_at"] is None
        assert body["metadata"]["thresholds"] == {"ok": 20, "degraded": 100}
        assert body["metadata"]["window_minutes"] == 60

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("pending", "expected_status"),
        [(5, "ok"), (80, "degraded"), (150, "fail")],
    )
    def test_known_channel_uses_db_queue_depth(
        self,
        app: FastAPI,
        client: TestClient,
        mock_db_pool,
        pending: int,
        expected_status: str,
    ) -> None:
        pool, conn = mock_db_pool
        conn.fetchrow.return_value = {"pending": pending, "last_ts": 1714896000.25}
        app.dependency_overrides[channel_health_module.get_optional_database_pool] = lambda: pool

        response = client.get("/api/channels/telegram/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == expected_status
        assert body["channel"] == "telegram"
        assert body["queue_depth"] == pending
        assert body["last_event_seen_at"] == 1714896000.25
        conn.fetchrow.assert_awaited_once()

