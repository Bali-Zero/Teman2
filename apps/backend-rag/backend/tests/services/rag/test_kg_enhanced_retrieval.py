from __future__ import annotations

import pytest

from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval


class _Acquire:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self.conn

    async def __aexit__(self, *exc_info) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


class _FakeConn:
    def __init__(self, fetch_results: list[list[dict]], fetchval_result: int | None = None) -> None:
        self.fetch_results = fetch_results
        self.fetchval_result = fetchval_result
        self.fetch_calls: list[tuple[str, tuple]] = []
        self.fetchval_calls: list[tuple[str, tuple]] = []

    async def fetch(self, sql: str, *args):
        self.fetch_calls.append((sql, args))
        return self.fetch_results.pop(0)

    async def fetchval(self, sql: str, *args):
        self.fetchval_calls.append((sql, args))
        return self.fetchval_result


def test_extract_entities_from_query_detects_and_deduplicates_indonesian_terms() -> None:
    service = KGEnhancedRetrieval(db_pool=object())

    entities = service.extract_entities_from_query(
        "Can a PT PMA use KBLI 56101 for KITAS, KITAS and NIB registration?",
    )

    assert ("PT PMA", "pt_pma") in entities
    assert ("KBLI 56101", "kbli") in entities
    assert ("KITAS", "kitas") in entities
    assert ("NIB", "nib") in entities
    assert entities.count(("KITAS", "kitas")) == 1


@pytest.mark.asyncio
async def test_find_kg_entities_sanitizes_like_search_and_tags_matched_mention() -> None:
    conn = _FakeConn(
        fetch_results=[
            [
                {
                    "entity_id": "kg-1",
                    "entity_type": "kbli",
                    "name": "KBLI 56101",
                    "confidence": 0.95,
                    "source_chunk_ids": ["chunk-1"],
                },
            ],
        ],
    )
    service = KGEnhancedRetrieval(db_pool=_FakePool(conn))

    found = await service.find_kg_entities([("KBLI 56101%_", "kbli")], limit_per_mention=2)

    assert found == [
        {
            "entity_id": "kg-1",
            "entity_type": "kbli",
            "name": "KBLI 56101",
            "confidence": 0.95,
            "source_chunk_ids": ["chunk-1"],
            "matched_mention": "KBLI 56101%_",
        },
    ]
    assert conn.fetch_calls[0][1] == ("%kbli%56101%", "kbli", 2)


@pytest.mark.asyncio
async def test_get_related_entities_caps_high_depth_for_super_hub_seeds() -> None:
    conn = _FakeConn(
        fetchval_result=600,
        fetch_results=[
            [
                {
                    "relationship_id": "rel-1",
                    "source_entity_id": "seed",
                    "target_entity_id": "target",
                    "relationship_type": "requires",
                    "confidence": 0.8,
                    "source_chunk_ids": ["chunk-rel"],
                    "source_name": "PT PMA",
                    "source_type": "company",
                    "target_name": "NIB",
                    "target_type": "permit",
                },
            ],
            [
                {
                    "entity_id": "target",
                    "entity_type": "permit",
                    "name": "NIB",
                    "confidence": 0.9,
                    "source_chunk_ids": ["chunk-node"],
                },
            ],
        ],
    )
    service = KGEnhancedRetrieval(db_pool=_FakePool(conn))

    related, relationships = await service.get_related_entities(
        ["seed"],
        max_depth=10,
        limit=5,
    )

    assert conn.fetchval_calls[0][1] == (["seed"],)
    assert conn.fetch_calls[0][1] == (["seed"], 2, 5)
    assert relationships[0]["relationship_type"] == "requires"
    assert related == [
        {
            "entity_id": "target",
            "entity_type": "permit",
            "name": "NIB",
            "confidence": 0.9,
            "source_chunk_ids": ["chunk-node"],
        },
    ]


@pytest.mark.asyncio
async def test_get_source_chunks_deduplicates_node_and_edge_chunk_ids() -> None:
    conn = _FakeConn(
        fetch_results=[
            [{"source_chunk_ids": ["chunk-1", "chunk-2"]}],
            [{"source_chunk_ids": ["chunk-2", "chunk-3"]}],
        ],
    )
    service = KGEnhancedRetrieval(db_pool=_FakePool(conn))

    chunk_ids = await service.get_source_chunks(["entity-1"])

    assert set(chunk_ids) == {"chunk-1", "chunk-2", "chunk-3"}


def test_build_graph_summary_groups_entities_relationships_and_route() -> None:
    service = KGEnhancedRetrieval(db_pool=object())
    route = service.match_golden_route("I want to open a restaurant in Bali")

    summary = service.build_graph_summary(
        entities=[
            {"entity_type": "company", "name": "PT PMA"},
            {"entity_type": "permit", "name": "NIB"},
        ],
        relationships=[
            {
                "source_name": "PT PMA",
                "relationship_type": "requires",
                "target_name": "NIB",
            },
        ],
        query_mentions=[("PT PMA", "pt_pma")],
        golden_route=route,
    )

    assert "[KNOWLEDGE GRAPH CONTEXT]" in summary
    assert "Open Restaurant as Foreigner" in summary
    assert "company: PT PMA" in summary
    assert "permit: NIB" in summary
    assert "PT PMA --[requires]--> NIB" in summary


@pytest.mark.asyncio
async def test_get_context_for_query_returns_golden_route_without_db_hits() -> None:
    conn = _FakeConn(fetch_results=[])
    service = KGEnhancedRetrieval(db_pool=_FakePool(conn))

    context = await service.get_context_for_query("open a restaurant in Bali", max_entities=5)

    assert context.golden_route is not None
    assert context.golden_route.route_id == "restaurant_foreigner"
    assert context.entities_found == []
    assert context.relationships == []
    assert context.source_chunk_ids == []
    assert context.confidence == 0.8
    assert "Open Restaurant as Foreigner" in context.graph_summary
    assert conn.fetch_calls == []
