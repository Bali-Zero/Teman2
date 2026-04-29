"""
P0-0 — /health surfaces startup_failed and warmup timeout.

Cicatrix STRUCTURAL 2026-04-29: backend `/health` was returning 200 OK
even when `app.state.startup_failed=True`, because `health_check()` never
called the existing `_check_startup_failed()` helper. Fly.io auto-restart
only fires on non-2xx so a deterministically-broken backend stayed
"healthy" indefinitely.

These tests pin the contract:
- 503 when `app.state.startup_failed=True`
- 503 when `app.state.startup_complete=False` after warmup deadline (180s)
- 200 when services are up normally

Reference: docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-0_health_endpoint_classify.md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.health import router  # noqa: E402


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app with health router."""
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    return fastapi_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestHealthStartupFailed:
    """Verify /health propagates startup_failed as HTTP 503."""

    def test_health_returns_503_when_startup_failed_true(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        """When app.state.startup_failed=True, /health must return 503."""
        app.state.startup_failed = True
        app.state.startup_error = "Critical service init failed: SearchService unavailable"

        response = client.get("/health")

        assert response.status_code == 503, (
            "Expected 503 when startup_failed=True; got "
            f"{response.status_code} body={response.text}"
        )
        body = response.json()
        assert body["status"] in ("unhealthy", "startup_failed"), (
            f"Expected status unhealthy/startup_failed; got {body['status']}"
        )

    def test_health_returns_503_after_warmup_deadline(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        """When startup_complete=False and started >180s ago, return 503."""
        app.state.startup_failed = False
        app.state.startup_complete = False
        # Pretend startup began 200s ago — past the 180s deadline.
        app.state.startup_started_at = time.time() - 200

        response = client.get("/health")

        assert response.status_code == 503, (
            "Expected 503 when warmup exceeded 180s deadline; got "
            f"{response.status_code} body={response.text}"
        )
        body = response.json()
        assert body["status"] in ("unhealthy", "startup_timeout"), (
            f"Expected status unhealthy/startup_timeout; got {body['status']}"
        )

    def test_health_returns_200_on_normal_ready_state(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        """When services are healthy, /health must still return 200."""
        app.state.startup_failed = False
        app.state.startup_complete = True
        app.state.startup_started_at = time.time() - 30

        # Simulate a fully-initialized search service so the existing
        # ready branch fires.
        mock_search_service = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.model = "text-embedding-3-small"
        mock_embedder.dimensions = 1536
        mock_embedder.provider = "openai"
        mock_search_service.embedder = mock_embedder
        app.state.search_service = mock_search_service

        with patch(
            "backend.app.routers.health.get_qdrant_stats", new_callable=AsyncMock,
        ) as mock_stats:
            mock_stats.return_value = {"collections": 12, "total_documents": 100_000}
            response = client.get("/health")

        assert response.status_code == 200, (
            f"Expected 200 on healthy ready state; got {response.status_code}"
        )
        body = response.json()
        assert body["status"] == "healthy", (
            f"Expected status=healthy; got {body['status']}"
        )
