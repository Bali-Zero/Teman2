"""
Evaluation harness for politics KB hierarchical retrieval.

Metrics:
- nDCG@5: Normalized Discounted Cumulative Gain at rank 5
- Recall@5: Fraction of relevant documents retrieved in top 5

Loads seed queries from eval/seed_queries.jsonl.
Each query has: query, relevant_doc_ids, weak_label flag.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.kb.politics.hierarchical.retriever import HierarchicalRetriever, RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class EvalQuery:
    """A single evaluation query with ground truth."""

    query: str
    relevant_doc_ids: list[str]
    weak_label: bool = False
    query_type: str = ""
    language: str = "id"


@dataclass
class EvalResult:
    """Result of evaluating a single query."""

    query: str
    ndcg_at_5: float
    recall_at_5: float
    retrieved_ids: list[str]
    relevant_ids: list[str]
    weak_label: bool


@dataclass
class EvalSummary:
    """Aggregate evaluation metrics."""

    mean_ndcg_at_5: float
    mean_recall_at_5: float
    mean_ndcg_hard_labels: float
    mean_recall_hard_labels: float
    total_queries: int
    hard_label_queries: int
    weak_label_queries: int
    per_query: list[EvalResult]


def _dcg(relevances: list[float], k: int) -> float:
    """Discounted Cumulative Gain at rank k."""
    total = 0.0
    for i, rel in enumerate(relevances[:k]):
        total += rel / math.log2(i + 2)  # +2 because rank starts at 1
    return total


def _ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Normalized DCG at rank k.

    Binary relevance: 1 if retrieved doc is in relevant set, else 0.
    """
    relevances = [1.0 if rid in relevant_ids else 0.0 for rid in retrieved_ids[:k]]
    dcg = _dcg(relevances, k)

    # Ideal DCG: all relevant docs at top
    ideal_relevances = sorted(relevances, reverse=True)
    # Add remaining relevant docs that weren't retrieved
    remaining = min(k, len(relevant_ids)) - sum(ideal_relevances)
    if remaining > 0:
        ideal_relevances = [1.0] * min(k, len(relevant_ids))
    idcg = _dcg(ideal_relevances, k)

    return dcg / idcg if idcg > 0 else 0.0


def _recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Recall at rank k: fraction of relevant docs retrieved in top k."""
    if not relevant_ids:
        return 0.0
    retrieved_set = set(retrieved_ids[:k])
    hits = len(retrieved_set & relevant_ids)
    return hits / len(relevant_ids)


def load_eval_queries(path: Path) -> list[EvalQuery]:
    """Load evaluation queries from JSONL file.

    Args:
        path: Path to seed_queries.jsonl.

    Returns:
        List of EvalQuery objects.
    """
    queries: list[EvalQuery] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            queries.append(EvalQuery(
                query=obj["query"],
                relevant_doc_ids=obj.get("relevant_doc_ids", []),
                weak_label=obj.get("weak_label", False),
                query_type=obj.get("query_type", ""),
                language=obj.get("language", "id"),
            ))
    return queries


def evaluate(
    retriever: HierarchicalRetriever,
    queries: list[EvalQuery],
    k: int = 5,
) -> EvalSummary:
    """Run evaluation on all queries.

    Args:
        retriever: Configured HierarchicalRetriever instance.
        queries: List of EvalQuery with ground truth.
        k: Rank cutoff (default 5).

    Returns:
        EvalSummary with per-query and aggregate metrics.
    """
    per_query: list[EvalResult] = []

    for eq in queries:
        results: list[RetrievalResult] = retriever.retrieve(eq.query, parent_limit=k)
        retrieved_ids = [r.record_id for r in results]
        relevant_set = set(eq.relevant_doc_ids)

        ndcg = _ndcg_at_k(retrieved_ids, relevant_set, k)
        recall = _recall_at_k(retrieved_ids, relevant_set, k)

        per_query.append(EvalResult(
            query=eq.query,
            ndcg_at_5=round(ndcg, 4),
            recall_at_5=round(recall, 4),
            retrieved_ids=retrieved_ids,
            relevant_ids=eq.relevant_doc_ids,
            weak_label=eq.weak_label,
        ))

    # Aggregate
    all_ndcg = [r.ndcg_at_5 for r in per_query]
    all_recall = [r.recall_at_5 for r in per_query]

    hard = [r for r in per_query if not r.weak_label]
    hard_ndcg = [r.ndcg_at_5 for r in hard]
    hard_recall = [r.recall_at_5 for r in hard]

    weak_count = sum(1 for r in per_query if r.weak_label)

    return EvalSummary(
        mean_ndcg_at_5=round(sum(all_ndcg) / len(all_ndcg), 4) if all_ndcg else 0.0,
        mean_recall_at_5=round(sum(all_recall) / len(all_recall), 4) if all_recall else 0.0,
        mean_ndcg_hard_labels=round(sum(hard_ndcg) / len(hard_ndcg), 4) if hard_ndcg else 0.0,
        mean_recall_hard_labels=round(sum(hard_recall) / len(hard_recall), 4) if hard_recall else 0.0,
        total_queries=len(per_query),
        hard_label_queries=len(hard),
        weak_label_queries=weak_count,
        per_query=per_query,
    )
