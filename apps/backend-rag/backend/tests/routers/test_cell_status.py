"""Tests for CELL dashboard status endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.cell_status as cell_status_module


@pytest.fixture
def app(mock_db_pool) -> FastAPI:
    pool, _conn = mock_db_pool
    application = FastAPI()
    application.include_router(cell_status_module.router)
    application.dependency_overrides[cell_status_module.get_database_pool] = lambda: pool
    application.dependency_overrides[cell_status_module.get_current_user] = lambda: {"id": "1", "role": "admin"}
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestCellStatusEndpoint:
    @pytest.mark.integration
    def test_status_reports_alive_and_uptime_distribution(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        now = datetime.now(timezone.utc)
        last = {
            "pulse_number": 12,
            "health_status": "green",
            "created_at": now - timedelta(seconds=30),
        }
        stats = {"total": 4, "green_count": 2, "yellow_count": 1, "red_count": 1}
        conn.fetchrow.side_effect = [last, stats]
        conn.fetch.return_value = [last]

        response = client.get("/api/cell/status")

        assert response.status_code == 200
        body = response.json()
        assert body["alive"] is True
        assert body["last_pulse"]["pulse_number"] == 12
        assert body["recent_pulses"][0]["health_status"] == "green"
        assert body["uptime_24h"] == {
            "green_percent": 50.0,
            "yellow_percent": 25.0,
            "red_percent": 25.0,
            "total_pulses": 4,
        }

    @pytest.mark.integration
    def test_status_handles_no_pulses(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow.side_effect = [None, {"total": 0, "green_count": 0, "yellow_count": 0, "red_count": 0}]
        conn.fetch.return_value = []

        response = client.get("/api/cell/status")

        assert response.status_code == 200
        body = response.json()
        assert body["alive"] is False
        assert body["last_pulse"] is None
        assert body["recent_pulses"] == []
        assert body["uptime_24h"]["total_pulses"] == 0
        assert body["uptime_24h"]["green_percent"] == 0


class TestCellMetricsEndpoint:
    @pytest.mark.integration
    def test_metrics_returns_error_counts(self, client: TestClient, mock_db_pool) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow.return_value = {"errors_5min": 2, "total_5min": 9}

        response = client.get("/api/cell/metrics")

        assert response.status_code == 200
        assert response.json() == {"errors_5min": 2, "total_5min": 9, "window_minutes": 5}


class TestCellAlertsEndpoint:
    @pytest.mark.integration
    def test_alerts_returns_recent_rows(self, client: TestClient, mock_db_pool) -> None:
        _pool, conn = mock_db_pool
        created_at = datetime(2026, 5, 9, 2, 0, tzinfo=timezone.utc)
        conn.fetch.return_value = [
            {
                "id": "alert-1",
                "level": "human",
                "action": "read_logs",
                "message": "Investigate red pulse",
                "health_status": "red",
                "pulse_number": 44,
                "created_at": created_at,
            },
        ]

        response = client.get("/api/cell/alerts?limit=1")

        assert response.status_code == 200
        body = response.json()
        assert body["alerts"][0]["id"] == "alert-1"
        assert body["alerts"][0]["pulse_number"] == 44
        conn.fetch.assert_awaited_once()

