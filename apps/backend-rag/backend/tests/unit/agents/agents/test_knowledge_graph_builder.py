from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.agents.knowledge_graph_builder import KnowledgeGraphBuilder


class AsyncContext:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_exc: Any) -> None:
        return None


def conversation_row(messages: Any) -> dict[str, Any]:
    return {"messages": messages, "client_id": "client-redacted", "created_at": "now"}


@pytest.fixture
def conn() -> MagicMock:
    db_conn = MagicMock()
    db_conn.fetchrow = AsyncMock()
    db_conn.fetch = AsyncMock()
    db_conn.transaction = MagicMock(return_value=AsyncContext(None))
    return db_conn


@pytest.fixture
def db_pool(conn: MagicMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncContext(conn))
    return pool


@pytest.fixture
def builder(db_pool: MagicMock) -> KnowledgeGraphBuilder:
    kg_builder = KnowledgeGraphBuilder(db_pool=db_pool)
    kg_builder.repository = MagicMock()
    kg_builder.repository.add_entity_mention = AsyncMock()
    return kg_builder


def test_init_raises_when_no_pool_is_available() -> None:
    fake_main_cloud = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with patch.dict(sys.modules, {"backend.app.main_cloud": fake_main_cloud}):
        with pytest.raises(RuntimeError, match="Database pool not available"):
            KnowledgeGraphBuilder()


@pytest.mark.asyncio
async def test_public_wrappers_delegate_to_services(builder: KnowledgeGraphBuilder) -> None:
    db_conn = MagicMock()
    entity = {"type": "visa", "name": "KITAS", "canonical_name": "KITAS"}
    builder.schema_service.init_schema = AsyncMock()
    builder.entity_extractor.extract_entities = AsyncMock(return_value=[entity])
    builder.relationship_extractor.extract_relationships = AsyncMock(return_value=[])
    builder.repository.upsert_entity = AsyncMock(return_value=17)
    builder.repository.upsert_relationship = AsyncMock()
    builder.repository.get_entity_insights = AsyncMock(return_value={"top_entities": []})
    builder.repository.semantic_search_entities = AsyncMock(return_value=[entity])

    assert await builder._get_db_pool() is builder.db_pool
    await builder.init_graph_schema()
    assert await builder.extract_entities_from_text("text", 1.5) == [entity]
    assert await builder.extract_relationships([entity], "text", 2.5) == []
    assert await builder.upsert_entity("visa", "KITAS", "KITAS", {}, db_conn) == 17
    await builder.upsert_relationship(1, 2, "RELATES_TO", 0.8, "evidence", {}, db_conn)
    assert await builder.get_entity_insights(3) == {"top_entities": []}
    assert await builder.semantic_search_entities("visa", 2) == [entity]

    builder.schema_service.init_schema.assert_awaited_once_with()
    builder.entity_extractor.extract_entities.assert_awaited_once_with("text", 1.5)
    builder.relationship_extractor.extract_relationships.assert_awaited_once_with(
        [entity], "text", 2.5
    )
    builder.repository.upsert_relationship.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_conversation_empty_id_and_missing_row_stop_early(
    builder: KnowledgeGraphBuilder,
    db_pool: MagicMock,
    conn: MagicMock,
) -> None:
    await builder.process_conversation("")
    db_pool.acquire.assert_not_called()

    conn.fetchrow.return_value = None
    builder.extract_entities_from_text = AsyncMock()
    await builder.process_conversation("conv-missing")

    conn.fetchrow.assert_awaited_once()
    builder.extract_entities_from_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_conversation_persists_entities_mentions_and_default_relationship(
    builder: KnowledgeGraphBuilder,
    conn: MagicMock,
) -> None:
    conn.fetchrow.return_value = conversation_row(
        '[{"role": "user", "content": "Need visa"}, '
        '{"role": "assistant", "content": "Discuss KITAS"}]'
    )
    entities = [
        {"type": "topic", "name": "Visa", "canonical_name": "visa", "context": "Need visa"},
        {"type": "permit", "name": "KITAS", "canonical_name": "kitas"},
    ]
    builder.extract_entities_from_text = AsyncMock(return_value=entities)
    builder.extract_relationships = AsyncMock(
        return_value=[{"source": "Visa", "target": "KITAS", "relationship": "MENTIONS"}]
    )
    builder.upsert_entity = AsyncMock(side_effect=[11, 22])
    builder.upsert_relationship = AsyncMock()

    await builder.process_conversation("conv-1")

    builder.extract_entities_from_text.assert_awaited_once_with(
        "user: Need visa\nassistant: Discuss KITAS"
    )
    assert [c.kwargs["metadata"] for c in builder.upsert_entity.await_args_list] == [
        {"context": "Need visa"},
        {"context": ""},
    ]
    assert [c.kwargs["context"] for c in builder.repository.add_entity_mention.await_args_list] == [
        "Need visa",
        "",
    ]
    builder.upsert_relationship.assert_awaited_once_with(
        source_id=11,
        target_id=22,
        rel_type="MENTIONS",
        strength=0.7,
        evidence="",
        source_ref={"type": "conversation", "id": "conv-1"},
        conn=conn,
    )


@pytest.mark.asyncio
async def test_process_conversation_uses_raw_text_when_message_json_is_malformed(
    builder: KnowledgeGraphBuilder,
    conn: MagicMock,
) -> None:
    conn.fetchrow.return_value = conversation_row("{not json")
    builder.extract_entities_from_text = AsyncMock(return_value=[])

    await builder.process_conversation("conv-bad-json")

    builder.extract_entities_from_text.assert_awaited_once_with("{not json")


@pytest.mark.asyncio
async def test_process_conversation_ignores_relationships_with_unknown_entities(
    builder: KnowledgeGraphBuilder,
    conn: MagicMock,
) -> None:
    conn.fetchrow.return_value = conversation_row([{"role": "user", "content": "Discuss visa"}])
    builder.extract_entities_from_text = AsyncMock(
        return_value=[
            {"type": "topic", "name": "Visa", "canonical_name": "visa"},
            {"type": "place", "name": "Indonesia", "canonical_name": "indonesia"},
        ]
    )
    builder.extract_relationships = AsyncMock(
        return_value=[{"source": "Visa", "target": "Unknown", "relationship": "MENTIONS"}]
    )
    builder.upsert_entity = AsyncMock(side_effect=[11, 22])
    builder.upsert_relationship = AsyncMock()

    await builder.process_conversation("conv-2")

    builder.upsert_relationship.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_graph_defaults_invalid_days_back_and_continues_after_errors(
    builder: KnowledgeGraphBuilder,
    conn: MagicMock,
) -> None:
    conn.fetch.return_value = [{"conversation_id": "conv-1"}, {"conversation_id": "conv-2"}]
    builder.process_conversation = AsyncMock(side_effect=[RuntimeError("boom"), None])

    await builder.build_graph_from_all_conversations(days_back=0)

    assert conn.fetch.await_args.args[1] == 30
    assert [c.args[0] for c in builder.process_conversation.await_args_list] == [
        "conv-1",
        "conv-2",
    ]


@pytest.mark.asyncio
async def test_build_graph_reraises_fetch_errors(
    builder: KnowledgeGraphBuilder,
    conn: MagicMock,
) -> None:
    conn.fetch.side_effect = RuntimeError("fetch failed")

    with pytest.raises(RuntimeError, match="fetch failed"):
        await builder.build_graph_from_all_conversations(days_back=7)
