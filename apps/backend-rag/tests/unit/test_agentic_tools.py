"""
Test for Agentic Tools Factory
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

# Mock VisionRAGService and app.core.config to avoid import errors and validation
mock_config = MagicMock()
mock_config.settings.GOOGLE_API_KEY = "test_key"

with patch.dict(
    sys.modules,
    {
        "backend.services.rag.vision_rag": MagicMock(),
        "app.core.config": mock_config,
        "backend.services.search_service": MagicMock(),
    },
):
    from backend.services.rag.agentic import VisionTool, create_agentic_rag


def test_create_agentic_rag_includes_vision_tool():
    """Test that the factory creates an orchestrator with VisionTool"""
    mock_retriever = MagicMock()
    mock_db_pool = MagicMock()

    orchestrator = create_agentic_rag(mock_retriever, mock_db_pool)

    # Check if VisionTool is in the tools list
    tool_names = [tool.name for tool in orchestrator.tools]
    assert "vision_analysis" in tool_names

    # Verify VisionTool instance
    vision_tool = next(t for t in orchestrator.tools if isinstance(t, VisionTool))
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

    # We need to import VectorSearchTool. Since it's not exported by create_agentic_rag,
    # we import it from the module (which is already patched in the context above)
    from backend.services.rag.agentic import VectorSearchTool

    tool = VectorSearchTool(retriever=mock_retriever)

    result = await tool.execute(query="test query", top_k=3)

    # Verify call
    mock_retriever.search_with_reranking.assert_called_once()
    call_kwargs = mock_retriever.search_with_reranking.call_args.kwargs
    assert call_kwargs["query"] == "test query"
    assert call_kwargs["limit"] == 3

    # Verify result format
    assert "[1] Reranked Doc 1" in result
    assert "[2] Reranked Doc 2" in result
