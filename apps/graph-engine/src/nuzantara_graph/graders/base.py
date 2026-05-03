"""BaseGrader ABC — common grading logic with fail-fast support.

Threshold hierarchy:
  score >= pass_threshold     → PASS  (continue to next node)
  score >= fail_fast_threshold → RETRY (loop back, with retry_hint)
  score < fail_fast_threshold  → FAIL  (skip downstream nodes, go to synthesis)

Fail-fast means: if the retrieval is so poor (< 0.2) that reasoning over
garbage documents would waste tokens and produce hallucinations, we skip
straight to a polite "rephrase your question" answer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from nuzantara_schemas.grading import GradeDecision, GradeResult
from nuzantara_schemas.state import GraphState

logger = structlog.get_logger()


class BaseGrader(ABC):
    """Abstract base for all grader nodes.

    Subclasses implement `_evaluate()` which returns (score, reason, retry_hint).
    The base class handles decision logic and state mutation.
    """

    grader_name: str = "base"
    pass_threshold: float = 0.7
    fail_fast_threshold: float = 0.2

    @abstractmethod
    def _evaluate(self, state: GraphState) -> tuple[float, str, str]:
        """Evaluate the state and return (score, reason, retry_hint).

        Args:
            state: Current graph state to evaluate

        Returns:
            (score, reason, retry_hint) where:
              - score: 0.0-1.0 quality score
              - reason: human-readable explanation
              - retry_hint: guidance for the retried node (empty if PASS)
        """
        ...

    def grade(self, state: GraphState) -> GradeResult:
        """Run evaluation and produce a GradeResult with decision."""
        score, reason, retry_hint = self._evaluate(state)

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
            "grade_result",
            grader=self.grader_name,
            decision=decision,
            score=round(score, 3),
            reason=reason[:100],
        )

        return result
