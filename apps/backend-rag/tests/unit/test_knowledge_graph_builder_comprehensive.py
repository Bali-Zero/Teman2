"""
Comprehensive Unit tests for KnowledgeGraphBuilder
Targets 95%+ coverage for the new persistence, LLM, and export features.
"""

import json

# Mock backend path
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.autonomous_agents.knowledge_graph_builder import (
    Entity,
    EntityType,
    KnowledgeGraphBuilder,
    Relationship,
    RelationType,
)


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock()
    return pool


@pytest.fixture
def mock_llm_gateway():
    gateway = MagicMock()
    gateway.conversational = AsyncMock()
    return gateway


@pytest.mark.asyncio
class TestKnowledgeGraphBuilderComprehensive:
    """Comprehensive tests for KnowledgeGraphBuilder to ensure >95% coverage"""

    async def test_add_entity_persistence(self, mock_db_pool):
        """Test adding entity with DB persistence and chunk linking"""
        builder = KnowledgeGraphBuilder(db_pool=mock_db_pool)
        entity = Entity(
            entity_id="node_1",
            entity_type=EntityType.LEGAL_ENTITY,
            name="Test PT",
            description="A test company",
            source_chunk_ids=["chunk_abc"],
        )

        await builder.add_entity(entity)

        # Verify in-memory cache
        assert "node_1" in builder.entities
        assert builder.entities["node_1"].source_chunk_ids == ["chunk_abc"]

        # Verify DB call
        assert mock_db_pool.execute.called
        args = mock_db_pool.execute.call_args[0]
        assert "INSERT INTO kg_nodes" in args[0]
        assert "node_1" in args

    async def test_add_relationship_persistence(self, mock_db_pool):
        """Test adding relationship with DB persistence and chunk linking"""
        builder = KnowledgeGraphBuilder(db_pool=mock_db_pool)
        rel = Relationship(
            relationship_id="rel_1",
            source_entity_id="node_1",
            target_entity_id="node_2",
            relationship_type=RelationType.REQUIRES,
            source_chunk_ids=["chunk_xyz"],
        )

        await builder.add_relationship(rel)

        # Verify in-memory cache
        assert "rel_1" in builder.relationships
        assert builder.relationships["rel_1"].source_chunk_ids == ["chunk_xyz"]

        # Verify DB call
        assert mock_db_pool.execute.called
        args = mock_db_pool.execute.call_args[0]
        assert "INSERT INTO kg_edges" in args[0]
        assert "rel_1" in args

    async def test_extract_entities_facade_llm(self, mock_llm_gateway):
        """Test extract_entities facade prefers LLM when available"""
        builder = KnowledgeGraphBuilder(llm_gateway=mock_llm_gateway)
        mock_llm_gateway.conversational.return_value = {
            "text": json.dumps(
                {
                    "entities": [
                        {"id": "e1", "type": "PERMIT", "name": "NIB", "description": "Test"}
                    ],
                    "relationships": [],
                }
            )
        }

        result = await builder.extract_entities("Text sample")

        assert mock_llm_gateway.conversational.called
        assert len(result["entities"]) == 1
        assert result["entities"][0]["entity_id"] == "e1"

    async def test_extract_entities_facade_regex(self):
        """Test extract_entities facade falls back to Regex when LLM is missing"""
        builder = KnowledgeGraphBuilder(llm_gateway=None)

        # Use a text that matches a known pattern
        text = "Check KBLI 56101 for requirements."
        result = await builder.extract_entities(text)

        assert len(result["entities"]) > 0
        assert any("56101" in e["name"] for e in result["entities"])

    async def test_export_formats(self):
        """Test all export formats (JSON, Cypher, GraphML)"""
        builder = KnowledgeGraphBuilder()
        e1 = Entity(entity_id="e1", entity_type="TEST", name="Node 1", description="Desc")
        e2 = Entity(entity_id="e2", entity_type="TEST", name="Node 2", description="Desc")
        r1 = Relationship(
            relationship_id="r1",
            source_entity_id="e1",
            target_entity_id="e2",
            relationship_type="LINK",
        )

        builder.entities = {"e1": e1, "e2": e2}
        builder.relationships = {"r1": r1}

        # Test JSON
        json_out = await builder.export_graph("json")
        assert "e1" in json_out

        # Test Cypher
        cypher_out = await builder.export_graph("cypher")
        assert "MERGE (e:Entity" in cypher_out
        assert "Node 1" in cypher_out

        # Test GraphML
        graphml_out = await builder.export_graph("graphml")
        assert "<?xml" in graphml_out
        assert '<node id="e1">' in graphml_out

    async def test_refresh_from_db(self, mock_db_pool):
        """Test refreshing in-memory state from database"""
        builder = KnowledgeGraphBuilder(db_pool=mock_db_pool)

        # Mock DB rows
        mock_db_pool.fetch.side_effect = [
            [
                {
                    "entity_id": "db_node",
                    "entity_type": "TYPE",
                    "name": "Name",
                    "description": "Desc",
                    "properties": "{}",
                    "confidence": 1.0,
                    "source_collection": "coll",
                    "source_chunk_ids": ["c1"],
                }
            ],
            [
                {
                    "relationship_id": "db_rel",
                    "source_entity_id": "s",
                    "target_entity_id": "t",
                    "relationship_type": "REL",
                    "properties": "{}",
                    "confidence": 1.0,
                    "source_collection": "coll",
                    "source_chunk_ids": ["c2"],
                }
            ],
        ]

        await builder._refresh_from_db()

        assert "db_node" in builder.entities
        assert "db_rel" in builder.relationships
        assert builder.entities["db_node"].source_chunk_ids == ["c1"]

    async def test_build_graph_from_collection_hybrid(self, mock_llm_gateway):
        """Test building graph from search results with chunk linking"""
        mock_search = MagicMock()
        mock_search.search = AsyncMock(
            return_value={"results": [{"id": "chunk_1", "text": "Content about KBLI 56101"}]}
        )

        builder = KnowledgeGraphBuilder(search_service=mock_search, llm_gateway=mock_llm_gateway)
        mock_llm_gateway.conversational.return_value = {"text": "{}"}

        await builder.build_graph_from_collection("test_coll")

        assert mock_search.search.called
        # Check if LLM was called with text and chunk metadata
        assert mock_llm_gateway.conversational.called

    def test_escape_xml_graphml(self):
        """Test XML special character escaping in GraphML export"""
        builder = KnowledgeGraphBuilder()
        builder.entities = {
            "e1": Entity(
                entity_id="e1", entity_type="TEST", name="Node & Name <tag>", description="Desc"
            )
        }
        graphml = builder._export_graphml()
        assert "Node &amp; Name &lt;tag&gt;" in graphml
