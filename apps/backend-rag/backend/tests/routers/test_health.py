"""Tests for the public health router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.health as health_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(health_module.router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_routes(self) -> None:
        assert health_module.router.prefix == "/health"
        paths = {route.path for route in health_module.router.routes}
        assert "/health" in paths
        assert "/health/detailed" in paths

    @pytest.mark.unit
    def test_startup_failed_helper_detects_flag(self) -> None:
        app = SimpleNamespace(state=SimpleNamespace(startup_failed=True, startup_error="boom"))
        assert health_module._check_startup_failed(app) == {
            "status": "startup_failed",
            "error": "boom",
        }


class TestHealthEndpoints:
    @pytest.mark.integration
    def test_basic_health_returns_200_for_light_process(self, app: FastAPI, client: TestClient) -> None:
        app.state.process_mode = "light"
        app.state.search_service = None

        response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["database"]["status"] == "connected"

    @pytest.mark.integration
    def test_basic_health_returns_ready_stats_for_rag_process(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        app.state.process_mode = "rag"
        app.state.search_service = SimpleNamespace(
            embedder=SimpleNamespace(provider="openai", model="text-embedding-3-small", dimensions=1536),
        )
        app.state.db_pool = MagicMock(get_size=lambda: 3, get_idle_size=lambda: 1)

        with (
            patch("backend.app.routers.health.get_qdrant_stats", AsyncMock(return_value={"collections": 2, "total_documents": 42})),
            patch("backend.app.routers.health._check_resource_thresholds", return_value=(None, None)),
        ):
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["database"]["collections"] == 2
        assert body["embeddings"]["dimensions"] == 1536

    @pytest.mark.integration
    def test_detailed_health_reports_component_statuses(
        self,
        app: FastAPI,
        client: TestClient,
        mock_db_pool,
        mock_redis,
    ) -> None:
        pool, conn = mock_db_pool
        conn.execute = AsyncMock(return_value="SELECT 1")
        pool.get_min_size = MagicMock(return_value=1)
        pool.get_max_size = MagicMock(return_value=10)
        pool.get_size = MagicMock(return_value=2)

        app.state.search_service = SimpleNamespace(embedder=SimpleNamespace(provider="openai", model="text-embedding-3-small"))
        app.state.ai_client = object()
        app.state.db_pool = pool
        app.state.memory_service = object()
        app.state.intelligent_router = object()
        app.state.health_monitor = MagicMock(get_status=MagicMock(return_value={"running": True}))
        app.state.redis_manager = MagicMock(
            health_check=AsyncMock(
                return_value={
                    "connected": True,
                    "latency_ms": 1,
                    "keys": 10,
                    "memory_used": "1MB",
                    "components": {},
                },
            ),
        )
        app.state.service_registry = MagicMock(get_status=MagicMock(return_value={"ok": True}))

        cache_service = MagicMock()
        cache_service.get_stats.return_value = {"hits": 5, "misses": 1}

        with (
            patch("backend.core.cache.get_cache_service", return_value=cache_service),
            patch("backend.middleware.rate_limiter.get_rate_limit_stats", return_value={"active_buckets": 1}),
        ):
            response = client.get("/health/detailed")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["services"]["database"]["status"] == "healthy"
        assert body["services"]["redis"]["details"]["connected"] is True

