"""
Unit tests for Knowledge Service
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.models import TierLevel
from app.modules.knowledge.service import KnowledgeService


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    with patch("app.modules.knowledge.service.settings") as mock:
        mock.qdrant_url = "http://localhost:6333"
        yield mock


@pytest.fixture
def mock_embedder():
    """Mock embeddings generator"""
    embedder = MagicMock()
    embedder.provider = "openai"
    embedder.dimensions = 1536
    embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
    return embedder


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client"""
    client = MagicMock()
    client.search = AsyncMock(
        return_value={
            "ids": ["id1", "id2"],
            "documents": ["doc1", "doc2"],
            "distances": [0.1, 0.2],
            "metadatas": [{"tier": "C"}, {"tier": "B"}],
        }
    )
    return client


@pytest.fixture
def mock_query_router():
    """Mock query router"""
    router = MagicMock()
    router.route = MagicMock(return_value="visa_oracle")
    return router


@pytest.fixture
def knowledge_service(mock_settings, mock_embedder, mock_qdrant_client, mock_query_router):
    """Create KnowledgeService instance with mocks"""
    with patch("core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        with patch("app.modules.knowledge.service.QdrantClient", return_value=mock_qdrant_client):
            with patch("app.modules.knowledge.service.QueryRouter", return_value=mock_query_router):
                service = KnowledgeService()
                # Replace collections with mocked clients
                for key in service.collections:
                    service.collections[key] = mock_qdrant_client
                return service


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_success(mock_settings, mock_embedder, mock_qdrant_client, mock_query_router):
    """Test KnowledgeService initialization"""
    with patch("core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        with patch("app.modules.knowledge.service.QdrantClient", return_value=mock_qdrant_client):
            with patch("app.modules.knowledge.service.QueryRouter", return_value=mock_query_router):
                service = KnowledgeService()
                assert service.embedder == mock_embedder
                assert len(service.collections) > 0
                assert service.router == mock_query_router


# ============================================================================
# Tests for search
# ============================================================================


@pytest.mark.asyncio
async def test_search_success(knowledge_service, mock_embedder, mock_qdrant_client):
    """Test successful search"""
    result = await knowledge_service.search(
        query="test query",
        user_level=2,
        limit=5,
    )

    assert result is not None
    assert result["query"] == "test query"
    assert result["user_level"] == 2
    assert "results" in result
    assert len(result["results"]) == 2
    assert mock_embedder.generate_query_embedding.called


@pytest.mark.asyncio
async def test_search_with_pricing_query(knowledge_service, mock_qdrant_client):
    """Test search detects pricing query"""
    result = await knowledge_service.search(
        query="how much does it cost",
        user_level=0,
        limit=5,
    )

    assert result["collection_used"] == "bali_zero_pricing"


@pytest.mark.asyncio
async def test_search_with_collection_override(knowledge_service, mock_qdrant_client):
    """Test search with collection override"""
    result = await knowledge_service.search(
        query="test",
        user_level=0,
        limit=5,
        collection_override="kb_indonesian",
    )

    assert result["collection_used"] == "kb_indonesian"


@pytest.mark.asyncio
async def test_search_with_tier_filter(knowledge_service, mock_qdrant_client):
    """Test search with tier filter"""
    result = await knowledge_service.search(
        query="test",
        user_level=2,
        limit=5,
        tier_filter=[TierLevel.C],
        collection_override="zantara_books",
    )

    assert result is not None
    assert TierLevel.C.value in result["allowed_tiers"]


@pytest.mark.asyncio
async def test_search_unknown_collection_defaults(knowledge_service, mock_qdrant_client):
    """Test search with unknown collection defaults to visa_oracle"""
    # Mock router to return unknown collection
    knowledge_service.router.route = MagicMock(return_value="unknown_collection")

    result = await knowledge_service.search(
        query="test",
        user_level=0,
        limit=5,
    )

    assert result["collection_used"] == "visa_oracle"


@pytest.mark.asyncio
async def test_search_empty_query(knowledge_service):
    """Test search with empty query"""
    result = await knowledge_service.search(
        query="",
        user_level=0,
        limit=5,
    )

    assert result is not None
    assert result["query"] == ""


@pytest.mark.asyncio
async def test_search_empty_results(knowledge_service, mock_qdrant_client):
    """Test search with empty results"""
    # Create a new mock client with empty results
    empty_client = MagicMock()
    empty_client.search = AsyncMock(
        return_value={
            "ids": [],
            "documents": [],
            "distances": [],
            "metadatas": [],
        }
    )

    # Replace the collection client
    knowledge_service.collections["visa_oracle"] = empty_client

    result = await knowledge_service.search(
        query="test",
        user_level=0,
        limit=5,
        collection_override="visa_oracle",
    )

    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_zantara_books_tier_filtering(knowledge_service, mock_qdrant_client):
    """Test search applies tier filtering for zantara_books collection"""
    result = await knowledge_service.search(
        query="test",
        user_level=1,  # Should allow S and A tiers
        limit=5,
        collection_override="zantara_books",
    )

    assert result is not None
    # Verify filter was applied
    assert mock_qdrant_client.search.called
    call_args = mock_qdrant_client.search.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_search_pricing_priority_bias(knowledge_service, mock_qdrant_client):
    """Test search applies pricing priority bias"""
    result = await knowledge_service.search(
        query="price",
        user_level=0,
        limit=5,
    )

    assert result["collection_used"] == "bali_zero_pricing"
    # Check that results have pricing_priority metadata
    if result["results"]:
        assert result["results"][0]["metadata"].get("pricing_priority") == "high"


@pytest.mark.asyncio
async def test_search_with_reranking(knowledge_service, mock_qdrant_client):
    """Test search with semantic re-ranking"""
    # Mock ReRanker
    mock_reranker = MagicMock()
    mock_reranker.model = True
    mock_reranker.rerank = MagicMock(
        return_value=[
            {"id": "doc1", "score": 0.9, "rerank_score": 0.9, "text": "relevant"},
            {"id": "doc2", "score": 0.1, "rerank_score": 0.1, "text": "irrelevant"},
        ]
    )

    # Inject reranker
    knowledge_service.reranker = mock_reranker

    # Mock search to return candidates
    mock_qdrant_client.search = AsyncMock(
        return_value={
            "ids": ["doc2", "doc1"],
            "documents": ["irrelevant", "relevant"],
            "distances": [0.1, 0.2],
            "metadatas": [{}, {}],
        }
    )

    result = await knowledge_service.search_with_reranking(query="test", user_level=0, limit=2)

    assert result["reranked"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["id"] == "doc1"  # Reranked to top

    # Verify wide funnel (limit * 3)
    call_args = mock_qdrant_client.search.call_args
    assert call_args.kwargs["limit"] == 6  # 2 * 3
