"""Tests for ARCH-3: Adaptive Query Decomposer.

Ollama calls are mocked — no real LLM needed.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research.query_decomposer import (
    CLUSTER_OBJECTIVES,
    MAX_QUERIES_PER_DECOMPOSITION,
    MIN_QUERIES_PER_DECOMPOSITION,
    DecompositionResult,
    QueryDecomposer,
    _call_ollama,
    _parse_query_array,
    decompose_query,
    get_decomposer,
)


# ---------------------------------------------------------------------------
# _parse_query_array
# ---------------------------------------------------------------------------

class TestParseQueryArray:
    def test_plain_json_array(self):
        text = '["query one about KITAS", "query two about permits", "query three about fees"]'
        result = _parse_query_array(text)
        assert result == ["query one about KITAS", "query two about permits", "query three about fees"]

    def test_markdown_fenced(self):
        text = '```json\n["Berikan update terbaru tentang KITAS 2026", "Bandingkan persyaratan RPTKA sebelum dan sesudah PP 34/2021"]\n```'
        result = _parse_query_array(text)
        assert result is not None
        assert len(result) == 2

    def test_array_with_explanation_before(self):
        text = '["Berikan update terbaru tentang peraturan imigrasi 2026", "Bandingkan prosedur KITAS dan KITAP Indonesia"]'
        result = _parse_query_array(text)
        assert result is not None
        assert len(result) == 2

    def test_empty_input(self):
        assert _parse_query_array("") is None
        assert _parse_query_array(None) is None

    def test_not_array(self):
        assert _parse_query_array('{"key": "value"}') is None

    def test_array_of_non_strings_filtered(self):
        text = '[123, "valid query string here", null, "another valid query"]'
        result = _parse_query_array(text)
        assert result is not None
        assert all(isinstance(q, str) for q in result)

    def test_short_strings_filtered(self):
        # Strings < 20 chars are filtered (too short to be real queries)
        text = '["short", "a valid long query about Indonesian immigration regulations 2026"]'
        result = _parse_query_array(text)
        assert result is not None
        assert len(result) == 1
        assert "immigration" in result[0]

    def test_invalid_json(self):
        assert _parse_query_array("[not valid json]") is None


# ---------------------------------------------------------------------------
# QueryDecomposer — Ollama success path
# ---------------------------------------------------------------------------

class TestQueryDecomposerOllama:
    def _make_ollama_response(self, queries: list[str]) -> str:
        return json.dumps(queries)

    def test_ollama_success_returns_queries(self):
        mock_queries = [
            "Berikan update terbaru tentang peraturan KITAS 2026 untuk pekerja asing",
            "Apa perubahan prosedur perpanjangan izin tinggal terbatas 2025-2026?",
            "Berapa biaya dan dokumen yang diperlukan untuk konversi KITAS ke KITAP?",
        ]
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=self._make_ollama_response(mock_queries),
        ):
            decomposer = QueryDecomposer(use_cache=False)
            result = decomposer.decompose(cluster="B", level="L1", domain="immigration")

        assert result.source == "ollama"
        assert len(result.queries) >= MIN_QUERIES_PER_DECOMPOSITION
        assert len(result.queries) <= MAX_QUERIES_PER_DECOMPOSITION
        assert result.cluster == "B"
        assert result.level == "L1"

    def test_ollama_result_capped_at_max(self):
        # Return more queries than max
        mock_queries = [f"Query about topic {i} Indonesia regulations 2026" for i in range(8)]
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=self._make_ollama_response(mock_queries),
        ):
            decomposer = QueryDecomposer(use_cache=False)
            result = decomposer.decompose(cluster="A", level="L1")

        assert len(result.queries) <= MAX_QUERIES_PER_DECOMPOSITION

    def test_ollama_failure_falls_back_to_static(self):
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=None,
        ):
            decomposer = QueryDecomposer(use_cache=False)
            result = decomposer.decompose(cluster="A", level="L1")

        assert result.source == "static_fallback"
        assert len(result.queries) == 1
        assert "RPTKA" in result.queries[0] or "izin kerja" in result.queries[0]

    def test_ollama_invalid_json_falls_back(self):
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value="This is not JSON at all.",
        ):
            decomposer = QueryDecomposer(use_cache=False)
            result = decomposer.decompose(cluster="B", level="L2")

        assert result.source == "static_fallback"
        assert "KITAS" in result.queries[0] or "konversi" in result.queries[0]

    def test_ollama_too_few_queries_falls_back(self):
        """If Ollama returns only 1 query (below minimum), fall back."""
        mock_queries = ["One single query about Indonesian immigration regulations 2026"]
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=json.dumps(mock_queries),
        ):
            decomposer = QueryDecomposer(use_cache=False)
            result = decomposer.decompose(cluster="C", level="L1")

        # 1 query is below MIN_QUERIES_PER_DECOMPOSITION (2)
        assert result.source == "static_fallback"


# ---------------------------------------------------------------------------
# QueryDecomposer — cache
# ---------------------------------------------------------------------------

class TestQueryDecomposerCache:
    def test_cache_hit_avoids_second_call(self):
        mock_queries = [
            "First query about immigration policies Indonesia 2026",
            "Second query about visa requirements Indonesia 2026",
        ]
        call_count = {"n": 0}

        def fake_ollama(system, user, model, timeout):
            call_count["n"] += 1
            return json.dumps(mock_queries)

        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            side_effect=fake_ollama,
        ):
            decomposer = QueryDecomposer(use_cache=True)
            r1 = decomposer.decompose(cluster="A", level="L1")
            r2 = decomposer.decompose(cluster="A", level="L1")  # same key

        assert call_count["n"] == 1  # only called once
        assert r1.queries == r2.queries

    def test_different_clusters_not_shared(self):
        q_a = ["Query A about work permits Indonesia 2026", "Query A2 about RPTKA Indonesia 2026"]
        q_b = ["Query B about stay permits Indonesia 2026", "Query B2 about KITAS Indonesia 2026"]
        responses = [json.dumps(q_a), json.dumps(q_b)]
        call_count = {"n": 0}

        def fake_ollama(system, user, model, timeout):
            resp = responses[call_count["n"]]
            call_count["n"] += 1
            return resp

        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            side_effect=fake_ollama,
        ):
            decomposer = QueryDecomposer(use_cache=True)
            r_a = decomposer.decompose(cluster="A", level="L1")
            r_b = decomposer.decompose(cluster="B", level="L1")

        assert r_a.queries != r_b.queries
        assert call_count["n"] == 2

    def test_clear_cache(self):
        mock_queries = [
            "Query about KITAS immigration regulations Indonesia",
            "Query about KITAP conversion procedures 2026",
        ]
        call_count = {"n": 0}

        def fake_ollama(system, user, model, timeout):
            call_count["n"] += 1
            return json.dumps(mock_queries)

        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            side_effect=fake_ollama,
        ):
            decomposer = QueryDecomposer(use_cache=True)
            decomposer.decompose(cluster="A", level="L1")
            decomposer.clear_cache()
            decomposer.decompose(cluster="A", level="L1")

        assert call_count["n"] == 2  # called again after cache clear


# ---------------------------------------------------------------------------
# decompose_first — drop-in replacement for _build_query
# ---------------------------------------------------------------------------

class TestDecomposeFirst:
    def test_returns_string(self):
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=None,  # force fallback
        ):
            decomposer = QueryDecomposer(use_cache=False)
            query = decomposer.decompose_first(cluster="A", level="L1")
        assert isinstance(query, str)
        assert len(query) > 20

    def test_fallback_clusters_all_covered(self):
        """All 5 clusters (A-E) have static fallback queries for L1 and L2."""
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=None,
        ):
            decomposer = QueryDecomposer(use_cache=False)
            for cluster in "ABCDE":
                for level in ("L1", "L2"):
                    q = decomposer.decompose_first(cluster=cluster, level=level)
                    assert isinstance(q, str) and len(q) > 30, (
                        f"Empty fallback for cluster={cluster}, level={level}"
                    )


# ---------------------------------------------------------------------------
# CLUSTER_OBJECTIVES coverage
# ---------------------------------------------------------------------------

class TestClusterObjectives:
    def test_immigration_all_clusters_covered(self):
        for cluster in "ABCDE":
            assert ("immigration", cluster) in CLUSTER_OBJECTIVES, (
                f"Missing objective for immigration/cluster {cluster}"
            )

    def test_all_objectives_non_empty(self):
        for key, obj in CLUSTER_OBJECTIVES.items():
            assert isinstance(obj, str) and len(obj) > 20, f"Empty objective for {key}"


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_pipeline_uses_decomposer(self):
        """NLMPipeline._build_query should return non-empty string via decomposer."""
        from apps.evaluator.nlm_deep_research.pipeline import NLMPipeline
        with patch(
            "apps.evaluator.nlm_deep_research.query_decomposer._call_ollama",
            return_value=None,  # force static fallback
        ):
            pipeline = NLMPipeline(dry_run=True)
            for cluster in "ABCDE":
                for level in ("L1", "L2"):
                    q = pipeline._build_query(level=level, cluster=cluster)
                    assert isinstance(q, str) and len(q) > 30

    def test_pipeline_decomposer_attribute(self):
        from apps.evaluator.nlm_deep_research.pipeline import NLMPipeline
        pipeline = NLMPipeline(dry_run=True)
        assert hasattr(pipeline, "_decomposer")
        assert isinstance(pipeline._decomposer, QueryDecomposer)
