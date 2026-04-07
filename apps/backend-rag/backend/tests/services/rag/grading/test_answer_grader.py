"""Tests for AnswerGrader."""

from backend.services.rag.grading import (
    AnswerGrader,
    GradeDecision,
    GradingContext,
)


class TestAnswerGrader:
    def test_empty_answer_fail(self) -> None:
        ctx = GradingContext(answer="")
        result = AnswerGrader().grade(ctx)
        assert result.decision == GradeDecision.FAIL
        assert result.score == 0.0

    def test_good_answer_pass(self) -> None:
        ctx = GradingContext(
            answer="A" * 250,
            sources=[{"title": "source1"}],
            confidence_overall=0.8,
        )
        result = AnswerGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS

    def test_short_answer_low_confidence_retry(self) -> None:
        ctx = GradingContext(
            answer="Short answer here.",
            sources=[],
            confidence_overall=0.3,
        )
        result = AnswerGrader().grade(ctx)
        assert result.decision in (GradeDecision.RETRY, GradeDecision.FAIL)
        assert result.score < 0.7

    def test_refusal_penalized(self) -> None:
        ctx = GradingContext(
            answer="I'm sorry, I cannot answer this question. Unable to find relevant information.",
            sources=[{"title": "src"}],
            confidence_overall=0.6,
        )
        result = AnswerGrader().grade(ctx)
        # Refusal should lower score
        assert result.score < 0.8

    def test_long_confident_no_sources_medium(self) -> None:
        """Long answer with high confidence but no sources."""
        ctx = GradingContext(
            answer="B" * 300,
            sources=[],
            confidence_overall=0.9,
        )
        result = AnswerGrader().grade(ctx)
        # 0.3 (length) + 0.05 (no sources) + 0.3 (high conf) + 0.2 (no refusal) = 0.85
        assert result.decision == GradeDecision.PASS
