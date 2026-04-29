"""Tests for apps/backend-rag/backend/app/routers/channels.py

Pre-W1.2 scope: regression test for the threshold ordering bug in
`/api/channels/health` — before this PR, the branch order was
`if > 20: degraded; elif > 50: down`, which made `down` unreachable
because anything `> 50` is also `> 20` and matched the first branch.

Test strategy: mount the router in an isolated FastAPI app, stub
`channel_router` (state) and `channel_metrics` (per-channel stats),
override `get_current_user` to bypass auth, drive the endpoint with
synthetic error_rate values across the three thresholds.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.dependencies import get_current_user
from backend.app.routers.channels import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(channel_router_stub: Any) -> FastAPI:
    """Build a minimal FastAPI app with channels router mounted and auth bypassed."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"email": "test@balizero.com"}
    app.state.channel_router = channel_router_stub
    app.state.db_pool = None  # /health gracefully handles None db_pool
    return app


def _stub_router(channels: list[str]) -> MagicMock:
    """Mock ChannelRouter exposing get_available_channels()."""
    cr = MagicMock()
    cr.get_available_channels.return_value = channels
    return cr


async def _get_health(app: FastAPI) -> dict[str, Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/channels/health")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Threshold ordering regression tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_status_up_when_error_rate_below_20pct():
    app = _build_app(_stub_router(["whatsapp"]))

    metrics = MagicMock()
    metrics.get_stats.return_value = {"messages_received": 100, "errors": 5}  # 5%
    with patch(
        "backend.channels.optimizations.channel_metrics",
        metrics,
    ):
        body = await _get_health(app)

    assert body["channels"]["whatsapp"]["status"] == "up"


@pytest.mark.asyncio
async def test_health_status_degraded_when_error_rate_between_20_and_50pct():
    app = _build_app(_stub_router(["whatsapp"]))

    metrics = MagicMock()
    metrics.get_stats.return_value = {"messages_received": 100, "errors": 30}  # 30%
    with patch(
        "backend.channels.optimizations.channel_metrics",
        metrics,
    ):
        body = await _get_health(app)

    assert body["channels"]["whatsapp"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_status_down_when_error_rate_above_50pct():
    """Regression: pre-fix this would return 'degraded' because the `> 20`
    branch matched before `> 50` was ever evaluated. With the fix, the
    stricter threshold is checked first."""
    app = _build_app(_stub_router(["whatsapp"]))

    metrics = MagicMock()
    metrics.get_stats.return_value = {"messages_received": 100, "errors": 60}  # 60%
    with patch(
        "backend.channels.optimizations.channel_metrics",
        metrics,
    ):
        body = await _get_health(app)

    assert body["channels"]["whatsapp"]["status"] == "down"
