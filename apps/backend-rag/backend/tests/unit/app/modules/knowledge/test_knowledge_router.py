"""
Unit tests for Knowledge Router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.models import SearchQuery, TierLevel
from backend.app.modules.knowledge.router import (
    get_search_service,
    search_health,
    search_options,
    semantic_search,
)


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
    request.method = "POST"
    request.url = MagicMock()
    request.url.path = "/api/search"
    request.headers = {}
    return request


@pytest.fixture
def mock_search_query():
    """Create SearchQuery fixture"""
    return SearchQuery(query="test query", level=0, limit=5)


class TestGetSearchService:
    """Tests for get_search_service function"""

    def test_get_search_service_from_app_state(self, mock_request, mock_search_service):
        """Test that get_search_service returns SearchService from backend.app.state"""
        mock_request.app.state.search_service = mock_search_service

        service = get_search_service(mock_request)
        assert service == mock_search_service

    def test_get_search_service_fallback_creates_singleton(self, mock_request):
        """Test that get_search_service creates singleton on fallback"""
        # Access module-level variable through sys.modules
        import sys

        router_mod = sys.modules.get("backend.app.modules.knowledge.router")
        if router_mod is None:
            import backend.app.modules.knowledge.router as router_mod

        # Reset singleton for clean test
        original_fallback = getattr(router_mod, "_knowledge_service_fallback", None)
        router_mod._knowledge_service_fallback = None

        # Remove search_service from backend.app.state
        mock_request.app.state.search_service = None

        try:
            # First call creates singleton
            service1 = get_search_service(mock_request)
            assert service1 is not None

            # Second call should reuse singleton
            service2 = get_search_service(mock_request)
            assert service1 is service2

        finally:
            # Cleanup
            router_mod._knowledge_service_fallback = original_fallback


class TestSemanticSearch:
    """Tests for semantic_search endpoint"""

    @pytest.mark.asyncio
    async def test_semantic_search_success(
        self, mock_search_service, mock_search_query, mock_request
    ):
        """Test successful semantic search using SearchService"""
        mock_request.app.state.search_service = mock_search_service

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(mock_search_query, mock_request)

            assert response.query == "test query"
            assert response.user_level == 0
            assert response.total_found == 1
            assert len(response.results) == 1
            assert response.results[0].text == "test document"
            # Verify apply_filters=True is passed (required for /api/search)
            call_args = mock_search_service.search.call_args
            assert call_args[1]["apply_filters"] is True

    def test_search_query_validation_level_negative(self):
        """Test that SearchQuery model rejects negative level at validation time"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SearchQuery(query="test", level=-1, limit=5)
        assert "greater_than_equal" in str(exc_info.value) or "level" in str(exc_info.value)

    def test_search_query_validation_level_too_high(self):
        """Test that SearchQuery model rejects level > 3 at validation time"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SearchQuery(query="test", level=4, limit=5)
        assert "less_than_equal" in str(exc_info.value) or "level" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_semantic_search_with_tier_filter(self, mock_search_service, mock_request):
        """Test semantic search with tier filter"""
        mock_request.app.state.search_service = mock_search_service
        query = SearchQuery(query="test", level=2, limit=5, tier_filter=[TierLevel.C])

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response is not None
            call_args = mock_search_service.search.call_args
            assert call_args[1]["tier_filter"] == [TierLevel.C]
            assert call_args[1]["apply_filters"] is True

    @pytest.mark.asyncio
    async def test_semantic_search_with_collection_override(
        self, mock_search_service, mock_request
    ):
        """Test semantic search with collection override"""
        mock_request.app.state.search_service = mock_search_service
        query = SearchQuery(query="test", level=0, limit=5, collection="kb_indonesian")

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response is not None
            call_args = mock_search_service.search.call_args
            assert call_args[1]["collection_override"] == "kb_indonesian"
            assert call_args[1]["apply_filters"] is True

    @pytest.mark.asyncio
    async def test_semantic_search_empty_results(self, mock_search_service, mock_request):
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

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response.total_found == 0
            assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_semantic_search_multiple_results(self, mock_search_service, mock_request):
        """Test semantic search with multiple results"""
        mock_request.app.state.search_service = mock_search_service
        mock_search_service.search.return_value = {
            "query": "test",
            "results": [
                {
                    "id": "id1",
                    "text": "doc1",
                    "metadata": {"book_title": "Book1", "tier": "C"},
                    "score": 0.9,
                },
                {
                    "id": "id2",
                    "text": "doc2",
                    "metadata": {"book_title": "Book2", "tier": "B"},
                    "score": 0.8,
                },
            ],
            "user_level": 0,
            "allowed_tiers": [],
            "collection_used": "visa_oracle",
        }

        query = SearchQuery(query="test", level=0, limit=5)

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response.total_found == 2
            assert len(response.results) == 2
            assert response.results[0].text == "doc1"
            assert response.results[1].text == "doc2"

    @pytest.mark.asyncio
    async def test_semantic_search_error_handling(self, mock_search_service, mock_request):
        """Test semantic search error handling"""
        mock_request.app.state.search_service = mock_search_service
        mock_search_service.search.side_effect = Exception("Search error")

        query = SearchQuery(query="test", level=0, limit=5)

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await semantic_search(query, mock_request)

            assert exc_info.value.status_code == 500
            assert "Search failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_semantic_search_http_exception_passthrough(
        self, mock_search_service, mock_request
    ):
        """Test that HTTPException is passed through without modification"""
        mock_request.app.state.search_service = mock_search_service
        mock_search_service.search.side_effect = HTTPException(
            status_code=400, detail="Bad request"
        )

        query = SearchQuery(query="test", level=0, limit=5)

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            with pytest.raises(HTTPException) as exc_info:
                await semantic_search(query, mock_request)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Bad request"

    @pytest.mark.asyncio
    async def test_semantic_search_tier_enum_conversion(self, mock_search_service, mock_request):
        """Test tier string to enum conversion"""
        mock_request.app.state.search_service = mock_search_service
        mock_search_service.search.return_value = {
            "query": "test",
            "results": [
                {
                    "id": "id1",
                    "text": "doc1",
                    "metadata": {"book_title": "Book1", "tier": "S"},
                    "score": 0.9,
                }
            ],
            "user_level": 0,
            "allowed_tiers": [],
            "collection_used": "visa_oracle",
        }

        query = SearchQuery(query="test", level=0, limit=5)

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response.results[0].metadata.tier == TierLevel.S

    @pytest.mark.asyncio
    async def test_semantic_search_tier_invalid_fallback(self, mock_search_service, mock_request):
        """Test tier invalid value falls back to TierLevel.C"""
        mock_request.app.state.search_service = mock_search_service
        mock_search_service.search.return_value = {
            "query": "test",
            "results": [
                {
                    "id": "id1",
                    "text": "doc1",
                    "metadata": {"book_title": "Book1", "tier": "INVALID"},
                    "score": 0.9,
                }
            ],
            "user_level": 0,
            "allowed_tiers": [],
            "collection_used": "visa_oracle",
        }

        query = SearchQuery(query="test", level=0, limit=5)

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response.results[0].metadata.tier == TierLevel.C

    @pytest.mark.asyncio
    async def test_semantic_search_missing_metadata_fields(self, mock_search_service, mock_request):
        """Test semantic search handles missing metadata fields gracefully"""
        mock_request.app.state.search_service = mock_search_service
        mock_search_service.search.return_value = {
            "query": "test",
            "results": [
                {
                    "id": "id1",
                    "text": "doc1",
                    "metadata": {},  # Empty metadata
                    "score": 0.9,
                }
            ],
            "user_level": 0,
            "allowed_tiers": [],
            "collection_used": "visa_oracle",
        }

        query = SearchQuery(query="test", level=0, limit=5)

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await semantic_search(query, mock_request)

            assert response.results[0].metadata.book_title == "Unknown"
            assert response.results[0].metadata.book_author == "Unknown"
            assert response.results[0].metadata.tier == TierLevel.C


class TestSearchHealth:
    """Tests for search_health endpoint"""

    @pytest.mark.asyncio
    async def test_search_health_success(self, mock_search_service, mock_request):
        """Test search health check success"""
        mock_request.app.state.search_service = mock_search_service

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_search_service
        ):
            response = await search_health(mock_request)

            assert response["status"] == "operational"
            assert response["service"] == "SearchService"
            assert response["embeddings"] == "ready"
            assert response["vector_db"] == "connected"

    @pytest.mark.asyncio
    async def test_search_health_fallback_to_knowledge_service(self, mock_request):
        """Test search health check falls back to KnowledgeService"""
        # Remove search_service from backend.app.state (simulate it not being initialized)
        if hasattr(mock_request.app.state, "search_service"):
            delattr(mock_request.app.state, "search_service")

        mock_knowledge_service = MagicMock()

        with patch(
            "backend.app.modules.knowledge.router.get_search_service", return_value=mock_knowledge_service
        ):
            # Mock hasattr to return False (simulating SearchService not in app.state)
            with patch("builtins.hasattr", side_effect=lambda obj, attr: attr != "search_service"):
                response = await search_health(mock_request)

                assert response["status"] == "operational"
                assert response["service"] == "KnowledgeService"

    @pytest.mark.asyncio
    async def test_search_health_service_unavailable(self, mock_request):
        """Test search health check when service unavailable"""
        with patch(
            "backend.app.modules.knowledge.router.get_search_service",
            side_effect=Exception("Service error"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await search_health(mock_request)

            assert exc_info.value.status_code == 503
            assert "Knowledge service unhealthy" in exc_info.value.detail


class TestSearchOptions:
    """Tests for search_options endpoint"""

    @pytest.mark.asyncio
    async def test_search_options(self):
        """Test OPTIONS endpoint for CORS preflight"""
        response = await search_options()
        assert response == {"status": "ok"}
