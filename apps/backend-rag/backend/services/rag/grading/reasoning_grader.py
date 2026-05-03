"""Reasoning grader — evaluates Chain-of-Thought quality.

Fail-fast at <0.2: reasoning is incoherent/empty — skip synthesis.
"""

from __future__ import annotations

import logging

from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext

logger = logging.getLogger(__name__)


class ReasoningGrader(BaseGrader):
    grader_name = "reasoning"
    pass_threshold = 0.7
    fail_fast_threshold = 0.2

    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        steps = ctx.reasoning_steps

        # No reasoning at all
        if not steps:
            return 0.0, "No reasoning steps produced", ""

        # Factors
        step_count = len(steps)
        has_observations = any(s.step_type == "observation" for s in steps)
        has_thoughts = any(s.step_type == "thought" for s in steps)
        avg_length = sum(len(s.content) for s in steps) / step_count

        score = 0.0

        # Step diversity (thoughts + observations)
        if has_thoughts and has_observations:
            score += 0.35
        elif has_thoughts or has_observations:
            score += 0.15

        # Step count (diminishing returns)
        if step_count >= 3:
            score += 0.3
        elif step_count >= 2:
            score += 0.2
        else:
            score += 0.1

        # Content depth (avg chars per step)
        if avg_length >= 50:
            score += 0.35
        elif avg_length >= 20:
            score += 0.2
        else:
            score += 0.05

        if score < self.fail_fast_threshold:
            return score, f"Reasoning critically shallow ({step_count} steps, avg {avg_length:.0f} chars)", ""

        if score < self.pass_threshold:
            hint = "Produce more detailed observations grounded in source documents"
            return score, f"Reasoning needs improvement (score={score:.2f})", hint

        return score, f"Good reasoning ({step_count} steps, {avg_length:.0f} avg chars)", ""
