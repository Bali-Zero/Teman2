"""Call the real SSE consumer and repository against the guarded PG fixture.

Only the language-model stream and request transport are synthetic. Database
reads, writes, the response generator and persistence metadata are real.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest

from backend.tests.db.test_universal_conversation_pg import conversation_pool  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_actual_stream_consumer_persists_concurrent_answers(
    conversation_pool: asyncpg.Pool,
) -> None:
    from backend.app.routers.agentic_rag import AgenticQueryRequest, stream_agentic_rag

    class SyntheticOrchestrator:
        async def stream_query(self, **kwargs):
            yield {"type": "token", "data": "synthetic-answer-" + kwargs["query"]}

    async def consume(index: int):
        request = AgenticQueryRequest(
            query=f"synthetic-question-{index}",
            session_id="synthetic-stream-session",
            # Exercise the supported caller-supplied history path, isolating the
            # persistence finalizer from unrelated RAG history retrieval.
            conversation_history=[{"role": "user", "content": "synthetic-prior"}],
        )
        http = SimpleNamespace(
            state=SimpleNamespace(correlation_id=f"synthetic-correlation-{index}"),
            headers={},
            is_disconnected=AsyncMock(return_value=False),
        )
        response = await stream_agentic_rag(
            request,
            http,
            current_user={"user_id": "synthetic-principal"},
            orchestrator=SyntheticOrchestrator(),
            db_pool=conversation_pool,
        )
        events = []
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            events.extend(
                json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")
            )
        metadata = [
            event["data"]
            for event in events
            if event["type"] == "metadata" and "persisted" in event["data"]
        ]
        assert len(metadata) == 1 and metadata[0]["persisted"] is True
        assert any(
            event == {"type": "token", "data": f"synthetic-answer-synthetic-question-{index}"}
            for event in events
        )
        return metadata[0]["conversation_id"]

    identifiers = await asyncio.gather(*(consume(i) for i in range(8)))
    assert len(set(identifiers)) == 1
    async with conversation_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, user_id, messages FROM conversations")
    assert len(rows) == 1 and rows[0]["id"] == identifiers[0]
    assert rows[0]["user_id"] == "synthetic-principal"
    assert len(rows[0]["messages"]) == 16
    assert {message["content"] for message in rows[0]["messages"]} == {
        item
        for i in range(8)
        for item in (f"synthetic-question-{i}", f"synthetic-answer-synthetic-question-{i}")
    }


@pytest.mark.asyncio
async def test_workspace_consumer_persists_concurrent_answers(conversation_pool, monkeypatch):
    from backend.app.routers import agentic_rag

    # Synthetic role directory; JWT middleware and the real team directory are
    # outside this persistence test. The consumer's authorization branches run.
    principal = "synthetic-agent@example.invalid"
    role = SimpleNamespace(role_id="synthetic-role", client_scope="assigned")
    monkeypatch.setattr(
        agentic_rag, "get_agent_role", lambda email: role if email == principal else None
    )
    monkeypatch.setattr(
        agentic_rag, "build_agent_context", lambda **kwargs: {"agent_name": "Synthetic Agent"}
    )

    class SyntheticOrchestrator:
        async def stream_query(self, **kwargs):
            assert kwargs["user_id"] == principal
            assert kwargs["agent_role"] is role and kwargs["channel"] == "workspace"
            yield {"type": "token", "data": "synthetic-workspace-answer"}

    async def consume(index):
        request = agentic_rag.WorkspaceQueryRequest(
            query=f"synthetic-workspace-question-{index}",
            session_id="synthetic-workspace-session",
            conversation_history=[{"role": "user", "content": "synthetic-prior"}],
        )
        http = SimpleNamespace(
            state=SimpleNamespace(correlation_id="synthetic-correlation"),
            headers={},
            is_disconnected=AsyncMock(return_value=False),
        )
        response = await agentic_rag.stream_workspace_agent(
            request,
            http,
            current_user={"email": principal},
            orchestrator=SyntheticOrchestrator(),
            db_pool=conversation_pool,
        )
        metadata = []
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    if event["type"] == "metadata" and "persisted" in event["data"]:
                        metadata.append(event["data"])
        assert len(metadata) == 1 and metadata[0]["persisted"] is True
        return metadata[0]["conversation_id"]

    ids = await asyncio.gather(*(consume(i) for i in range(8)))
    assert len(set(ids)) == 1
    async with conversation_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, user_id, messages FROM conversations")
        assert await conn.fetchval("SELECT count(*) FROM conversations") == 1
    assert row["id"] == ids[0] and row["user_id"] == principal
    assert len(row["messages"]) == 16


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identity,status", [({}, 401), ({"email": "unknown@example.invalid"}, 403)]
)
async def test_workspace_denial_writes_nothing(conversation_pool, monkeypatch, identity, status):
    from fastapi import HTTPException

    from backend.app.routers import agentic_rag

    monkeypatch.setattr(agentic_rag, "get_agent_role", lambda email: None)
    request = agentic_rag.WorkspaceQueryRequest(
        query="synthetic-query", session_id="synthetic-denied"
    )
    with pytest.raises(HTTPException) as failure:
        await agentic_rag.stream_workspace_agent(
            request,
            SimpleNamespace(),
            current_user=identity,
            orchestrator=SimpleNamespace(),
            db_pool=conversation_pool,
        )
    assert failure.value.status_code == status
    async with conversation_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM conversations") == 0
