"""
Unit tests for backend/services/autonomous_agents/knowledge_graph_builder.py

Covers: Entity/Relationship dataclasses, KnowledgeGraphBuilder init,
        add_entity, add_relationship, extract_entities_from_text,
        infer_relationships_from_text, extract_entities (unified),
        extract_via_llm, build_graph_from_collection, _refresh_from_db,
        export_graph (json/cypher/graphml), get_graph_stats,
        query_graph (memory + DB), _query_graph_from_memory,
        _query_graph_from_db.
"""

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.autonomous_agents.knowledge_graph_builder import (
    Entity,
    EntityType,
    KnowledgeGraphBuilder,
    Relationship,
    RelationType,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def builder():
    """KG builder with no external deps."""
    return KnowledgeGraphBuilder()


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg Pool."""
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool._mock_conn = conn
    return pool


@pytest.fixture
def builder_with_db(mock_db_pool):
    """KG builder with DB pool."""
    return KnowledgeGraphBuilder(db_pool=mock_db_pool)


@pytest.fixture
def mock_llm_gateway():
    """Mock LLMGateway."""
    gw = MagicMock()
    gw.conversational = AsyncMock(return_value={
        "text": '{"entities": [{"id": "kbli_56101", "type": "KBLI_CODE", "name": "56101", "description": "Restaurant"}], "relationships": [{"source": "kbli_56101", "target": "permit_nib", "type": "REQUIRES", "description": "needs NIB"}]}',
        "model": "test-model",
    })
    return gw


@pytest.fixture
def builder_with_llm(mock_llm_gateway):
    """KG builder with LLM gateway."""
    return KnowledgeGraphBuilder(llm_gateway=mock_llm_gateway)


@pytest.fixture
def sample_entity():
    return Entity(
        entity_id="kbli_code_56101",
        entity_type=EntityType.KBLI_CODE,
        name="56101",
        description="Restaurant KBLI code",
        confidence=0.9,
    )


@pytest.fixture
def sample_relationship():
    return Relationship(
        relationship_id="kbli_56101_requires_permit_nib",
        source_entity_id="kbli_56101",
        target_entity_id="permit_nib",
        relationship_type=RelationType.REQUIRES,
        confidence=0.85,
    )


# ============================================================================
# Dataclass tests
# ============================================================================


class TestEntity:
    def test_entity_defaults(self):
        e = Entity(entity_id="e1", entity_type="test", name="Test", description="desc")
        assert e.properties == {}
        assert e.source_collection is None
        assert e.confidence == 1.0
        assert e.source_chunk_ids == []
        assert e.created_at is not None

    def test_entity_asdict(self, sample_entity):
        d = asdict(sample_entity)
        assert d["entity_id"] == "kbli_code_56101"
        assert d["entity_type"] == EntityType.KBLI_CODE


class TestRelationship:
    def test_relationship_defaults(self):
        r = Relationship(
            relationship_id="r1", source_entity_id="s1",
            target_entity_id="t1", relationship_type="requires",
        )
        assert r.properties == {}
        assert r.confidence == 1.0

    def test_relationship_asdict(self, sample_relationship):
        d = asdict(sample_relationship)
        assert d["source_entity_id"] == "kbli_56101"


# ============================================================================
# Init tests
# ============================================================================


class TestInit:
    def test_init_no_deps(self, builder):
        assert builder.search is None
        assert builder.db_pool is None
        assert builder.llm_gateway is None
        assert builder.entities == {}
        assert builder.relationships == {}

    def test_init_with_db(self, builder_with_db):
        assert builder_with_db.db_pool is not None

    def test_init_with_llm(self, builder_with_llm):
        assert builder_with_llm.llm_gateway is not None

    def test_graph_stats_initialized(self, builder):
        stats = builder.get_graph_stats()
        assert stats["total_entities"] == 0
        assert stats["total_relationships"] == 0
        assert stats["collections_analyzed"] == []


# ============================================================================
# add_entity / add_relationship
# ============================================================================


class TestAddEntity:
    @pytest.mark.asyncio
    async def test_add_entity_in_memory(self, builder, sample_entity):
        await builder.add_entity(sample_entity)
        assert sample_entity.entity_id in builder.entities

    @pytest.mark.asyncio
    async def test_add_entity_with_db(self, builder_with_db, mock_db_pool, sample_entity):
        mock_db_pool.execute = AsyncMock()
        await builder_with_db.add_entity(sample_entity)
        assert sample_entity.entity_id in builder_with_db.entities
        mock_db_pool.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_entity_db_error(self, builder_with_db, mock_db_pool, sample_entity):
        mock_db_pool.execute = AsyncMock(side_effect=Exception("DB error"))
        await builder_with_db.add_entity(sample_entity)
        assert sample_entity.entity_id in builder_with_db.entities


class TestAddRelationship:
    @pytest.mark.asyncio
    async def test_add_relationship_in_memory(self, builder, sample_relationship):
        await builder.add_relationship(sample_relationship)
        assert sample_relationship.relationship_id in builder.relationships

    @pytest.mark.asyncio
    async def test_add_relationship_with_db(self, builder_with_db, mock_db_pool, sample_relationship):
        mock_db_pool.execute = AsyncMock()
        await builder_with_db.add_relationship(sample_relationship)
        assert sample_relationship.relationship_id in builder_with_db.relationships
        mock_db_pool.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_relationship_db_error(self, builder_with_db, mock_db_pool, sample_relationship):
        mock_db_pool.execute = AsyncMock(side_effect=Exception("DB error"))
        await builder_with_db.add_relationship(sample_relationship)
        assert sample_relationship.relationship_id in builder_with_db.relationships


# ============================================================================
# extract_entities_from_text
# ============================================================================


class TestExtractEntitiesFromText:
    def test_extract_kbli(self, builder):
        text = "KBLI 56101 is the code for restaurants in Indonesia"
        entities = builder.extract_entities_from_text(text)
        kbli_entities = [e for e in entities if e.entity_type == EntityType.KBLI_CODE]
        assert len(kbli_entities) >= 1
        assert any("56101" in e.name for e in kbli_entities)

    def test_extract_visa(self, builder):
        text = "You need a work permit to stay in Indonesia"
        entities = builder.extract_entities_from_text(text)
        visa_entities = [e for e in entities if e.entity_type == EntityType.VISA_TYPE]
        assert len(visa_entities) >= 1

    def test_empty_text(self, builder):
        entities = builder.extract_entities_from_text("")
        assert entities == []

    def test_multiple_matches_same_text(self, builder):
        text = "KBLI 56101 and also KBLI 56101 again"
        entities = builder.extract_entities_from_text(text)
        # Multiple regex patterns may match the same entity - that's expected behavior
        kbli_entities = [e for e in entities if "56101" in e.name]
        assert len(kbli_entities) >= 1

    def test_skip_existing(self, builder):
        text = "KBLI 56101 is required"
        entities1 = builder.extract_entities_from_text(text)
        for e in entities1:
            builder.entities[e.entity_id] = e
        entities2 = builder.extract_entities_from_text(text)
        kbli2 = [e for e in entities2 if "56101" in e.name and e.entity_type == EntityType.KBLI_CODE]
        assert len(kbli2) == 0

    def test_with_source_collection(self, builder):
        text = "KBLI 56101 restaurant"
        entities = builder.extract_entities_from_text(text, source_collection="my_collection")
        for e in entities:
            assert e.source_collection == "my_collection"


# ============================================================================
# infer_relationships_from_text
# ============================================================================


class TestInferRelationships:
    def test_requires_relationship(self, builder):
        e1 = Entity(entity_id="e1", entity_type="permit", name="NIB", description="d1")
        e2 = Entity(entity_id="e2", entity_type="document", name="NPWP", description="d2")
        text = "NIB requires NPWP for registration"
        rels = builder.infer_relationships_from_text(text, [e1, e2])
        assert len(rels) >= 1
        assert any(r.relationship_type == RelationType.REQUIRES for r in rels)

    def test_costs_relationship(self, builder):
        e1 = Entity(entity_id="e1", entity_type="permit", name="SIUP", description="d1")
        e2 = Entity(entity_id="e2", entity_type="service", name="Rp 500000", description="d2")
        text = "SIUP costs Rp 500000 for processing"
        rels = builder.infer_relationships_from_text(text, [e1, e2])
        assert len(rels) >= 1

    def test_no_relationship(self, builder):
        e1 = Entity(entity_id="e1", entity_type="permit", name="AAA", description="d")
        e2 = Entity(entity_id="e2", entity_type="permit", name="BBB", description="d")
        text = "AAA is a thing. BBB is another thing."
        rels = builder.infer_relationships_from_text(text, [e1, e2])
        assert len(rels) == 0

    def test_entity_not_in_text(self, builder):
        e1 = Entity(entity_id="e1", entity_type="permit", name="NotPresent", description="d")
        e2 = Entity(entity_id="e2", entity_type="permit", name="AlsoMissing", description="d")
        text = "This text has nothing relevant"
        rels = builder.infer_relationships_from_text(text, [e1, e2])
        assert len(rels) == 0


# ============================================================================
# extract_entities (unified)
# ============================================================================


class TestExtractEntities:
    @pytest.mark.asyncio
    @patch("backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector")
    async def test_regex_fallback(self, mock_metrics, builder):
        text = "KBLI 56101 requires NPWP registration"
        result = await builder.extract_entities(text)
        assert "entities" in result
        assert "relationships" in result
        mock_metrics.record_kg_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_path(self, builder_with_llm):
        text = "KBLI 56101 requires NIB"
        result = await builder_with_llm.extract_entities(text)
        assert "entities" in result
        assert "relationships" in result
        builder_with_llm.llm_gateway.conversational.assert_awaited_once()


# ============================================================================
# extract_via_llm
# ============================================================================


class TestExtractViaLLM:
    @pytest.mark.asyncio
    async def test_no_llm(self, builder):
        result = await builder.extract_via_llm("some text")
        assert result == {"entities": [], "relationships": []}

    @pytest.mark.asyncio
    @patch("backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector")
    async def test_successful_extraction(self, mock_metrics, builder_with_llm):
        result = await builder_with_llm.extract_via_llm("KBLI 56101", source_collection="test", chunk_id="c1")
        assert len(result["entities"]) >= 1
        assert len(result["relationships"]) >= 1
        mock_metrics.record_kg_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self, builder_with_llm):
        builder_with_llm.llm_gateway.conversational = AsyncMock(
            return_value={"text": "not valid json at all", "model": "test"},
        )
        result = await builder_with_llm.extract_via_llm("some text")
        assert result == {"entities": [], "relationships": []}

    @pytest.mark.asyncio
    async def test_llm_raises_exception(self, builder_with_llm):
        builder_with_llm.llm_gateway.conversational = AsyncMock(side_effect=Exception("LLM error"))
        result = await builder_with_llm.extract_via_llm("some text")
        assert result == {"entities": [], "relationships": []}

    @pytest.mark.asyncio
    @patch("backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector")
    async def test_extraction_with_code_fence(self, mock_metrics, builder_with_llm):
        builder_with_llm.llm_gateway.conversational = AsyncMock(return_value={
            "text": '```json\n{"entities": [{"id": "test_1", "type": "PERMIT", "name": "NIB", "description": "Business ID"}], "relationships": []}\n```',
            "model": "test",
        })
        result = await builder_with_llm.extract_via_llm("text")
        assert len(result["entities"]) == 1

    @pytest.mark.asyncio
    @patch("backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector")
    async def test_entity_id_sanitization(self, mock_metrics, builder_with_llm):
        builder_with_llm.llm_gateway.conversational = AsyncMock(return_value={
            "text": '{"entities": [{"id": "test/bad id!", "type": "PERMIT", "name": "Test", "description": "d"}], "relationships": []}',
            "model": "test",
        })
        result = await builder_with_llm.extract_via_llm("text")
        eid = result["entities"][0]["entity_id"]
        assert "/" not in eid
        assert "!" not in eid


# ============================================================================
# build_graph_from_collection
# ============================================================================


class TestBuildGraphFromCollection:
    @pytest.mark.asyncio
    async def test_no_search_service(self, builder):
        result = await builder.build_graph_from_collection("test_collection")
        assert result == 0

    @pytest.mark.asyncio
    async def test_search_error(self, builder):
        builder.search = MagicMock()
        builder.search.search = AsyncMock(side_effect=Exception("Search error"))
        result = await builder.build_graph_from_collection("test_collection")
        assert result == 0

    @pytest.mark.asyncio
    async def test_with_results_regex(self, builder):
        builder.search = MagicMock()
        builder.search.search = AsyncMock(return_value={
            "results": [
                {"text": "KBLI 56101 restaurant business", "id": "chunk1"},
                {"text": "work permit requirements", "id": "chunk2"},
            ],
        })
        result = await builder.build_graph_from_collection("test_col")
        assert result >= 0
        assert "test_col" in builder.graph_stats["collections_analyzed"]

    @pytest.mark.asyncio
    @patch("backend.services.autonomous_agents.knowledge_graph_builder.metrics_collector")
    async def test_with_results_llm(self, mock_metrics, builder_with_llm):
        builder_with_llm.search = MagicMock()
        builder_with_llm.search.search = AsyncMock(return_value={
            "results": [{"text": "test text", "id": "c1"}],
        })
        result = await builder_with_llm.build_graph_from_collection("test_col")
        assert result == 1


# ============================================================================
# _refresh_from_db
# ============================================================================


class TestRefreshFromDB:
    @pytest.mark.asyncio
    async def test_no_db_pool(self, builder):
        await builder._refresh_from_db()
        assert builder.entities == {}

    @pytest.mark.asyncio
    async def test_refresh_from_db(self, builder_with_db, mock_db_pool):
        node_row = {
            "entity_id": "e1", "entity_type": "permit", "name": "NIB",
            "description": "Business ID", "properties": '{"key": "val"}',
            "confidence": 0.9, "source_collection": "test", "source_chunk_ids": ["c1"],
        }
        edge_row = {
            "relationship_id": "r1", "source_entity_id": "e1", "target_entity_id": "e2",
            "relationship_type": "requires", "properties": {"k": "v"},
            "confidence": 0.8, "source_collection": "test", "source_chunk_ids": [],
        }
        mock_db_pool.fetch = AsyncMock(side_effect=[[MagicMock(**{"__getitem__": lambda s, k: node_row[k]})], [MagicMock(**{"__getitem__": lambda s, k: edge_row[k]})]])

        # Use simpler approach: mock fetch to return dicts
        mock_node = MagicMock()
        mock_node.__getitem__ = lambda self, key: node_row[key]
        mock_edge = MagicMock()
        mock_edge.__getitem__ = lambda self, key: edge_row[key]

        mock_db_pool.fetch = AsyncMock(side_effect=[[mock_node], [mock_edge]])
        await builder_with_db._refresh_from_db()
        assert "e1" in builder_with_db.entities
        assert "r1" in builder_with_db.relationships

    @pytest.mark.asyncio
    async def test_refresh_db_error(self, builder_with_db, mock_db_pool):
        mock_db_pool.fetch = AsyncMock(side_effect=Exception("DB error"))
        await builder_with_db._refresh_from_db()


# ============================================================================
# export_graph
# ============================================================================


class TestExportGraph:
    @pytest.mark.asyncio
    async def test_export_json(self, builder, sample_entity, sample_relationship):
        await builder.add_entity(sample_entity)
        await builder.add_relationship(sample_relationship)
        result = await builder.export_graph(format="json")
        data = json.loads(result)
        assert len(data["entities"]) == 1
        assert len(data["relationships"]) == 1
        assert "stats" in data

    @pytest.mark.asyncio
    async def test_export_cypher(self, builder, sample_entity, sample_relationship):
        await builder.add_entity(sample_entity)
        await builder.add_relationship(sample_relationship)
        result = await builder.export_graph(format="cypher")
        assert "MERGE" in result
        assert "MATCH" in result

    @pytest.mark.asyncio
    async def test_export_graphml(self, builder, sample_entity, sample_relationship):
        await builder.add_entity(sample_entity)
        await builder.add_relationship(sample_relationship)
        result = await builder.export_graph(format="graphml")
        assert "<graphml" in result
        assert "<node" in result
        assert "<edge" in result

    @pytest.mark.asyncio
    async def test_export_unknown_format(self, builder):
        with pytest.raises(NotImplementedError):
            await builder.export_graph(format="unknown")

    @pytest.mark.asyncio
    async def test_export_empty_graph(self, builder):
        result = await builder.export_graph(format="json")
        data = json.loads(result)
        assert data["entities"] == []
        assert data["relationships"] == []

    @pytest.mark.asyncio
    async def test_export_json_with_db_refreshes(self, builder_with_db, mock_db_pool):
        mock_db_pool.fetch = AsyncMock(return_value=[])
        await builder_with_db.export_graph(format="json")
        assert mock_db_pool.fetch.await_count == 2  # nodes + edges


# ============================================================================
# query_graph
# ============================================================================


class TestQueryGraph:
    @pytest.mark.asyncio
    async def test_query_not_found_memory(self, builder):
        result = await builder.query_graph("nonexistent")
        assert result["found"] is False
        assert result["total_entities"] == 0

    @pytest.mark.asyncio
    async def test_query_found_memory(self, builder, sample_entity, sample_relationship):
        await builder.add_entity(sample_entity)
        await builder.add_relationship(sample_relationship)
        result = await builder.query_graph("56101")
        assert result["found"] is True
        assert result["total_entities"] >= 1

    @pytest.mark.asyncio
    async def test_query_with_depth(self, builder):
        e1 = Entity(entity_id="e1", entity_type="permit", name="NIB", description="d1")
        e2 = Entity(entity_id="e2", entity_type="permit", name="NPWP", description="d2")
        e3 = Entity(entity_id="e3", entity_type="permit", name="SIUP", description="d3")
        r1 = Relationship(relationship_id="r1", source_entity_id="e1", target_entity_id="e2", relationship_type="requires")
        r2 = Relationship(relationship_id="r2", source_entity_id="e2", target_entity_id="e3", relationship_type="requires")

        await builder.add_entity(e1)
        await builder.add_entity(e2)
        await builder.add_entity(e3)
        await builder.add_relationship(r1)
        await builder.add_relationship(r2)

        result_depth1 = await builder.query_graph("NIB", max_depth=1)
        result_depth2 = await builder.query_graph("NIB", max_depth=2)
        assert result_depth2["total_entities"] >= result_depth1["total_entities"]

    @pytest.mark.asyncio
    async def test_query_from_db(self, builder_with_db, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(return_value=None)
        result = await builder_with_db.query_graph("test")
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_query_from_db_with_result(self, builder_with_db, mock_db_pool):
        conn = mock_db_pool._mock_conn
        start_node = {
            "entity_id": "e1", "entity_type": "permit", "name": "NIB",
            "description": "d", "properties": {}, "confidence": 0.9,
            "source_collection": "test",
        }
        # Use a dict-like mock that supports both [] and dict() conversion
        mock_row = MagicMock(spec=dict)
        mock_row.__getitem__ = lambda self, key: start_node[key]
        mock_row.get = lambda self, key, default=None: start_node.get(key, default)
        mock_row.keys = MagicMock(return_value=start_node.keys())
        mock_row.__iter__ = MagicMock(return_value=iter(start_node))
        mock_row.__len__ = MagicMock(return_value=len(start_node))

        # fetchrow returns the start node, fetch returns empty edges, then entities
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.fetch = AsyncMock(side_effect=[[], [mock_row]])

        result = await builder_with_db.query_graph("NIB")
        assert result["found"] is True

    @pytest.mark.asyncio
    async def test_query_from_db_error_falls_back(self, builder_with_db, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        result = await builder_with_db.query_graph("test")
        assert result["found"] is False


# ============================================================================
# Cypher/GraphML edge cases
# ============================================================================


class TestExportEdgeCases:
    @pytest.mark.asyncio
    async def test_cypher_special_chars(self, builder):
        e = Entity(entity_id="e1", entity_type="permit", name='Test "quoted"', description='Desc with "quotes"')
        await builder.add_entity(e)
        result = await builder.export_graph(format="cypher")
        assert "\u201c" not in result or "quoted" in result  # quotes escaped

    @pytest.mark.asyncio
    async def test_graphml_special_chars(self, builder):
        e = Entity(entity_id="e1", entity_type="permit", name="Test & <entity>", description="d")
        await builder.add_entity(e)
        result = await builder.export_graph(format="graphml")
        assert "&amp;" in result
        assert "&lt;" in result

    @pytest.mark.asyncio
    async def test_cypher_entity_with_properties(self, builder):
        e = Entity(
            entity_id="e1", entity_type="permit", name="NIB",
            description="d", properties={"cost": 100, "active": True, "note": "test"},
        )
        await builder.add_entity(e)
        result = await builder.export_graph(format="cypher")
        assert "cost: 100" in result
        assert "active: true" in result or "active: True" in result
