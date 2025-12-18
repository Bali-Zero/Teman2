"""
Test for IntelligentRouter with new Agentic RAG integration
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent / "backend"))

from services.intelligent_router import IntelligentRouter


@pytest.fixture
def mock_search_service():
    service = MagicMock()
    service.retrieve_with_graph_expansion = AsyncMock(
        return_value={
            "primary_results": {"chunks": [{"text": "Legal content", "metadata": {}}]},
            "graph_expansion": {},
        }
    )
    return service


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.process_query = AsyncMock(
        return_value={"answer": "Agentic Answer", "sources": [{"text": "Source 1"}]}
    )
    return orch


@patch("services.intelligent_router.create_agentic_rag")
@pytest.mark.asyncio
async def test_router_initialization(mock_create_agentic, mock_search_service, mock_orchestrator):
    """Test that router initializes Agentic RAG with correct dependencies"""
    mock_create_agentic.return_value = mock_orchestrator

    router = IntelligentRouter(search_service=mock_search_service)

    # Verify create_agentic_rag was called with search_service
    mock_create_agentic.assert_called_once()
    call_kwargs = mock_create_agentic.call_args.kwargs
    assert call_kwargs["retriever"] == mock_search_service

    # Verify orchestrator is set
    assert router.orchestrator == mock_orchestrator


@patch("services.intelligent_router.create_agentic_rag")
@pytest.mark.asyncio
async def test_router_delegation(mock_create_agentic, mock_search_service, mock_orchestrator):
    """Test that route_chat delegates to orchestrator"""
    mock_create_agentic.return_value = mock_orchestrator

    router = IntelligentRouter(search_service=mock_search_service)

    response = await router.route_chat("Test Query", "user123")

    # Verify delegation
    mock_orchestrator.process_query.assert_called_once_with(query="Test Query", user_id="user123")

    # Verify response format
    assert response["response"] == "Agentic Answer"
    assert response["ai_used"] == "agentic-rag"
    assert response["category"] == "agentic"


@patch("services.intelligent_router.create_agentic_rag")
@pytest.mark.asyncio
async def test_router_streaming(mock_create_agentic, mock_search_service, mock_orchestrator):
    """Test that stream_chat delegates to orchestrator"""
    mock_create_agentic.return_value = mock_orchestrator

    # Mock stream_query to yield items
    async def mock_stream_gen(query, user_id):
        yield {"type": "generation", "content": "Chunk 1"}
        yield {"type": "generation", "content": "Chunk 2"}

    mock_orchestrator.stream_query = mock_stream_gen

    router = IntelligentRouter(search_service=mock_search_service)

    chunks = []
    async for chunk in router.stream_chat("Test Query", "user123"):
        chunks.append(chunk)

    # Verify chunks
    assert len(chunks) == 2
    assert chunks[0]["content"] == "Chunk 1"
    assert chunks[1]["content"] == "Chunk 2"
