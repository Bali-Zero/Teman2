"""Tests for the system observability router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.system_observability as system_observability_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(system_observability_module.router)
    application.dependency_overrides[system_observability_module.get_admin_user] = lambda: {"id": "1", "role": "admin"}
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestSystemObservability:
    @pytest.mark.integration
    def test_system_health_returns_service_report(self, app: FastAPI, client: TestClient) -> None:
        service = MagicMock()
        service.http_client = object()
        service.run_all_checks = AsyncMock(return_value={"status": "ok"})
        app.dependency_overrides[system_observability_module.get_unified_health_service] = lambda: service

        response = client.get("/api/admin/system-health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.integration
    def test_postgres_tables_returns_names(self, client: TestClient) -> None:
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[{"table_name": "clients"}, {"table_name": "practices"}])
        conn.close = AsyncMock()

        with patch("asyncpg.connect", AsyncMock(return_value=conn)):
            response = client.get("/api/admin/postgres/tables")

        assert response.status_code == 200
        assert response.json() == ["clients", "practices"]

    @pytest.mark.integration
    def test_table_data_rejects_invalid_table_name(self, client: TestClient) -> None:
        response = client.get("/api/admin/postgres/data?table=bad-name")
        assert response.status_code == 400

    @pytest.mark.integration
    def test_qdrant_collections_returns_result(self, client: TestClient) -> None:
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.get = AsyncMock(return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"result": {"collections": [{"name": "kbli"}]}}),
        ))

        with (
            patch("backend.core.qdrant_db.QdrantClient", MagicMock()),
            patch("httpx.AsyncClient", return_value=http_client),
        ):
            response = client.get("/api/admin/qdrant/collections")

        assert response.status_code == 200
        assert response.json()["collections"][0]["name"] == "kbli"
