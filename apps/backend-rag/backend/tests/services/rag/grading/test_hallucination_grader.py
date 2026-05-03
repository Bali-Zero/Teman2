"""Tests for HallucinationGrader."""

import pytest

from backend.services.rag.grading import (
    GradeDecision,
    GradingContext,
    HallucinationGrader,
    RetrievedDoc,
)
from backend.services.rag.grading.hallucination_grader import grade_with_llm_verification


class TestHallucinationGrader:
    def test_empty_answer_passes(self) -> None:
        ctx = GradingContext(answer="")
        result = HallucinationGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS
        assert result.score == 1.0

    def test_no_sources_low_score(self) -> None:
        ctx = GradingContext(answer="KITAS costs USD 2500 and requires RPTKA approval.")
        result = HallucinationGrader().grade(ctx)
        assert result.score <= 0.2

    def test_well_grounded_answer(self) -> None:
        ctx = GradingContext(
            answer="KITAS processing requires RPTKA approval and sponsor company",
            sources=[{"title": "visa_oracle"}],
            retrieved_documents=[
                RetrievedDoc(
                    content="KITAS processing requires RPTKA approval. "
                    "A sponsor company (PT) must file the application.",
                    score=0.9,
                ),
            ],
        )
        result = HallucinationGrader().grade(ctx)
        # Most answer terms should be in source
        assert result.score >= 0.5

    def test_fabricated_answer_fails(self) -> None:
        ctx = GradingContext(
            answer="The quantum blockchain protocol enables instant KITAS through satellite uplink",
            retrieved_documents=[
                RetrievedDoc(content="KITAS is a stay permit for foreign workers in Indonesia", score=0.3),
            ],
        )
        result = HallucinationGrader().grade(ctx)
        assert result.score < 0.5

    def test_strict_threshold(self) -> None:
        """Hallucination grader uses 0.8 pass threshold (stricter than default 0.7)."""
        grader = HallucinationGrader()
        assert grader.pass_threshold == 0.8


@pytest.mark.asyncio
async def test_grade_with_llm_no_gateway() -> None:
    """Without LLM gateway, falls back to heuristic only."""
    ctx = GradingContext(
        answer="Test answer about KITAS requirements",
        retrieved_documents=[
            RetrievedDoc(content="KITAS requirements include sponsor and RPTKA", score=0.8),
        ],
    )
    result = await grade_with_llm_verification(ctx, llm_gateway=None)
    # Should still produce a valid result from heuristic
    assert result.grader == "hallucination"
    assert 0.0 <= result.score <= 1.0
