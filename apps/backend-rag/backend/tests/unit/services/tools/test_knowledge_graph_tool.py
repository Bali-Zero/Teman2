"""
Unit tests for services/tools/knowledge_graph_tool.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.tools.knowledge_graph_tool import KnowledgeGraphTool


class TestKnowledgeGraphTool:
    """Tests for KnowledgeGraphTool"""

    @pytest.fixture
    def mock_kg_builder(self):
        """Create mock KnowledgeGraphBuilder"""
        builder = MagicMock()
        builder.query_graph = AsyncMock()
        return builder

    @pytest.fixture
    def kg_tool(self, mock_kg_builder):
        """Create KnowledgeGraphTool instance"""
        return KnowledgeGraphTool(mock_kg_builder)

    def test_init(self, mock_kg_builder):
        """Test initialization"""
        tool = KnowledgeGraphTool(mock_kg_builder)
        assert tool.kg_builder == mock_kg_builder

    def test_name_property(self, kg_tool):
        """Test name property"""
        assert kg_tool.name == "knowledge_graph_search"

    def test_description_property(self, kg_tool):
        """Test description property"""
        desc = kg_tool.description
        assert "knowledge graph" in desc.lower()
        assert "relationships" in desc.lower()
        assert "Prerequisites" in desc
        assert "Connections" in desc

    def test_parameters_schema(self, kg_tool):
        """Test parameters_schema property"""
        schema = kg_tool.parameters_schema
        assert schema["type"] == "object"
        assert "entity" in schema["properties"]
        assert "depth" in schema["properties"]
        assert "relationship_type" in schema["properties"]
        assert "entity" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_entity_not_found(self, kg_tool, mock_kg_builder):
        """Test execute when entity not found"""
        mock_kg_builder.query_graph.return_value = {"found": False, "query": "Unknown Entity"}

        result = await kg_tool.execute(entity="Unknown Entity")

        assert "No entity found" in result
        assert "Unknown Entity" in result
        mock_kg_builder.query_graph.assert_called_once_with(
            entity_name="Unknown Entity", max_depth=1
        )

    @pytest.mark.asyncio
    async def test_execute_entity_found_no_relationships(self, kg_tool, mock_kg_builder):
        """Test execute when entity found but no relationships"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 1,
            "total_relationships": 0,
            "start_entity": {
                "entity_id": "1",
                "name": "PT PMA",
                "entity_type": "business_entity",
                "description": "Indonesian limited liability company",
            },
            "entities": [{"entity_id": "1", "name": "PT PMA"}],
            "relationships": [],
        }

        result = await kg_tool.execute(entity="PT PMA")

        assert "PT PMA" in result
        assert "1 nodes" in result
        assert "0 edges" in result
        assert "No direct relationships found" in result

    @pytest.mark.asyncio
    async def test_execute_with_relationships(self, kg_tool, mock_kg_builder):
        """Test execute with relationships"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 3,
            "total_relationships": 2,
            "start_entity": {
                "entity_id": "1",
                "name": "PT PMA",
                "entity_type": "business_entity",
                "description": "Indonesian LLC",
            },
            "entities": [
                {"entity_id": "1", "name": "PT PMA"},
                {"entity_id": "2", "name": "KITAS"},
                {"entity_id": "3", "name": "NIB"},
            ],
            "relationships": [
                {
                    "source_entity_id": "1",
                    "target_entity_id": "2",
                    "relationship_type": "requires",
                    "properties": {},
                },
                {
                    "source_entity_id": "1",
                    "target_entity_id": "3",
                    "relationship_type": "requires",
                    "properties": {"cost": "IDR 5M"},
                },
            ],
        }

        result = await kg_tool.execute(entity="PT PMA")

        assert "PT PMA" in result
        assert "3 nodes" in result
        assert "2 edges" in result
        assert "REQUIRES" in result
        assert "KITAS" in result
        assert "NIB" in result
        assert "cost=IDR 5M" in result

    @pytest.mark.asyncio
    async def test_execute_with_depth(self, kg_tool, mock_kg_builder):
        """Test execute with custom depth"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "KITAS",
            "total_entities": 1,
            "total_relationships": 0,
            "start_entity": {"entity_id": "1", "name": "KITAS", "entity_type": "visa"},
            "entities": [],
            "relationships": [],
        }

        await kg_tool.execute(entity="KITAS", depth=2)

        mock_kg_builder.query_graph.assert_called_once_with(entity_name="KITAS", max_depth=2)

    @pytest.mark.asyncio
    async def test_execute_depth_clamped_to_max(self, kg_tool, mock_kg_builder):
        """Test execute with depth > 2 gets clamped to 2"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "test",
            "total_entities": 1,
            "total_relationships": 0,
            "start_entity": {"entity_id": "1", "name": "test", "entity_type": "test"},
            "entities": [],
            "relationships": [],
        }

        await kg_tool.execute(entity="test", depth=10)

        mock_kg_builder.query_graph.assert_called_once_with(
            entity_name="test",
            max_depth=2,  # Clamped to max 2
        )

    @pytest.mark.asyncio
    async def test_execute_depth_clamped_to_min(self, kg_tool, mock_kg_builder):
        """Test execute with depth < 1 gets clamped to 1"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "test",
            "total_entities": 1,
            "total_relationships": 0,
            "start_entity": {"entity_id": "1", "name": "test", "entity_type": "test"},
            "entities": [],
            "relationships": [],
        }

        await kg_tool.execute(entity="test", depth=0)

        mock_kg_builder.query_graph.assert_called_once_with(
            entity_name="test",
            max_depth=1,  # Clamped to min 1
        )

    @pytest.mark.asyncio
    async def test_execute_with_relationship_type_filter(self, kg_tool, mock_kg_builder):
        """Test execute with relationship_type filter"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 3,
            "total_relationships": 3,
            "start_entity": {"entity_id": "1", "name": "PT PMA", "entity_type": "business"},
            "entities": [
                {"entity_id": "1", "name": "PT PMA"},
                {"entity_id": "2", "name": "KITAS"},
                {"entity_id": "3", "name": "Tax"},
            ],
            "relationships": [
                {
                    "source_entity_id": "1",
                    "target_entity_id": "2",
                    "relationship_type": "requires",
                    "properties": {},
                },
                {
                    "source_entity_id": "1",
                    "target_entity_id": "3",
                    "relationship_type": "tax_obligation",
                    "properties": {},
                },
                {
                    "source_entity_id": "2",
                    "target_entity_id": "3",
                    "relationship_type": "costs",
                    "properties": {},
                },
            ],
        }

        result = await kg_tool.execute(entity="PT PMA", relationship_type="requires")

        # Only "requires" relationship should be shown
        assert "REQUIRES" in result
        # "tax_obligation" and "costs" should be filtered out
        lines = result.split("\n")
        rel_lines = [l for l in lines if "--" in l]
        assert len(rel_lines) == 1  # Only 1 relationship matches filter

    @pytest.mark.asyncio
    async def test_execute_relationship_direction_outgoing(self, kg_tool, mock_kg_builder):
        """Test relationship formatting for outgoing edges"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 2,
            "total_relationships": 1,
            "start_entity": {"entity_id": "1", "name": "PT PMA", "entity_type": "business"},
            "entities": [{"entity_id": "1", "name": "PT PMA"}, {"entity_id": "2", "name": "KITAS"}],
            "relationships": [
                {
                    "source_entity_id": "1",  # From start entity
                    "target_entity_id": "2",
                    "relationship_type": "requires",
                    "properties": {},
                }
            ],
        }

        result = await kg_tool.execute(entity="PT PMA")

        # Should show [This] --> Target format
        assert "[This] --REQUIRES--> KITAS" in result

    @pytest.mark.asyncio
    async def test_execute_relationship_direction_incoming(self, kg_tool, mock_kg_builder):
        """Test relationship formatting for incoming edges"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 2,
            "total_relationships": 1,
            "start_entity": {"entity_id": "1", "name": "PT PMA", "entity_type": "business"},
            "entities": [
                {"entity_id": "1", "name": "PT PMA"},
                {"entity_id": "2", "name": "Director"},
            ],
            "relationships": [
                {
                    "source_entity_id": "2",
                    "target_entity_id": "1",  # To start entity
                    "relationship_type": "manages",
                    "properties": {},
                }
            ],
        }

        result = await kg_tool.execute(entity="PT PMA")

        # Should show Source --> [This] format
        assert "Director --MANAGES--> [This]" in result

    @pytest.mark.asyncio
    async def test_execute_relationship_third_party(self, kg_tool, mock_kg_builder):
        """Test relationship formatting for third-party edges"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 3,
            "total_relationships": 1,
            "start_entity": {"entity_id": "1", "name": "PT PMA", "entity_type": "business"},
            "entities": [
                {"entity_id": "1", "name": "PT PMA"},
                {"entity_id": "2", "name": "KITAS"},
                {"entity_id": "3", "name": "Immigration"},
            ],
            "relationships": [
                {
                    "source_entity_id": "2",  # Neither source nor target is start entity
                    "target_entity_id": "3",
                    "relationship_type": "issued_by",
                    "properties": {},
                }
            ],
        }

        result = await kg_tool.execute(entity="PT PMA")

        # Should show Source --> Target format (no [This])
        assert "KITAS --ISSUED_BY--> Immigration" in result

    @pytest.mark.asyncio
    async def test_execute_many_relationships_truncated(self, kg_tool, mock_kg_builder):
        """Test that relationships are truncated at 20"""
        # Create 25 relationships
        relationships = []
        entities = [{"entity_id": "1", "name": "PT PMA"}]
        for i in range(2, 27):
            entities.append({"entity_id": str(i), "name": f"Entity{i}"})
            relationships.append(
                {
                    "source_entity_id": "1",
                    "target_entity_id": str(i),
                    "relationship_type": "relates_to",
                    "properties": {},
                }
            )

        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 26,
            "total_relationships": 25,
            "start_entity": {"entity_id": "1", "name": "PT PMA", "entity_type": "business"},
            "entities": entities,
            "relationships": relationships,
        }

        result = await kg_tool.execute(entity="PT PMA")

        # Should show truncation message
        assert "... and 5 more connections" in result

    @pytest.mark.asyncio
    async def test_execute_with_none_depth(self, kg_tool, mock_kg_builder):
        """Test execute with depth=None defaults to 1"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "test",
            "total_entities": 1,
            "total_relationships": 0,
            "start_entity": {"entity_id": "1", "name": "test", "entity_type": "test"},
            "entities": [],
            "relationships": [],
        }

        await kg_tool.execute(entity="test", depth=None)

        mock_kg_builder.query_graph.assert_called_once_with(entity_name="test", max_depth=1)

    @pytest.mark.asyncio
    async def test_execute_excludes_source_confidence_from_props(self, kg_tool, mock_kg_builder):
        """Test that source and confidence are excluded from property display"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "PT PMA",
            "total_entities": 2,
            "total_relationships": 1,
            "start_entity": {"entity_id": "1", "name": "PT PMA", "entity_type": "business"},
            "entities": [{"entity_id": "1", "name": "PT PMA"}, {"entity_id": "2", "name": "KITAS"}],
            "relationships": [
                {
                    "source_entity_id": "1",
                    "target_entity_id": "2",
                    "relationship_type": "requires",
                    "properties": {
                        "source": "training_data",  # Should be excluded
                        "confidence": 0.95,  # Should be excluded
                        "cost": "IDR 5M",  # Should be included
                    },
                }
            ],
        }

        result = await kg_tool.execute(entity="PT PMA")

        assert "cost=IDR 5M" in result
        assert "source=" not in result
        assert "confidence=" not in result

    @pytest.mark.asyncio
    async def test_execute_entity_without_description(self, kg_tool, mock_kg_builder):
        """Test entity without description"""
        mock_kg_builder.query_graph.return_value = {
            "found": True,
            "query": "Simple",
            "total_entities": 1,
            "total_relationships": 0,
            "start_entity": {
                "entity_id": "1",
                "name": "Simple",
                "entity_type": "test",
                # No description field
            },
            "entities": [],
            "relationships": [],
        }

        result = await kg_tool.execute(entity="Simple")

        assert "Simple" in result
        assert "Description:" not in result
