from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.rag.agentic import context_manager as module
from backend.services.rag.agentic.context_manager import (
    fetch_memory_facts,
    fetch_profile_and_history,
    get_user_context,
)


class FakeMemoryCache:
    def __init__(self, entities: dict[str, Any] | None = None) -> None:
        self.entities = entities or {}
        self.requested_ids: list[str] = []

    def get_entities(self, conversation_id: str) -> dict[str, Any]:
        self.requested_ids.append(conversation_id)
        return self.entities


class FakeAcquire:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self.conn

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeConnection:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((query, args))
        return self.row


class FakePool:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


class FakeMemoryOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def get_user_context(self, user_id: str, query: str | None = None) -> SimpleNamespace:
        self.calls.append((user_id, query))
        return SimpleNamespace(
            profile_facts=["Prefers concise updates"],
            collective_facts=["KITAS renewal needs timeline check"],
            timeline_summary="Recent visa renewal discussion",
            kg_entities=[{"name": "KITAS"}],
            summary="User summary",
            counters={"conversations": 3},
        )


@pytest.mark.asyncio
async def test_fetch_profile_and_history_returns_empty_context_for_anonymous_user() -> None:
    result = await fetch_profile_and_history(db_pool=None, user_id="anonymous")

    assert result == {"profile": None, "history": [], "entities": {}}


@pytest.mark.asyncio
async def test_fetch_profile_and_history_loads_profile_history_and_cached_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = FakeMemoryCache({"visa_type": "KITAS"})
    monkeypatch.setattr(module, "get_memory_cache", lambda: cache)
    latest_conversation = {
        "id": "conversation-1",
        "messages": json.dumps(
            [{"role": "user", "content": f"message {index}"} for index in range(25)],
        ),
    }
    row = {
        "id": "user-1",
        "name": "Marco",
        "role": "client",
        "department": "Sales",
        "preferred_language": "en",
        "notes": "VIP",
        "email": "marco@example.com",
        "latest_conversation": json.dumps(latest_conversation),
    }
    conn = FakeConnection(row)

    result = await fetch_profile_and_history(
        FakePool(conn),
        "marco@example.com",
        session_id="session-1",
    )

    assert result["profile"] == {
        "id": "user-1",
        "name": "Marco",
        "role": "client",
        "department": "Sales",
        "preferred_language": "en",
        "notes": "VIP",
        "email": "marco@example.com",
    }
    assert len(result["history"]) == 20
    assert result["history"][0]["content"] == "message 5"
    assert result["entities"] == {"visa_type": "KITAS"}
    assert cache.requested_ids == ["conversation-1"]
    assert conn.fetchrow_calls[0][1] == ("marco@example.com", "session-1")


@pytest.mark.asyncio
async def test_fetch_memory_facts_returns_empty_data_without_orchestrator() -> None:
    result = await fetch_memory_facts(None, "user-1", query="KITAS")

    assert result == {
        "facts": [],
        "collective_facts": [],
        "timeline_summary": None,
        "kg_entities": [],
        "summary": None,
        "counters": None,
        "memory_context": None,
    }


@pytest.mark.asyncio
async def test_fetch_memory_facts_maps_memory_context_fields() -> None:
    orchestrator = FakeMemoryOrchestrator()

    result = await fetch_memory_facts(orchestrator, "user-1", query="KITAS")

    assert orchestrator.calls == [("user-1", "KITAS")]
    assert result["facts"] == ["Prefers concise updates"]
    assert result["collective_facts"] == ["KITAS renewal needs timeline check"]
    assert result["timeline_summary"] == "Recent visa renewal discussion"
    assert result["kg_entities"] == [{"name": "KITAS"}]
    assert result["summary"] == "User summary"
    assert result["counters"] == {"conversations": 3}
    assert result["memory_context"].profile_facts == ["Prefers concise updates"]


@pytest.mark.asyncio
async def test_get_user_context_returns_empty_context_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "get_memory_cache", lambda: FakeMemoryCache())

    result = await get_user_context(None, "anonymous")

    assert result == {
        "profile": None,
        "history": [],
        "facts": [],
        "collective_facts": [],
        "entities": {},
    }


@pytest.mark.asyncio
async def test_get_user_context_merges_profile_and_memory_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "get_memory_cache", lambda: FakeMemoryCache({"kbli": "47911"}))
    row = {
        "id": "user-1",
        "name": "Marco",
        "role": "client",
        "department": "Sales",
        "preferred_language": "en",
        "notes": None,
        "email": "marco@example.com",
        "latest_conversation": {
            "id": "conversation-1",
            "messages": [{"role": "user", "content": "Need KITAS"}],
        },
    }
    orchestrator = FakeMemoryOrchestrator()

    result = await get_user_context(
        FakePool(FakeConnection(row)),
        "marco@example.com",
        memory_orchestrator=orchestrator,
        query="Need KITAS",
        session_id="session-1",
    )

    assert result["profile"]["name"] == "Marco"
    assert result["history"] == [{"role": "user", "content": "Need KITAS"}]
    assert result["entities"] == {"kbli": "47911"}
    assert result["facts"] == ["Prefers concise updates"]
    assert result["collective_facts"] == ["KITAS renewal needs timeline check"]
    assert result["kg_entities"] == [{"name": "KITAS"}]
