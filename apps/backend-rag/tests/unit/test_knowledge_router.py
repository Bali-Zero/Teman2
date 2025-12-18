"""
Unit tests for Knowledge Router

UPDATED: Router now uses SearchService (canonical retriever) instead of KnowledgeService singleton.
Tests updated to reflect this change.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.models import SearchQuery, TierLevel
from app.modules.knowledge.router import get_search_service, search_health, semantic_search


@pytest.fixture
def mock_search_service():
    """Mock SearchService (canonical retriever)"""
    service = MagicMock()
    service.search = AsyncMock(
        return_value={
            "query": "test",
            "results": [
                {
                    "id": "id1",
                    "text": "test document",
                    "metadata": {
                        "book_title": "Test Book",
                        "book_author": "Test Author",
                        "tier": "C",
                        "min_level": 0,
                        "chunk_index": 0,
                        "page_number": 1,
                        "language": "en",
                        "topics": [],
                        "file_path": "/test.pdf",
                        "total_chunks": 10,
                    },
                    "score": 0.95,
                }
            ],
            "user_level": 0,
            "allowed_tiers": [],
            "collection_used": "visa_oracle",
        }
    )
    return service


@pytest.fixture
def mock_request():
    """Mock FastAPI Request with app.state.search_service"""
    request = MagicMock(spec=Request)
    request.app.state = MagicMock()
    return request


@pytest.fixture
def mock_search_query():
    """Create SearchQuery fixture"""
    return SearchQuery(query="test query", level=0, limit=5)


# ============================================================================
# Tests for get_search_service
# ============================================================================


def test_get_search_service_from_app_state(mock_request, mock_search_service):
    """Test that get_search_service returns SearchService from app.state"""
    mock_request.app.state.search_service = mock_search_service

    service = get_search_service(mock_request)
    assert service == mock_search_service


def test_get_search_service_fallback_to_knowledge_service(mock_request):
    """Test that get_search_service falls back to KnowledgeService if SearchService not in app.state"""
    # Remove search_service from app.state
    delattr(mock_request.app.state, "search_service")
    mock_request.app.state.search_service = None

    with patch("app.modules.knowledge.router.KnowledgeService") as mock_knowledge_class:
        mock_knowledge_instance = MagicMock()
        mock_knowledge_class.return_value = mock_knowledge_instance

        service = get_search_service(mock_request)
        assert service == mock_knowledge_instance
        mock_knowledge_class.assert_called_once()


# ============================================================================
# Tests for semantic_search
# ============================================================================


@pytest.mark.asyncio
async def test_semantic_search_success(mock_search_service, mock_search_query, mock_request):
    """Test successful semantic search using SearchService"""
    mock_request.app.state.search_service = mock_search_service

    with patch("app.modules.knowledge.router.get_search_service", return_value=mock_search_service):
        response = await semantic_search(mock_search_query, mock_request)

        assert response.query == "test query"
        assert response.user_level == 0
        assert response.total_found == 1
        assert len(response.results) == 1
        assert response.results[0].text == "test document"
        # Verify apply_filters=True is passed (required for /api/search)
        call_args = mock_search_service.search.call_args
        assert call_args[1]["apply_filters"] is True


@pytest.mark.asyncio
async def test_semantic_search_invalid_level(mock_search_service, mock_request):
    """Test semantic search with invalid level - Pydantic validation prevents this"""
    # Pydantic will validate level before reaching the endpoint
    # So we test that Pydantic validation works
    with pytest.raises(Exception):  # Pydantic validation error
        invalid_query = SearchQuery(query="test", level=5, limit=5)  # level > 3


@pytest.mark.asyncio
async def test_semantic_search_with_tier_filter(mock_search_service, mock_request):
    """Test semantic search with tier filter"""
    mock_request.app.state.search_service = mock_search_service
    query = SearchQuery(query="test", level=2, limit=5, tier_filter=[TierLevel.C])

    with patch("app.modules.knowledge.router.get_search_service", return_value=mock_search_service):
        response = await semantic_search(query, mock_request)

        assert response is not None
        call_args = mock_search_service.search.call_args
        assert call_args[1]["tier_filter"] == [TierLevel.C]
        assert call_args[1]["apply_filters"] is True


@pytest.mark.asyncio
async def test_semantic_search_with_collection_override(mock_search_service, mock_request):
    """Test semantic search with collection override"""
    mock_request.app.state.search_service = mock_search_service
    query = SearchQuery(query="test", level=0, limit=5, collection="kb_indonesian")

    with patch("app.modules.knowledge.router.get_search_service", return_value=mock_search_service):
        response = await semantic_search(query, mock_request)

        assert response is not None
        call_args = mock_search_service.search.call_args
        assert call_args[1]["collection_override"] == "kb_indonesian"
        assert call_args[1]["apply_filters"] is True


@pytest.mark.asyncio
async def test_semantic_search_empty_results(mock_search_service, mock_request):
    """Test semantic search with empty results"""
    mock_request.app.state.search_service = mock_search_service
    mock_search_service.search.return_value = {
        "query": "test",
        "results": [],
        "user_level": 0,
        "allowed_tiers": [],
        "collection_used": "visa_oracle",
    }

    query = SearchQuery(query="test", level=0, limit=5)

    with patch("app.modules.knowledge.router.get_search_service", return_value=mock_search_service):
        response = await semantic_search(query, mock_request)

        assert response.total_found == 0
        assert len(response.results) == 0


@pytest.mark.asyncio
async def test_semantic_search_error_handling(mock_search_service, mock_request):
    """Test semantic search error handling"""
    mock_request.app.state.search_service = mock_search_service
    mock_search_service.search.side_effect = Exception("Search error")

    query = SearchQuery(query="test", level=0, limit=5)

    with patch("app.modules.knowledge.router.get_search_service", return_value=mock_search_service):
        with pytest.raises(HTTPException) as exc_info:
            await semantic_search(query, mock_request)

        assert exc_info.value.status_code == 500
        assert "Search failed" in exc_info.value.detail


# ============================================================================
# Tests for search_health
# ============================================================================


@pytest.mark.asyncio
async def test_search_health_success(mock_search_service, mock_request):
    """Test search health check success"""
    mock_request.app.state.search_service = mock_search_service

    with patch("app.modules.knowledge.router.get_search_service", return_value=mock_search_service):
        response = await search_health(mock_request)

        assert response["status"] == "operational"
        assert response["service"] == "SearchService"
        assert response["embeddings"] == "ready"
        assert response["vector_db"] == "connected"


@pytest.mark.asyncio
async def test_search_health_fallback_to_knowledge_service(mock_request):
    """Test search health check falls back to KnowledgeService"""
    # Remove search_service from app.state (simulate it not being initialized)
    if hasattr(mock_request.app.state, "search_service"):
        delattr(mock_request.app.state, "search_service")

    mock_knowledge_service = MagicMock()

    with patch(
        "app.modules.knowledge.router.get_search_service", return_value=mock_knowledge_service
    ):
        # Mock hasattr to return False (simulating SearchService not in app.state)
        with patch("builtins.hasattr", side_effect=lambda obj, attr: attr != "search_service"):
            response = await search_health(mock_request)

            assert response["status"] == "operational"
            assert response["service"] == "KnowledgeService"


@pytest.mark.asyncio
async def test_search_health_service_unavailable(mock_request):
    """Test search health check when service unavailable"""
    with patch(
        "app.modules.knowledge.router.get_search_service", side_effect=Exception("Service error")
    ):
        with pytest.raises(HTTPException) as exc_info:
            await search_health(mock_request)

        assert exc_info.value.status_code == 503
        assert "Knowledge service unhealthy" in exc_info.value.detail
