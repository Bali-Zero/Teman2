from __future__ import annotations

import json
from typing import Any

from backend.services.misc import conversation_service as conversation_module
from backend.services.misc.conversation_service import ConversationService


class FakeMemoryCache:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []
        self.conversations: dict[str, list[dict[str, str]]] = {}

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self.messages.append((session_id, role, content))

    def get_conversation(self, session_id: str) -> list[dict[str, str]]:
        return self.conversations.get(session_id, [])


class FakeConn:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.calls.append((query, args))
        return self.row


class FakeAcquire:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConn:
        return self.conn

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class FakePool:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


async def test_save_conversation_writes_memory_cache_and_db(monkeypatch) -> None:
    cache = FakeMemoryCache()
    conn = FakeConn({"id": 42})
    monkeypatch.setattr(conversation_module, "get_memory_cache", lambda: cache)
    service = ConversationService(FakePool(conn))
    messages = [{"role": "user", "content": "hello"}]

    result = await service.save_conversation(
        user_email="user@example.test",
        messages=messages,
        session_id="session-1",
        metadata={"source": "test"},
    )

    assert result["success"] is True
    assert result["conversation_id"] == 42
    assert result["persistence_mode"] == "db"
    assert cache.messages == [("session-1", "user", "hello")]
    assert conn.calls[0][1][0:4] == (
        "user@example.test",
        "session-1",
        messages,
        {"source": "test"},
    )


async def test_save_conversation_uses_memory_fallback_without_db(monkeypatch) -> None:
    cache = FakeMemoryCache()
    monkeypatch.setattr(conversation_module, "get_memory_cache", lambda: cache)
    service = ConversationService(None)  # type: ignore[arg-type]

    result = await service.save_conversation(
        user_email="user@example.test",
        messages=[{"content": "missing role"}],
        session_id="session-1",
    )

    assert result["conversation_id"] == 0
    assert result["persistence_mode"] == "memory_fallback"
    assert cache.messages == [("session-1", "unknown", "missing role")]


async def test_get_history_reads_db_json_and_applies_limit() -> None:
    messages = [{"role": "user", "content": "one"}, {"role": "assistant", "content": "two"}]
    service = ConversationService(FakePool(FakeConn({"messages": json.dumps(messages)})))

    history = await service.get_history("user@example.test", limit=1)

    assert history == {"messages": [messages[1]], "source": "db", "total": 2}


async def test_get_history_falls_back_to_memory_cache(monkeypatch) -> None:
    cache = FakeMemoryCache()
    cache.conversations["session-1"] = [
        {"role": "user", "content": "cached"},
        {"role": "assistant", "content": "answer"},
    ]
    monkeypatch.setattr(conversation_module, "get_memory_cache", lambda: cache)
    service = ConversationService(None)  # type: ignore[arg-type]

    history = await service.get_history(
        "user@example.test",
        limit=1,
        session_id="session-1",
    )

    assert history == {
        "messages": [{"role": "assistant", "content": "answer"}],
        "source": "memory_cache",
        "total": 2,
    }
