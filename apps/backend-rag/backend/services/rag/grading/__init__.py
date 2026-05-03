"""RAG Grading Framework — quality gates for the retrieval-augmented generation pipeline.

Ported from apps/graph-engine graders, adapted for backend-rag orchestrator.

Usage:
    from backend.services.rag.grading import (
        GradingContext,
        RetrievalGrader,
        ReasoningGrader,
        AnswerGrader,
        HallucinationGrader,
        PricingGrader,
        GradeDecision,
        GradeResult,
    )

    ctx = GradingContext.from_search_results(results)
    grade = RetrievalGrader().grade(ctx)
    if grade.decision == GradeDecision.FAIL:
        return early_exit(grade.reason)
"""

from backend.services.rag.grading.answer_grader import AnswerGrader
from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext, ReasoningStep, RetrievedDoc
from backend.services.rag.grading.hallucination_grader import (
    HallucinationGrader,
    grade_with_llm_verification,
)
from backend.services.rag.grading.pricing_grader import PricingGrader, contains_pricing
from backend.services.rag.grading.reasoning_grader import ReasoningGrader
from backend.services.rag.grading.retrieval_grader import RetrievalGrader
from backend.services.rag.grading.schemas import (
    ConfidenceScores,
    GradeDecision,
    GradeResult,
)

__all__ = [
    "AnswerGrader",
    "BaseGrader",
    "ConfidenceScores",
    "GradeDecision",
    "GradeResult",
    "GradingContext",
    "HallucinationGrader",
    "PricingGrader",
    "ReasoningGrader",
    "ReasoningStep",
    "RetrievalGrader",
    "RetrievedDoc",
    "contains_pricing",
    "grade_with_llm_verification",
]
