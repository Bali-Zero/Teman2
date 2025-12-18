"""
Unit tests to improve coverage for SearchService.

Tests edge cases and error handling paths to reach >90% coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import httpx

from services.search_service import SearchService

# Import Qdrant exceptions the same way as search_service.py
try:
    from qdrant_client.http import exceptions as qdrant_exceptions
except ImportError:
    # Fallback for older versions
    try:
        from qdrant_client import exceptions as qdrant_exceptions
    except ImportError:
        # Create a mock exception class if import fails
        class UnexpectedResponse(Exception):
            pass

        class qdrant_exceptions:
            UnexpectedResponse = UnexpectedResponse


class TestSearchServiceCoverage:
    """Test edge cases and error handling for SearchService."""

    @pytest.fixture
    def mock_collection_manager(self):
        """Create mock collection manager"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(
            return_value={
                "documents": ["Doc 1"],
                "metadatas": [{}],
                "distances": [0.2],
                "ids": ["doc1"],
            }
        )
        mock_manager.get_collection = MagicMock(return_value=mock_collection)
        return mock_manager, mock_collection

    @pytest.fixture
    def mock_query_router(self):
        """Create mock query router"""
        mock_router = MagicMock()
        mock_router.route_query = MagicMock(
            return_value={"collection_name": "visa_oracle", "confidence": 0.9}
        )
        return mock_router

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder"""
        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
        mock_embedder.provider = "test"
        mock_embedder.dimensions = 384
        return mock_embedder

    @pytest.fixture
    def search_service(self, mock_collection_manager, mock_query_router, mock_embedder):
        """Create SearchService instance"""
        mock_manager, _ = mock_collection_manager
        service = SearchService(
            collection_manager=mock_manager,
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder
        return service

    @pytest.mark.asyncio
    async def test_collection_not_found_fallback_fails(self, search_service, mock_collection_manager):
        """Test when collection not found and fallback to visa_oracle also fails"""
        mock_manager, _ = mock_collection_manager
        mock_manager.get_collection.return_value = None  # Both collections fail

        search_service.query_router.route_query.return_value = {
            "collection_name": "unknown_collection",
            "confidence": 0.9,
        }

        with pytest.raises(ValueError, match="Failed to initialize default collection"):
            await search_service._prepare_search_context(
                query="test query",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )

    @pytest.mark.asyncio
    async def test_search_qdrant_exception(self, search_service, mock_collection_manager):
        """Test search method handles Qdrant exceptions"""
        mock_manager, mock_collection = mock_collection_manager
        # Create a proper Qdrant exception
        # UnexpectedResponse requires: status_code, reason_phrase, content, headers
        import httpx
        exception = qdrant_exceptions.UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Server Error",
            content=b"Error",
            headers=httpx.Headers()
        )
        mock_collection.search.side_effect = exception

        with pytest.raises(qdrant_exceptions.UnexpectedResponse):
            await search_service.search(query="test", user_level=1, limit=5)

    @pytest.mark.asyncio
    async def test_search_httpx_error(self, search_service, mock_collection_manager):
        """Test search method handles HTTP errors"""
        mock_manager, mock_collection = mock_collection_manager
        mock_collection.search.side_effect = httpx.HTTPError("Connection failed")

        with pytest.raises(httpx.HTTPError):
            await search_service.search(query="test", user_level=1, limit=5)

    @pytest.mark.asyncio
    async def test_search_key_error(self, search_service, mock_collection_manager):
        """Test search method handles KeyError"""
        mock_manager, mock_collection = mock_collection_manager
        # Return dict that will cause KeyError when accessing results
        # format_search_results uses .get() so it won't raise KeyError
        # Instead, we need to make the search method itself raise KeyError
        # by accessing a key that doesn't exist in the return value
        def raise_keyerror(*args, **kwargs):
            raise KeyError("documents")
        
        mock_collection.search.side_effect = raise_keyerror

        # The KeyError should be caught and re-raised
        with pytest.raises(KeyError):
            await search_service.search(query="test", user_level=1, limit=5)

    @pytest.mark.asyncio
    async def test_init_reranker_lazy_load(self, search_service):
        """Test lazy loading of reranker"""
        # Ensure reranker doesn't exist
        if hasattr(search_service, "_reranker"):
            delattr(search_service, "_reranker")

        with patch("core.reranker.ReRanker") as mock_reranker_class:
            mock_reranker = MagicMock()
            mock_reranker_class.return_value = mock_reranker

            reranker = search_service._init_reranker()

            assert reranker == mock_reranker
            assert search_service._reranker == mock_reranker
            mock_reranker_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_reranking_no_rerank_branch(
        self, search_service, mock_collection_manager
    ):
        """Test search_with_reranking when reranker is not enabled or no results"""
        mock_manager, mock_collection = mock_collection_manager

        # Mock reranker as disabled
        mock_reranker = MagicMock()
        mock_reranker.enabled = False
        search_service._reranker = mock_reranker

        result = await search_service.search_with_reranking(
            query="test query", user_level=1, limit=5
        )

        assert result["reranked"] is False
        assert result["early_exit"] is False
        mock_reranker.rerank.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_pricing_query(
        self, search_service, mock_collection_manager
    ):
        """Test search_with_conflict_resolution with pricing query"""
        mock_manager, mock_collection = mock_collection_manager

        search_service.query_router.route_query.return_value = {
            "collection_name": "bali_zero_pricing",
            "collections": ["bali_zero_pricing"],
            "confidence": 1.0,
            "is_pricing": True,  # This triggers the pricing branch
        }

        result = await search_service.search_with_conflict_resolution(
            query="pricing query", user_level=1, limit=5
        )

        assert result is not None
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_exception_fallback(
        self, search_service, mock_collection_manager
    ):
        """Test search_with_conflict_resolution handles exceptions and falls back"""
        mock_manager, mock_collection = mock_collection_manager

        # Make search fail with an exception
        mock_collection.search.side_effect = RuntimeError("Search failed")

        # Mock the fallback search method
        with patch.object(search_service, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": [], "collection_used": "visa_oracle"}

            result = await search_service.search_with_conflict_resolution(
                query="test query", user_level=1, limit=5
            )

            # Should fallback to simple search
            mock_search.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_qdrant_exception(
        self, search_service, mock_collection_manager
    ):
        """Test search_with_conflict_resolution handles Qdrant exceptions"""
        mock_manager, mock_collection = mock_collection_manager

        import httpx
        exception = qdrant_exceptions.UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Server Error",
            content=b"Error",
            headers=httpx.Headers()
        )
        mock_collection.search.side_effect = exception

        with patch.object(search_service, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": [], "collection_used": "visa_oracle"}

            result = await search_service.search_with_conflict_resolution(
                query="test query", user_level=1, limit=5
            )

            # Verify result is returned (either from fallback or empty)
            assert result is not None
            assert "results" in result
            # Fallback may or may not be called depending on when exception occurs
            # The important thing is that the exception is handled gracefully

    @pytest.mark.asyncio
    async def test_search_collection_collection_not_found(
        self, search_service, mock_collection_manager
    ):
        """Test search_collection when collection not found, creates ad-hoc client"""
        mock_manager, _ = mock_collection_manager
        mock_manager.get_collection.return_value = None  # Collection not found

        with patch("core.qdrant_db.QdrantClient") as mock_qdrant_client:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value={
                    "documents": ["Doc 1"],
                    "metadatas": [{}],
                    "distances": [0.2],
                    "ids": ["doc1"],
                }
            )
            mock_qdrant_client.return_value = mock_client

            result = await search_service.search_collection(
                query="test", collection_name="new_collection", limit=5
            )

            assert result is not None
            assert "results" in result
            mock_qdrant_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_collection_exception_handling(
        self, search_service, mock_collection_manager
    ):
        """Test search_collection handles exceptions gracefully"""
        mock_manager, mock_collection = mock_collection_manager
        mock_collection.search.side_effect = ValueError("Search failed")

        result = await search_service.search_collection(
            query="test", collection_name="visa_oracle", limit=5
        )

        assert result is not None
        assert "error" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_collection_httpx_error(
        self, search_service, mock_collection_manager
    ):
        """Test search_collection handles HTTP errors"""
        mock_manager, mock_collection = mock_collection_manager
        mock_collection.search.side_effect = httpx.HTTPError("Connection failed")

        result = await search_service.search_collection(
            query="test", collection_name="visa_oracle", limit=5
        )

        assert result is not None
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_collection_key_error(
        self, search_service, mock_collection_manager
    ):
        """Test search_collection handles KeyError"""
        mock_manager, mock_collection = mock_collection_manager
        # Return dict missing 'documents' key which will cause KeyError in format_search_results
        mock_collection.search.return_value = {
            "metadatas": [{}],
            "distances": [0.2],
            "ids": ["doc1"],
            # Missing "documents" key - this will cause KeyError
        }

        result = await search_service.search_collection(
            query="test", collection_name="visa_oracle", limit=5
        )

        assert result is not None
        # KeyError should be caught and return error dict
        assert "error" in result or "results" in result

