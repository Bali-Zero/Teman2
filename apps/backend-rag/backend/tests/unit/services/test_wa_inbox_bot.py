"""Tests for the WA Meta-inbox bot reply generator (generate_bot_reply).

Covers the Option-B safety contract:
  - feature flag OFF (default) → raises (worker marks failed/retry, no send).
  - no customer message in thread → raises.
  - RAG abstain → raises (never guess).
  - empty RAG answer → raises.
  - happy path → returns the RAG answer, sends the correct payload to the
    RAG worker (query = latest customer msg, history oldest→newest, channel).
  - [ESCALATE] marker stripped from the answer.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.services.integrations import wa_inbox_bot


class _Conn:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        fetchrow_result: dict[str, Any] | None = None,
        fetchrow_error: Exception | None = None,
    ) -> None:
        self._rows = rows
        self._fetchrow_result = fetchrow_result
        self._fetchrow_error = fetchrow_error
        self.fetchrow_calls = 0

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return self._rows

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        # Used by resolve_sender_identity's team_members/clients lookups.
        # No table-routing needed here — these tests either want "no match"
        # (default None, both lookups miss → role=unknown) or "DB down"
        # (fetchrow_error, raised on the first lookup it makes).
        self.fetchrow_calls += 1
        if self._fetchrow_error is not None:
            raise self._fetchrow_error
        return self._fetchrow_result


class _Pool:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        fetchrow_result: dict[str, Any] | None = None,
        fetchrow_error: Exception | None = None,
    ) -> None:
        self._conn = _Conn(rows, fetchrow_result=fetchrow_result, fetchrow_error=fetchrow_error)

    def acquire(self) -> Any:
        @asynccontextmanager
        async def _cm():
            yield self._conn

        return _cm()


def _thread(thread_id: int = 7, phone: str = "62811") -> dict[str, Any]:
    return {"thread_id": thread_id, "counterpart_phone": phone}


def _mock_rag(monkeypatch, response_json: dict[str, Any]) -> dict[str, Any]:
    """Patch the persistent RAG client; return a captured dict for assertions."""
    captured: dict[str, Any] = {}

    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=response_json)

    async def _post(url: str, json: dict[str, Any]) -> Any:
        captured["url"] = url
        captured["json"] = json
        return resp

    client = MagicMock()
    client.post = AsyncMock(side_effect=_post)

    async def _get_client() -> Any:
        return client

    monkeypatch.setattr(wa_inbox_bot, "_get_rag_client", _get_client)
    return captured


# newest→oldest as the SQL ORDER BY DESC returns them.
_ROWS_NEWEST_FIRST = [
    {"direction": "inbound", "sender_role": "customer", "body": "Quanto costa un KITAS?"},
    {"direction": "outbound", "sender_role": "bot", "body": "Ciao! Come posso aiutarti?"},
    {"direction": "inbound", "sender_role": "customer", "body": "Ciao"},
]


@pytest.mark.asyncio
async def test_flag_off_raises(monkeypatch):
    monkeypatch.delenv("WA_INBOX_BOT_AUTOREPLY", raising=False)
    pool = _Pool(_ROWS_NEWEST_FIRST)
    with pytest.raises(RuntimeError, match="disabled"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_no_customer_message_raises(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    pool = _Pool([{"direction": "outbound", "sender_role": "bot", "body": "hi"}])
    with pytest.raises(RuntimeError, match="no customer message"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_abstain_raises(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(monkeypatch, {"abstain": True, "abstain_reason": "low_evidence", "answer": ""})
    pool = _Pool(_ROWS_NEWEST_FIRST)
    with pytest.raises(RuntimeError, match="abstained"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_empty_answer_raises(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(monkeypatch, {"abstain": False, "answer": "   "})
    pool = _Pool(_ROWS_NEWEST_FIRST)
    with pytest.raises(RuntimeError, match="empty RAG answer"):
        await wa_inbox_bot.generate_bot_reply(pool, _thread())


@pytest.mark.asyncio
async def test_happy_path_returns_answer_and_payload(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    captured = _mock_rag(
        monkeypatch,
        {"abstain": False, "answer": "Il KITAS investitore parte da..."},
    )
    pool = _Pool(_ROWS_NEWEST_FIRST)

    answer = await wa_inbox_bot.generate_bot_reply(pool, _thread(thread_id=7, phone="62811"))

    assert answer == "Il KITAS investitore parte da..."
    sent = captured["json"]
    # query = the LATEST inbound customer message
    assert sent["query"] == "Quanto costa un KITAS?"
    assert sent["channel"] == "whatsapp"
    assert sent["user_id"] == "whatsapp_62811"
    assert sent["session_id"] == "wa_meta_session_7"
    # history oldest→newest, EXCLUDING the query row → ["Ciao"(user), bot(assistant)]
    hist = sent["conversation_history"]
    assert hist == [
        {"role": "user", "content": "Ciao"},
        {"role": "assistant", "content": "Ciao! Come posso aiutarti?"},
    ]


@pytest.mark.asyncio
async def test_escalate_marker_stripped(monkeypatch):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    _mock_rag(
        monkeypatch,
        {"abstain": False, "answer": "Ti metto in contatto col team [ESCALATE]"},
    )
    pool = _Pool(_ROWS_NEWEST_FIRST)
    answer = await wa_inbox_bot.generate_bot_reply(pool, _thread())
    assert "[ESCALATE]" not in answer
    assert answer == "Ti metto in contatto col team"


# ── Service-to-service auth header (X-Internal-Key) ──
# Regression guard for the silent-401 bug: /api/agentic-rag/query is not public,
# so the api→rag hop MUST carry X-Internal-Key or HybridAuthMiddleware rejects it
# with 401 → the worker marks every bot row failed → the bot never replies.


def test_rag_client_headers_sends_internal_key_when_configured(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", "secret-xyz")
    headers = wa_inbox_bot._rag_client_headers()
    assert headers == {"X-Internal-Key": "secret-xyz"}


def test_rag_client_headers_omits_internal_key_and_warns_when_unset(monkeypatch, caplog):
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", None)
    with caplog.at_level("WARNING"):
        headers = wa_inbox_bot._rag_client_headers()
    assert headers == {}
    assert any("WA_MIRROR_INTERNAL_KEY not configured" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_get_rag_client_applies_internal_key_header(monkeypatch):
    """End-to-end: the cached client carries the X-Internal-Key header."""
    monkeypatch.setattr(wa_inbox_bot, "_rag_client", None)
    monkeypatch.setattr(wa_inbox_bot.settings, "wa_mirror_internal_key", "secret-xyz")
    monkeypatch.setattr(wa_inbox_bot, "get_rag_worker_url", lambda: "http://rag.internal:8080")
    client = await wa_inbox_bot._get_rag_client()
    try:
        assert client.headers.get("x-internal-key") == "secret-xyz"
    finally:
        await client.aclose()
        wa_inbox_bot._rag_client = None


# ── P9: admission semaphore bounding concurrent RAG calls ──────────────────


def test_bot_generation_semaphore_defaults_to_3(monkeypatch):
    monkeypatch.delenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", raising=False)
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    sem = wa_inbox_bot._get_bot_generation_semaphore()
    assert sem._value == 3


def test_bot_generation_semaphore_env_override(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "7")
    sem = wa_inbox_bot._get_bot_generation_semaphore()
    assert sem._value == 7


def test_bot_generation_semaphore_invalid_env_falls_back_to_3(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "not-a-number")
    sem = wa_inbox_bot._get_bot_generation_semaphore()
    assert sem._value == 3


def test_bot_generation_semaphore_is_a_singleton(monkeypatch):
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "2")
    first = wa_inbox_bot._get_bot_generation_semaphore()
    # a second env value must NOT retroactively resize an already-built semaphore
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "9")
    second = wa_inbox_bot._get_bot_generation_semaphore()
    assert first is second
    assert second._value == 2


@pytest.mark.asyncio
async def test_bot_generation_semaphore_bounds_concurrent_rag_calls(monkeypatch):
    """5 concurrent generate_bot_reply calls with max_concurrent=2 must never
    have more than 2 RAG POSTs in flight at once."""
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    monkeypatch.setattr(wa_inbox_bot, "_bot_generation_semaphore", None)
    monkeypatch.setenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "2")

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value={"abstain": False, "answer": "ok"})

    async def _post(url: str, json: dict[str, Any]) -> Any:
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return resp

    client = MagicMock()
    client.post = AsyncMock(side_effect=_post)

    async def _get_client() -> Any:
        return client

    monkeypatch.setattr(wa_inbox_bot, "_get_rag_client", _get_client)

    pool = _Pool(_ROWS_NEWEST_FIRST)
    results = await asyncio.gather(
        *[
            wa_inbox_bot.generate_bot_reply(pool, _thread(thread_id=i))
            for i in range(5)
        ]
    )

    assert results == ["ok"] * 5
    assert max_in_flight <= 2
    assert client.post.await_count == 5


# ── P0-ID containment (2026-07-24): no client-side profile field anymore ──
# Team-assistant V1 (2026-07-19) used to resolve the sender's identity HERE
# and forward it as an explicit `profile` request field. That mechanism was
# removed: the RAG router now re-derives the same identity server-side
# (`agentic_rag.py::_resolve_trusted_wa_profile`) from `user_id`, so a
# client-declared `profile` can never be forged. These tests assert the new
# innocence contract: `generate_bot_reply`'s payload NEVER carries a
# `profile` key, and NEVER calls a DB-backed identity lookup of its own,
# regardless of whether the sender is owner/team/client/unknown or the DB
# is down — that work is no longer this function's job.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_env", "team_env", "fetchrow_result", "fetchrow_error", "phone"),
    [
        pytest.param("62811000111", None, None, None, "62811000111", id="owner"),
        pytest.param(
            None, "62811000222:Test Member Alpha", None, None, "62811000222", id="team-env"
        ),
        pytest.param(
            None,
            None,
            {"id": "tm-1", "display_name": "Test Member Beta", "email": "beta@balizero.com"},
            None,
            "62811000333",
            id="team-db",
        ),
        pytest.param(None, None, None, None, "62899999999", id="unknown"),
        pytest.param(
            None,
            None,
            None,
            asyncpg.PostgresError("db down"),
            "62899999999",
            id="db-down",
        ),
    ],
)
async def test_payload_never_carries_a_profile_key(
    monkeypatch, owner_env, team_env, fetchrow_result, fetchrow_error, phone
):
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")
    if owner_env:
        monkeypatch.setenv("WHATSAPP_OWNER_NUMBERS", owner_env)
    else:
        monkeypatch.delenv("WHATSAPP_OWNER_NUMBERS", raising=False)
    if team_env:
        monkeypatch.setenv("WHATSAPP_TEAM_NUMBERS", team_env)
    else:
        monkeypatch.delenv("WHATSAPP_TEAM_NUMBERS", raising=False)
    captured = _mock_rag(monkeypatch, {"abstain": False, "answer": "ok"})
    pool = _Pool(_ROWS_NEWEST_FIRST, fetchrow_result=fetchrow_result, fetchrow_error=fetchrow_error)

    await wa_inbox_bot.generate_bot_reply(pool, _thread(phone=phone))

    sent = captured["json"]
    assert "profile" not in sent
    # fetchrow (team/client DB lookups) would only ever fire from a local
    # identity resolution — asserting it was never called proves the
    # function truly stopped resolving identity itself, not just that it
    # happened to drop the key afterward.
    assert pool._conn.fetchrow_calls == 0
