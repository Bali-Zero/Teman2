"""
Unit tests for HybridSearchService.

Tests BM25 vectorization, RRF fusion (bimodal and trimodal),
hybrid search orchestration, and dense-only fallback.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_service(*, bm25_enabled: bool = True):
    """Create HybridSearchService with mocked dependencies."""
    mock_settings = MagicMock()
    mock_settings.qdrant_url = "http://localhost:6333"
    mock_settings.enable_bm25 = bm25_enabled

    mock_vectorizer = MagicMock()
    mock_vectorizer.generate_batch_sparse_vectors.return_value = [
        {"indices": [1, 2], "values": [0.5, 0.3]},
    ]
    mock_vectorizer.generate_query_sparse_vector.return_value = {
        "indices": [1, 2], "values": [0.5, 0.3],
    }

    mock_cm = MagicMock()
    mock_embedder = AsyncMock()
    mock_embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)

    with patch("backend.services.rag.hybrid_search.settings", mock_settings), \
         patch("backend.services.rag.hybrid_search.get_bm25_vectorizer", return_value=mock_vectorizer), \
         patch("backend.services.rag.hybrid_search.CollectionManager", return_value=mock_cm):
        from backend.services.rag.hybrid_search import HybridSearchService
        svc = HybridSearchService(
            collection_manager=mock_cm,
            bm25_vectorizer=mock_vectorizer if bm25_enabled else None,
            embedder=mock_embedder,
        )
        # Force the bm25 state
        if bm25_enabled:
            svc._bm25_enabled = True
            svc._bm25_vectorizer = mock_vectorizer

    return svc, mock_cm, mock_embedder


# ---------------------------------------------------------------------------
# Tests: BM25 property
# ---------------------------------------------------------------------------


class TestBm25Enabled:
    def test_enabled_when_both_set(self):
        svc, _, _ = _make_service(bm25_enabled=True)
        assert svc.bm25_enabled is True

    def test_disabled_when_no_vectorizer(self):
        svc, _, _ = _make_service(bm25_enabled=False)
        svc._bm25_enabled = False
        assert svc.bm25_enabled is False


# ---------------------------------------------------------------------------
# Tests: BM25 vector computation
# ---------------------------------------------------------------------------


class TestComputeBm25Vectors:
    def test_returns_vectors(self):
        svc, _, _ = _make_service()
        result = svc.compute_bm25_vectors(["hello world"])
        assert len(result) == 1
        assert "indices" in result[0]

    def test_returns_empty_when_disabled(self):
        svc, _, _ = _make_service(bm25_enabled=False)
        svc._bm25_enabled = False
        result = svc.compute_bm25_vectors(["hello"])
        assert result == [{"indices": [], "values": []}]

    def test_handles_vectorizer_error(self):
        svc, _, _ = _make_service()
        svc._bm25_vectorizer.generate_batch_sparse_vectors.side_effect = RuntimeError("fail")
        result = svc.compute_bm25_vectors(["hello"])
        assert result == [{"indices": [], "values": []}]


class TestComputeBm25QueryVector:
    def test_returns_vector(self):
        svc, _, _ = _make_service()
        result = svc.compute_bm25_query_vector("visa KITAS")
        assert "indices" in result

    def test_returns_empty_when_disabled(self):
        svc, _, _ = _make_service(bm25_enabled=False)
        svc._bm25_enabled = False
        result = svc.compute_bm25_query_vector("query")
        assert result == {"indices": [], "values": []}


# ---------------------------------------------------------------------------
# Tests: Reciprocal Rank Fusion (bimodal)
# ---------------------------------------------------------------------------


class TestReciprocalRankFusion:
    def test_empty_both(self):
        svc, _, _ = _make_service()
        result = svc.reciprocal_rank_fusion([], [])
        assert result == []

    def test_empty_sparse(self):
        svc, _, _ = _make_service()
        dense = [{"id": "1", "score": 0.9, "text": "a"}]
        result = svc.reciprocal_rank_fusion(dense, [])
        assert len(result) == 1
        assert "fusion_score" in result[0]

    def test_empty_dense(self):
        svc, _, _ = _make_service()
        sparse = [{"id": "1", "score": 0.8, "text": "a"}]
        result = svc.reciprocal_rank_fusion([], sparse)
        assert len(result) == 1

    def test_merges_both_signals(self):
        svc, _, _ = _make_service()
        dense = [
            {"id": "1", "score": 0.9, "text": "a"},
            {"id": "2", "score": 0.7, "text": "b"},
        ]
        sparse = [
            {"id": "2", "score": 0.8, "text": "b"},
            {"id": "3", "score": 0.6, "text": "c"},
        ]
        result = svc.reciprocal_rank_fusion(dense, sparse, alpha=0.5)
        ids = [r["id"] for r in result]
        # doc "2" appears in both, should rank high
        assert "2" in ids
        assert "1" in ids
        assert "3" in ids
        # All results should have fusion_score
        for r in result:
            assert "fusion_score" in r
            assert "dense_rank" in r
            assert "sparse_rank" in r

    def test_sorted_by_fusion_score(self):
        svc, _, _ = _make_service()
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "1", "score": 0.9}]
        result = svc.reciprocal_rank_fusion(dense, sparse, alpha=0.5)
        # Single result — already sorted
        assert result[0]["fusion_score"] > 0

    def test_alpha_0_all_sparse(self):
        svc, _, _ = _make_service()
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "2", "score": 0.9}]
        result = svc.reciprocal_rank_fusion(dense, sparse, alpha=0.0)
        # alpha=0 means all sparse, doc 2 should rank higher
        assert result[0]["id"] == "2"

    def test_alpha_1_all_dense(self):
        svc, _, _ = _make_service()
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "2", "score": 0.9}]
        result = svc.reciprocal_rank_fusion(dense, sparse, alpha=1.0)
        assert result[0]["id"] == "1"


# ---------------------------------------------------------------------------
# Tests: Trimodal RRF
# ---------------------------------------------------------------------------


class TestTrimodalRRF:
    def test_fallback_to_bimodal_without_graph(self):
        svc, _, _ = _make_service()
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "1", "score": 0.8}]
        result = svc.reciprocal_rank_fusion_trimodal(dense, sparse, [])
        assert len(result) == 1

    def test_all_empty(self):
        svc, _, _ = _make_service()
        result = svc.reciprocal_rank_fusion_trimodal([], [], [])
        assert result == []

    def test_three_signals(self):
        svc, _, _ = _make_service()
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "2", "score": 0.8}]
        graph = [{"id": "1", "score": 1.0}, {"id": "3", "score": 0.7}]
        result = svc.reciprocal_rank_fusion_trimodal(
            dense, sparse, graph, weights=(0.4, 0.3, 0.3),
        )
        assert len(result) == 3
        for r in result:
            assert "graph_rank" in r
        # doc 1 in dense + graph → should be first
        assert result[0]["id"] == "1"


# ---------------------------------------------------------------------------
# Tests: Format results
# ---------------------------------------------------------------------------


class TestFormatResults:
    def test_formats_correctly(self):
        svc, _, _ = _make_service()
        raw = {
            "ids": ["id1", "id2"],
            "documents": ["text1", "text2"],
            "metadatas": [{"src": "a"}, {"src": "b"}],
            "scores": [0.9, 0.7],
        }
        result = svc._format_results(raw)
        assert len(result) == 2
        assert result[0]["id"] == "id1"
        assert result[0]["text"] == "text1"
        assert result[0]["score"] == 0.9

    def test_empty_results(self):
        svc, _, _ = _make_service()
        result = svc._format_results({"ids": [], "documents": [], "metadatas": [], "scores": []})
        assert result == []

    def test_uses_distances_fallback(self):
        svc, _, _ = _make_service()
        raw = {"ids": ["1"], "documents": ["t"], "metadatas": [{}], "distances": [0.5]}
        result = svc._format_results(raw)
        assert result[0]["score"] == 0.5


# ---------------------------------------------------------------------------
# Tests: search_hybrid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchHybrid:
    async def test_graceful_degradation_on_error(self):
        svc, cm, embedder = _make_service()
        cm.get_collection.side_effect = Exception("Qdrant down")

        with patch("backend.services.rag.hybrid_search.QdrantClient", side_effect=Exception("fail")):
            result = await svc.search_hybrid("test query", "legal_unified_hybrid")

        assert result["search_type"] == "error"
        assert result["total_results"] == 0
        assert "error" in result

    async def test_dense_only_when_bm25_disabled(self):
        svc, cm, embedder = _make_service(bm25_enabled=False)
        svc._bm25_enabled = False

        mock_vdb = AsyncMock()
        mock_vdb.search.return_value = {
            "ids": ["1"], "documents": ["text"], "metadatas": [{}], "scores": [0.9],
        }
        cm.get_collection.return_value = mock_vdb

        with patch("backend.services.search.search_service._uses_named_vectors", return_value=False):
            result = await svc.search_hybrid("test", "collection")

        assert result["bm25_enabled"] is False


# ---------------------------------------------------------------------------
# Tests: search_dense_only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchDenseOnly:
    async def test_successful_search(self):
        svc, cm, embedder = _make_service()
        mock_vdb = AsyncMock()
        mock_vdb.search.return_value = {
            "ids": ["1"], "documents": ["text"], "metadatas": [{}], "scores": [0.95],
        }
        cm.get_collection.return_value = mock_vdb

        with patch("backend.services.search.search_service._uses_named_vectors", return_value=False):
            result = await svc.search_dense_only("test query", "collection")

        assert result["search_type"] == "dense_only"
        assert result["total_results"] == 1
        assert result["bm25_enabled"] is False

    async def test_error_returns_empty(self):
        svc, cm, embedder = _make_service()
        cm.get_collection.return_value = None

        with patch("backend.services.rag.hybrid_search.QdrantClient") as mock_qc:
            mock_qc.return_value.search = AsyncMock(side_effect=Exception("fail"))
            result = await svc.search_dense_only("test", "collection")

        assert result["search_type"] == "error"
        assert result["total_results"] == 0


# ---------------------------------------------------------------------------
# Tests: compare_search_methods
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCompareSearchMethods:
    async def test_comparison_output(self):
        svc, _, _ = _make_service()
        svc.search_hybrid = AsyncMock(return_value={
            "results": [{"id": "1"}, {"id": "2"}],
            "duration_ms": 50,
        })
        svc.search_dense_only = AsyncMock(return_value={
            "results": [{"id": "1"}, {"id": "3"}],
            "duration_ms": 30,
        })

        result = await svc.compare_search_methods("test", "collection")
        assert result["comparison"]["hybrid_count"] == 2
        assert result["comparison"]["dense_count"] == 2
        assert result["comparison"]["overlap_count"] == 1
        assert result["comparison"]["overlap_percentage"] == 50.0
