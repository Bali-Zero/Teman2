"""Tests for root-level utility endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.root_endpoints as root_endpoints_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(root_endpoints_module.router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRootEndpoints:
    @pytest.mark.integration
    def test_root_returns_ready_message(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"message": "ZANTARA RAG Backend Ready"}

    @pytest.mark.integration
    def test_csrf_token_returns_matching_body_and_headers(self, client: TestClient) -> None:
        token_values = ["c" * 64, "s" * 32]

        with patch("backend.app.routers.root_endpoints.secrets.token_hex", side_effect=token_values):
            response = client.get("/api/csrf-token")

        body = response.json()
        assert response.status_code == 200
        assert body["csrfToken"] == "c" * 64
        assert body["sessionId"].startswith("session_")
        assert body["sessionId"].endswith("_" + ("s" * 32))
        assert response.headers["X-CSRF-Token"] == body["csrfToken"]
        assert response.headers["X-Session-Id"] == body["sessionId"]

    @pytest.mark.integration
    def test_dashboard_stats_gracefully_degrades_without_db_pool(self, client: TestClient) -> None:
        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["system_health"] == "unknown"
        assert body["knowledge_base"]["status"] == "Database unavailable"
        assert body["error"] == "Database pool not initialized"

    @pytest.mark.integration
    def test_dashboard_stats_reads_counts_from_db(
        self,
        app: FastAPI,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        pool, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[7, 93000])
        app.state.db_pool = pool

        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["active_agents"] == "7"
        assert body["system_health"] == "99.9%"
        assert body["uptime_status"] == "ONLINE"
        assert body["knowledge_base"] == {"vectors": "93,000", "status": "Operational"}
        assert conn.fetchval.await_count == 2

    @pytest.mark.integration
    def test_dashboard_stats_returns_error_state_on_db_exception(
        self,
        app: FastAPI,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        pool, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=RuntimeError("db down"))
        app.state.db_pool = pool

        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["system_health"] == "error"
        assert body["uptime_status"] == "ERROR"
        assert body["knowledge_base"]["status"] == "Error: db down"
        assert body["error"] == "Failed to retrieve statistics"
