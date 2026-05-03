"""Tests for /api/analytics/funnel-event (F-19)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.database import get_database_pool
from backend.app.routers.analytics import router


def make_app() -> FastAPI:
    """Build a minimal FastAPI app with a mocked DB pool — no real DB required."""
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
async def test_funnel_event_whitelisted() -> None:
    """Whitelisted event is accepted and returns ok=True."""
    app = make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/analytics/funnel-event",
            json={
                "session_id": "33333333-3333-4333-8333-333333333333",
                "event": "kbli_code_viewed",
                "payload": {"code": "47111"},
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_funnel_event_unknown_rejected() -> None:
    """Unknown event returns ok=False (not 422) — analytics never blocks UX."""
    app = make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/analytics/funnel-event",
            json={
                "session_id": "44444444-4444-4444-8444-444444444444",
                "event": "not_in_whitelist",
                "payload": {},
            },
        )
        # Controller + implementer spec: unknown event returns ok=False
        # (not 422) — so analytics "never blocks UX".
        assert r.status_code == 200
        assert r.json().get("ok") is False


@pytest.mark.asyncio
async def test_funnel_event_rejects_short_session_id() -> None:
    """Pydantic validation: session_id shorter than 32 chars → 422."""
    app = make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/analytics/funnel-event",
            json={
                "session_id": "tooshort",
                "event": "kbli_search",
                "payload": {},
            },
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_funnel_event_all_eleven_allowed() -> None:
    """Verify all 11 whitelisted events are accepted."""
    app = make_app()
    allowed = [
        "visa_quiz_completed",
        "visa_result_viewed",
        "visa_chat_question",
        "visa_whatsapp_cta",
        "visa_calling_block",
        "kbli_code_viewed",
        "kbli_search",
        "kbli_chat_question",
        "tax_dashboard_viewed",
        "property_cta_clicked",
        "property_chat_question",
    ]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for event in allowed:
            r = await c.post(
                "/api/analytics/funnel-event",
                json={
                    "session_id": "55555555-5555-5555-8555-555555555555",
                    "event": event,
                    "payload": {},
                },
            )
            assert r.status_code == 200, f"Event {event!r} failed: {r.text}"
            assert r.json()["ok"] is True, f"Event {event!r} returned ok=False"
