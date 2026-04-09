"""Tests for the query analytics router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.query_analytics as query_analytics_module


@pytest.fixture
def repo() -> MagicMock:
    fake = MagicMock()
    fake.get_dashboard_summary = AsyncMock(return_value={"summary": True})
    fake.get_failed_queries = AsyncMock(return_value=[{"query": "missing"}])
    fake.record_feedback = AsyncMock(return_value=True)
    return fake


@pytest.fixture
def app(repo: MagicMock) -> FastAPI:
    application = FastAPI()
    application.include_router(query_analytics_module.router)
    application.dependency_overrides[query_analytics_module._verify_founder_access] = lambda: {"id": "1", "role": "admin"}
    application.dependency_overrides[query_analytics_module._get_repo] = lambda: repo
    application.dependency_overrides[query_analytics_module.get_current_user] = lambda: {"id": "1", "role": "user"}
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestAnalyticsEndpoints:
    @pytest.mark.integration
    def test_dashboard_returns_summary(self, client: TestClient) -> None:
        response = client.get("/api/analytics/query-insights?days=7")
        assert response.status_code == 200
        assert response.json()["summary"] is True

    @pytest.mark.integration
    def test_failed_queries_returns_rows(self, client: TestClient) -> None:
        response = client.get("/api/analytics/query-insights/failed?limit=5&days=7")
        assert response.status_code == 200
        assert response.json()[0]["query"] == "missing"

    @pytest.mark.integration
    def test_feedback_rejects_invalid_value(self, client: TestClient) -> None:
        response = client.post(
            "/api/analytics/query-insights/feedback",
            json={"query_id": "q1", "feedback": "bad_value"},
        )
        assert response.status_code == 400

    @pytest.mark.integration
    def test_feedback_returns_404_when_query_missing(self, client: TestClient, repo: MagicMock) -> None:
        repo.record_feedback = AsyncMock(return_value=False)
        response = client.post(
            "/api/analytics/query-insights/feedback",
            json={"query_id": "q1", "feedback": "thumbs_up"},
        )
        assert response.status_code == 404

