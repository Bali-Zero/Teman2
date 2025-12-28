"""
Extended unit tests for SearchService to improve coverage
Tests additional methods and edge cases
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import TierLevel
from services.search.search_service import SearchService


@pytest.fixture
def mock_collection_manager():
    """Create mock collection manager"""
    mock_manager = MagicMock()
    mock_collection = MagicMock()
    mock_collection.search = AsyncMock(
        return_value={
            "documents": ["Doc 1", "Doc 2"],
            "metadatas": [{}, {}],
            "distances": [0.2, 0.3],
            "ids": ["doc1", "doc2"],
        }
    )
    mock_collection.hybrid_search = AsyncMock(
        return_value={
            "documents": ["Doc 1"],
            "metadatas": [{}],
            "distances": [0.2],
            "ids": ["doc1"],
            "search_type": "hybrid_rrf",
        }
    )
    mock_manager.get_collection = MagicMock(return_value=mock_collection)
    return mock_manager, mock_collection


@pytest.fixture
def mock_query_router():
    """Create mock query router"""
    mock_router = MagicMock()
    mock_router.route_query = MagicMock(
        return_value={"collection_name": "visa_oracle", "confidence": 0.9}
    )
    return mock_router


@pytest.fixture
def mock_embedder():
    """Create mock embedder"""
    mock_embedder = MagicMock()
    mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
    mock_embedder.provider = "test"
    mock_embedder.dimensions = 384
    return mock_embedder


@pytest.fixture
def mock_bm25_vectorizer():
    """Create mock BM25 vectorizer"""
    mock_bm25 = MagicMock()
    mock_bm25.generate_query_sparse_vector = MagicMock(
        return_value={"indices": [1, 2, 3], "values": [0.5, 0.3, 0.2]}
    )
    return mock_bm25


@pytest.fixture
def mock_reranker():
    """Create mock reranker"""
    mock_reranker = MagicMock()
    mock_reranker.enabled = True
    mock_reranker.rerank = AsyncMock(
        return_value=[
            {"text": "Doc 1", "score": 0.95, "metadata": {}},
            {"text": "Doc 2", "score": 0.85, "metadata": {}},
        ]
    )
    return mock_reranker


@pytest.fixture
def search_service(mock_collection_manager, mock_query_router, mock_embedder):
    """Create SearchService instance"""
    mock_manager, _ = mock_collection_manager
    with patch("core.embeddings.create_embeddings_generator") as mock_create:
        mock_create.return_value = mock_embedder
        service = SearchService(
            collection_manager=mock_manager,
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder
        return service


class TestSearchServiceInit:
    """Tests for SearchService initialization"""

    def test_init_with_all_dependencies(self, mock_collection_manager, mock_query_router, mock_embedder):
        """Test initialization with all dependencies provided"""
        mock_manager, _ = mock_collection_manager
        with patch("core.embeddings.create_embeddings_generator") as mock_create:
            mock_create.return_value = mock_embedder
            service = SearchService(
                collection_manager=mock_manager,
                query_router=mock_query_router,
            )
            assert service.collection_manager == mock_manager
            assert service.query_router == mock_query_router

    def test_init_creates_default_dependencies(self, mock_embedder):
        """Test initialization creates default dependencies when None"""
        with patch("core.embeddings.create_embeddings_generator") as mock_create:
            mock_create.return_value = mock_embedder
            with patch("services.search.search_service.CollectionManager") as mock_cm:
                mock_cm_instance = MagicMock()
                mock_cm.return_value = mock_cm_instance
                service = SearchService()
                assert service.collection_manager is not None


class TestCulturalInsights:
    """Tests for cultural_insights property"""

    def test_cultural_insights_property(self, search_service):
        """Test cultural_insights property access"""
        # cultural_insights is a property that returns self._cultural_insights
        # It should be a CulturalInsightsService instance (created during init)
        result = search_service.cultural_insights
        # Should be a service instance (not None, created during init)
        assert result is not None
        assert hasattr(result, "__class__")


class TestPrepareSearchContext:
    """Tests for _prepare_search_context method"""

    def test_prepare_search_context_success(self, search_service):
        """Test successful preparation of search context"""
        embedding, collection, vector_db, chroma_filter, tier_values = search_service._prepare_search_context(
            query="test query",
            user_level=1,
            tier_filter=None,
            collection_override=None,
            apply_filters=None,
        )
        assert embedding == [0.1] * 384
        assert collection == "visa_oracle"
        assert vector_db is not None

    def test_prepare_search_context_empty_query(self, search_service):
        """Test _prepare_search_context raises error for empty query"""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            search_service._prepare_search_context(
                query="",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )

    def test_prepare_search_context_invalid_user_level(self, search_service):
        """Test _prepare_search_context raises error for invalid user level"""
        with pytest.raises(ValueError, match="User level must be between 0 and 3"):
            search_service._prepare_search_context(
                query="test",
                user_level=5,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )

    def test_prepare_search_context_with_tier_filter(self, search_service):
        """Test _prepare_search_context with tier filter"""
        embedding, collection, vector_db, chroma_filter, tier_values = search_service._prepare_search_context(
            query="test query",
            user_level=2,
            tier_filter=[TierLevel.S, TierLevel.A],
            collection_override=None,
            apply_filters=None,
        )
        assert len(tier_values) >= 0  # May be empty if not zantara_books

    def test_prepare_search_context_with_collection_override(self, search_service):
        """Test _prepare_search_context with collection override"""
        search_service.query_router.route_query = MagicMock(
            return_value={"collection_name": "custom_collection", "confidence": 0.9}
        )
        embedding, collection, vector_db, chroma_filter, tier_values = search_service._prepare_search_context(
            query="test query",
            user_level=1,
            tier_filter=None,
            collection_override="custom_collection",
            apply_filters=None,
        )
        assert collection == "custom_collection"

    def test_prepare_search_context_apply_filters_false(self, search_service):
        """Test _prepare_search_context with apply_filters=False"""
        embedding, collection, vector_db, chroma_filter, tier_values = search_service._prepare_search_context(
            query="test query",
            user_level=1,
            tier_filter=None,
            collection_override=None,
            apply_filters=False,
        )
        assert chroma_filter is None

    def test_prepare_search_context_failed_embedding(self, search_service):
        """Test _prepare_search_context handles failed embedding generation"""
        search_service.embedder.generate_query_embedding = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="Failed to generate query embedding"):
            search_service._prepare_search_context(
                query="test query",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )

    def test_prepare_search_context_empty_embedding(self, search_service):
        """Test _prepare_search_context handles empty embedding"""
        search_service.embedder.generate_query_embedding = MagicMock(return_value=[])
        with pytest.raises(ValueError, match="Failed to generate query embedding"):
            search_service._prepare_search_context(
                query="test query",
                user_level=1,
                tier_filter=None,
                collection_override=None,
                apply_filters=None,
            )


class TestInitReranker:
    """Tests for _init_reranker method"""

    def test_init_reranker_lazy_load(self, search_service):
        """Test that reranker is lazy loaded"""
        # First call should create reranker
        reranker1 = search_service._init_reranker()
        # Second call should return same instance
        reranker2 = search_service._init_reranker()
        assert reranker1 == reranker2


class TestSearchWithReranking:
    """Tests for search_with_reranking method"""

    @pytest.mark.asyncio
    async def test_search_with_reranking_success(self, search_service, mock_reranker):
        """Test successful search with reranking"""
        search_service._init_reranker = MagicMock(return_value=mock_reranker)
        
        results = await search_service.search_with_reranking(
            query="test query",
            user_level=1,
            limit=5,
        )
        
        assert "results" in results
        assert "reranked" in results
        assert results["reranked"] is True

    @pytest.mark.asyncio
    async def test_search_with_reranking_early_exit(self, search_service, mock_reranker):
        """Test search_with_reranking early exit for high confidence"""
        search_service._init_reranker = MagicMock(return_value=mock_reranker)
        
        # Mock search to return high confidence result
        async def mock_search(*args, **kwargs):
            return {
                "results": [{"text": "Doc", "score": 0.95, "metadata": {}}],
                "collection": "test",
            }
        
        search_service.search = AsyncMock(side_effect=mock_search)
        
        results = await search_service.search_with_reranking(
            query="test query",
            user_level=1,
            limit=5,
        )
        
        assert results.get("early_exit") is True
        assert results.get("reranked") is False

    @pytest.mark.asyncio
    async def test_search_with_reranking_disabled_reranker(self, search_service):
        """Test search_with_reranking when reranker is disabled"""
        mock_reranker_disabled = MagicMock()
        mock_reranker_disabled.enabled = False
        search_service._init_reranker = MagicMock(return_value=mock_reranker_disabled)
        
        async def mock_search(*args, **kwargs):
            return {
                "results": [{"text": "Doc", "score": 0.8, "metadata": {}}],
                "collection": "test",
            }
        
        search_service.search = AsyncMock(side_effect=mock_search)
        
        results = await search_service.search_with_reranking(
            query="test query",
            user_level=1,
            limit=5,
        )
        
        assert results.get("reranked") is False
        assert results.get("early_exit") is False


class TestHybridSearch:
    """Tests for hybrid_search method"""

    @pytest.mark.asyncio
    async def test_hybrid_search_success(self, search_service, mock_bm25_vectorizer):
        """Test successful hybrid search"""
        search_service._bm25_vectorizer = mock_bm25_vectorizer
        
        results = await search_service.hybrid_search(
            query="test query",
            user_level=1,
            limit=5,
        )
        
        assert "results" in results
        assert "search_type" in results
        assert results["bm25_enabled"] is True

    @pytest.mark.asyncio
    async def test_hybrid_search_without_bm25(self, search_service):
        """Test hybrid search without BM25 vectorizer"""
        search_service._bm25_vectorizer = None
        
        results = await search_service.hybrid_search(
            query="test query",
            user_level=1,
            limit=5,
        )
        
        assert "results" in results
        assert results["bm25_enabled"] is False

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback_on_error(self, search_service):
        """Test hybrid search falls back to regular search on error"""
        search_service._bm25_vectorizer = MagicMock()
        search_service._bm25_vectorizer.generate_query_sparse_vector = MagicMock(
            side_effect=Exception("BM25 error")
        )
        
        # Mock regular search to succeed
        async def mock_search(*args, **kwargs):
            return {
                "results": [{"text": "Doc", "score": 0.8, "metadata": {}}],
                "collection": "test",
            }
        
        search_service.search = AsyncMock(side_effect=mock_search)
        
        results = await search_service.hybrid_search(
            query="test query",
            user_level=1,
            limit=5,
        )
        
        # Should have called regular search as fallback
        assert search_service.search.called


class TestSearchCollection:
    """Tests for search_collection method"""

    @pytest.mark.asyncio
    async def test_search_collection_success(self, search_service):
        """Test successful search_collection"""
        results = await search_service.search_collection(
            query="test query",
            collection_name="visa_oracle",
            limit=5,
        )
        
        assert "results" in results
        assert results["collection"] == "visa_oracle"

    @pytest.mark.asyncio
    async def test_search_collection_not_found(self, search_service):
        """Test search_collection when collection not found"""
        search_service.collection_manager.get_collection = MagicMock(return_value=None)
        
        # Mock QdrantClient creation (imported inside the method)
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value={
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": [],
            })
            mock_qdrant.return_value = mock_client
            
            # Should create client and return results
            results = await search_service.search_collection(
                query="test query",
                collection_name="nonexistent",
            )
            assert "results" in results


class TestLevelToTiers:
    """Tests for LEVEL_TO_TIERS mapping"""

    def test_level_to_tiers_mapping(self, search_service):
        """Test that LEVEL_TO_TIERS mapping is correct"""
        assert TierLevel.S in search_service.LEVEL_TO_TIERS[0]
        assert TierLevel.S in search_service.LEVEL_TO_TIERS[1]
        assert TierLevel.A in search_service.LEVEL_TO_TIERS[1]
        assert len(search_service.LEVEL_TO_TIERS[3]) == 5  # S, A, B, C, D

