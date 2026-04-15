"""Self-RAG Grader — post-retrieval quality gate.

Evaluates retrieved documents BEFORE they enter the ReAct reasoning loop.
Decides if context is sufficient for high-quality generation, or if
additional retrieval strategies (HyDE, broader search) should be triggered.

Decisions:
  PASS  → Retrieved docs are sufficient. Proceed to reasoning.
  RETRY → Docs are mediocre. Trigger HyDE expansion or broader search.
  FAIL  → Docs are garbage or absent. Fall back to disclaimer.

# Organo: backend-rag/grading → produce GradeResult → consuma da orchestrator_core
"""

from __future__ import annotations

import logging

from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext

logger = logging.getLogger(__name__)

# Content length thresholds
_MIN_USEFUL_CONTENT_LEN = 50  # chars — below this, doc is trivially short
_GOOD_CONTENT_LEN = 100  # chars — above this, doc has substance


class SelfRAGGrader(BaseGrader):
    """Grade retrieved documents for sufficiency before reasoning."""

    grader_name = "self_rag"
    pass_threshold = 0.5
    fail_fast_threshold = 0.15

    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        docs = ctx.retrieved_documents

        if not docs:
            return 0.0, "No documents retrieved", ""

        # ── Score component 1: Relevance scores (60% weight) ──
        all_scores = [d.score for d in docs]
        top_scores = sorted(all_scores, reverse=True)[:3]
        top_avg = sum(top_scores) / len(top_scores) if top_scores else 0.0
        overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
        relevance = top_avg * 0.6 + overall_avg * 0.4

        # ── Score component 2: Content substance (40% weight) ──
        content_lengths = [len(d.content.strip()) for d in docs]
        useful_docs = sum(1 for cl in content_lengths if cl >= _MIN_USEFUL_CONTENT_LEN)
        substantial_docs = sum(1 for cl in content_lengths if cl >= _GOOD_CONTENT_LEN)

        if len(docs) > 0:
            useful_ratio = useful_docs / len(docs)
            substantial_ratio = substantial_docs / len(docs)
        else:
            useful_ratio = 0.0
            substantial_ratio = 0.0

        content_score = useful_ratio * 0.5 + substantial_ratio * 0.5

        # ── Combined score ──
        combined = relevance * 0.6 + content_score * 0.4

        if combined < self.fail_fast_threshold:
            reason = (
                f"Retrieval insufficient (score={combined:.2f}). "
                f"Top avg={top_avg:.2f}, {useful_docs}/{len(docs)} docs useful."
            )
            return combined, reason, ""

        if combined < self.pass_threshold:
            reason = (
                f"Retrieval marginal (score={combined:.2f}). "
                f"Top avg={top_avg:.2f}, {substantial_docs}/{len(docs)} substantial."
            )
            return combined, reason, "trigger_hyde"

        reason = (
            f"Retrieval sufficient (score={combined:.2f}). "
            f"{len(docs)} docs, top avg={top_avg:.2f}, "
            f"{substantial_docs}/{len(docs)} substantial."
        )
        return combined, reason, ""
