"""Tests for ReasoningGrader."""

from backend.services.rag.grading import (
    GradeDecision,
    GradingContext,
    ReasoningGrader,
    ReasoningStep,
)


class TestReasoningGrader:
    def test_no_steps_fail(self) -> None:
        ctx = GradingContext()
        result = ReasoningGrader().grade(ctx)
        assert result.decision == GradeDecision.FAIL
        assert result.score == 0.0

    def test_rich_reasoning_pass(self) -> None:
        ctx = GradingContext(
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="User asks about KITAS requirements for restaurant business"),
                ReasoningStep(step_type="observation", content="Found: KITAS requires RPTKA approval from Kemnaker with minimum capital IDR 10B for PMA"),
                ReasoningStep(step_type="thought", content="Need to check KBLI eligibility for restaurant (56101) under PMA scheme"),
                ReasoningStep(step_type="observation", content="KBLI 56101 is open for PMA with restaurant license from Dinas Pariwisata"),
            ],
        )
        result = ReasoningGrader().grade(ctx)
        assert result.decision == GradeDecision.PASS
        assert result.score >= 0.7

    def test_single_short_step_low(self) -> None:
        ctx = GradingContext(
            reasoning_steps=[ReasoningStep(content="ok")],
        )
        result = ReasoningGrader().grade(ctx)
        assert result.score < 0.5

    def test_thoughts_only_medium(self) -> None:
        """Only thoughts, no observations — partial diversity score."""
        ctx = GradingContext(
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="A" * 60),
                ReasoningStep(step_type="thought", content="B" * 60),
                ReasoningStep(step_type="thought", content="C" * 60),
            ],
        )
        result = ReasoningGrader().grade(ctx)
        # 0.15 (one type) + 0.3 (3 steps) + 0.35 (60 avg chars) = 0.80
        assert result.decision == GradeDecision.PASS

    def test_diverse_short_steps_retry(self) -> None:
        """Both types but very short content."""
        ctx = GradingContext(
            reasoning_steps=[
                ReasoningStep(step_type="thought", content="hmm"),
                ReasoningStep(step_type="observation", content="ok"),
            ],
        )
        result = ReasoningGrader().grade(ctx)
        # 0.35 (diverse) + 0.2 (2 steps) + 0.05 (short) = 0.60 → retry
        assert result.decision == GradeDecision.RETRY
