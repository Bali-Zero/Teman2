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


# ---------------------------------------------------------------------------
# /health-public — Innervation Genoma bridge endpoint (W1.2)
# ---------------------------------------------------------------------------


def _build_app_no_auth(channel_router_stub: Any) -> FastAPI:
    """Same as _build_app but does NOT override get_current_user — verifies
    the public endpoint genuinely doesn't require auth, not that we bypassed it."""
    app = FastAPI()
    app.include_router(router)
    app.state.channel_router = channel_router_stub
    app.state.db_pool = None
    return app


async def _get_health_public(app: FastAPI) -> tuple[int, dict[str, Any]]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/channels/health-public")
    return resp.status_code, (resp.json() if resp.status_code == 200 else {})


@pytest.mark.asyncio
async def test_health_public_returns_per_channel_status_no_auth():
    """The endpoint must respond 200 with no auth header attached."""
    app = _build_app_no_auth(_stub_router(["whatsapp", "telegram", "instagram", "web"]))

    metrics = MagicMock()
    metrics.get_stats.return_value = {"messages_received": 100, "errors": 5}  # 5%
    with patch(
        "backend.channels.optimizations.channel_metrics",
        metrics,
    ):
        status_code, body = await _get_health_public(app)

    assert status_code == 200
    assert "ts" in body and isinstance(body["ts"], (int, float))
    assert "channels" in body
    assert set(body["channels"].keys()) == {"whatsapp", "telegram", "instagram", "web"}
    for chan_name, chan_body in body["channels"].items():
        assert chan_body == {"status": "up"}, f"{chan_name} body shape drift: {chan_body}"


@pytest.mark.asyncio
async def test_health_public_does_not_leak_dlq_metrics_or_counts():
    """The endpoint MUST NOT expose dlq counts, error_rate strings, raw stats,
    registered_count, or any other field beyond `ts` and `channels.<name>.status`."""
    app = _build_app_no_auth(_stub_router(["whatsapp"]))

    metrics = MagicMock()
    metrics.get_stats.return_value = {
        "messages_received": 1000,
        "errors": 30,
        "internal_secret": "should-not-leak",
    }
    with patch(
        "backend.channels.optimizations.channel_metrics",
        metrics,
    ):
        _, body = await _get_health_public(app)

    forbidden_top_level = {
        "dlq", "stats", "registered_count", "error_rate", "timestamp", "status",
    }
    assert not (set(body.keys()) & forbidden_top_level), (
        f"public endpoint leaked top-level keys: "
        f"{set(body.keys()) & forbidden_top_level}"
    )
    for chan in body["channels"].values():
        assert set(chan.keys()) == {"status"}, (
            f"channel body leaked extra keys: {chan.keys()}"
        )


@pytest.mark.asyncio
async def test_health_public_threshold_ladder_matches_private_health():
    """Stay consistent with /health: 5%→up, 30%→degraded, 60%→down."""
    cases = [(5, "up"), (30, "degraded"), (60, "down")]
    for errors, expected_status in cases:
        app = _build_app_no_auth(_stub_router(["whatsapp"]))
        metrics = MagicMock()
        metrics.get_stats.return_value = {"messages_received": 100, "errors": errors}
        with patch(
            "backend.channels.optimizations.channel_metrics",
            metrics,
        ):
            _, body = await _get_health_public(app)

        assert body["channels"]["whatsapp"]["status"] == expected_status, (
            f"errors={errors}% → expected {expected_status} "
            f"got {body['channels']['whatsapp']['status']}"
        )


@pytest.mark.asyncio
async def test_health_public_uninitialized_returns_known_channels_unknown_status():
    """W1.2-bug-2 regression: when `app.state.channel_router` is None
    (api process group runs `initialize_services_light` which intentionally
    sets channel_router=None — the heavy ChannelRouter lives in the rag
    process group), the endpoint MUST still return the four known channel
    names with status='unknown'. The bridge_state_reader maps unknown
    vocab to `degraded`, so the operator sees yellow ('can't see, channel
    is registered'), not red ('channel is dead')."""
    app = FastAPI()
    app.include_router(router)
    app.state.channel_router = None  # simulate light-init mode
    app.state.db_pool = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/channels/health-public")

    assert resp.status_code == 200
    body = resp.json()
    assert "ts" in body and isinstance(body["ts"], (int, float))
    assert set(body["channels"].keys()) == {"whatsapp", "telegram", "instagram", "web"}
    for chan_name, chan_body in body["channels"].items():
        assert chan_body == {"status": "unknown"}, (
            f"{chan_name} unexpected body shape: {chan_body}"
        )
    # An informational `info` field is acceptable so operators can tell why
    # the response is `unknown` from a lone curl.
    assert "info" in body or "error" in body
