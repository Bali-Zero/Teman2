"""Tests for backend/app/routers/intel_observability.py (Phase D 2026-05-20).

Scope:
  - _classify_health pure-function logic (traffic-light edges)
  - endpoint returns 503 when db pool is None
  - endpoint returns 200 with degraded body when individual queries fail
    (graceful degradation — Symbiosis Law 4)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.routers.intel_observability import (
    _classify_health,
    router,
)

# ── Pure-function classifier ────────────────────────────────────────────────


def test_classify_green_when_outbox_low_and_router_fresh():
    intel = {
        "outbox_depth": 5,
        "router_last_classified_at": datetime.now(timezone.utc).isoformat(),
    }
    assert _classify_health(intel, {}, {}) == "green"


def test_classify_yellow_when_outbox_over_100():
    intel = {
        "outbox_depth": 150,
        "router_last_classified_at": datetime.now(timezone.utc).isoformat(),
    }
    assert _classify_health(intel, {}, {}) == "yellow"


def test_classify_red_when_outbox_over_1000():
    intel = {
        "outbox_depth": 1500,
        "router_last_classified_at": datetime.now(timezone.utc).isoformat(),
    }
    assert _classify_health(intel, {}, {}) == "red"


def test_classify_yellow_when_router_stale_1h_to_6h():
    intel = {
        "outbox_depth": 0,
        "router_last_classified_at": (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat(),
    }
    assert _classify_health(intel, {}, {}) == "yellow"


def test_classify_red_when_router_stale_over_6h():
    intel = {
        "outbox_depth": 0,
        "router_last_classified_at": (
            datetime.now(timezone.utc) - timedelta(hours=8)
        ).isoformat(),
    }
    assert _classify_health(intel, {}, {}) == "red"


def test_classify_green_when_router_missing_but_outbox_low():
    """No router activity timestamp + low outbox = green (fresh deploy)."""
    intel = {"outbox_depth": 0, "router_last_classified_at": None}
    assert _classify_health(intel, {}, {}) == "green"


def test_classify_malformed_timestamp_falls_back_to_outbox_only():
    intel = {"outbox_depth": 50, "router_last_classified_at": "not-a-date"}
    assert _classify_health(intel, {}, {}) == "green"


# ── Endpoint integration ────────────────────────────────────────────────────


def _build_app(db_pool: Any) -> FastAPI:
    from backend.app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = db_pool
    # Test-only auth bypass — production endpoint requires auth (panel fix 2026-05-20)
    app.dependency_overrides[get_current_user] = lambda: {"email": "test@balizero.com"}
    return app


@pytest.mark.asyncio
async def test_endpoint_returns_503_when_db_pool_none():
    app = _build_app(None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/intel/health/pipeline")
    assert resp.status_code == 503
    assert "db pool not initialized" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_endpoint_requires_auth_when_no_override():
    """Production endpoint is protected by get_current_user dependency.

    Panel review 2026-05-20 (DeepSeek HIGH finding): observability endpoint
    must not be public. Without the test-only override, FastAPI calls the
    real get_current_user which returns 401 on missing Authorization header.
    """
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = None
    # NO dependency override — should hit real auth
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/intel/health/pipeline")
    # Either 401 (no auth header) or 403 — anything but 200/503 from the route body
    assert resp.status_code in (401, 403), f"expected auth failure, got {resp.status_code}"


@pytest.mark.asyncio
async def test_endpoint_degrades_gracefully_on_query_failure():
    """If individual queries raise, endpoint returns 200 with *_error fields.

    This honors Symbiosis Law 4 (graceful degradation): partial data better
    than silent failure.
    """
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=Exception("simulated PG outage"))
    conn.fetch = AsyncMock(side_effect=Exception("simulated PG outage"))

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    app = _build_app(pool)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/intel/health/pipeline")

    assert resp.status_code == 200
    body = resp.json()
    assert "intel_lake" in body
    assert "wr2" in body
    assert "probes" in body
    assert "checked_at" in body
    assert "health" in body
    # Errors propagated as *_error fields, not as exceptions
    assert any(k.endswith("_error") for k in body["intel_lake"])
