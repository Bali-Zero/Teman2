"""
P0-1 — `@degraded_safe` decorator + structured 503 from `get_search_service`.

Cicatrix STRUCTURAL 2026-04-29: `_init_critical_services()` raised
RuntimeError if SearchService or ZantaraAIClient failed to init. Fly.io
auto-restart loop because the failure was deterministic. P0-0 (in main)
made `/health` return 503 on `app.state.startup_failed`. P0-1 now converts
the fail-fast to log-and-degrade so uvicorn always binds 8080 and the
service-locator dependency raises a structured 503 when the underlying
service is unavailable.

These tests pin the contract for the decorator + dependency:
- `@degraded_safe` catches init failures, logs, and registers the service
  name in `app.state.degraded_services`.
- `get_search_service` raises HTTPException(503) with structured detail
  containing the degraded set when `app.state.search_service is None`.
- Healthy path is unchanged (no false-positive degraded state, dependency
  returns the service).

Reference: docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-1_searchservice_degraded_mode.md
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException

from backend.app.deps.services import get_search_service
from backend.app.setup.service_initializer import degraded_safe


@pytest.fixture
def app() -> FastAPI:
    """Bare FastAPI app with no app.state pre-population."""
    return FastAPI()


@pytest.fixture
def request_factory(app: FastAPI):
    """Factory that builds a FastAPI Request bound to `app`.

    `get_search_service` only reads `request.app.state`, so we use a
    lightweight MagicMock with the right shape rather than constructing a
    real Request from a starlette scope.
    """

    def _make() -> MagicMock:
        req = MagicMock()
        req.app = app
        return req

    return _make


class TestDegradedSafe:
    """`@degraded_safe(service_name)` catches init failure → degraded set."""

    @pytest.mark.asyncio
    async def test_degraded_safe_catches_runtime_error(self, app: FastAPI) -> None:
        """When the wrapped init raises, the decorator logs, returns None,
        and registers the service name in app.state.degraded_services."""

        @degraded_safe("search")
        async def _failing_init(app: FastAPI) -> object:
            raise RuntimeError("Qdrant unreachable")

        result = await _failing_init(app)

        assert result is None, "decorator must return None on failure"
        assert hasattr(app.state, "degraded_services"), (
            "decorator must initialize app.state.degraded_services"
        )
        assert "search" in app.state.degraded_services, (
            f"expected 'search' in degraded_services; got {app.state.degraded_services}"
        )

    @pytest.mark.asyncio
    async def test_degraded_safe_passes_through_on_success(
        self, app: FastAPI,
    ) -> None:
        """On success the decorator must NOT touch app.state.degraded_services
        and must return the wrapped function's value verbatim."""
        sentinel = object()

        @degraded_safe("ai_client")
        async def _ok_init(app: FastAPI) -> object:
            return sentinel

        result = await _ok_init(app)

        assert result is sentinel, "decorator must pass through return value"
        # degraded_services should either be absent or not contain ai_client
        degraded = getattr(app.state, "degraded_services", set())
        assert "ai_client" not in degraded, (
            "successful init must NOT register service as degraded; "
            f"got {degraded}"
        )

    @pytest.mark.asyncio
    async def test_degraded_safe_accumulates_multiple_failures(
        self, app: FastAPI,
    ) -> None:
        """Two distinct failures must both end up in degraded_services."""

        @degraded_safe("search")
        async def _fail_search(app: FastAPI) -> None:
            raise RuntimeError("Qdrant down")

        @degraded_safe("ai_client")
        async def _fail_ai(app: FastAPI) -> None:
            raise ValueError("OpenAI key invalid")

        await _fail_search(app)
        await _fail_ai(app)

        assert "search" in app.state.degraded_services
        assert "ai_client" in app.state.degraded_services
        assert len(app.state.degraded_services) == 2


class TestGetSearchServiceDegraded:
    """`get_search_service` returns structured 503 when service is None."""

    def test_get_search_service_503_when_degraded(
        self, app: FastAPI, request_factory,
    ) -> None:
        """When app.state.search_service is None and degraded set contains
        'search', the dependency must raise HTTPException(503) with
        structured detail including the degraded set."""
        app.state.search_service = None
        app.state.degraded_services = {"search"}
        request = request_factory()

        with pytest.raises(HTTPException) as exc_info:
            get_search_service(request)

        exc = exc_info.value
        assert exc.status_code == 503, f"expected 503; got {exc.status_code}"
        # Detail must be a dict with the structured contract.
        assert isinstance(exc.detail, dict), (
            f"detail must be a dict; got {type(exc.detail).__name__}"
        )
        # Required keys per the brainstorm contract.
        assert "error" in exc.detail
        # Either retry_after_seconds (P0-1 contract) or retry_after (legacy)
        # must be present so clients can back off.
        assert "retry_after_seconds" in exc.detail or "retry_after" in exc.detail
        # degraded_services must surface in the response so the client knows
        # which subsystems are out.
        assert "degraded_services" in exc.detail, (
            f"detail must include degraded_services; got keys={list(exc.detail)}"
        )
        assert "search" in exc.detail["degraded_services"]

    def test_get_search_service_returns_when_present(
        self, app: FastAPI, request_factory,
    ) -> None:
        """Smoke positive path: when the service is set, the dependency
        returns it without raising."""
        sentinel = MagicMock(name="SearchService")
        app.state.search_service = sentinel
        request = request_factory()

        result = get_search_service(request)

        assert result is sentinel, "dependency must return the registered service"
