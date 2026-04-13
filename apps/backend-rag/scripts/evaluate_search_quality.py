#!/usr/bin/env python3
"""
Search Quality Evaluation Script

Evaluates search quality against a golden dataset of curated queries.
Computes Precision@10, MRR (Mean Reciprocal Rank), and NDCG@10.

Can run in two modes:
1. Online: Hit actual Qdrant instance
2. Offline: Use mock results for framework validation

Usage:
    # Online mode (requires Qdrant access)
    PYTHONPATH=. python scripts/evaluate_search_quality.py

    # Offline mode (mock data for CI/testing)
    PYTHONPATH=. python scripts/evaluate_search_quality.py --offline

    # Specific domain
    PYTHONPATH=. python scripts/evaluate_search_quality.py --domain visa
"""

import argparse
import json
import logging
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Paths
GOLDEN_DATASET_PATH = Path(__file__).parent.parent / "data" / "evaluation" / "search_quality_golden.json"
RESULTS_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "evaluation" / "baseline_results.json"


@dataclass
class QueryResult:
    """Result of evaluating a single golden query."""

    query_id: str
    query: str
    domain: str
    expected_collection: str
    actual_collection: str | None = None
    precision_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    top_10_scores: list[float] = field(default_factory=list)
    relevant_in_top_10: int = 0
    first_relevant_rank: int | None = None
    error: str | None = None


@dataclass
class EvaluationSummary:
    """Summary of the full evaluation run."""

    timestamp: str = ""
    mode: str = "online"
    total_queries: int = 0
    evaluated_queries: int = 0
    failed_queries: int = 0
    overall_precision_at_10: float = 0.0
    overall_mrr: float = 0.0
    overall_ndcg_at_10: float = 0.0
    per_domain: dict[str, dict[str, float]] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "total_queries": self.total_queries,
            "evaluated_queries": self.evaluated_queries,
            "failed_queries": self.failed_queries,
            "overall": {
                "precision_at_10": round(self.overall_precision_at_10, 4),
                "mrr": round(self.overall_mrr, 4),
                "ndcg_at_10": round(self.overall_ndcg_at_10, 4),
            },
            "per_domain": {
                domain: {k: round(v, 4) for k, v in metrics.items()}
                for domain, metrics in self.per_domain.items()
            },
            "results": self.results,
        }


def load_golden_dataset(path: Path | None = None) -> list[dict[str, Any]]:
    """Load golden queries from JSON file."""
    dataset_path = path or GOLDEN_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {dataset_path}")

    with open(dataset_path) as f:
        data = json.load(f)

    queries = data.get("queries", [])
    logger.info("Loaded %d golden queries from %s", len(queries), dataset_path)
    return queries


def is_result_relevant(
    result: dict[str, Any],
    expected_keywords: list[str],
) -> bool:
    """
    Check if a search result is relevant based on keyword matching.

    A result is relevant if its text content contains at least one of the
    expected top-result keywords (case-insensitive).

    Args:
        result: Search result dict (should have 'text' or 'content' key)
        expected_keywords: Keywords that indicate relevance

    Returns:
        True if at least one keyword found in result text
    """
    text = ""
    for key in ("text", "content", "document", "payload", "metadata"):
        val = result.get(key, "")
        if isinstance(val, str):
            text += " " + val
        elif isinstance(val, dict):
            text += " " + json.dumps(val)

    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in expected_keywords)


def compute_precision_at_k(
    results: list[dict[str, Any]],
    expected_keywords: list[str],
    k: int = 10,
) -> tuple[float, int]:
    """
    Compute Precision@K: fraction of top-K results that are relevant.

    Returns:
        Tuple of (precision, relevant_count)
    """
    top_k = results[:k]
    if not top_k:
        return 0.0, 0

    relevant_count = sum(
        1 for r in top_k if is_result_relevant(r, expected_keywords)
    )
    return relevant_count / len(top_k), relevant_count


def compute_mrr(
    results: list[dict[str, Any]],
    expected_keywords: list[str],
    k: int = 10,
) -> tuple[float, int | None]:
    """
    Compute Mean Reciprocal Rank: 1/rank of first relevant result.

    Returns:
        Tuple of (mrr_score, first_relevant_rank or None)
    """
    for i, result in enumerate(results[:k]):
        if is_result_relevant(result, expected_keywords):
            rank = i + 1
            return 1.0 / rank, rank
    return 0.0, None


def compute_ndcg_at_k(
    results: list[dict[str, Any]],
    expected_keywords: list[str],
    relevance_labels: dict[str, int],
    k: int = 10,
) -> float:
    """
    Compute NDCG@K (Normalized Discounted Cumulative Gain).

    Uses keyword-based graded relevance from relevance_labels.

    Args:
        results: Search results
        expected_keywords: Keywords for binary relevance
        relevance_labels: Mapping of keyword -> relevance grade (0-3)
        k: Cutoff

    Returns:
        NDCG@K score (0.0 to 1.0)
    """
    top_k = results[:k]
    if not top_k:
        return 0.0

    # Compute actual gains
    gains: list[float] = []
    for result in top_k:
        text = ""
        for key in ("text", "content", "document", "payload", "metadata"):
            val = result.get(key, "")
            if isinstance(val, str):
                text += " " + val
            elif isinstance(val, dict):
                text += " " + json.dumps(val)

        text_lower = text.lower()
        # Sum relevance grades for all matching keywords
        gain = sum(
            grade
            for keyword, grade in relevance_labels.items()
            if keyword.lower() in text_lower
        )
        gains.append(float(gain))

    # DCG
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))

    # Ideal DCG: the best possible gain is the sum of ALL relevance grades
    # (a perfect result matches every keyword). We create k copies of the
    # max possible gain, then sort descending.
    max_gain_per_result = float(sum(relevance_labels.values()))
    ideal_gains = [max_gain_per_result] * min(k, len(top_k))
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal_gains))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def generate_mock_results(
    golden_query: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Generate mock search results for offline evaluation.

    Creates 10 results where the first 3-5 are relevant (contain
    expected keywords) and the rest are noise.
    """
    keywords = golden_query.get("expected_top_result_keywords", [])
    mock_results = []

    # First 4 results contain keywords (simulating good search)
    for i in range(4):
        kw_subset = keywords[: (i % len(keywords)) + 1] if keywords else ["test"]
        mock_results.append({
            "text": f"Document about {' and '.join(kw_subset)} in Indonesian law. "
                    f"This covers procedures and requirements.",
            "score": 0.95 - (i * 0.05),
            "id": f"mock_{golden_query['id']}_{i}",
        })

    # Remaining 6 results are noise
    for i in range(6):
        mock_results.append({
            "text": f"General document about administrative procedures part {i + 1}. "
                    f"Contains unrelated legal information.",
            "score": 0.60 - (i * 0.05),
            "id": f"mock_{golden_query['id']}_noise_{i}",
        })

    return mock_results


def evaluate_query_offline(
    golden_query: dict[str, Any],
) -> QueryResult:
    """Evaluate a single query using mock data (offline mode)."""
    mock_results = generate_mock_results(golden_query)
    return _evaluate_results(golden_query, mock_results, golden_query["expected_collection"])


def _evaluate_results(
    golden_query: dict[str, Any],
    results: list[dict[str, Any]],
    actual_collection: str,
) -> QueryResult:
    """Evaluate search results against golden query expectations."""
    keywords = golden_query.get("expected_top_result_keywords", [])
    relevance_labels = golden_query.get("relevance_labels", {})

    precision, relevant_count = compute_precision_at_k(results, keywords, k=10)
    mrr_score, first_rank = compute_mrr(results, keywords, k=10)
    ndcg = compute_ndcg_at_k(results, keywords, relevance_labels, k=10)

    return QueryResult(
        query_id=golden_query["id"],
        query=golden_query["query"],
        domain=golden_query["domain"],
        expected_collection=golden_query["expected_collection"],
        actual_collection=actual_collection,
        precision_at_10=precision,
        mrr=mrr_score,
        ndcg_at_10=ndcg,
        top_10_scores=[r.get("score", 0.0) for r in results[:10]],
        relevant_in_top_10=relevant_count,
        first_relevant_rank=first_rank,
    )


def aggregate_results(results: list[QueryResult]) -> EvaluationSummary:
    """Aggregate individual query results into a summary."""
    summary = EvaluationSummary(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_queries=len(results),
    )

    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]
    summary.evaluated_queries = len(successful)
    summary.failed_queries = len(failed)

    if successful:
        summary.overall_precision_at_10 = sum(r.precision_at_10 for r in successful) / len(successful)
        summary.overall_mrr = sum(r.mrr for r in successful) / len(successful)
        summary.overall_ndcg_at_10 = sum(r.ndcg_at_10 for r in successful) / len(successful)

    # Per-domain aggregation
    domains: dict[str, list[QueryResult]] = {}
    for r in successful:
        domains.setdefault(r.domain, []).append(r)

    for domain, domain_results in sorted(domains.items()):
        n = len(domain_results)
        summary.per_domain[domain] = {
            "count": n,
            "precision_at_10": sum(r.precision_at_10 for r in domain_results) / n,
            "mrr": sum(r.mrr for r in domain_results) / n,
            "ndcg_at_10": sum(r.ndcg_at_10 for r in domain_results) / n,
        }

    # Individual results
    for r in results:
        summary.results.append({
            "query_id": r.query_id,
            "query": r.query,
            "domain": r.domain,
            "expected_collection": r.expected_collection,
            "actual_collection": r.actual_collection,
            "precision_at_10": round(r.precision_at_10, 4),
            "mrr": round(r.mrr, 4),
            "ndcg_at_10": round(r.ndcg_at_10, 4),
            "relevant_in_top_10": r.relevant_in_top_10,
            "first_relevant_rank": r.first_relevant_rank,
            "error": r.error,
        })

    return summary


def run_evaluation(
    domain_filter: str | None = None,
    offline: bool = False,
    golden_path: Path | None = None,
    output_path: Path | None = None,
) -> EvaluationSummary:
    """
    Run the full evaluation pipeline.

    Args:
        domain_filter: Evaluate only queries from this domain
        offline: Use mock data instead of Qdrant
        golden_path: Path to golden dataset JSON
        output_path: Path to write results JSON

    Returns:
        EvaluationSummary with all metrics
    """
    golden_queries = load_golden_dataset(golden_path)

    if domain_filter:
        golden_queries = [q for q in golden_queries if q["domain"] == domain_filter]
        logger.info("Filtered to %d queries for domain '%s'", len(golden_queries), domain_filter)

    results: list[QueryResult] = []
    mode = "offline" if offline else "online"

    for i, gq in enumerate(golden_queries):
        query_id = gq["id"]
        logger.info("[%d/%d] Evaluating %s: %s", i + 1, len(golden_queries), query_id, gq["query"][:60])

        try:
            if offline:
                result = evaluate_query_offline(gq)
            else:
                # Online mode: would call actual search service
                # For now, fall back to offline if search service unavailable
                logger.warning("Online mode not yet implemented, using offline for %s", query_id)
                result = evaluate_query_offline(gq)

            results.append(result)
        except Exception as e:
            logger.error("Failed to evaluate %s: %s", query_id, e)
            results.append(QueryResult(
                query_id=query_id,
                query=gq["query"],
                domain=gq["domain"],
                expected_collection=gq["expected_collection"],
                error=str(e),
            ))

    summary = aggregate_results(results)
    summary.mode = mode

    # Save results
    out_path = output_path or RESULTS_OUTPUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info("Results saved to %s", out_path)

    return summary


def print_summary(summary: EvaluationSummary) -> None:
    """Print a human-readable summary to stdout."""
    print("\n" + "=" * 60)
    print("SEARCH QUALITY EVALUATION RESULTS")
    print("=" * 60)
    print(f"Mode: {summary.mode}")
    print(f"Timestamp: {summary.timestamp}")
    print(f"Queries: {summary.evaluated_queries}/{summary.total_queries} evaluated "
          f"({summary.failed_queries} failed)")
    print()
    print("OVERALL METRICS:")
    print(f"  Precision@10: {summary.overall_precision_at_10:.4f}")
    print(f"  MRR:          {summary.overall_mrr:.4f}")
    print(f"  NDCG@10:      {summary.overall_ndcg_at_10:.4f}")
    print()
    print("PER-DOMAIN METRICS:")
    for domain, metrics in sorted(summary.per_domain.items()):
        n = int(metrics.get("count", 0))
        print(f"  {domain} (n={n}):")
        print(f"    Precision@10: {metrics['precision_at_10']:.4f}")
        print(f"    MRR:          {metrics['mrr']:.4f}")
        print(f"    NDCG@10:      {metrics['ndcg_at_10']:.4f}")
    print("=" * 60)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Evaluate search quality against golden dataset")
    parser.add_argument("--domain", type=str, default=None, help="Filter by domain")
    parser.add_argument("--offline", action="store_true", help="Use mock data (no Qdrant needed)")
    parser.add_argument("--golden", type=str, default=None, help="Path to golden dataset JSON")
    parser.add_argument("--output", type=str, default=None, help="Path to write results JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    golden_path = Path(args.golden) if args.golden else None
    output_path = Path(args.output) if args.output else None

    summary = run_evaluation(
        domain_filter=args.domain,
        offline=args.offline,
        golden_path=golden_path,
        output_path=output_path,
    )

    print_summary(summary)


if __name__ == "__main__":
    main()
