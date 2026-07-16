"""PR0 safety freeze (W3) — /handoff must resolve the recommended visa name
and price ONLY from the server-persisted `visa_oracle_sessions` snapshot
(itself PricingService-derived, written by /recommend), never from the
client-posted `recommended_visas`/prices in the HandoffRequest body.

Round2 spec §6.2 handoff row: "Client-supplied recommendations, prices, and
quiz facts are ignored and eventually removed." product-design.md §2 lists
the untrusted handoff path among the confirmed P0 claims.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request


class _AcquireCM:
    """Minimal async context manager mimicking `pool.acquire()`."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a):
        return False


def _fake_pool(fetchrow_return):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))
    return pool, conn


def _build_request() -> Request:
    return Request({"type": "http", "headers": []})


def _stub_telegram(monkeypatch):
    fake_telegram = MagicMock()
    fake_telegram.send_message = AsyncMock()
    monkeypatch.setattr(
        "backend.services.integrations.telegram_bot_service.telegram_bot",
        fake_telegram,
    )
    return fake_telegram


@pytest.mark.asyncio
async def test_handoff_uses_server_price_ignores_client_price(monkeypatch):
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps({"nationality": "US", "purpose": "work", "duration": "long"}),
        "recommended_visas": json.dumps(
            [{"visa_name": "Working KITAS", "price": "18.000.000 IDR", "score": 4.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "US", "purpose": "work", "duration": "long"},
        recommended_visas=[{"visa_name": "FREE VISA SCAM", "price": "1 IDR"}],
        messages=[],
    )
    resp = await mod.handoff(_build_request(), body, db_pool=pool)

    assert resp.success is True
    assert "Working" in resp.whatsapp_url
    assert "KITAS" in resp.whatsapp_url
    assert "18.000.000" in resp.whatsapp_url
    assert "FREE" not in resp.whatsapp_url
    assert "SCAM" not in resp.whatsapp_url


@pytest.mark.asyncio
async def test_handoff_no_price_when_session_not_found(monkeypatch):
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool(None)  # no persisted row for this session_id
    _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="unknown-session",
        quiz_answers={"nationality": "US", "purpose": "work", "duration": "long"},
        recommended_visas=[{"visa_name": "Should Be Ignored", "price": "999 IDR"}],
        messages=[],
    )
    resp = await mod.handoff(_build_request(), body, db_pool=pool)

    assert resp.success is True
    assert "Should Be Ignored" not in resp.whatsapp_url
    assert "contact" in resp.whatsapp_url
    assert "pricing" in resp.whatsapp_url


@pytest.mark.asyncio
async def test_handoff_logs_divergence_warning(monkeypatch, caplog):
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps({}),
        "recommended_visas": json.dumps(
            [{"visa_name": "Working KITAS", "price": "18.000.000 IDR", "score": 4.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "US"},
        recommended_visas=[{"visa_name": "Different Visa", "price": "1 IDR"}],
        messages=[],
    )
    with caplog.at_level("WARNING"):
        await mod.handoff(_build_request(), body, db_pool=pool)

    assert any("diverges" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handoff_no_divergence_warning_when_client_matches_server(monkeypatch, caplog):
    """Innocence test: identical client/server top pick logs nothing."""
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps({}),
        "recommended_visas": json.dumps(
            [{"visa_name": "Working KITAS", "price": "18.000.000 IDR", "score": 4.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "US"},
        recommended_visas=[{"visa_name": "Working KITAS", "price": "18.000.000 IDR"}],
        messages=[],
    )
    with caplog.at_level("WARNING"):
        await mod.handoff(_build_request(), body, db_pool=pool)

    assert not any("diverges" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handoff_uses_server_visas_for_telegram_summary(monkeypatch):
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps({"nationality": "DE", "purpose": "retire", "duration": "long"}),
        "recommended_visas": json.dumps(
            [{"visa_name": "Retirement KITAS", "price": "9.000.000 IDR", "score": 3.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    fake_telegram = _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "DE", "purpose": "retire", "duration": "long"},
        recommended_visas=[{"visa_name": "Not The Real One", "price": "0 IDR"}],
        messages=[],
    )
    await mod.handoff(_build_request(), body, db_pool=pool)

    fake_telegram.send_message.assert_awaited_once()
    sent_text = fake_telegram.send_message.call_args.kwargs.get("text", "")
    assert "Retirement KITAS" in sent_text
    assert "Not The Real One" not in sent_text


# ---------------------------------------------------------------------------
# _fetch_session_snapshot — pure helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_session_snapshot_returns_none_on_db_error():
    from backend.app.routers import visa_oracle as mod

    pool = MagicMock()

    def _raise(*_a, **_kw):
        raise RuntimeError("connection refused")

    pool.acquire = MagicMock(side_effect=_raise)

    result = await mod._fetch_session_snapshot(pool, "s1")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_session_snapshot_returns_none_when_no_row():
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool(None)
    result = await mod._fetch_session_snapshot(pool, "s1")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_session_snapshot_decodes_json_strings():
    from backend.app.routers import visa_oracle as mod

    row = {
        "quiz_answers": json.dumps({"nationality": "US"}),
        "recommended_visas": json.dumps([{"visa_name": "X"}]),
    }
    pool, _conn = _fake_pool(row)

    result = await mod._fetch_session_snapshot(pool, "s1")
    assert result == {
        "quiz_answers": {"nationality": "US"},
        "recommended_visas": [{"visa_name": "X"}],
    }


@pytest.mark.asyncio
async def test_fetch_session_snapshot_handles_already_decoded_values():
    """asyncpg can return jsonb as already-decoded objects depending on
    codec configuration — handle both shapes defensively."""
    from backend.app.routers import visa_oracle as mod

    row = {
        "quiz_answers": {"nationality": "US"},
        "recommended_visas": [{"visa_name": "X"}],
    }
    pool, _conn = _fake_pool(row)

    result = await mod._fetch_session_snapshot(pool, "s1")
    assert result == {
        "quiz_answers": {"nationality": "US"},
        "recommended_visas": [{"visa_name": "X"}],
    }
