"""Tests for the public health router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.health as health_module
from backend.app.setup.route_walk import iter_leaf_routes


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
        paths = {route.path for route in iter_leaf_routes(health_module.router)}
        assert "/health" in paths
        assert "/health/detailed" in paths

    @pytest.mark.unit
    def test_startup_failed_helper_detects_flag(self) -> None:
        app = SimpleNamespace(state=SimpleNamespace(startup_failed=True, startup_error="boom"))
        assert health_module._check_startup_failed(app) == {
            "status": "startup_failed",
            "error": "boom",
        }

    @pytest.mark.unit
    def test_skills_mirror_probe_detects_registry_drift(self) -> None:
        probe = health_module._build_skills_mirror_probe(
            live_counts={"bali_zero_skills_hybrid": 613},
            freshness={},
        )

        assert probe["collection"] == "bali_zero_skills_hybrid"
        assert probe["status"] == "registry_drift"
        assert "missing_from_collection_manager" in probe["issues"]


class TestHealthEndpoints:
    @pytest.mark.integration
    def test_basic_health_returns_200_for_light_process(
        self, app: FastAPI, client: TestClient
    ) -> None:
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
            embedder=SimpleNamespace(
                provider="openai", model="text-embedding-3-small", dimensions=1536
            ),
        )
        app.state.db_pool = MagicMock(get_size=lambda: 3, get_idle_size=lambda: 1)

        with (
            patch(
                "backend.app.routers.health.get_qdrant_stats",
                AsyncMock(return_value={"collections": 2, "total_documents": 42}),
            ),
            patch(
                "backend.app.routers.health._check_resource_thresholds", return_value=(None, None)
            ),
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

        app.state.search_service = SimpleNamespace(
            embedder=SimpleNamespace(provider="openai", model="text-embedding-3-small")
        )
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
            patch(
                "backend.middleware.rate_limiter.get_rate_limit_stats",
                return_value={"active_buckets": 1},
            ),
        ):
            response = client.get("/health/detailed")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["services"]["database"]["status"] == "healthy"
        assert body["services"]["redis"]["details"]["connected"] is True

    @pytest.mark.integration
    def test_detailed_health_reports_real_faq_and_semantic_cache_hit_rate(
        self,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """faq_semantic_cache must report the WA orchestrator's real FAQ +
        semantic cache counters — not the unrelated generic CacheService
        (backend.core.cache) that the old "query_cache" block exposed under
        a name that read as "the WA cache". Regression guard for the
        cache-hit-rate blind spot fixed 2026-07-21."""
        from backend.app.metrics import (
            faq_cache_hits_total,
            faq_cache_misses_total,
            semantic_cache_hits_total,
            semantic_cache_misses_total,
        )
        from backend.app.routers.health import _counter_snapshot

        faq_hits_before, _ = _counter_snapshot(faq_cache_hits_total)
        faq_misses_before, _ = _counter_snapshot(faq_cache_misses_total)
        sem_hits_before, _ = _counter_snapshot(semantic_cache_hits_total)
        sem_misses_before, _ = _counter_snapshot(semantic_cache_misses_total)

        # Simulate one hit + one miss on each cache tier.
        faq_cache_hits_total.labels(domain="tax").inc()
        faq_cache_misses_total.inc()
        semantic_cache_hits_total.labels(match_type="semantic").inc()
        semantic_cache_misses_total.inc()

        response = client.get("/health/detailed")

        assert response.status_code == 200
        services = response.json()["services"]

        # Old misleading key must be gone; renamed key present.
        assert "query_cache" not in services
        assert "generic_query_cache" in services

        cache = services["faq_semantic_cache"]
        assert cache["status"] == "healthy"
        assert cache["details"]["scope"].startswith("per-worker")

        faq = cache["details"]["faq_cache"]
        assert faq["hits"] == faq_hits_before + 1
        assert faq["misses"] == faq_misses_before + 1
        assert faq["hits_by_domain"]["domain=tax"] >= 1

        semantic = cache["details"]["semantic_cache"]
        assert semantic["hits"] == sem_hits_before + 1
        assert semantic["misses"] == sem_misses_before + 1
        assert semantic["hits_by_match_type"]["match_type=semantic"] >= 1
