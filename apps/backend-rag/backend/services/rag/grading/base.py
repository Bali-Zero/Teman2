"""BaseGrader ABC — common grading logic with fail-fast support.

Threshold hierarchy:
  score >= pass_threshold     → PASS  (continue to next node)
  score >= fail_fast_threshold → RETRY (loop back, with retry_hint)
  score < fail_fast_threshold  → FAIL  (skip downstream nodes)

Ported from apps/graph-engine/src/nuzantara_graph/graders/base.py
Adapted: structlog → logging, nuzantara_schemas → local schemas, GraphState → GradingContext
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from backend.services.rag.grading.context import GradingContext
from backend.services.rag.grading.schemas import GradeDecision, GradeResult

logger = logging.getLogger(__name__)


class BaseGrader(ABC):
    """Abstract base for all grader nodes.

    Subclasses implement `_evaluate()` which returns (score, reason, retry_hint).
    The base class handles decision logic and state mutation.
    """

    grader_name: str = "base"
    pass_threshold: float = 0.7
    fail_fast_threshold: float = 0.2

    @abstractmethod
    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        """Evaluate the context and return (score, reason, retry_hint).

        Args:
            ctx: Grading context with answer, documents, reasoning, etc.

        Returns:
            (score, reason, retry_hint) where:
              - score: 0.0-1.0 quality score
              - reason: human-readable explanation
              - retry_hint: guidance for the retried node (empty if PASS)
        """
        ...

    def grade(self, ctx: GradingContext) -> GradeResult:
        """Run evaluation and produce a GradeResult with decision."""
        score, reason, retry_hint = self._evaluate(ctx)

        # Clamp score
        score = max(0.0, min(1.0, score))

        if score >= self.pass_threshold:
            decision = GradeDecision.PASS
        elif score >= self.fail_fast_threshold:
            decision = GradeDecision.RETRY
        else:
            decision = GradeDecision.FAIL

        result = GradeResult(
            grader=self.grader_name,
            decision=decision,
            score=score,
            reason=reason,
            retry_hint=retry_hint if decision == GradeDecision.RETRY else "",
        )

        logger.info(
            "grade_result: grader=%s decision=%s score=%.3f reason=%s",
            self.grader_name,
            decision,
            score,
            reason[:100],
        )

        return result
