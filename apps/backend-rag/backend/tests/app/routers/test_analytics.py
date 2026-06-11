"""Tests for /api/analytics/funnel-event (F-19 + MYTHOS B1).

Covers: allowlist acceptance/rejection (data-driven off ALLOWED_EVENTS),
session-id validation, hostname capture (D3/D9 foundation) and the §6
PII-scrub guardrail (payload values redacted before storage).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.database import get_database_pool
from backend.app.routers.analytics import router, scrub_pii

SESSION_ID = "55555555-5555-5555-8555-555555555555"


def make_app() -> tuple[FastAPI, AsyncMock]:
    """Build a minimal FastAPI app with a mocked DB pool — no real DB required.

    Returns the app AND the mocked connection so tests can assert on what
    actually gets persisted (PII scrub, hostname).
    """
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

    async def fake_pool() -> MagicMock:
        return mock_pool

    app.dependency_overrides[get_database_pool] = fake_pool
    return app, mock_conn


async def _post_event(
    app: FastAPI, body: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/analytics/funnel-event", json=body)
        return r.status_code, r.json()


@pytest.mark.asyncio
async def test_funnel_event_whitelisted() -> None:
    """Whitelisted event is accepted and returns ok=True."""
    app, _ = make_app()
    status, payload = await _post_event(
        app,
        {
            "session_id": "33333333-3333-4333-8333-333333333333",
            "event": "kbli_code_viewed",
            "payload": {"code": "47111"},
        },
    )
    assert status == 200
    assert payload["ok"] is True


@pytest.mark.asyncio
async def test_funnel_event_unknown_rejected() -> None:
    """Unknown event returns ok=False (not 422) — analytics never blocks UX."""
    app, mock_conn = make_app()
    status, payload = await _post_event(
        app,
        {
            "session_id": "44444444-4444-4444-8444-444444444444",
            "event": "not_in_whitelist",
            "payload": {},
        },
    )
    # Controller + implementer spec: unknown event returns ok=False
    # (not 422) — so analytics "never blocks UX".
    assert status == 200
    assert payload.get("ok") is False
    # Fail-closed: nothing reaches storage for an unknown event,
    # even if the payload contained PII.
    mock_conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_funnel_event_rejects_short_session_id() -> None:
    """Pydantic validation: session_id shorter than 32 chars → 422."""
    app, _ = make_app()
    status, _ = await _post_event(
        app,
        {"session_id": "tooshort", "event": "kbli_search", "payload": {}},
    )
    assert status == 422


@pytest.mark.asyncio
async def test_funnel_event_every_allowlisted_event_accepted() -> None:
    """Every event in ALLOWED_EVENTS is accepted end-to-end.

    Driven directly off the router's allowlist (not a hardcoded copy) so it
    cannot drift; cross-stack parity with funnel-view.ts + funnel-app.ts is
    enforced by test_analytics_funnel_parity.py.
    """
    from backend.app.routers.analytics import ALLOWED_EVENTS

    app, _ = make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for event in sorted(ALLOWED_EVENTS):
            r = await c.post(
                "/api/analytics/funnel-event",
                json={"session_id": SESSION_ID, "event": event, "payload": {}},
            )
            assert r.status_code == 200, f"Event {event!r} failed: {r.text}"
            assert r.json()["ok"] is True, f"Event {event!r} returned ok=False"


# ---------------------------------------------------------------------------
# MYTHOS D3/D9 foundation: hostname capture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_funnel_event_persists_hostname() -> None:
    """The emitting hostname is accepted and passed through to storage."""
    app, mock_conn = make_app()
    status, payload = await _post_event(
        app,
        {
            "session_id": SESSION_ID,
            "event": "visa_quiz_completed",
            "payload": {"purpose": "business"},
            "hostname": "balizero.com",
        },
    )
    assert status == 200
    assert payload["ok"] is True
    mock_conn.execute.assert_awaited_once()
    args = mock_conn.execute.await_args.args
    # Positional SQL params: ($1 session_id, $2 event, $3 payload, $4 hostname)
    assert args[1] == SESSION_ID
    assert args[2] == "visa_quiz_completed"
    assert args[4] == "balizero.com"


@pytest.mark.asyncio
async def test_funnel_event_hostname_optional() -> None:
    """Events without a hostname (SSR / legacy emitters) are still accepted."""
    app, mock_conn = make_app()
    status, payload = await _post_event(
        app,
        {"session_id": SESSION_ID, "event": "kbli_search", "payload": {}},
    )
    assert status == 200
    assert payload["ok"] is True
    args = mock_conn.execute.await_args.args
    assert args[4] is None


# ---------------------------------------------------------------------------
# MYTHOS §6 guardrail: PII scrub (scrub, don't drop)
# ---------------------------------------------------------------------------


def test_scrub_pii_redacts_email_and_phone() -> None:
    """Email + phone-like values are redacted; surrounding text survives."""
    payload = {
        "note": "reach me at fake_user@example.com please",
        "phone": "+62 812 3456 7890",
        "nested": {"messages": ["call +1 (555) 123-4567 tomorrow"]},
    }
    out = scrub_pii(payload)
    assert out["note"] == "reach me at [redacted] please"
    assert out["phone"] == "[redacted]"
    assert out["nested"]["messages"][0] == "call [redacted] tomorrow"
    dumped = json.dumps(out)
    assert "fake_user@example.com" not in dumped
    assert "3456" not in dumped


def test_scrub_pii_leaves_clean_payload_unchanged() -> None:
    """Non-PII strings, numbers, bools and short codes pass through intact."""
    payload = {
        "kbli_code": "47111",
        "top_visa": "C1 Tourism",
        "note": "leasehold 25 years",
        "visa_count": 3,
        "lat": -8.65,
        "active": True,
        "none": None,
    }
    assert scrub_pii(payload) == payload


@pytest.mark.asyncio
async def test_funnel_event_payload_pii_scrubbed_before_storage() -> None:
    """A payload arriving with email/phone is STORED redacted (scrub ≠ drop)."""
    app, mock_conn = make_app()
    status, payload = await _post_event(
        app,
        {
            "session_id": SESSION_ID,
            "event": "visa_whatsapp_cta",
            "payload": {
                "action": "clicked",
                "contact": "fake_user@example.com",
                "phone": "+62 812 3456 7890",
            },
        },
    )
    assert status == 200
    assert payload["ok"] is True
    args = mock_conn.execute.await_args.args
    stored = json.loads(args[3])
    # Scrubbed, not dropped: keys survive, PII values are redacted.
    assert stored["action"] == "clicked"
    assert stored["contact"] == "[redacted]"
    assert stored["phone"] == "[redacted]"
    assert "fake_user@example.com" not in args[3]
