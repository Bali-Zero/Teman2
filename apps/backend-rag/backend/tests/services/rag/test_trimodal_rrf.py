"""Tests for Trimodal RRF Fusion (Vector + BM25 + Graph)."""

from backend.services.rag.hybrid_search import HybridSearchService


class TestTrimodalRRF:
    def setup_method(self) -> None:
        self.service = HybridSearchService.__new__(HybridSearchService)

    def test_empty_all(self) -> None:
        """No results from any source → falls back to bimodal → empty."""
        result = self.service.reciprocal_rank_fusion_trimodal([], [], [])
        assert result == []

    def test_dense_only(self) -> None:
        """Only dense results → falls back gracefully."""
        dense = [{"id": "1", "score": 0.9, "text": "doc1"}]
        result = self.service.reciprocal_rank_fusion_trimodal(dense, [], [])
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_graph_boost(self) -> None:
        """Document in graph results should get boosted."""
        dense = [
            {"id": "1", "score": 0.9, "text": "doc1"},
            {"id": "2", "score": 0.8, "text": "doc2"},
        ]
        sparse = [
            {"id": "2", "score": 0.9, "text": "doc2"},
            {"id": "1", "score": 0.7, "text": "doc1"},
        ]
        graph = [
            {"id": "2", "score": 1.0},  # doc2 has graph signal
        ]

        result = self.service.reciprocal_rank_fusion_trimodal(
            dense, sparse, graph,
            weights=(0.4, 0.3, 0.3),
        )

        # doc2 should be ranked higher due to triple signal
        ids = [r["id"] for r in result]
        assert ids[0] == "2"  # doc2 first (graph boost)

    def test_graph_only_doc(self) -> None:
        """Document only in graph results gets non-zero score."""
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "1", "score": 0.8}]
        graph = [{"id": "3", "score": 1.0}]  # doc3 only in graph

        result = self.service.reciprocal_rank_fusion_trimodal(
            dense, sparse, graph,
            weights=(0.4, 0.3, 0.3),
        )

        doc3 = [r for r in result if r["id"] == "3"]
        assert len(doc3) == 1
        assert doc3[0]["fusion_score"] > 0
        assert doc3[0].get("graph_rank") == 1

    def test_weights_respected(self) -> None:
        """Different weight configurations change ranking."""
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "2", "score": 0.9}]
        graph = [{"id": "3", "score": 0.9}]

        # Graph-heavy weights
        result_graph_heavy = self.service.reciprocal_rank_fusion_trimodal(
            dense, sparse, graph,
            weights=(0.1, 0.1, 0.8),
        )

        # Dense-heavy weights
        result_dense_heavy = self.service.reciprocal_rank_fusion_trimodal(
            dense, sparse, graph,
            weights=(0.8, 0.1, 0.1),
        )

        # With graph-heavy weights, doc3 (graph) should score highest
        assert result_graph_heavy[0]["id"] == "3"
        # With dense-heavy weights, doc1 (dense) should score highest
        assert result_dense_heavy[0]["id"] == "1"

    def test_no_graph_fallback_to_bimodal(self) -> None:
        """Empty graph results falls back to bimodal RRF."""
        dense = [{"id": "1", "score": 0.9}]
        sparse = [{"id": "1", "score": 0.8}]

        result = self.service.reciprocal_rank_fusion_trimodal(
            dense, sparse, [],
            weights=(0.4, 0.3, 0.3),
        )

        assert len(result) >= 1
        assert result[0]["id"] == "1"

    def test_graph_rank_in_output(self) -> None:
        """Output should include graph_rank field."""
        dense = [{"id": "1"}]
        graph = [{"id": "1", "score": 0.5}]

        result = self.service.reciprocal_rank_fusion_trimodal(
            dense, [], graph,
        )

        assert "graph_rank" in result[0]
        assert result[0]["graph_rank"] == 1

    def test_large_k_reduces_rank_impact(self) -> None:
        """With large k, rank differences matter less."""
        dense = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        # With k=60 (default), rank 1 vs rank 3 difference is small
        result = self.service.reciprocal_rank_fusion_trimodal(
            dense, [], [],
        )

        scores = [r["fusion_score"] for r in result]
        # All scores should be close (small spread with high k)
        assert max(scores) - min(scores) < 0.001
