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

# ---------------------------------------------------------------------------
# FIX-5 (Codex red-team P1 #4, client-trusted quiz + Markdown injection) and
# FIX-6 (Codex red-team P1 #5, async-persist race) additions live in this
# same file — they extend the existing W3 (server-authoritative price)
# coverage above with: (a) quiz_answers also preferring the server snapshot,
# (b) an explicit UNVERIFIED marker instead of silent suppression on a
# body-only lead, (c) retry behavior for both the snapshot read and the
# handoff-triggered UPDATE.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    """FIX-6 added real `asyncio.sleep` backoff to the retry paths this file
    exercises — default it to a no-op so the module stays fast. The
    dedicated retry-behavior tests below re-`monkeypatch.setattr` their own
    sleep stub AFTER this fixture runs (same `monkeypatch` instance per
    test), which simply overrides this default when they need to observe
    `sleep_calls`."""
    from backend.app.routers import visa_oracle as mod

    async def _noop_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", _noop_sleep)


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


# ---------------------------------------------------------------------------
# FIX-5 — quiz_answers also prefer the server-persisted snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handoff_uses_server_quiz_answers_for_whatsapp_url(monkeypatch):
    """FIX-5 (Codex red-team P1 #4): quiz facts (nationality/purpose/
    duration) also come from the server-persisted snapshot when one exists
    — not the client body. A stale or manipulated client body must not
    silently swap what's presented in the WhatsApp deep-link."""
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps(
            {"nationality": "Germany", "purpose": "retire", "duration": "long"}
        ),
        "recommended_visas": json.dumps(
            [{"visa_name": "Retirement KITAS", "price": "9.000.000 IDR", "score": 3.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "France", "purpose": "visit", "duration": "short"},
        recommended_visas=[],
        messages=[],
    )
    resp = await mod.handoff(_build_request(), body, db_pool=pool)

    assert "Germany" in resp.whatsapp_url
    assert "France" not in resp.whatsapp_url


@pytest.mark.asyncio
async def test_handoff_uses_server_quiz_answers_for_telegram_summary(monkeypatch):
    """Same server-preference for the Telegram lead summary."""
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps(
            {"nationality": "Germany", "purpose": "retire", "duration": "long"}
        ),
        "recommended_visas": json.dumps(
            [{"visa_name": "Retirement KITAS", "price": "9.000.000 IDR", "score": 3.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    fake_telegram = _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "France", "purpose": "visit", "duration": "short"},
        recommended_visas=[],
        messages=[],
    )
    await mod.handoff(_build_request(), body, db_pool=pool)

    sent_text = fake_telegram.send_message.call_args.kwargs.get("text", "")
    assert "Germany" in sent_text
    assert "France" not in sent_text


@pytest.mark.asyncio
async def test_handoff_falls_back_to_body_quiz_answers_when_no_snapshot(monkeypatch):
    """Innocence: when there is genuinely no server snapshot (session never
    persisted / not found), the body-posted quiz_answers are the only
    source available — falling back to them is correct, not a regression."""
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool(None)
    _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="unknown-session",
        quiz_answers={"nationality": "France", "purpose": "visit", "duration": "short"},
        recommended_visas=[],
        messages=[],
    )
    resp = await mod.handoff(_build_request(), body, db_pool=pool)

    assert "France" in resp.whatsapp_url


@pytest.mark.asyncio
async def test_handoff_body_only_lead_marked_unverified_not_suppressed(monkeypatch):
    """FIX-5: a body-only handoff (no server session at all) must still
    fire the Telegram lead — leads matter commercially — but tagged
    UNVERIFIED rather than silently suppressed or presented as verified."""
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool(None)  # no persisted row — genuinely no session
    fake_telegram = _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="unknown-session",
        quiz_answers={"nationality": "France", "purpose": "visit", "duration": "short"},
        recommended_visas=[],
        messages=[],
    )
    resp = await mod.handoff(_build_request(), body, db_pool=pool)

    assert resp.telegram_sent is True
    fake_telegram.send_message.assert_awaited_once()
    sent_text = fake_telegram.send_message.call_args.kwargs.get("text", "")
    assert "UNVERIFIED" in sent_text


@pytest.mark.asyncio
async def test_handoff_verified_session_has_no_unverified_marker(monkeypatch):
    """Innocence: a genuinely server-verified session must NOT carry the
    UNVERIFIED marker."""
    from backend.app.routers import visa_oracle as mod

    server_row = {
        "quiz_answers": json.dumps({"nationality": "US", "purpose": "work", "duration": "long"}),
        "recommended_visas": json.dumps(
            [{"visa_name": "Working KITAS", "price": "18.000.000 IDR", "score": 4.0}]
        ),
    }
    pool, _conn = _fake_pool(server_row)
    fake_telegram = _stub_telegram(monkeypatch)

    body = mod.HandoffRequest(
        session_id="s1",
        quiz_answers={"nationality": "US", "purpose": "work", "duration": "long"},
        recommended_visas=[],
        messages=[],
    )
    await mod.handoff(_build_request(), body, db_pool=pool)

    sent_text = fake_telegram.send_message.call_args.kwargs.get("text", "")
    assert "UNVERIFIED" not in sent_text


# ---------------------------------------------------------------------------
# FIX-6 — async-persist race: retry helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_snapshot_with_retry_succeeds_on_second_attempt(monkeypatch):
    """FIX-6 (Codex red-team P1 #5): the first read misses (INSERT still in
    flight), the second succeeds — the retry must not give up after one
    None."""
    from backend.app.routers import visa_oracle as mod

    calls = {"n": 0}

    async def _fake_fetch(_pool, _sid):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return {"quiz_answers": {"nationality": "US"}, "recommended_visas": [{"visa_name": "X"}]}

    monkeypatch.setattr(mod, "_fetch_session_snapshot", _fake_fetch)
    sleep_calls: list[float] = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    result = await mod._fetch_session_snapshot_with_retry(MagicMock(), "s1")

    assert result == {
        "quiz_answers": {"nationality": "US"},
        "recommended_visas": [{"visa_name": "X"}],
    }
    assert calls["n"] == 2
    assert sleep_calls == [0.4]


@pytest.mark.asyncio
async def test_fetch_snapshot_with_retry_gives_up_after_max_attempts(monkeypatch):
    """Still None after every attempt falls through to the existing safe
    no-price path — never raises, never hangs."""
    from backend.app.routers import visa_oracle as mod

    calls = {"n": 0}

    async def _fake_fetch(_pool, _sid):
        calls["n"] += 1
        return None

    monkeypatch.setattr(mod, "_fetch_session_snapshot", _fake_fetch)
    sleep_calls: list[float] = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    result = await mod._fetch_session_snapshot_with_retry(MagicMock(), "s1")

    assert result is None
    assert calls["n"] == 3
    assert sleep_calls == [0.4, 0.4]


@pytest.mark.asyncio
async def test_fetch_snapshot_with_retry_no_sleep_when_immediately_found(monkeypatch):
    """Innocence: the common case (session already persisted) must not pay
    any retry latency."""
    from backend.app.routers import visa_oracle as mod

    calls = {"n": 0}

    async def _fake_fetch(_pool, _sid):
        calls["n"] += 1
        return {"quiz_answers": {}, "recommended_visas": []}

    monkeypatch.setattr(mod, "_fetch_session_snapshot", _fake_fetch)
    sleep_calls: list[float] = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    result = await mod._fetch_session_snapshot_with_retry(MagicMock(), "s1")

    assert result == {"quiz_answers": {}, "recommended_visas": []}
    assert calls["n"] == 1
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_persist_session_handoff_retries_once_when_row_not_found(monkeypatch):
    """FIX-6: the UPDATE runs before /recommend's INSERT lands (0 rows
    affected) — retry once after 1s, then log-and-continue either way."""
    from backend.app.routers import visa_oracle as mod

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["UPDATE 0", "UPDATE 1"])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await mod._persist_session_handoff(pool, "s1")

    assert conn.execute.await_count == 2
    assert sleep_calls == [1.0]


@pytest.mark.asyncio
async def test_persist_session_handoff_logs_and_continues_when_row_never_appears(
    monkeypatch, caplog
):
    """Still 0 rows after the retry — must log and return, never raise."""
    from backend.app.routers import visa_oracle as mod

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 0")
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    async def _fake_sleep(seconds):
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    with caplog.at_level("INFO"):
        await mod._persist_session_handoff(pool, "s1")

    assert conn.execute.await_count == 2
    assert any("after 1s retry" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_persist_session_handoff_no_retry_when_row_found_immediately(monkeypatch):
    """Innocence: the common case succeeds on the first UPDATE — no sleep,
    no second query."""
    from backend.app.routers import visa_oracle as mod

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await mod._persist_session_handoff(pool, "s1")

    assert conn.execute.await_count == 1
    assert sleep_calls == []


class TestUpdateRowCount:
    """Unit tests for the asyncpg command-status parser backing FIX-6."""

    def test_parses_update_n(self) -> None:
        from backend.app.routers import visa_oracle as mod

        assert mod._update_row_count("UPDATE 1") == 1

    def test_parses_update_zero(self) -> None:
        from backend.app.routers import visa_oracle as mod

        assert mod._update_row_count("UPDATE 0") == 0

    def test_returns_zero_on_none(self) -> None:
        from backend.app.routers import visa_oracle as mod

        assert mod._update_row_count(None) == 0

    def test_returns_zero_on_malformed_status(self) -> None:
        from backend.app.routers import visa_oracle as mod

        assert mod._update_row_count("not-a-status") == 0
