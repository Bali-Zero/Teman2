"""
Test for Agentic Tools Factory
"""

import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_root = Path(__file__).parents[2]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.services.rag.agentic import create_agentic_rag, VisionTool


@pytest.mark.asyncio
async def test_create_agentic_rag_includes_vision_tool():
    """Test that the factory creates an orchestrator with VisionTool"""
    mock_retriever = MagicMock()
    mock_db_pool = MagicMock()

    # Patch KnowledgeGraphBuilder and KnowledgeGraphTool to avoid complex init
    mock_kg_tool = MagicMock()
    mock_kg_tool.name = "knowledge_graph_search"
    
    with patch("backend.services.autonomous_agents.knowledge_graph_builder.KnowledgeGraphBuilder", return_value=MagicMock()):
        with patch("backend.services.tools.knowledge_graph_tool.KnowledgeGraphTool", return_value=mock_kg_tool):
            orchestrator = create_agentic_rag(mock_retriever, mock_db_pool)

    # orchestrator.tools is now a dict {name: tool_object}
    assert "vision_analysis" in orchestrator.tools
    assert "knowledge_graph_search" in orchestrator.tools

    # Verify VisionTool instance
    vision_tool = orchestrator.tools["vision_analysis"]
    assert isinstance(vision_tool, VisionTool)
    assert vision_tool.name == "vision_analysis"
    assert "visual elements" in vision_tool.description


@pytest.mark.asyncio
async def test_vector_search_tool_uses_reranking():
    """Test that VectorSearchTool uses search_with_reranking if available"""
    mock_retriever = MagicMock()
    # Mock search_with_reranking
    mock_retriever.search_with_reranking = AsyncMock(
        return_value={
            "results": [{"text": "Reranked Doc 1"}, {"text": "Reranked Doc 2"}],
            "reranked": True,
        }
    )

    from backend.services.rag.agentic import VectorSearchTool

    tool = VectorSearchTool(retriever=mock_retriever)

    # Specify a collection to avoid federated search
    result_json = await tool.execute(query="test query", top_k=3, collection="visa_oracle")
    result = json.loads(result_json)

    # Verify call
    mock_retriever.search_with_reranking.assert_called_once()
    
    # Verify result contains the expected content
    assert "Reranked Doc 1" in result["content"]
    assert "Reranked Doc 2" in result["content"]
    assert len(result["sources"]) == 2