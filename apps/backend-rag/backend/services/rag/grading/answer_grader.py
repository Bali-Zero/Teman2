"""Answer grader — evaluates synthesized answer quality."""

from __future__ import annotations

import logging

from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext

logger = logging.getLogger(__name__)

_REFUSAL_MARKERS = [
    "unable to", "cannot answer", "i don't know", "non riesco",
    "i'm not sure", "non sono sicuro", "saya tidak bisa",
]


class AnswerGrader(BaseGrader):
    grader_name = "answer"
    pass_threshold = 0.7
    fail_fast_threshold = 0.2

    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        answer = ctx.answer

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
        if ctx.sources:
            score += 0.2
        else:
            score += 0.05

        # Confidence check
        conf = ctx.confidence_overall
        if conf >= 0.7:
            score += 0.3
        elif conf >= 0.4:
            score += 0.15
        else:
            score += 0.05

        # Not a refusal/error message
        is_refusal = any(m in answer.lower() for m in _REFUSAL_MARKERS)
        if not is_refusal:
            score += 0.2

        if score < self.fail_fast_threshold:
            return score, f"Answer critically poor (len={answer_len}, conf={conf:.2f})", ""

        if score < self.pass_threshold:
            hint = "Provide a more complete answer with specific details and source citations"
            return score, f"Answer needs improvement (score={score:.2f})", hint

        return score, f"Good answer (len={answer_len}, conf={conf:.2f}, sources={len(ctx.sources)})", ""
