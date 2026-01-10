"""
Complete test coverage for graph_tool.py
Target: >95% coverage

This file provides comprehensive tests for:
- GraphTraversalTool class - initialization, properties, execution, error handling
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.graph_tool import GraphTraversalTool

# ============================================================================
# TESTS: GraphTraversalTool - Complete Coverage
# ============================================================================


class TestGraphTraversalToolInit:
    """Tests for GraphTraversalTool initialization"""

    def test_graph_traversal_tool_init(self):
        """Test GraphTraversalTool initialization"""
        mock_graph_service = MagicMock()
        tool = GraphTraversalTool(mock_graph_service)
        assert tool.graph == mock_graph_service

    def test_graph_traversal_tool_init_with_none(self):
        """Test GraphTraversalTool initialization with None (edge case)"""
        tool = GraphTraversalTool(None)
        assert tool.graph is None


class TestGraphTraversalToolProperties:
    """Tests for GraphTraversalTool properties"""

    def test_name_property(self):
        """Test name property"""
        tool = GraphTraversalTool(MagicMock())
        assert tool.name == "graph_traversal"

    def test_description_property(self):
        """Test description property"""
        tool = GraphTraversalTool(MagicMock())
        desc = tool.description
        assert isinstance(desc, str)
        assert "legal Knowledge Graph" in desc
        assert "relationships" in desc.lower()
        assert "prerequisites" in desc.lower()
        assert "KITAS" in desc

    def test_parameters_schema_property(self):
        """Test parameters_schema property"""
        tool = GraphTraversalTool(MagicMock())
        schema = tool.parameters_schema
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "entity_name" in schema["properties"]
        assert "depth" in schema["properties"]
        assert "required" in schema
        assert "entity_name" in schema["required"]


class TestGraphTraversalToolExecute:
    """Tests for GraphTraversalTool.execute()"""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful graph traversal"""
        mock_graph_service = MagicMock()

        # Mock entity node
        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "KITAS"
        mock_entity.type = "Visa"

        # Mock subgraph
        mock_subgraph = {
            "nodes": [
                {"id": "entity_123", "name": "KITAS", "type": "Visa"},
                {"id": "entity_456", "name": "Passport", "type": "Document"},
            ],
            "edges": [
                {"type": "requires", "target": "entity_456"},
            ],
        }

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("KITAS", depth=1)

        assert "KITAS" in result
        assert "Visa" in result
        assert "Relationships" in result
        assert "requires" in result
        assert "Passport" in result
        mock_graph_service.find_entity_by_name.assert_called_once_with("KITAS", limit=1)
        mock_graph_service.traverse.assert_called_once_with("entity_123", max_depth=1)

    @pytest.mark.asyncio
    async def test_execute_entity_not_found(self):
        """Test execution when entity is not found"""
        mock_graph_service = MagicMock()
        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[])

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("NonExistentEntity", depth=1)

        assert "No entity found" in result
        assert "NonExistentEntity" in result
        assert "Try a broader term" in result
        mock_graph_service.traverse.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_depth_parameter(self):
        """Test execution with depth parameter"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "PT PMA"
        mock_entity.type = "Company"

        mock_subgraph = {"nodes": [], "edges": []}

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("PT PMA", depth=3)

        # Should cap depth at 3
        mock_graph_service.traverse.assert_called_once_with("entity_123", max_depth=3)

    @pytest.mark.asyncio
    async def test_execute_depth_exceeds_max(self):
        """Test execution with depth exceeding max (should cap at 3)"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Test Entity"
        mock_entity.type = "Type"

        mock_subgraph = {"nodes": [], "edges": []}

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity", depth=5)

        # Should cap at 3 even if depth=5
        mock_graph_service.traverse.assert_called_once_with("entity_123", max_depth=3)

    @pytest.mark.asyncio
    async def test_execute_default_depth(self):
        """Test execution with default depth"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Test Entity"
        mock_entity.type = "Type"

        mock_subgraph = {"nodes": [], "edges": []}

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity")  # No depth specified

        # Should use default depth=1
        mock_graph_service.traverse.assert_called_once_with("entity_123", max_depth=1)

    @pytest.mark.asyncio
    async def test_execute_multiple_edges(self):
        """Test execution with multiple edges"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "KITAS"
        mock_entity.type = "Visa"

        mock_subgraph = {
            "nodes": [
                {"id": "entity_123", "name": "KITAS"},
                {"id": "entity_456", "name": "Passport"},
                {"id": "entity_789", "name": "Medical Check"},
            ],
            "edges": [
                {"type": "requires", "target": "entity_456"},
                {"type": "requires", "target": "entity_789"},
                {"type": "costs", "target": "entity_999"},
            ],
        }

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("KITAS", depth=1)

        assert "Relationships (3):" in result
        assert "requires" in result
        assert "costs" in result

    @pytest.mark.asyncio
    async def test_execute_edge_with_missing_target_name(self):
        """Test execution when edge target is not in node_map"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Test Entity"
        mock_entity.type = "Type"

        mock_subgraph = {
            "nodes": [{"id": "entity_123", "name": "Test Entity"}],
            "edges": [
                {"type": "related_to", "target": "unknown_id"},  # Not in node_map
            ],
        }

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity", depth=1)

        # Should use the target ID directly if not in node_map
        assert "unknown_id" in result or "related_to" in result

    @pytest.mark.asyncio
    async def test_execute_empty_subgraph(self):
        """Test execution with empty subgraph"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Test Entity"
        mock_entity.type = "Type"

        mock_subgraph = {"nodes": [], "edges": []}

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity", depth=1)

        assert "Test Entity" in result
        assert "Relationships (0):" in result

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self):
        """Test execution error handling"""
        mock_graph_service = MagicMock()
        mock_graph_service.find_entity_by_name = AsyncMock(side_effect=Exception("Database error"))

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity", depth=1)

        assert "Graph traversal error" in result
        assert "Database error" in result

    @pytest.mark.asyncio
    async def test_execute_traverse_exception(self):
        """Test execution when traverse raises exception"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Test Entity"
        mock_entity.type = "Type"

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(side_effect=ValueError("Traverse failed"))

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity", depth=1)

        assert "Graph traversal error" in result
        assert "Traverse failed" in result

    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self):
        """Test execution with additional kwargs (should be ignored)"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Test Entity"
        mock_entity.type = "Type"

        mock_subgraph = {"nodes": [], "edges": []}

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Test Entity", depth=1, extra_param="ignored")

        # Should work fine, extra kwargs are ignored
        assert "Test Entity" in result

    @pytest.mark.asyncio
    async def test_execute_complex_node_structure(self):
        """Test execution with complex node structure"""
        mock_graph_service = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "entity_123"
        mock_entity.name = "Complex Entity"
        mock_entity.type = "ComplexType"

        mock_subgraph = {
            "nodes": [
                {
                    "id": "entity_123",
                    "name": "Complex Entity",
                    "type": "ComplexType",
                    "metadata": {"key": "value"},
                },
                {"id": "entity_456", "name": "Related Entity"},
            ],
            "edges": [{"type": "connects", "target": "entity_456"}],
        }

        mock_graph_service.find_entity_by_name = AsyncMock(return_value=[mock_entity])
        mock_graph_service.traverse = AsyncMock(return_value=mock_subgraph)

        tool = GraphTraversalTool(mock_graph_service)
        result = await tool.execute("Complex Entity", depth=1)

        assert "Complex Entity" in result
        assert "ComplexType" in result
        assert "Related Entity" in result
