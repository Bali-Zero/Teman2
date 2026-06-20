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

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations import wa_inbox_bot


class _Conn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return self._rows


class _Pool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._conn = _Conn(rows)

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
