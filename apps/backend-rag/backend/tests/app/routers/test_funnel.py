"""
Tests for funnel session tracking endpoints.

Uses the same pattern as test_hr_owner_cashout.py:
- Build a minimal FastAPI app with dependency overrides (no real DB required)
- AsyncClient + ASGITransport
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.database import get_database_pool
from backend.app.routers.funnel import router


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    # Build a mock pool whose acquire() is an async context manager
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.fetchrow = AsyncMock(return_value=None)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)

    async def fake_pool():
        return mock_pool

    app.dependency_overrides[get_database_pool] = fake_pool
    return app


@pytest.mark.asyncio
async def test_touch_creates_session() -> None:
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/funnel/session/touch",
            json={
                "session_id": "11111111-1111-4111-8111-111111111111",
                "funnel": "visa",
                "step_state": {"step": 1},
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_touch_rejects_bad_funnel() -> None:
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/funnel/session/touch",
            json={
                "session_id": "22222222-2222-4222-8222-222222222222",
                "funnel": "invalid",
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_touch_rejects_short_session_id() -> None:
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/funnel/session/touch",
            json={
                "session_id": "short",
                "funnel": "kbli",
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_convert_session_no_match_returns_ok() -> None:
    """convert endpoint should return ok=True even when session_id not found (no-op)."""
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/funnel/session/convert",
            json={
                "session_id": "33333333-3333-4333-8333-333333333333",
                "client_id": "44444444-4444-4444-8444-444444444444",
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
