"""Tests for the RAG monitoring router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.monitoring_rag as monitoring_module
from backend.services.rag.evaluation.monitoring import AlertThresholds


@pytest.fixture
def monitor() -> MagicMock:
    fake = MagicMock()
    fake.get_dashboard_data = AsyncMock(return_value={
        "time_range": "24h",
        "total_queries": 10,
        "timestamp": "2026-04-09T00:00:00Z",
        "retrieval_quality": {},
        "performance": {},
        "usage_patterns": {},
        "alerts": {},
        "alert_thresholds": {},
    })
    fake.get_scores_trend = AsyncMock(return_value=[{"day": "2026-04-09", "avg": 0.7}])
    fake.get_latency_percentiles = AsyncMock(return_value={
        "period_days": 7,
        "total_queries": 10,
        "percentiles": {"p95": 100.0},
        "min": 10.0,
        "max": 200.0,
        "avg": 75.0,
    })
    fake.get_alert_thresholds.return_value = AlertThresholds(
        min_score=0.3,
        max_abstain_rate=0.2,
        max_latency_ms=5000.0,
        min_cache_hit_rate=0.5,
    )
    fake.set_alert_thresholds = MagicMock()
    return fake


@pytest.fixture
def app(monitor: MagicMock) -> FastAPI:
    application = FastAPI()
    application.include_router(monitoring_module.router)
    application.dependency_overrides[monitoring_module.verify_admin_access] = lambda: {"id": "1", "role": "admin"}
    application.dependency_overrides[monitoring_module.get_retrieval_quality_monitor] = lambda: monitor
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestMonitoringEndpoints:
    @pytest.mark.unit
    def test_verify_admin_access_rejects_non_admin(self) -> None:
        with pytest.raises(Exception):
            monitoring_module.verify_admin_access({"id": "2", "role": "user"})

    @pytest.mark.integration
    def test_retrieval_quality_returns_dashboard(self, client: TestClient) -> None:
        response = client.get("/api/monitoring/retrieval-quality?time_range=24h")
        assert response.status_code == 200
        assert response.json()["total_queries"] == 10

    @pytest.mark.integration
    def test_set_and_get_alert_thresholds(self, client: TestClient, monitor: MagicMock) -> None:
        set_response = client.post(
            "/api/monitoring/alert-threshold",
            json={
                "min_score": 0.4,
                "max_abstain_rate": 0.3,
                "max_latency_ms": 4000.0,
                "min_cache_hit_rate": 0.6,
            },
        )
        get_response = client.get("/api/monitoring/alert-threshold")

        assert set_response.status_code == 200
        assert get_response.status_code == 200
        monitor.set_alert_thresholds.assert_called_once()

    @pytest.mark.integration
    def test_health_endpoint_is_public(self, client: TestClient) -> None:
        response = client.get("/api/monitoring/health")
        assert response.status_code == 200
        assert response.json()["service"] == "rag-monitoring"

