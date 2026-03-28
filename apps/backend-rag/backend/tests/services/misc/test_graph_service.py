import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.misc.graph_service import GraphEntity, GraphRelation, GraphService


@asynccontextmanager
async def _mock_acquire(conn):
    yield conn


def _build_pool(conn):
    pool = MagicMock()
    pool.acquire = lambda: _mock_acquire(conn)
    return pool


@pytest.mark.asyncio
async def test_add_entity_merges_description():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="entity-1")
    service = GraphService(_build_pool(conn))

    entity = GraphEntity(
        id="entity-1",
        type="person",
        name="Alice",
        description="Founder",
        properties={"role": "CEO"},
    )

    result = await service.add_entity(entity)

    assert result == "entity-1"
    args = conn.fetchval.call_args[0]
    payload = json.loads(args[4])
    assert payload["description"] == "Founder"
    assert payload["role"] == "CEO"


@pytest.mark.asyncio
async def test_add_relation_builds_id_and_strength():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="s__works_at__t")
    service = GraphService(_build_pool(conn))

    relation = GraphRelation(
        source_id="s",
        target_id="t",
        type="Works At",
        properties={"source": "manual"},
        strength=0.85,
    )

    result = await service.add_relation(relation)

    assert result == "s__works_at__t"
    args = conn.fetchval.call_args[0]
    assert args[1] == "s__works_at__t"
    payload = json.loads(args[5])
    assert payload["strength"] == 0.85
    assert payload["source"] == "manual"


@pytest.mark.asyncio
async def test_get_neighbors_with_filters_and_limit():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "relationship_type": "REL",
                "strength": 0.7,
                "target_id": "t1",
                "target_name": "Target",
                "target_type": "org",
                "description": "desc",
            },
        ],
    )
    service = GraphService(_build_pool(conn))

    result = await service.get_neighbors("s1", relation_type="REL", limit=5)

    assert result[0]["relationship_type"] == "REL"
    assert result[0]["strength"] == 0.7
    assert result[0]["target_id"] == "t1"


@pytest.mark.asyncio
async def test_find_entity_by_name_handles_missing_properties():
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "entity_id": "e1",
                "entity_type": "person",
                "name": "Alice",
                "properties": {"description": "Founder", "role": "CEO"},
            },
            {
                "entity_id": "e2",
                "entity_type": "org",
                "name": "Acme",
                "properties": None,
            },
        ],
    )
    service = GraphService(_build_pool(conn))

    result = await service.find_entity_by_name("Ali")

    assert result[0].description == "Founder"
    assert result[0].properties["role"] == "CEO"
    assert result[1].description is None
    assert result[1].properties == {}


@pytest.mark.asyncio
async def test_traverse_builds_subgraph():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "id": "n1",
            "type": "person",
            "name": "Alice",
            "description": "Founder",
        },
    )

    async def _fetch(query, *params):
        if params[0] == "n1":
            return [
                {
                    "relationship_type": "REL",
                    "target_entity_id": "n2",
                    "strength": 0.5,
                    "target_type": "org",
                    "target_name": "Acme",
                    "target_desc": "Company",
                },
            ]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch)
    service = GraphService(_build_pool(conn))

    result = await service.traverse("n1", max_depth=2)

    assert len(result["nodes"]) == 2
    assert result["edges"][0]["target"] == "n2"
    assert result["edges"][0]["strength"] == 0.5
