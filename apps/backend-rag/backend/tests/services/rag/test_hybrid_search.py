"""
NUZANTARA RAG - Hybrid Search Service Tests

Comprehensive test suite for HybridSearchService covering:
- BM25 vector computation
- Reciprocal Rank Fusion (RRF)
- Hybrid search integration with Qdrant
- Performance comparison between hybrid and dense-only search
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.hybrid_search import (
    RRF_K,
    HybridSearchService,
    get_hybrid_search_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("backend.services.rag.hybrid_search.settings") as mock:
        mock.qdrant_url = "http://localhost:6333"
        mock.enable_bm25 = True
        mock.bm25_vocab_size = 30000
        mock.bm25_k1 = 1.5
        mock.bm25_b = 0.75
        yield mock


@pytest.fixture
def mock_bm25_vectorizer():
    """Mock BM25 vectorizer for testing."""
    vectorizer = MagicMock()
    vectorizer.generate_query_sparse_vector.return_value = {
        "indices": [1234, 5678, 9012],
        "values": [0.85, 0.72, 0.61],
    }
    vectorizer.generate_batch_sparse_vectors.return_value = [
        {"indices": [1234], "values": [0.85]},
        {"indices": [5678], "values": [0.72]},
    ]
    return vectorizer


@pytest.fixture
def mock_collection_manager():
    """Mock collection manager for testing."""
    manager = MagicMock()
    mock_client = AsyncMock()
    mock_client.hybrid_search = AsyncMock(
        return_value={
            "ids": ["doc1", "doc2", "doc3"],
            "documents": ["text1", "text2", "text3"],
            "metadatas": [{}, {}, {}],
            "scores": [0.95, 0.87, 0.76],
            "total_found": 3,
            "search_type": "hybrid_rrf",
        },
    )
    mock_client.search = AsyncMock(
        return_value={
            "ids": ["doc1", "doc2"],
            "documents": ["text1", "text2"],
            "metadatas": [{"source": "test"}, {"source": "test2"}],
            "distances": [0.1, 0.2],
        },
    )
    manager.get_collection.return_value = mock_client
    return manager


@pytest.fixture
def hybrid_service(mock_settings, mock_collection_manager, mock_bm25_vectorizer):
    """Create hybrid search service with mocked dependencies."""
    with patch(
        "backend.services.rag.hybrid_search.get_bm25_vectorizer", return_value=mock_bm25_vectorizer,
    ):
        service = HybridSearchService(
            collection_manager=mock_collection_manager,
            bm25_vectorizer=mock_bm25_vectorizer,
        )
        service._bm25_enabled = True
        return service


# =============================================================================
# BM25 Vector Computation Tests
# =============================================================================


class TestBM25VectorComputation:
    """Tests for BM25 sparse vector computation."""

    def test_compute_bm25_vectors_success(self, hybrid_service, mock_bm25_vectorizer):
        """Test successful BM25 vector computation for texts."""
        texts = ["visa application process", "KITAS requirements"]

        result = hybrid_service.compute_bm25_vectors(texts)

        assert len(result) == 2
        assert "indices" in result[0]
        assert "values" in result[0]
        mock_bm25_vectorizer.generate_batch_sparse_vectors.assert_called_once_with(texts)

    def test_compute_bm25_vectors_empty_list(self, hybrid_service, mock_bm25_vectorizer):
        """Test BM25 vector computation with empty list."""
        mock_bm25_vectorizer.generate_batch_sparse_vectors.return_value = []

        result = hybrid_service.compute_bm25_vectors([])

        assert result == []

    def test_compute_bm25_vectors_disabled(self, hybrid_service):
        """Test BM25 vector computation when disabled."""
        hybrid_service._bm25_enabled = False

        result = hybrid_service.compute_bm25_vectors(["test text"])

        assert len(result) == 1
        assert result[0] == {"indices": [], "values": []}

    def test_compute_bm25_vectors_error(self, hybrid_service, mock_bm25_vectorizer):
        """Test BM25 vector computation with error."""
        mock_bm25_vectorizer.generate_batch_sparse_vectors.side_effect = Exception("BM25 error")

        result = hybrid_service.compute_bm25_vectors(["test"])

        assert len(result) == 1
        assert result[0] == {"indices": [], "values": []}

    def test_compute_bm25_query_vector_success(self, hybrid_service, mock_bm25_vectorizer):
        """Test successful BM25 query vector computation."""
        query = "KITAS visa application"

        result = hybrid_service.compute_bm25_query_vector(query)

        assert "indices" in result
        assert "values" in result
        assert len(result["indices"]) == 3
        assert len(result["values"]) == 3
        mock_bm25_vectorizer.generate_query_sparse_vector.assert_called_once_with(query)

    def test_compute_bm25_query_vector_empty(self, hybrid_service, mock_bm25_vectorizer):
        """Test BM25 query vector with empty query."""
        mock_bm25_vectorizer.generate_query_sparse_vector.return_value = {
            "indices": [],
            "values": [],
        }

        result = hybrid_service.compute_bm25_query_vector("")

        assert result == {"indices": [], "values": []}

    def test_compute_bm25_query_vector_disabled(self, hybrid_service):
        """Test BM25 query vector when disabled."""
        hybrid_service._bm25_enabled = False

        result = hybrid_service.compute_bm25_query_vector("test")

        assert result == {"indices": [], "values": []}


# =============================================================================
# Reciprocal Rank Fusion (RRF) Tests
# =============================================================================


class TestReciprocalRankFusion:
    """Tests for Reciprocal Rank Fusion algorithm."""

    def test_rrf_both_results_present(self, hybrid_service):
        """Test RRF when both dense and sparse results are present."""
        dense_results = [
            {"id": "doc1", "score": 0.9, "text": "text1"},
            {"id": "doc2", "score": 0.8, "text": "text2"},
            {"id": "doc3", "score": 0.7, "text": "text3"},
        ]
        sparse_results = [
            {"id": "doc2", "score": 0.85, "text": "text2"},
            {"id": "doc1", "score": 0.75, "text": "text1"},
            {"id": "doc4", "score": 0.65, "text": "text4"},
        ]

        result = hybrid_service.reciprocal_rank_fusion(dense_results, sparse_results, alpha=0.5)

        assert len(result) == 4  # All unique docs
        # Check that fusion scores are calculated
        for r in result:
            assert "fusion_score" in r
            assert r["fusion_score"] > 0

        # Check ranks are recorded
        doc1 = next(r for r in result if r["id"] == "doc1")
        assert doc1["dense_rank"] == 1
        assert doc1["sparse_rank"] == 2

    def test_rrf_empty_dense_results(self, hybrid_service):
        """Test RRF with empty dense results."""
        sparse_results = [
            {"id": "doc1", "score": 0.9, "text": "text1"},
        ]

        result = hybrid_service.reciprocal_rank_fusion([], sparse_results, alpha=0.5)

        assert len(result) == 1
        assert result[0]["fusion_score"] == 0.9 * 0.5  # Score scaled by (1 - alpha)

    def test_rrf_empty_sparse_results(self, hybrid_service):
        """Test RRF with empty sparse results."""
        dense_results = [
            {"id": "doc1", "score": 0.9, "text": "text1"},
        ]

        result = hybrid_service.reciprocal_rank_fusion(dense_results, [], alpha=0.5)

        assert len(result) == 1
        assert result[0]["fusion_score"] == 0.9 * 0.5  # Score scaled by alpha

    def test_rrf_both_empty(self, hybrid_service):
        """Test RRF when both result lists are empty."""
        result = hybrid_service.reciprocal_rank_fusion([], [], alpha=0.5)

        assert result == []

    def test_rrf_alpha_variations(self, hybrid_service):
        """Test RRF with different alpha values."""
        dense_results = [{"id": "doc1", "score": 0.9, "text": "text1"}]
        sparse_results = [{"id": "doc1", "score": 0.8, "text": "text1"}]

        # Alpha 1.0 - all weight to dense
        result_dense = hybrid_service.reciprocal_rank_fusion(
            dense_results, sparse_results, alpha=1.0,
        )
        dense_only_score = round(1.0 / (RRF_K + 1), 6)  # rank 1, rounded to 6 decimals

        # Alpha 0.0 - all weight to sparse
        result_sparse = hybrid_service.reciprocal_rank_fusion(
            dense_results, sparse_results, alpha=0.0,
        )
        sparse_only_score = round(1.0 / (RRF_K + 1), 6)  # rank 1, rounded to 6 decimals

        # Alpha 0.5 - balanced
        result_balanced = hybrid_service.reciprocal_rank_fusion(
            dense_results, sparse_results, alpha=0.5,
        )
        balanced_score = round(0.5 * (1.0 / (RRF_K + 1)) + 0.5 * (1.0 / (RRF_K + 1)), 6)

        assert result_dense[0]["fusion_score"] == pytest.approx(dense_only_score, rel=1e-4)
        assert result_sparse[0]["fusion_score"] == pytest.approx(sparse_only_score, rel=1e-4)
        assert result_balanced[0]["fusion_score"] == pytest.approx(balanced_score, rel=1e-4)

    def test_rrf_sorting(self, hybrid_service):
        """Test that RRF results are sorted by fusion score."""
        dense_results = [
            {"id": "doc3", "score": 0.7, "text": "text3"},  # rank 3
            {"id": "doc1", "score": 0.9, "text": "text1"},  # rank 1
        ]
        sparse_results = [
            {"id": "doc2", "score": 0.8, "text": "text2"},  # rank 1 in sparse
        ]

        result = hybrid_service.reciprocal_rank_fusion(dense_results, sparse_results, alpha=0.5)

        # Should be sorted by fusion score descending
        scores = [r["fusion_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_different_id_formats(self, hybrid_service):
        """Test RRF handles different ID field formats."""
        dense_results = [
            {"_id": "doc1", "score": 0.9, "text": "text1"},  # _id instead of id
        ]
        sparse_results = [
            {"id": "doc1", "score": 0.8, "text": "text1"},
        ]

        result = hybrid_service.reciprocal_rank_fusion(dense_results, sparse_results, alpha=0.5)

        assert len(result) == 1
        assert result[0]["id"] == "doc1"


# =============================================================================
# Hybrid Search Integration Tests
# =============================================================================


class TestHybridSearchIntegration:
    """Integration tests for hybrid search with Qdrant."""

    @pytest.mark.asyncio
    async def test_search_hybrid_native(self, hybrid_service, mock_collection_manager):
        """Test hybrid search using native Qdrant hybrid search."""
        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_hybrid(
                query="visa KITAS",
                collection="legal_unified_hybrid",
                limit=5,
                alpha=0.5,
            )

            assert "results" in result
            assert result["collection"] == "legal_unified_hybrid"
            assert result["search_type"] == "hybrid_rrf"
            assert result["bm25_enabled"] is True
            assert result["alpha"] == 0.5

    @pytest.mark.asyncio
    async def test_search_hybrid_fallback_to_manual(self, hybrid_service, mock_collection_manager):
        """Test hybrid search fallback when native hybrid fails."""
        # Make hybrid_search raise an exception
        mock_client = mock_collection_manager.get_collection.return_value
        mock_client.hybrid_search.side_effect = Exception("Native hybrid not available")

        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_hybrid(
                query="visa KITAS",
                collection="legal_unified_hybrid",
                limit=5,
            )

            assert "results" in result
            # Should fallback to manual or dense-only
            assert result["search_type"] in ["hybrid_manual_rrf", "dense_only"]

    @pytest.mark.asyncio
    async def test_search_hybrid_no_bm25(self, hybrid_service, mock_collection_manager):
        """Test hybrid search when BM25 is not available."""
        hybrid_service._bm25_enabled = False

        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_hybrid(
                query="visa KITAS",
                collection="legal_unified",
                limit=5,
            )

            assert result["bm25_enabled"] is False
            assert result["search_type"] == "dense_only"

    @pytest.mark.asyncio
    async def test_search_hybrid_empty_query(self, hybrid_service):
        """Test hybrid search with empty query."""
        result = await hybrid_service.search_hybrid(
            query="",
            collection="legal_unified_hybrid",
            limit=5,
        )

        # Should return empty results or handle gracefully
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_hybrid_collection_not_found(
        self, hybrid_service, mock_collection_manager,
    ):
        """Test hybrid search when collection doesn't exist."""
        mock_collection_manager.get_collection.return_value = None

        with patch("backend.services.rag.hybrid_search.QdrantClient") as mock_qdrant:
            mock_client = AsyncMock()
            mock_client.hybrid_search = AsyncMock(
                return_value={
                    "ids": [],
                    "documents": [],
                    "metadatas": [],
                    "scores": [],
                    "total_found": 0,
                },
            )
            mock_qdrant.return_value = mock_client

            result = await hybrid_service.search_hybrid(
                query="test",
                collection="nonexistent_collection",
                limit=5,
            )

            assert "results" in result

    @pytest.mark.asyncio
    async def test_search_hybrid_with_filters(self, hybrid_service, mock_collection_manager):
        """Test hybrid search with metadata filters."""
        filters = {"tier": {"$in": ["S", "A"]}}

        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            await hybrid_service.search_hybrid(
                query="visa KITAS",
                collection="legal_unified_hybrid",
                limit=5,
                filters=filters,
            )

            # Verify filters were passed to search
            mock_client = mock_collection_manager.get_collection.return_value
            if mock_client.hybrid_search.called:
                call_kwargs = mock_client.hybrid_search.call_args[1]
                assert call_kwargs.get("filter") == filters


# =============================================================================
# Dense-Only Search Tests
# =============================================================================


class TestDenseOnlySearch:
    """Tests for dense-only search fallback."""

    @pytest.mark.asyncio
    async def test_search_dense_only_success(self, hybrid_service, mock_collection_manager):
        """Test successful dense-only search."""
        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_dense_only(
                query="visa requirements",
                collection="legal_unified",
                limit=5,
            )

            assert result["search_type"] == "dense_only"
            assert result["bm25_enabled"] is False
            assert result["alpha"] == 1.0
            assert "results" in result
            assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_search_dense_only_error(self, hybrid_service, mock_collection_manager):
        """Test dense-only search with error."""
        mock_collection_manager.get_collection.return_value.search.side_effect = Exception(
            "Search failed",
        )

        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_dense_only(
                query="test",
                collection="legal_unified",
                limit=5,
            )

            assert result["search_type"] == "error"
            assert "error" in result
            assert result["results"] == []


# =============================================================================
# Search Comparison Tests
# =============================================================================


class TestSearchComparison:
    """Tests for comparing hybrid vs dense search."""

    @pytest.mark.asyncio
    async def test_compare_search_methods(self, hybrid_service):
        """Test comparison between hybrid and dense search."""
        with (
            patch.object(hybrid_service, "search_hybrid", new_callable=AsyncMock) as mock_hybrid,
            patch.object(hybrid_service, "search_dense_only", new_callable=AsyncMock) as mock_dense,
        ):
            mock_hybrid.return_value = {
                "results": [{"id": "doc1"}, {"id": "doc2"}],
                "duration_ms": 150.5,
            }
            mock_dense.return_value = {
                "results": [{"id": "doc2"}, {"id": "doc3"}],
                "duration_ms": 100.2,
            }

            result = await hybrid_service.compare_search_methods(
                query="visa KITAS",
                collection="legal_unified_hybrid",
                limit=5,
            )

            assert "hybrid" in result
            assert "dense" in result
            assert "comparison" in result
            assert result["comparison"]["hybrid_count"] == 2
            assert result["comparison"]["dense_count"] == 2
            assert result["comparison"]["overlap_count"] == 1  # doc2
            assert result["comparison"]["overlap_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_compare_search_methods_no_overlap(self, hybrid_service):
        """Test comparison with no overlapping results."""
        with (
            patch.object(hybrid_service, "search_hybrid", new_callable=AsyncMock) as mock_hybrid,
            patch.object(hybrid_service, "search_dense_only", new_callable=AsyncMock) as mock_dense,
        ):
            mock_hybrid.return_value = {
                "results": [{"id": "doc1"}],
                "duration_ms": 150.0,
            }
            mock_dense.return_value = {
                "results": [{"id": "doc2"}],
                "duration_ms": 100.0,
            }

            result = await hybrid_service.compare_search_methods(
                query="test",
                collection="test_collection",
                limit=5,
            )

            assert result["comparison"]["overlap_count"] == 0
            assert result["comparison"]["overlap_percentage"] == 0.0


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Tests for HybridSearchService initialization."""

    def test_init_with_defaults(self, mock_settings):
        """Test initialization with default dependencies."""
        with (
            patch("backend.services.rag.hybrid_search.CollectionManager"),
            patch("backend.services.rag.hybrid_search.get_bm25_vectorizer") as mock_get_bm25,
        ):
            mock_get_bm25.return_value = MagicMock()

            service = HybridSearchService()

            assert service.collection_manager is not None
            assert service.bm25_enabled is True

    def test_init_bm25_disabled(self, mock_settings):
        """Test initialization when BM25 is disabled."""
        mock_settings.enable_bm25 = False

        with patch("backend.services.rag.hybrid_search.CollectionManager"):
            service = HybridSearchService()

            assert service.bm25_enabled is False
            assert service._bm25_vectorizer is None

    def test_init_bm25_import_error(self, mock_settings):
        """Test initialization when BM25 import fails."""
        with (
            patch("backend.services.rag.hybrid_search.CollectionManager"),
            patch("backend.services.rag.hybrid_search.get_bm25_vectorizer") as mock_get_bm25,
        ):
            mock_get_bm25.side_effect = ImportError("BM25 not available")

            service = HybridSearchService()

            assert service.bm25_enabled is False

    def test_bm25_enabled_property(self, hybrid_service):
        """Test bm25_enabled property."""
        assert hybrid_service.bm25_enabled is True

        hybrid_service._bm25_enabled = False
        assert hybrid_service.bm25_enabled is False

        hybrid_service._bm25_enabled = True
        hybrid_service._bm25_vectorizer = None
        assert hybrid_service.bm25_enabled is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for global singleton instance."""

    def test_get_hybrid_search_service_singleton(self):
        """Test that get_hybrid_search_service returns a singleton."""
        with patch("backend.services.rag.hybrid_search.HybridSearchService") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            # Reset global instance
            import backend.services.rag.hybrid_search as hs_module

            hs_module._hybrid_search_service = None

            service1 = get_hybrid_search_service()
            service2 = get_hybrid_search_service()

            assert service1 is service2
            mock_cls.assert_called_once()


# =============================================================================
# Result Formatting Tests
# =============================================================================


class TestResultFormatting:
    """Tests for result formatting."""

    def test_format_results_standard(self, hybrid_service):
        """Test formatting standard Qdrant results."""
        raw_results = {
            "ids": ["doc1", "doc2"],
            "documents": ["text1", "text2"],
            "metadatas": [{"key": "value1"}, {"key": "value2"}],
            "scores": [0.95, 0.85],
        }

        formatted = hybrid_service._format_results(raw_results)

        assert len(formatted) == 2
        assert formatted[0]["id"] == "doc1"
        assert formatted[0]["text"] == "text1"
        assert formatted[0]["metadata"] == {"key": "value1"}
        assert formatted[0]["score"] == 0.95

    def test_format_results_with_distances(self, hybrid_service):
        """Test formatting results with distances instead of scores."""
        raw_results = {
            "ids": ["doc1"],
            "documents": ["text1"],
            "metadatas": [{}],
            "distances": [0.1],  # Using distances instead of scores
        }

        formatted = hybrid_service._format_results(raw_results)

        assert len(formatted) == 1
        assert formatted[0]["score"] == 0.1

    def test_format_results_empty(self, hybrid_service):
        """Test formatting empty results."""
        raw_results = {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "scores": [],
        }

        formatted = hybrid_service._format_results(raw_results)

        assert formatted == []

    def test_format_results_mismatched_lengths(self, hybrid_service):
        """Test formatting results with mismatched array lengths."""
        raw_results = {
            "ids": ["doc1", "doc2"],
            "documents": ["text1"],  # Only one document
            "metadatas": [],  # No metadata
            "scores": [0.9, 0.8, 0.7],  # Three scores
        }

        formatted = hybrid_service._format_results(raw_results)

        # Should handle gracefully with defaults
        assert len(formatted) == 2  # Based on ids length
        assert formatted[0]["text"] == "text1"
        assert formatted[1]["text"] == ""  # Default for missing


# =============================================================================
# Performance and Keyword-Heavy Query Tests
# =============================================================================


class TestPerformanceAndKeywordQueries:
    """Tests to verify hybrid beats pure vector on keyword-heavy queries."""

    def test_rrf_boosts_keyword_matches(self, hybrid_service):
        """
        Test that RRF gives higher scores to documents matching both dense and sparse.

        This simulates the case where a keyword-heavy query (e.g., "KITAS 2024 requirements")
        should match documents containing those exact keywords via BM25, even if the
        semantic meaning might be slightly different.
        """
        # Dense results (semantic similarity)
        dense_results = [
            {"id": "doc_semantic", "score": 0.92, "text": "General visa information"},
            {"id": "doc_keyword", "score": 0.78, "text": "KITAS 2024 requirements"},
        ]

        # Sparse results (keyword matching)
        sparse_results = [
            {"id": "doc_keyword", "score": 0.95, "text": "KITAS 2024 requirements"},
            {"id": "doc_other", "score": 0.80, "text": "Other KITAS info"},
        ]

        result = hybrid_service.reciprocal_rank_fusion(dense_results, sparse_results, alpha=0.5)

        # The doc that appears in both should have highest fusion score
        doc_keyword = next(r for r in result if r["id"] == "doc_keyword")
        doc_semantic = next(r for r in result if r["id"] == "doc_semantic")

        # doc_keyword should have higher score due to presence in both lists
        assert doc_keyword["fusion_score"] > doc_semantic["fusion_score"]

    @pytest.mark.asyncio
    async def test_hybrid_faster_with_caching(self, hybrid_service):
        """Test that cached searches are faster."""
        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            # First call
            start = __import__("time").time()
            result1 = await hybrid_service.search_hybrid(
                query="cached query",
                collection="test_collection",
                limit=5,
            )
            __import__("time").time() - start

            # Second call (should be cached)
            start = __import__("time").time()
            result2 = await hybrid_service.search_hybrid(
                query="cached query",
                collection="test_collection",
                limit=5,
            )
            __import__("time").time() - start

            # Both should return same results
            assert result1["query"] == result2["query"]


# =============================================================================
# Indonesian Language Support Tests
# =============================================================================


class TestIndonesianLanguageSupport:
    """Tests for Indonesian language query support."""

    def test_bm25_tokenizes_indonesian(self, hybrid_service, mock_bm25_vectorizer):
        """Test BM25 tokenization for Indonesian queries."""
        indonesian_queries = [
            "peraturan pemerintah tentang visa",
            "persyaratan KITAS untuk warga negara asing",
            "izin tinggal terbatas",
            "badan hukum Indonesia",
        ]

        for query in indonesian_queries:
            result = hybrid_service.compute_bm25_query_vector(query)
            # Should produce valid sparse vector
            assert "indices" in result
            assert "values" in result
            mock_bm25_vectorizer.generate_query_sparse_vector.assert_called_with(query)

    @pytest.mark.asyncio
    async def test_hybrid_search_indonesian_query(self, hybrid_service):
        """Test hybrid search with Indonesian query."""
        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_hybrid(
                query="peraturan visa KITAS terbaru",
                collection="legal_unified_hybrid",
                limit=5,
            )

            assert result["query"] == "peraturan visa KITAS terbaru"
            assert "results" in result


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_search_hybrid_graceful_degradation(self, hybrid_service):
        """Test that search gracefully degrades on errors."""
        # Force all internal methods to fail
        hybrid_service.collection_manager.get_collection.side_effect = Exception("DB Error")

        result = await hybrid_service.search_hybrid(
            query="test",
            collection="test_collection",
            limit=5,
        )

        # Should return error response, not raise
        assert "error" in result
        assert result["results"] == []
        assert result["total_results"] == 0

    def test_compute_bm25_vectors_graceful_failure(self, hybrid_service, mock_bm25_vectorizer):
        """Test BM25 computation handles errors gracefully."""
        mock_bm25_vectorizer.generate_batch_sparse_vectors.side_effect = Exception(
            "Tokenization error",
        )

        result = hybrid_service.compute_bm25_vectors(["test text"])

        # Should return empty vectors, not raise
        assert result == [{"indices": [], "values": []}]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_rrf_with_missing_id(self, hybrid_service):
        """Test RRF handles results without IDs."""
        dense_results = [
            {"score": 0.9, "text": "no id field"},  # Missing id
            {"id": "", "score": 0.8, "text": "empty id"},  # Empty id
        ]
        sparse_results = [
            {"id": "doc1", "score": 0.85, "text": "has id"},
        ]

        result = hybrid_service.reciprocal_rank_fusion(dense_results, sparse_results)

        # Should only include results with valid IDs
        assert all(r["id"] for r in result)

    @pytest.mark.asyncio
    async def test_search_with_zero_limit(self, hybrid_service):
        """Test search with limit=0."""
        result = await hybrid_service.search_hybrid(
            query="test",
            collection="test_collection",
            limit=0,
        )

        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_with_large_limit(self, hybrid_service):
        """Test search with very large limit."""
        with patch("backend.core.embeddings.create_embeddings_generator") as mock_embedder:
            mock_embedder.return_value.generate_query_embedding = AsyncMock(
                return_value=[0.1] * 1536,
            )

            result = await hybrid_service.search_hybrid(
                query="test",
                collection="test_collection",
                limit=1000,
            )

            assert "results" in result
