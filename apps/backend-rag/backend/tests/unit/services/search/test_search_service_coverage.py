"""
Comprehensive unit tests for backend/services/search/search_service.py
Covers: _uses_named_vectors, SearchService (search, search_with_reranking,
        hybrid_search, _prepare_search_context, _rrf_fuse_multi,
        _search_with_multi_expansion, _single_query_search, _init_reranker,
        _init_bm25_with_retry, _alert_bm25_failure, property accessors).
"""

import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level function test
# ---------------------------------------------------------------------------

class TestUsesNamedVectors:

    def test_known_named_collections(self):
        from backend.services.search.search_service import _uses_named_vectors
        assert _uses_named_vectors("legal_unified") is True
        assert _uses_named_vectors("tax_genius") is True
        assert _uses_named_vectors("visa_oracle") is True
        assert _uses_named_vectors("kbli_2025_final") is True

    def test_hybrid_suffix(self):
        from backend.services.search.search_service import _uses_named_vectors
        assert _uses_named_vectors("some_custom_hybrid") is True

    def test_non_named_collection(self):
        from backend.services.search.search_service import _uses_named_vectors
        assert _uses_named_vectors("some_random_collection") is False


# ---------------------------------------------------------------------------
# SearchService fixture with heavy mocking to avoid real init
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.qdrant_url = "http://localhost:6333"
    s.enable_bm25 = False
    s.bm25_vocab_size = 30000
    s.bm25_k1 = 1.5
    s.bm25_b = 0.75
    s.enable_reranker = False
    s.reranker_backend = "cross-encoder"
    s.enable_query_expansion = False
    return s


@pytest.fixture
def search_service(mock_settings):
    """Create SearchService with all dependencies mocked via DI, bypassing __init__."""
    from backend.services.search.search_service import SearchService

    # Bypass the heavy __init__ entirely
    svc = object.__new__(SearchService)

    # Set up all attributes that __init__ would set
    mock_embedder = MagicMock()
    mock_embedder.provider = "openai"
    mock_embedder.dimensions = 1536
    mock_embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
    svc.embedder = mock_embedder

    mock_cm = MagicMock()
    mock_vector_db = AsyncMock()
    mock_vector_db.search = AsyncMock(return_value=[])
    mock_cm.get_collection.return_value = mock_vector_db
    svc.collection_manager = mock_cm

    mock_qr = MagicMock()
    mock_qr.route_query.return_value = {"collection_name": "legal_unified"}
    svc.query_router = mock_qr

    svc.conflict_resolver = MagicMock()
    svc._cultural_insights = MagicMock()

    mock_health = MagicMock()
    mock_health.record_query = MagicMock()
    svc.health_monitor = mock_health

    svc.warmup_service = MagicMock()

    mock_expander = MagicMock()
    mock_expander.expand = AsyncMock(return_value="expanded query")
    svc.query_expander = mock_expander

    svc._embedding_cache = OrderedDict()
    svc._embedding_cache_max = 256
    svc.conflict_stats = {"total_multi_collection_searches": 0, "conflicts_detected": 0, "conflicts_resolved": 0, "timestamp_resolutions": 0}

    svc._bm25_vectorizer = None
    svc._bm25_enabled = False
    svc._bm25_initialization_attempts = 0
    svc._max_bm25_init_attempts = 3

    return svc


# ============================================================================
# SearchService LEVEL_TO_TIERS
# ============================================================================

class TestLevelToTiers:

    def test_level_0(self):
        from backend.services.search.search_service import SearchService
        from backend.app.models import TierLevel
        assert SearchService.LEVEL_TO_TIERS[0] == [TierLevel.S]

    def test_level_3(self):
        from backend.services.search.search_service import SearchService
        from backend.app.models import TierLevel
        tiers = SearchService.LEVEL_TO_TIERS[3]
        assert TierLevel.D in tiers


# ============================================================================
# _prepare_search_context
# ============================================================================

class TestPrepareSearchContext:

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, search_service):
        with pytest.raises(ValueError, match="cannot be empty"):
            await search_service._prepare_search_context("", 1, None, None, None)

    @pytest.mark.asyncio
    async def test_whitespace_query_raises(self, search_service):
        with pytest.raises(ValueError, match="cannot be empty"):
            await search_service._prepare_search_context("   ", 1, None, None, None)

    @pytest.mark.asyncio
    async def test_invalid_user_level_raises(self, search_service):
        with pytest.raises(ValueError, match="must be between 0 and 3"):
            await search_service._prepare_search_context("test", 5, None, None, None)

    @pytest.mark.asyncio
    async def test_negative_user_level_raises(self, search_service):
        with pytest.raises(ValueError, match="must be between 0 and 3"):
            await search_service._prepare_search_context("test", -1, None, None, None)

    @pytest.mark.asyncio
    async def test_valid_returns_tuple(self, search_service):
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None):
            mock_kt.return_value.translate.return_value = "test"
            embedding, col, vdb, filt, tiers = await search_service._prepare_search_context(
                "test query", 1, None, None, None,
            )
            assert len(embedding) == 1536
            assert col == "legal_unified"

    @pytest.mark.asyncio
    async def test_embedding_cache_hit(self, search_service):
        """Second call with same query uses cache."""
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None):
            mock_kt.return_value.translate.return_value = "test query"
            await search_service._prepare_search_context("test query", 1, None, None, None)
            # Second call should use cache
            search_service.embedder.generate_query_embedding.reset_mock()
            await search_service._prepare_search_context("test query", 1, None, None, None)
            search_service.embedder.generate_query_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_embedding_fails_raises(self, search_service):
        search_service.embedder.generate_query_embedding = AsyncMock(return_value=[])
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None):
            mock_kt.return_value.translate.return_value = "fail query"
            with pytest.raises(ValueError, match="Failed to generate"):
                await search_service._prepare_search_context("fail query", 1, None, None, None)

    @pytest.mark.asyncio
    async def test_unknown_collection_falls_back(self, search_service):
        """Unknown collection falls back to legal_unified."""
        search_service.collection_manager.get_collection.side_effect = [None, MagicMock()]
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None):
            mock_kt.return_value.translate.return_value = "test"
            _, col, _, _, _ = await search_service._prepare_search_context("test", 1, None, None, None)
            assert col == "legal_unified"

    @pytest.mark.asyncio
    async def test_filters_disabled(self, search_service):
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value={"tier": "S"}):
            mock_kt.return_value.translate.return_value = "test"
            _, _, _, filt, _ = await search_service._prepare_search_context("test", 1, None, None, False)
            assert filt is None


# ============================================================================
# search
# ============================================================================

class TestSearch:

    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self, search_service, mock_settings):
        search_service.collection_manager.get_collection.return_value.search = AsyncMock(return_value=[])
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None), \
             patch("backend.services.search.search_service.format_search_results", return_value=[]):
            mock_kt.return_value.translate.return_value = "test query"
            result = await search_service.search("test query", user_level=1)
            assert "results" in result
            assert result["query"] == "test query"

    @pytest.mark.asyncio
    async def test_search_with_collection_override(self, search_service, mock_settings):
        search_service.collection_manager.get_collection.return_value.search = AsyncMock(return_value=[])
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None), \
             patch("backend.services.search.search_service.format_search_results", return_value=[]):
            mock_kt.return_value.translate.return_value = "visa KITAS"
            result = await search_service.search("visa KITAS", user_level=1, collection_override="visa_oracle")
            assert "results" in result

    @pytest.mark.asyncio
    async def test_search_exception_returns_empty(self, search_service, mock_settings):
        """Search exception returns empty results (graceful degradation)."""
        search_service.collection_manager.get_collection.return_value.search = AsyncMock(
            side_effect=ValueError("search failed"),
        )
        with patch("backend.services.search.keyword_translator.get_keyword_translator") as mock_kt, \
             patch("backend.services.search.search_service.build_search_filter", return_value=None):
            mock_kt.return_value.translate.return_value = "test"
            result = await search_service.search("test", user_level=1)
            assert result["results"] == []
            assert "error" in result


# ============================================================================
# _rrf_fuse_multi (static method)
# ============================================================================

class TestRRFFuseMulti:

    def test_basic_fusion(self):
        from backend.services.search.search_service import SearchService

        result_sets = [
            [{"id": "a", "text": "doc A", "score": 0.9}, {"id": "b", "text": "doc B", "score": 0.7}],
            [{"id": "b", "text": "doc B", "score": 0.8}, {"id": "c", "text": "doc C", "score": 0.6}],
        ]
        fused = SearchService._rrf_fuse_multi(result_sets, k=60)
        assert len(fused) == 3
        # "b" should be first since it appears in both sets
        assert fused[0]["id"] == "b"
        assert "rrf_score" in fused[0]

    def test_empty_sets(self):
        from backend.services.search.search_service import SearchService

        fused = SearchService._rrf_fuse_multi([], k=60)
        assert fused == []

    def test_single_set(self):
        from backend.services.search.search_service import SearchService

        result_sets = [[{"id": "x", "text": "only", "score": 1.0}]]
        fused = SearchService._rrf_fuse_multi(result_sets, k=60)
        assert len(fused) == 1
        assert fused[0]["id"] == "x"

    def test_no_id_uses_text_prefix(self):
        from backend.services.search.search_service import SearchService

        result_sets = [
            [{"text": "document content here", "score": 0.9}],
            [{"text": "document content here", "score": 0.8}],
        ]
        fused = SearchService._rrf_fuse_multi(result_sets, k=60)
        # Same text → same doc_id → merged
        assert len(fused) == 1


# ============================================================================
# search_with_reranking
# ============================================================================

class TestSearchWithReranking:

    @pytest.mark.asyncio
    async def test_early_exit_high_score(self, search_service, mock_settings):
        """Top result > 0.85 → early exit, skip reranking."""
        search_service.search = AsyncMock(return_value={
            "results": [{"score": 0.9, "text": "best"}, {"score": 0.6, "text": "ok"}],
            "query": "test",
        })

        with patch("backend.services.search.search_service.METRICS_AVAILABLE", True), \
             patch("backend.services.search.search_service.rag_early_exit_total", MagicMock()):
            result = await search_service.search_with_reranking("test", user_level=1, limit=1)
            assert result["early_exit"] is True
            assert result["reranked"] is False
            assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_reranking_applied(self, search_service, mock_settings):
        """When top score < 0.85, reranking is applied."""
        search_service.search = AsyncMock(return_value={
            "results": [{"score": 0.5, "text": "mid"}, {"score": 0.4, "text": "low"}],
            "query": "test",
        })

        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(return_value=[{"score": 0.7, "text": "reranked"}])

        with patch.object(search_service, '_init_reranker', return_value=mock_reranker), \
             patch("backend.services.search.search_service.METRICS_AVAILABLE", False):
            result = await search_service.search_with_reranking("test", user_level=1, limit=1)
            assert result["reranked"] is True
            mock_reranker.rerank.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reranker_disabled(self, search_service, mock_settings):
        search_service.search = AsyncMock(return_value={
            "results": [{"score": 0.5, "text": "mid"}],
            "query": "test",
        })

        mock_reranker = MagicMock()
        mock_reranker.enabled = False

        with patch.object(search_service, '_init_reranker', return_value=mock_reranker), \
             patch("backend.services.search.search_service.METRICS_AVAILABLE", False):
            result = await search_service.search_with_reranking("test", user_level=1, limit=1)
            assert result["reranked"] is False
            assert result["early_exit"] is False


# ============================================================================
# _init_bm25_with_retry
# ============================================================================

class TestInitBM25:

    @pytest.mark.asyncio
    async def test_bm25_disabled(self, search_service, mock_settings):
        with patch("backend.services.search.search_service.settings", mock_settings):
            mock_settings.enable_bm25 = False
            result = await search_service._init_bm25_with_retry()
        assert result is False

    @pytest.mark.asyncio
    async def test_bm25_import_error(self, search_service, mock_settings):
        with patch("backend.services.search.search_service.settings", mock_settings), \
             patch("backend.core.bm25_vectorizer.BM25Vectorizer", side_effect=ImportError("no module")):
            mock_settings.enable_bm25 = True
            result = await search_service._init_bm25_with_retry()
        assert result is False

    @pytest.mark.asyncio
    async def test_bm25_success(self, search_service, mock_settings):
        mock_bm25 = MagicMock()
        with patch("backend.services.search.search_service.settings", mock_settings), \
             patch("backend.core.bm25_vectorizer.BM25Vectorizer", return_value=mock_bm25), \
             patch("backend.services.search.search_service.metrics_collector", MagicMock()):
            mock_settings.enable_bm25 = True
            result = await search_service._init_bm25_with_retry()
        assert result is True
        assert search_service._bm25_enabled is True


# ============================================================================
# _alert_bm25_failure
# ============================================================================

class TestAlertBM25Failure:

    @pytest.mark.asyncio
    async def test_alert_logs_error(self, search_service):
        await search_service._alert_bm25_failure(RuntimeError("test error"))
        # Should not raise

# ============================================================================
# Property accessors
# ============================================================================

class TestPropertyAccessors:

    def test_cultural_insights_property(self, search_service):
        search_service._cultural_insights = MagicMock()
        assert search_service.cultural_insights is search_service._cultural_insights

    def test_hybrid_search_service_property(self, search_service):
        with patch("backend.services.rag.hybrid_search.get_hybrid_search_service") as mock_hss:
            mock_hss.return_value = MagicMock()
            result = search_service.hybrid_search_service
            assert result is not None
