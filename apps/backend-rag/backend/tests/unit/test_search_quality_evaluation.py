"""
Tests for Search Quality Evaluation Framework

Validates that the evaluation framework correctly computes
Precision@10, MRR, and NDCG@10 metrics with mock data.
"""

import json
import math
from pathlib import Path
from typing import Any

import pytest

# Add scripts to path for import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from scripts.evaluate_search_quality import (
    QueryResult,
    aggregate_results,
    compute_mrr,
    compute_ndcg_at_k,
    compute_precision_at_k,
    evaluate_query_offline,
    generate_mock_results,
    is_result_relevant,
    load_golden_dataset,
    run_evaluation,
)


class TestRelevanceChecking:
    """Tests for result relevance checking."""

    def test_relevant_result_with_keyword(self) -> None:
        result = {"text": "KITAS work permit application process"}
        assert is_result_relevant(result, ["KITAS", "work permit"]) is True

    def test_irrelevant_result(self) -> None:
        result = {"text": "General administrative procedures"}
        assert is_result_relevant(result, ["KITAS", "visa"]) is False

    def test_case_insensitive_matching(self) -> None:
        result = {"text": "kitas application requirements"}
        assert is_result_relevant(result, ["KITAS"]) is True

    def test_content_key_fallback(self) -> None:
        result = {"content": "KITAS documentation required"}
        assert is_result_relevant(result, ["KITAS"]) is True

    def test_metadata_key_fallback(self) -> None:
        result = {"metadata": {"title": "KITAS Guide"}}
        assert is_result_relevant(result, ["KITAS"]) is True

    def test_empty_result(self) -> None:
        result: dict[str, Any] = {}
        assert is_result_relevant(result, ["KITAS"]) is False


class TestPrecisionAtK:
    """Tests for Precision@K computation."""

    def test_perfect_precision(self) -> None:
        results = [{"text": f"KITAS doc {i}"} for i in range(10)]
        precision, count = compute_precision_at_k(results, ["KITAS"], k=10)
        assert precision == 1.0
        assert count == 10

    def test_half_precision(self) -> None:
        results = (
            [{"text": f"KITAS doc {i}"} for i in range(5)]
            + [{"text": f"unrelated doc {i}"} for i in range(5)]
        )
        precision, count = compute_precision_at_k(results, ["KITAS"], k=10)
        assert precision == 0.5
        assert count == 5

    def test_zero_precision(self) -> None:
        results = [{"text": f"unrelated doc {i}"} for i in range(10)]
        precision, count = compute_precision_at_k(results, ["KITAS"], k=10)
        assert precision == 0.0
        assert count == 0

    def test_empty_results(self) -> None:
        precision, count = compute_precision_at_k([], ["KITAS"], k=10)
        assert precision == 0.0
        assert count == 0

    def test_fewer_than_k_results(self) -> None:
        results = [{"text": "KITAS doc 1"}, {"text": "noise"}]
        precision, count = compute_precision_at_k(results, ["KITAS"], k=10)
        assert precision == 0.5
        assert count == 1


class TestMRR:
    """Tests for Mean Reciprocal Rank computation."""

    def test_first_result_relevant(self) -> None:
        results = [{"text": "KITAS guide"}, {"text": "noise"}]
        mrr, rank = compute_mrr(results, ["KITAS"], k=10)
        assert mrr == 1.0
        assert rank == 1

    def test_third_result_relevant(self) -> None:
        results = [
            {"text": "noise 1"},
            {"text": "noise 2"},
            {"text": "KITAS guide"},
        ]
        mrr, rank = compute_mrr(results, ["KITAS"], k=10)
        assert abs(mrr - 1 / 3) < 0.001
        assert rank == 3

    def test_no_relevant_results(self) -> None:
        results = [{"text": f"noise {i}"} for i in range(10)]
        mrr, rank = compute_mrr(results, ["KITAS"], k=10)
        assert mrr == 0.0
        assert rank is None

    def test_empty_results(self) -> None:
        mrr, rank = compute_mrr([], ["KITAS"], k=10)
        assert mrr == 0.0
        assert rank is None


class TestNDCG:
    """Tests for NDCG@K computation."""

    def test_perfect_ndcg(self) -> None:
        """When all keywords match in order of relevance grade."""
        results = [{"text": "KITAS work permit RPTKA IMTA"}]  # All keywords
        labels = {"KITAS": 3, "work permit": 3, "RPTKA": 2}
        ndcg = compute_ndcg_at_k(results, ["KITAS"], labels, k=10)
        assert ndcg > 0.0

    def test_zero_ndcg(self) -> None:
        results = [{"text": f"unrelated {i}"} for i in range(10)]
        labels = {"KITAS": 3, "visa": 2}
        ndcg = compute_ndcg_at_k(results, ["KITAS"], labels, k=10)
        assert ndcg == 0.0

    def test_empty_results(self) -> None:
        labels = {"KITAS": 3}
        ndcg = compute_ndcg_at_k([], ["KITAS"], labels, k=10)
        assert ndcg == 0.0

    def test_ndcg_bounded(self) -> None:
        """NDCG should always be between 0 and 1."""
        results = [{"text": "KITAS visa RPTKA"}] * 10
        labels = {"KITAS": 3, "visa": 2, "RPTKA": 1}
        ndcg = compute_ndcg_at_k(results, ["KITAS"], labels, k=10)
        assert 0.0 <= ndcg <= 1.0


class TestMockGeneration:
    """Tests for mock result generation."""

    def test_generates_10_results(self) -> None:
        gq = {
            "id": "test_01",
            "query": "test query",
            "expected_top_result_keywords": ["KITAS", "visa"],
        }
        results = generate_mock_results(gq)
        assert len(results) == 10

    def test_first_results_are_relevant(self) -> None:
        gq = {
            "id": "test_01",
            "query": "test query",
            "expected_top_result_keywords": ["KITAS", "visa"],
        }
        results = generate_mock_results(gq)
        # First 4 should be relevant
        for r in results[:4]:
            assert is_result_relevant(r, ["KITAS", "visa"]) is True


class TestOfflineEvaluation:
    """Tests for the offline evaluation workflow."""

    def test_offline_evaluation_produces_result(self) -> None:
        gq = {
            "id": "visa_01",
            "query": "What documents do I need for a KITAS?",
            "domain": "visa",
            "expected_collection": "visa_oracle",
            "expected_top_result_keywords": ["KITAS", "work permit", "documents"],
            "relevance_labels": {"KITAS": 3, "work permit": 2},
        }
        result = evaluate_query_offline(gq)
        assert result.query_id == "visa_01"
        assert result.error is None
        assert result.precision_at_10 > 0.0
        assert result.mrr > 0.0

    def test_offline_run_with_all_golden_queries(self) -> None:
        """Full offline run should complete without errors."""
        summary = run_evaluation(
            offline=True,
            output_path=Path("/tmp/test_eval_results.json"),
        )
        assert summary.total_queries == 50
        assert summary.evaluated_queries == 50
        assert summary.failed_queries == 0
        assert summary.overall_precision_at_10 > 0.0
        assert summary.overall_mrr > 0.0
        assert summary.overall_ndcg_at_10 > 0.0

    def test_domain_filter(self) -> None:
        summary = run_evaluation(
            domain_filter="visa",
            offline=True,
            output_path=Path("/tmp/test_eval_visa.json"),
        )
        assert summary.total_queries == 10
        assert all(r["domain"] == "visa" for r in summary.results)


class TestAggregation:
    """Tests for result aggregation."""

    def test_aggregate_empty(self) -> None:
        summary = aggregate_results([])
        assert summary.total_queries == 0
        assert summary.overall_precision_at_10 == 0.0

    def test_aggregate_single_result(self) -> None:
        result = QueryResult(
            query_id="test_01",
            query="test",
            domain="visa",
            expected_collection="visa_oracle",
            precision_at_10=0.8,
            mrr=1.0,
            ndcg_at_10=0.75,
        )
        summary = aggregate_results([result])
        assert summary.total_queries == 1
        assert summary.overall_precision_at_10 == 0.8
        assert summary.overall_mrr == 1.0
        assert "visa" in summary.per_domain

    def test_aggregate_multiple_domains(self) -> None:
        results = [
            QueryResult("v1", "q1", "visa", "visa_oracle", precision_at_10=0.8, mrr=1.0, ndcg_at_10=0.7),
            QueryResult("t1", "q2", "tax", "tax_genius", precision_at_10=0.6, mrr=0.5, ndcg_at_10=0.5),
        ]
        summary = aggregate_results(results)
        assert "visa" in summary.per_domain
        assert "tax" in summary.per_domain
        assert summary.overall_precision_at_10 == pytest.approx(0.7, abs=0.01)

    def test_summary_serializable(self) -> None:
        """Summary dict should be JSON-serializable."""
        result = QueryResult("v1", "q1", "visa", "vo", precision_at_10=0.8, mrr=1.0, ndcg_at_10=0.7)
        summary = aggregate_results([result])
        d = summary.to_dict()
        # Should not raise
        json.dumps(d)
        assert "overall" in d
        assert "per_domain" in d


class TestGoldenDatasetLoading:
    """Tests for golden dataset loading."""

    def test_load_golden_dataset(self) -> None:
        """Golden dataset should load with 50 queries."""
        queries = load_golden_dataset()
        assert len(queries) == 50

    def test_golden_queries_have_required_fields(self) -> None:
        """Each query must have id, query, domain, expected_collection, expected_top_result_keywords."""
        queries = load_golden_dataset()
        required = {"id", "query", "domain", "expected_collection", "expected_top_result_keywords"}
        for q in queries:
            missing = required - set(q.keys())
            assert not missing, f"Query {q.get('id', '?')} missing fields: {missing}"

    def test_golden_covers_all_domains(self) -> None:
        """Golden dataset should cover visa, company, tax, property, regulation, cross_domain."""
        queries = load_golden_dataset()
        domains = {q["domain"] for q in queries}
        expected_domains = {"visa", "company", "tax", "property", "regulation", "cross_domain"}
        assert expected_domains == domains

    def test_domain_distribution(self) -> None:
        """Check approximate query distribution per domain."""
        queries = load_golden_dataset()
        domain_counts: dict[str, int] = {}
        for q in queries:
            domain_counts[q["domain"]] = domain_counts.get(q["domain"], 0) + 1

        assert domain_counts["visa"] == 10
        assert domain_counts["company"] == 10
        assert domain_counts["tax"] == 10
        assert domain_counts["property"] == 10
        assert domain_counts["regulation"] == 5
        assert domain_counts["cross_domain"] == 5
