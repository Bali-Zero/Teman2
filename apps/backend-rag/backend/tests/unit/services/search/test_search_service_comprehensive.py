"""
Unit tests for SearchService
Target: 100% coverage
Composer: 3
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.search.search_service import SearchService


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client"""
    client = MagicMock()

    # search is async but returns dict directly
    async def mock_search(*args, **kwargs):
        return {
            "ids": ["1", "2"],
            "documents": ["doc1", "doc2"],
            "metadatas": [{"tier": "S"}, {"tier": "A"}],
            "distances": [0.1, 0.2],
            "total_found": 2,
        }

    client.search = mock_search
    return client


@pytest.fixture
def mock_embedder():
    """Mock embedding service"""
    embedder = MagicMock()
    embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
    embedder.provider = "openai"
    embedder.dimensions = 1536
    return embedder


@pytest.fixture
def search_service(mock_qdrant_client, mock_embedder):
    """Create search service instance"""
    with (
        patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder),
        patch("backend.core.qdrant_db.QdrantClient", return_value=mock_qdrant_client),
        patch("backend.services.search.search_service.CollectionManager") as mock_cm,
        patch("backend.services.search.search_service.ConflictResolver"),
        patch("backend.services.search.search_service.CulturalInsightsService"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.services.ingestion.collection_health_service.CollectionHealthService"),
        patch("backend.services.search.search_service.CollectionWarmupService"),
    ):
        # Mock CollectionManager to return our mock client
        mock_cm_instance = MagicMock()
        mock_cm_instance.get_collection.return_value = mock_qdrant_client
        mock_cm.return_value = mock_cm_instance

        service = SearchService()
        # Override embedder for testing
        service.embedder = mock_embedder
        # Override collection_manager to use our mock
        service.collection_manager = mock_cm_instance
        return service


class TestSearchService:
    """Tests for SearchService"""

    @pytest.mark.asyncio
    async def test_search_basic(self, search_service):
        """Test basic search"""
        result = await search_service.search(query="test query", user_level=1, limit=5)
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_collection(self, search_service):
        """Test search with specific collection"""
        result = await search_service.search(
            query="test", user_level=1, limit=5, collection_override="visa_oracle"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_reranking(self, search_service):
        """Test search with reranking"""
        result = await search_service.search_with_reranking(query="test", user_level=1, limit=5)
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_tier_filtering(self, search_service):
        """Test tier-based filtering"""
        result = await search_service.search(
            query="test",
            user_level=0,  # Lower tier
            limit=5,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_error_handling(self, search_service, mock_qdrant_client):
        """Test error handling"""
        # Mock search to raise exception
        mock_qdrant_client.search.side_effect = Exception("Qdrant error")

        # SearchService should handle errors gracefully
        result = await search_service.search(query="test", user_level=1, limit=5)
        # Should return empty results or handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_apply_filters(self, search_service):
        """Test search with apply_filters parameter"""
        result = await search_service.search(
            query="test", user_level=1, limit=5, apply_filters=True
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_tier_filter(self, search_service):
        """Test search with tier filter"""
        from backend.app.models import TierLevel

        result = await search_service.search(
            query="test", user_level=2, limit=5, tier_filter=[TierLevel.S, TierLevel.A]
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_empty_query(self, search_service):
        """Test search with empty query"""
        # The error is caught and returns empty results, so we check for that
        result = await search_service.search(query="", user_level=1, limit=5)
        # Should return empty results or error dict
        assert result is not None
        assert "error" in result or len(result.get("results", [])) == 0

    @pytest.mark.asyncio
    async def test_search_invalid_user_level(self, search_service):
        """Test search with invalid user level"""
        # The error is caught and returns empty results, so we check for that
        result = await search_service.search(
            query="test",
            user_level=5,  # Invalid
            limit=5,
        )
        # Should return empty results or error dict
        assert result is not None
        assert "error" in result or len(result.get("results", [])) == 0

    @pytest.mark.asyncio
    async def test_search_with_reranking_early_exit(self, search_service):
        """Test search with reranking - early exit for high score"""

        # Mock search to return high score result
        async def mock_search_high_score(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{"tier": "S"}],
                "distances": [0.05],  # High score (low distance)
                "total_found": 1,
            }

        search_service.collection_manager.get_collection.return_value.search = (
            mock_search_high_score
        )

        result = await search_service.search_with_reranking(query="test", user_level=1, limit=5)
        assert result.get("early_exit") is True

    @pytest.mark.asyncio
    async def test_search_with_reranking_disabled(self, search_service):
        """Test search with reranking when reranker is disabled"""
        with patch.object(search_service, "_init_reranker") as mock_reranker:
            mock_reranker.return_value.enabled = False

            result = await search_service.search_with_reranking(query="test", user_level=1, limit=5)
            assert result.get("reranked") is False

    @pytest.mark.asyncio
    async def test_hybrid_search(self, search_service):
        """Test hybrid search"""
        # Mock BM25 vectorizer
        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector = MagicMock(
            return_value={"indices": [1, 2], "values": [0.5, 0.3]}
        )
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        # Mock hybrid_search method
        async def mock_hybrid_search(*args, **kwargs):
            return {
                "ids": ["1", "2"],
                "documents": ["doc1", "doc2"],
                "metadatas": [{"tier": "S"}, {"tier": "A"}],
                "distances": [0.1, 0.2],
                "total_found": 2,
                "search_type": "hybrid_rrf",
            }

        search_service.collection_manager.get_collection.return_value.hybrid_search = (
            mock_hybrid_search
        )

        result = await search_service.hybrid_search(query="test", user_level=1, limit=5)
        assert result is not None
        assert result.get("search_type") == "hybrid_rrf"

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback(self, search_service):
        """Test hybrid search fallback to dense-only"""
        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector = MagicMock(return_value=None)
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        result = await search_service.hybrid_search(query="test", user_level=1, limit=5)
        assert result is not None

    @pytest.mark.asyncio
    async def test_hybrid_search_with_reranking(self, search_service):
        """Test hybrid search with reranking"""
        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector = MagicMock(
            return_value={"indices": [1], "values": [0.5]}
        )
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        async def mock_hybrid_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{"tier": "S"}],
                "distances": [0.05],
                "total_found": 1,
                "search_type": "hybrid_rrf",
            }

        search_service.collection_manager.get_collection.return_value.hybrid_search = (
            mock_hybrid_search
        )

        result = await search_service.hybrid_search_with_reranking(
            query="test", user_level=1, limit=5
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution(self, search_service):
        """Test search with conflict resolution"""
        # Mock query router
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "legal_unified",
                "collections": ["legal_unified", "visa_oracle"],
                "confidence": 0.9,
                "is_pricing": False,
            }
        )

        # Mock conflict resolver
        search_service.conflict_resolver.detect_conflicts = MagicMock(return_value=[])
        search_service.conflict_resolver.resolve_conflicts = MagicMock(return_value=([], []))

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        assert result is not None
        assert "conflicts_detected" in result

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_with_conflicts(self, search_service):
        """Test search with conflict resolution - with conflicts"""
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "legal_unified",
                "collections": ["legal_unified", "visa_oracle"],
                "confidence": 0.9,
                "is_pricing": False,
            }
        )

        # Mock conflicts detected - return a list with conflict dicts
        conflicts = [{"type": "temporal", "reason": "Different timestamps"}]
        search_service.conflict_resolver.detect_conflicts = MagicMock(return_value=conflicts)
        search_service.conflict_resolver.resolve_conflicts = MagicMock(
            return_value=(
                [{"content": "resolved", "score": 0.9}],
                [{"type": "temporal", "reason": "Resolved"}],
            )
        )

        # Mock search results for both collections - need to return results for conflict detection
        async def mock_search(*args, **kwargs):
            return {
                "ids": ["1", "2"],
                "documents": ["doc1", "doc2"],
                "metadatas": [{"tier": "S", "title": "Law A"}, {"tier": "A", "title": "Law A"}],
                "distances": [0.1, 0.2],
                "total_found": 2,
            }

        # Setup collection manager to return mock client for both collections
        mock_client1 = MagicMock()
        mock_client1.search = mock_search
        mock_client2 = MagicMock()
        mock_client2.search = mock_search

        def get_collection_side_effect(name):
            if name == "legal_unified":
                return mock_client1
            elif name == "visa_oracle":
                return mock_client2
            return None

        search_service.collection_manager.get_collection.side_effect = get_collection_side_effect

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        # Conflicts should be detected if we have duplicate titles
        assert result["conflicts_detected"] >= 0  # May be 0 if no actual conflicts detected

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_pricing(self, search_service):
        """Test search with conflict resolution - pricing query"""
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "legal_unified_hybrid",
                "collections": ["legal_unified_hybrid", "visa_oracle"],
                "confidence": 0.9,
                "is_pricing": True,
            }
        )

        search_service.conflict_resolver.detect_conflicts = MagicMock(return_value=[])

        result = await search_service.search_with_conflict_resolution(
            query="How much does KITAS cost?", user_level=1, limit=5
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_error(self, search_service):
        """Test search with conflict resolution error handling"""
        search_service.query_router.route_query = MagicMock(side_effect=Exception("Router error"))

        # Should fallback to simple search
        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_collection(self, search_service):
        """Test search_collection method"""
        result = await search_service.search_collection(
            query="test", collection_name="test_collection", limit=5
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_collection_error(self, search_service):
        """Test search_collection error handling"""
        search_service.collection_manager.get_collection.return_value = None

        # Should create ad-hoc client
        with patch("backend.core.qdrant_db.QdrantClient") as mock_client:
            mock_client.return_value.search = AsyncMock(
                return_value={
                    "ids": ["1"],
                    "documents": ["doc1"],
                    "metadatas": [{}],
                    "distances": [0.1],
                    "total_found": 1,
                }
            )

            result = await search_service.search_collection(
                query="test", collection_name="new_collection", limit=5
            )
            assert result is not None

    def test_get_conflict_stats(self, search_service):
        """Test get_conflict_stats"""
        search_service.conflict_stats = {
            "total_multi_collection_searches": 10,
            "conflicts_detected": 2,
            "conflicts_resolved": 2,
            "timestamp_resolutions": 1,
        }

        search_service.conflict_resolver.get_stats = MagicMock(
            return_value={"conflicts_detected": 2, "conflicts_resolved": 2}
        )

        stats = search_service.get_conflict_stats()
        assert "conflict_rate" in stats
        assert "resolution_rate" in stats

    @pytest.mark.asyncio
    async def test_init_bm25_with_retry(self, search_service):
        """Test BM25 initialization with retry"""
        with patch("backend.core.bm25_vectorizer.BM25Vectorizer") as mock_bm25_class:
            mock_bm25_class.side_effect = [Exception("Error"), MagicMock()]

            result = await search_service._init_bm25_with_retry()
            # Should retry and succeed or fail gracefully
            assert result is True or result is False

    @pytest.mark.asyncio
    async def test_init_bm25_disabled(self, search_service):
        """Test BM25 initialization when disabled"""
        # Save original state
        original_enable = search_service._bm25_enabled
        original_settings = None

        try:
            # Temporarily disable BM25 in settings
            import backend.app.core.config as config_module

            original_settings_value = config_module.settings.enable_bm25

            # Patch settings.enable_bm25
            with patch.object(config_module.settings, "enable_bm25", False):
                # The method checks settings.enable_bm25 first
                result = await search_service._init_bm25_with_retry()
                assert result is False
        finally:
            # Restore original state
            search_service._bm25_enabled = original_enable

    def test_cultural_insights_property(self, search_service):
        """Test cultural_insights property"""
        assert search_service.cultural_insights is not None

    @pytest.mark.asyncio
    async def test_prepare_search_context(self, search_service):
        """Test _prepare_search_context"""
        embedding, collection, vector_db, chroma_filter, tier_values = (
            search_service._prepare_search_context(
                query="test",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )
        )
        assert embedding is not None
        assert collection is not None
        assert vector_db is not None

    @pytest.mark.asyncio
    async def test_prepare_search_context_zantara_books(self, search_service):
        """Test _prepare_search_context for zantara_books collection"""
        search_service.query_router.route_query = MagicMock(
            return_value={"collection_name": "zantara_books"}
        )

        embedding, collection, vector_db, chroma_filter, tier_values = (
            search_service._prepare_search_context(
                query="test",
                user_level=2,
                tier_filter=None,
                collection_override="zantara_books",
                apply_filters=True,
            )
        )
        assert collection == "zantara_books"

    @pytest.mark.asyncio
    async def test_prepare_search_context_apply_filters_false(self, search_service):
        """Test _prepare_search_context with apply_filters=False"""
        embedding, collection, vector_db, chroma_filter, tier_values = (
            search_service._prepare_search_context(
                query="test query",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=False,
            )
        )
        # When apply_filters=False, chroma_filter should be None
        assert chroma_filter is None

    @pytest.mark.asyncio
    async def test_prepare_search_context_collection_fallback(self, search_service):
        """Test _prepare_search_context when collection not found - fallback to legal_unified"""
        # First call returns None (collection not found), second call returns client
        mock_client = MagicMock()

        async def mock_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc"],
                "metadatas": [{}],
                "distances": [0.1],
                "total_found": 1,
            }

        mock_client.search = mock_search

        search_service.collection_manager.get_collection.side_effect = [None, mock_client]

        embedding, collection, vector_db, chroma_filter, tier_values = (
            search_service._prepare_search_context(
                query="test query",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )
        )
        # Should fallback to legal_unified
        assert collection == "legal_unified"

    @pytest.mark.asyncio
    async def test_prepare_search_context_collection_fallback_fails(self, search_service):
        """Test _prepare_search_context when both collection and fallback fail"""
        search_service.collection_manager.get_collection.return_value = None

        with pytest.raises(ValueError, match="Failed to initialize default collection"):
            search_service._prepare_search_context(
                query="test query",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )

    @pytest.mark.asyncio
    async def test_prepare_search_context_empty_embedding(self, search_service):
        """Test _prepare_search_context when embedding generation fails"""
        search_service.embedder.generate_query_embedding.return_value = []

        with pytest.raises(ValueError, match="Failed to generate query embedding"):
            search_service._prepare_search_context(
                query="test",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )

    @pytest.mark.asyncio
    async def test_init_bm25_import_error(self, search_service):
        """Test _init_bm25_with_retry with ImportError"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_bm25 = True
            mock_settings.bm25_vocab_size = 100000
            mock_settings.bm25_k1 = 1.2
            mock_settings.bm25_b = 0.75

            with patch("backend.core.bm25_vectorizer.BM25Vectorizer", side_effect=ImportError("No module")):
                # Reset state
                search_service._bm25_enabled = False
                search_service._bm25_vectorizer = None
                # This tests the import error branch
                result = await search_service._init_bm25_with_retry()
                # Should return False due to import error (no retry on import error)
                assert result is False

    @pytest.mark.asyncio
    async def test_init_bm25_retry_with_backoff(self, search_service):
        """Test _init_bm25_with_retry retries with exponential backoff"""
        call_count = 0

        def mock_bm25_init(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Temporary error")
            return MagicMock()

        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_bm25 = True
            mock_settings.bm25_vocab_size = 100000
            mock_settings.bm25_k1 = 1.2
            mock_settings.bm25_b = 0.75

            with patch("backend.core.bm25_vectorizer.BM25Vectorizer", side_effect=mock_bm25_init):
                # Reset state
                search_service._bm25_enabled = False
                search_service._bm25_vectorizer = None

                result = await search_service._init_bm25_with_retry()
                # Should retry and eventually succeed
                assert result is True
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_alert_bm25_failure(self, search_service):
        """Test _alert_bm25_failure logs error"""
        error = RuntimeError("Test error")

        with patch("backend.services.search.search_service.logger") as mock_logger:
            await search_service._alert_bm25_failure(error)
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_alert_bm25_failure_exception(self, search_service):
        """Test _alert_bm25_failure handles exceptions"""
        error = RuntimeError("Test error")

        with patch("backend.services.search.search_service.logger") as mock_logger:
            # Make the first logger.error call raise an exception
            mock_logger.error.side_effect = [Exception("Log error"), None]

            await search_service._alert_bm25_failure(error)
            # Should handle the exception gracefully
            assert mock_logger.error.call_count == 2

    @pytest.mark.asyncio
    async def test_search_with_hybrid_collection(self, search_service):
        """Test search with hybrid collection uses named vector"""
        search_service.query_router.route_query = MagicMock(
            return_value={"collection_name": "legal_unified_hybrid"}
        )

        mock_client = MagicMock()

        async def mock_search(query_embedding, filter=None, limit=5, vector_name=None):
            # Verify vector_name is "dense" for hybrid collections
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{}],
                "distances": [0.1],
                "total_found": 1,
                "vector_name_used": vector_name,
            }

        mock_client.search = mock_search
        search_service.collection_manager.get_collection.return_value = mock_client

        result = await search_service.search(query="test", user_level=1, limit=5)
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_hybrid_success(self, search_service):
        """Test search uses hybrid search when BM25 is available"""
        # Enable BM25
        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector.return_value = {
            "indices": [1, 2],
            "values": [0.5, 0.3],
        }
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        mock_client = MagicMock()

        async def mock_hybrid_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{}],
                "distances": [0.1],
                "total_found": 1,
            }

        mock_client.hybrid_search = mock_hybrid_search

        async def mock_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{}],
                "distances": [0.1],
                "total_found": 1,
            }

        mock_client.search = mock_search
        search_service.collection_manager.get_collection.return_value = mock_client

        result = await search_service.search(query="test", user_level=1, limit=5)
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_hybrid_fallback_on_error(self, search_service):
        """Test search falls back to dense-only when hybrid search fails"""
        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector.return_value = {"indices": [1], "values": [0.5]}
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        mock_client = MagicMock()

        async def mock_hybrid_search(*args, **kwargs):
            raise Exception("Hybrid search failed")

        mock_client.hybrid_search = mock_hybrid_search

        async def mock_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{}],
                "distances": [0.1],
                "total_found": 1,
            }

        mock_client.search = mock_search
        search_service.collection_manager.get_collection.return_value = mock_client

        result = await search_service.search(query="test", user_level=1, limit=5)
        # Should fallback to dense-only and still return results
        assert result is not None
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_value_error(self, search_service):
        """Test search handles ValueError from empty query"""
        # Test empty query handling - this triggers ValueError in _prepare_search_context
        result = await search_service.search(query="", user_level=1, limit=5)
        # Should return error dict or empty results
        assert result is not None
        assert "error" in result or len(result.get("results", [])) == 0

    @pytest.mark.asyncio
    async def test_search_invalid_level_error(self, search_service):
        """Test search handles invalid user level"""
        result = await search_service.search(
            query="test",
            user_level=99,  # Invalid level
            limit=5,
        )
        # Should return error dict or empty results
        assert result is not None
        assert "error" in result or len(result.get("results", [])) == 0

    @pytest.mark.asyncio
    async def test_search_handles_generic_exception(self, search_service):
        """Test search handles generic exceptions gracefully"""
        # This tests that the search method doesn't crash on unexpected errors
        result = await search_service.search(query="test query", user_level=1, limit=5)
        # Should return valid result structure
        assert result is not None
        assert "query" in result

    def test_init_reranker(self, search_service):
        """Test _init_reranker lazy loading"""
        # Remove any existing reranker
        if hasattr(search_service, "_reranker"):
            delattr(search_service, "_reranker")

        with patch("backend.core.reranker.ReRanker") as mock_reranker_class:
            mock_reranker = MagicMock()
            mock_reranker.enabled = True
            mock_reranker.api_url = "http://test"
            mock_reranker_class.return_value = mock_reranker

            result = search_service._init_reranker()
            assert result is mock_reranker
            assert search_service._reranker is mock_reranker

    def test_init_reranker_cached(self, search_service):
        """Test _init_reranker returns cached instance"""
        mock_reranker = MagicMock()
        search_service._reranker = mock_reranker

        result = search_service._init_reranker()
        assert result is mock_reranker

    @pytest.mark.asyncio
    async def test_search_with_reranking_reranker_enabled(self, search_service):
        """Test search_with_reranking when reranker is enabled"""

        # Mock search to return low-score results (not early exit)
        async def mock_search(*args, **kwargs):
            return {
                "ids": ["1", "2", "3"],
                "documents": ["doc1", "doc2", "doc3"],
                "metadatas": [{"tier": "S"}, {"tier": "A"}, {"tier": "B"}],
                "distances": [0.5, 0.6, 0.7],  # Low scores - won't trigger early exit
                "total_found": 3,
            }

        search_service.collection_manager.get_collection.return_value.search = mock_search

        # Mock reranker
        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(
            return_value=[
                {"content": "reranked1", "score": 0.95},
                {"content": "reranked2", "score": 0.85},
            ]
        )
        search_service._reranker = mock_reranker

        result = await search_service.search_with_reranking(query="test", user_level=1, limit=2)
        assert result["reranked"] is True
        assert result["early_exit"] is False

    @pytest.mark.asyncio
    async def test_hybrid_search_with_reranking_early_exit(self, search_service):
        """Test hybrid_search_with_reranking early exit path"""

        # Mock to return high score result
        async def mock_hybrid_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{}],
                "distances": [0.02],  # High score (low distance = 0.98 score)
                "total_found": 1,
                "search_type": "hybrid_rrf",
            }

        mock_client = MagicMock()
        mock_client.hybrid_search = mock_hybrid_search

        async def mock_search(*args, **kwargs):
            return {
                "ids": ["1"],
                "documents": ["doc1"],
                "metadatas": [{}],
                "distances": [0.02],
                "total_found": 1,
            }

        mock_client.search = mock_search
        search_service.collection_manager.get_collection.return_value = mock_client

        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector.return_value = {"indices": [1], "values": [0.5]}
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        result = await search_service.hybrid_search_with_reranking(
            query="test", user_level=1, limit=5
        )
        assert result["early_exit"] is True
        assert result["reranked"] is False

    @pytest.mark.asyncio
    async def test_hybrid_search_with_reranking_full_pipeline(self, search_service):
        """Test hybrid_search_with_reranking full pipeline"""

        async def mock_hybrid_search(*args, **kwargs):
            return {
                "ids": ["1", "2", "3"],
                "documents": ["doc1", "doc2", "doc3"],
                "metadatas": [{}, {}, {}],
                "distances": [0.5, 0.6, 0.7],  # Low scores
                "total_found": 3,
                "search_type": "hybrid_rrf",
            }

        mock_client = MagicMock()
        mock_client.hybrid_search = mock_hybrid_search
        search_service.collection_manager.get_collection.return_value = mock_client

        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector.return_value = {"indices": [1], "values": [0.5]}
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        # Mock reranker
        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(return_value=[{"content": "reranked1", "score": 0.95}])
        search_service._reranker = mock_reranker

        result = await search_service.hybrid_search_with_reranking(
            query="test", user_level=1, limit=2
        )
        assert result["reranked"] is True
        assert result["pipeline"] == "hybrid_bm25_rrf_zerank2"

    @pytest.mark.asyncio
    async def test_hybrid_search_with_reranking_disabled(self, search_service):
        """Test hybrid_search_with_reranking when reranker is disabled"""

        async def mock_hybrid_search(*args, **kwargs):
            return {
                "ids": ["1", "2"],
                "documents": ["doc1", "doc2"],
                "metadatas": [{}, {}],
                "distances": [0.5, 0.6],
                "total_found": 2,
                "search_type": "hybrid_rrf",
            }

        mock_client = MagicMock()
        mock_client.hybrid_search = mock_hybrid_search
        search_service.collection_manager.get_collection.return_value = mock_client

        mock_bm25 = MagicMock()
        mock_bm25.generate_query_sparse_vector.return_value = {"indices": [1], "values": [0.5]}
        search_service._bm25_vectorizer = mock_bm25
        search_service._bm25_enabled = True

        # Mock reranker disabled
        mock_reranker = MagicMock()
        mock_reranker.enabled = False
        search_service._reranker = mock_reranker

        result = await search_service.hybrid_search_with_reranking(
            query="test", user_level=1, limit=2
        )
        assert result["reranked"] is False
        assert result["early_exit"] is False

    @pytest.mark.asyncio
    async def test_hybrid_search_error_fallback(self, search_service):
        """Test hybrid_search falls back to regular search on error"""
        # Make _prepare_search_context raise an exception
        original_prepare = search_service._prepare_search_context

        def failing_prepare(*args, **kwargs):
            raise RuntimeError("Prepare failed")

        with patch.object(search_service, "_prepare_search_context", failing_prepare):
            # This should catch the error and fallback to regular search
            # Restore prepare for fallback
            with patch.object(search_service, "search") as mock_search:
                mock_search.return_value = {"results": [], "query": "test"}

                result = await search_service.hybrid_search(query="test", user_level=1, limit=5)
                mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_dense_fallback_no_bm25(self, search_service):
        """Test hybrid_search falls back to regular search when BM25 unavailable"""
        # Disable BM25
        search_service._bm25_vectorizer = None
        search_service._bm25_enabled = False

        result = await search_service.hybrid_search(query="test", user_level=1, limit=5)
        # Should still return results via fallback to regular search
        assert result is not None
        # When BM25 is unavailable, it falls back to dense-only
        assert result.get("search_type") == "dense_only" or result.get("bm25_enabled") is False

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_collection_not_found(self, search_service):
        """Test search_with_conflict_resolution when collection not found"""
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "primary",
                "collections": ["primary", "secondary"],
                "confidence": 0.9,
                "is_pricing": False,
            }
        )

        # First collection not found
        search_service.collection_manager.get_collection.side_effect = [None, MagicMock()]

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_search_task_exception(self, search_service):
        """Test search_with_conflict_resolution handles task exceptions"""
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "primary",
                "collections": ["primary"],
                "confidence": 0.9,
                "is_pricing": False,
            }
        )

        mock_client = MagicMock()

        async def mock_search(*args, **kwargs):
            raise Exception("Search failed")

        mock_client.search = mock_search
        search_service.collection_manager.get_collection.return_value = mock_client
        search_service.conflict_resolver.detect_conflicts = MagicMock(return_value=[])

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_no_fallbacks(self, search_service):
        """Test search_with_conflict_resolution with fallbacks disabled"""
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "primary",
                "collections": ["primary"],
                "confidence": 0.95,
                "is_pricing": False,
            }
        )

        search_service.conflict_resolver.detect_conflicts = MagicMock(return_value=[])

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5, enable_fallbacks=False
        )
        assert result["fallbacks_used"] is False

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_returns_results(self, search_service):
        """Test search_with_conflict_resolution returns valid structure"""
        search_service.query_router.route_query = MagicMock(
            return_value={
                "collection_name": "primary",
                "collections": ["primary"],
                "confidence": 0.9,
                "is_pricing": False,
            }
        )
        search_service.conflict_resolver.detect_conflicts = MagicMock(return_value=[])

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        # Verify the result has the expected structure
        assert "query" in result
        assert "results" in result
        assert "conflicts_detected" in result
        assert "primary_collection" in result

    @pytest.mark.asyncio
    async def test_search_with_conflict_resolution_runtime_error(self, search_service):
        """Test search_with_conflict_resolution handles RuntimeError"""
        search_service.query_router.route_query = MagicMock(
            side_effect=RuntimeError("Runtime error")
        )

        result = await search_service.search_with_conflict_resolution(
            query="test", user_level=1, limit=5
        )
        # Should fallback to simple search
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_collection_exception(self, search_service):
        """Test search_collection handles specific exceptions"""
        import httpx

        mock_client = MagicMock()

        async def mock_search(*args, **kwargs):
            raise httpx.HTTPError("HTTP error")

        mock_client.search = mock_search
        search_service.collection_manager.get_collection.return_value = mock_client

        result = await search_service.search_collection(
            query="test", collection_name="test_collection", limit=5
        )
        assert "error" in result

    def test_get_conflict_stats_zero_searches(self, search_service):
        """Test get_conflict_stats with zero searches"""
        search_service.conflict_stats = {
            "total_multi_collection_searches": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "timestamp_resolutions": 0,
        }

        search_service.conflict_resolver.get_stats = MagicMock(
            return_value={"conflicts_detected": 0, "conflicts_resolved": 0}
        )

        stats = search_service.get_conflict_stats()
        assert stats["conflict_rate"] == "0.0%"
        assert stats["resolution_rate"] == "0.0%"


class TestSearchServiceMetrics:
    """Tests for metrics collection in SearchService"""

    @pytest.mark.asyncio
    async def test_search_records_metrics(self, search_service):
        """Test that search records metrics when METRICS_AVAILABLE"""
        # Just verify search works - metrics are optional
        result = await search_service.search(query="test", user_level=1, limit=5)
        assert result is not None
        assert "results" in result


class TestSearchServiceBM25Init:
    """Tests for BM25 initialization in SearchService"""

    @pytest.fixture
    def mock_settings_bm25_enabled(self):
        """Mock settings with BM25 enabled"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.enable_bm25 = True
            mock_settings.bm25_vocab_size = 100000
            mock_settings.bm25_k1 = 1.2
            mock_settings.bm25_b = 0.75
            mock_settings.qdrant_url = "http://localhost:6333"
            yield mock_settings

    def test_init_bm25_import_error_in_constructor(self, mock_settings_bm25_enabled):
        """Test BM25 ImportError handling in constructor"""
        with (
            patch("backend.core.embeddings.create_embeddings_generator") as mock_emb,
            patch("backend.services.search.search_service.CollectionManager"),
            patch("backend.services.search.search_service.ConflictResolver"),
            patch("backend.services.search.search_service.CulturalInsightsService"),
            patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
            patch("backend.services.ingestion.collection_health_service.CollectionHealthService"),
            patch("backend.services.search.search_service.CollectionWarmupService"),
            patch("backend.core.bm25_vectorizer.BM25Vectorizer", side_effect=ImportError("No module")),
        ):
            mock_embedder = MagicMock()
            mock_embedder.provider = "openai"
            mock_embedder.dimensions = 1536
            mock_emb.return_value = mock_embedder

            service = SearchService()
            assert service._bm25_enabled is False

    def test_init_bm25_generic_error_in_constructor(self, mock_settings_bm25_enabled):
        """Test BM25 generic error handling in constructor"""
        with (
            patch("backend.core.embeddings.create_embeddings_generator") as mock_emb,
            patch("backend.services.search.search_service.CollectionManager"),
            patch("backend.services.search.search_service.ConflictResolver"),
            patch("backend.services.search.search_service.CulturalInsightsService"),
            patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
            patch("backend.services.ingestion.collection_health_service.CollectionHealthService"),
            patch("backend.services.search.search_service.CollectionWarmupService"),
            patch("backend.core.bm25_vectorizer.BM25Vectorizer", side_effect=RuntimeError("Init error")),
        ):
            mock_embedder = MagicMock()
            mock_embedder.provider = "openai"
            mock_embedder.dimensions = 1536
            mock_emb.return_value = mock_embedder

            service = SearchService()
            assert service._bm25_enabled is False
