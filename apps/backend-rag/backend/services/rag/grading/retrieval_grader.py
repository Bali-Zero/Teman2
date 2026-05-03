"""Retrieval grader — evaluates retrieved document quality.

Fail-fast: if avg relevance < 0.2, documents are garbage — skip reasoning
entirely and ask the user to rephrase.
"""

from __future__ import annotations

import logging

from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext

logger = logging.getLogger(__name__)


class RetrievalGrader(BaseGrader):
    grader_name = "retrieval"
    pass_threshold = 0.7
    fail_fast_threshold = 0.2

    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        docs = ctx.retrieved_documents

        # No documents at all → fail fast
        if not docs:
            return 0.0, "No documents retrieved", "Broaden the search query"

        # Average relevance score
        avg_score = sum(d.score for d in docs) / len(docs)

        # Top-k relevance (best 3 docs)
        top_scores = sorted([d.score for d in docs], reverse=True)[:3]
        top_avg = sum(top_scores) / len(top_scores)

        # Combined: weight top docs more (60% top, 40% overall)
        combined = top_avg * 0.6 + avg_score * 0.4

        if combined < self.fail_fast_threshold:
            reason = (
                f"Retrieval quality critically low (score={combined:.2f}). "
                f"Top docs avg={top_avg:.2f}, overall avg={avg_score:.2f}. "
                f"{len(docs)} docs retrieved but none relevant."
            )
            return combined, reason, ""

        if combined < self.pass_threshold:
            reason = (
                f"Retrieval below threshold (score={combined:.2f}). "
                f"Top docs avg={top_avg:.2f}."
            )
            hint = "Try more specific keywords or different entity combinations"
            return combined, reason, hint

        reason = f"Good retrieval (score={combined:.2f}), {len(docs)} docs, top avg={top_avg:.2f}"
        return combined, reason, ""
