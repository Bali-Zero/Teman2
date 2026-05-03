"""Answer grader — evaluates synthesized answer quality."""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.graders.base import BaseGrader
from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState

logger = structlog.get_logger()


class AnswerGrader(BaseGrader):
    grader_name = "answer"
    pass_threshold = 0.7
    fail_fast_threshold = 0.2

    def _evaluate(self, state: GraphState) -> tuple[float, str, str]:
        answer = state.answer

        # No answer
        if not answer or not answer.strip():
            return 0.0, "Empty answer", ""

        score = 0.0
        answer_len = len(answer)

        # Length (minimum useful response)
        if answer_len >= 200:
            score += 0.3
        elif answer_len >= 50:
            score += 0.2
        else:
            score += 0.05

        # Has sources cited
        if state.sources:
            score += 0.2
        else:
            score += 0.05

        # Confidence check (from synthesize node's self-assessment)
        conf = state.confidence.overall
        if conf >= 0.7:
            score += 0.3
        elif conf >= 0.4:
            score += 0.15
        else:
            score += 0.05

        # Not a refusal/error message
        refusal_markers = ["unable to", "cannot answer", "i don't know", "non riesco"]
        is_refusal = any(m in answer.lower() for m in refusal_markers)
        if not is_refusal:
            score += 0.2
        else:
            score += 0.0

        if score < self.fail_fast_threshold:
            return score, f"Answer critically poor (len={answer_len}, conf={conf:.2f})", ""

        if score < self.pass_threshold:
            hint = "Provide a more complete answer with specific details and source citations"
            return score, f"Answer needs improvement (score={score:.2f})", hint

        return score, f"Good answer (len={answer_len}, conf={conf:.2f}, sources={len(state.sources)})", ""


def make_answer_grader(services: Services | None = None):
    """Factory that creates an answer grader node."""
    grader = AnswerGrader()

    async def answer_grader_node(state: GraphState) -> dict[str, Any]:
        result = grader.grade(state)
        grades = list(state.grades) + [result]

        updates: dict[str, Any] = {
            "grades": grades,
            "current_node": "grade_answer",
        }

        if result.decision.value == "retry":
            updates["correction_count"] = min(state.correction_count + 1, state.max_corrections)

        return updates

    return answer_grader_node
