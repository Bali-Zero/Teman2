"""Tests for the event bus router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.event_bus as event_bus_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(event_bus_module.router)
    application.dependency_overrides[event_bus_module.get_current_user] = lambda: {"id": "1", "role": "admin"}
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestEventBusEndpoints:
    @pytest.mark.integration
    def test_stats_returns_not_initialized_when_missing(self, client: TestClient) -> None:
        response = client.get("/api/events/stats")
        assert response.status_code == 200
        assert response.json()["running"] is False

    @pytest.mark.integration
    def test_emit_returns_trace_data(self, app: FastAPI, client: TestClient) -> None:
        app.state.event_bus = SimpleNamespace(
            emit=AsyncMock(return_value=SimpleNamespace(handler_count=2, duration_ms=3.5, errors=[])),
        )

        response = client.post("/api/events/emit", json={"event_type": "test.ping", "payload": {"hello": "world"}})

        assert response.status_code == 200
        assert response.json()["emitted"] is True
        assert response.json()["handler_count"] == 2
