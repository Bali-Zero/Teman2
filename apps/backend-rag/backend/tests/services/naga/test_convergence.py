"""Tests for the Naga convergence detector.

Verifies that check_convergence correctly decides when the research loop
should stop (CONVERGED), continue (ITERATE), or give up (TIMEOUT).
"""

from __future__ import annotations

import pytest

from backend.services.naga.quality.convergence import (
    ConvergenceResult,
    check_convergence,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def three_questions() -> list[str]:
    """Three sample sub-questions for a typical research session."""
    return [
        "What are the KITAS visa requirements for 2026?",
        "How long does the KITAS application process take?",
        "What is the cost of a KITAS visa?",
    ]


# ---------------------------------------------------------------------------
# ConvergenceResult dataclass
# ---------------------------------------------------------------------------

class TestConvergenceResult:
    """Verify ConvergenceResult is frozen and stores all fields."""

    def test_frozen_immutability(self) -> None:
        result = ConvergenceResult(
            decision="CONVERGED",
            reason="Coverage met, novelty low",
            coverage=0.90,
            novelty=0.05,
            gap_questions=(),
        )
        with pytest.raises(AttributeError):
            result.decision = "ITERATE"  # type: ignore[misc]

    def test_frozen_gap_questions_tuple(self) -> None:
        result = ConvergenceResult(
            decision="ITERATE",
            reason="Low coverage",
            coverage=0.33,
            novelty=0.80,
            gap_questions=("Q1", "Q2"),
        )
        assert isinstance(result.gap_questions, tuple)
        assert result.gap_questions == ("Q1", "Q2")

    def test_all_fields_accessible(self) -> None:
        result = ConvergenceResult(
            decision="TIMEOUT",
            reason="Budget exhausted",
            coverage=0.60,
            novelty=0.30,
            gap_questions=("Q1",),
        )
        assert result.decision == "TIMEOUT"
        assert result.reason == "Budget exhausted"
        assert result.coverage == 0.60
        assert result.novelty == 0.30
        assert result.gap_questions == ("Q1",)


# ---------------------------------------------------------------------------
# High coverage + low novelty -> CONVERGED
# ---------------------------------------------------------------------------

class TestConverged:
    """When coverage is high and novelty is low, the loop should stop."""

    def test_high_coverage_low_novelty(self, three_questions: list[str]) -> None:
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question={
                three_questions[0]: 5,
                three_questions[1]: 3,
                three_questions[2]: 2,
            },
            new_claims_this_iteration=1,
            total_claims=20,
            iteration=3,
            budget_can_search=True,
        )
        assert result.decision == "CONVERGED"
        assert result.coverage == 1.0
        assert result.novelty == pytest.approx(0.05)
        assert result.gap_questions == ()

    def test_converged_at_exact_thresholds(self) -> None:
        """Coverage exactly at 0.80 and novelty exactly below 0.10."""
        questions = ["Q1", "Q2", "Q3", "Q4", "Q5"]
        result = check_convergence(
            sub_questions=questions,
            claims_per_question={
                "Q1": 2,
                "Q2": 1,
                "Q3": 3,
                "Q4": 1,
                # Q5 has 0 claims -> coverage = 4/5 = 0.80
            },
            new_claims_this_iteration=0,
            total_claims=10,
            iteration=2,
            budget_can_search=True,
        )
        assert result.decision == "CONVERGED"
        assert result.coverage == pytest.approx(0.80)
        assert result.novelty == pytest.approx(0.0)

    def test_all_questions_covered(self, three_questions: list[str]) -> None:
        """When every sub-question has at least 1 claim, coverage = 1.0."""
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question=dict.fromkeys(three_questions, 1),
            new_claims_this_iteration=0,
            total_claims=5,
            iteration=2,
            budget_can_search=True,
        )
        assert result.decision == "CONVERGED"
        assert result.coverage == 1.0
        assert result.gap_questions == ()


# ---------------------------------------------------------------------------
# Low coverage + budget remaining -> ITERATE with gaps
# ---------------------------------------------------------------------------

class TestIterate:
    """When coverage is low and budget remains, the loop must continue."""

    def test_low_coverage_returns_iterate(self, three_questions: list[str]) -> None:
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question={three_questions[0]: 3},
            new_claims_this_iteration=3,
            total_claims=3,
            iteration=1,
            budget_can_search=True,
        )
        assert result.decision == "ITERATE"
        assert result.coverage == pytest.approx(1.0 / 3.0)

    def test_iterate_returns_gap_questions(self, three_questions: list[str]) -> None:
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question={three_questions[0]: 5},
            new_claims_this_iteration=5,
            total_claims=5,
            iteration=1,
            budget_can_search=True,
        )
        assert result.decision == "ITERATE"
        assert set(result.gap_questions) == {three_questions[1], three_questions[2]}

    def test_high_novelty_forces_iterate(self, three_questions: list[str]) -> None:
        """Even with high coverage, if novelty is high we should keep going."""
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question=dict.fromkeys(three_questions, 2),
            new_claims_this_iteration=5,
            total_claims=6,
            iteration=1,
            budget_can_search=True,
        )
        assert result.decision == "ITERATE"
        assert result.novelty == pytest.approx(5.0 / 6.0)


# ---------------------------------------------------------------------------
# Budget exhausted -> TIMEOUT
# ---------------------------------------------------------------------------

class TestTimeout:
    """When budget_can_search is False the loop must stop immediately."""

    def test_budget_exhausted(self, three_questions: list[str]) -> None:
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question={three_questions[0]: 2},
            new_claims_this_iteration=2,
            total_claims=2,
            iteration=5,
            budget_can_search=False,
        )
        assert result.decision == "TIMEOUT"
        assert "budget" in result.reason.lower() or "exhausted" in result.reason.lower()

    def test_timeout_even_with_low_coverage(self, three_questions: list[str]) -> None:
        """Budget exhausted trumps low coverage -- must stop."""
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question={},
            new_claims_this_iteration=0,
            total_claims=0,
            iteration=10,
            budget_can_search=False,
        )
        assert result.decision == "TIMEOUT"
        assert result.coverage == 0.0


# ---------------------------------------------------------------------------
# No claims yet -> novelty = 1.0, ITERATE
# ---------------------------------------------------------------------------

class TestNoClaims:
    """When the loop starts and no claims exist, novelty should be 1.0."""

    def test_no_claims_novelty_one(self, three_questions: list[str]) -> None:
        result = check_convergence(
            sub_questions=three_questions,
            claims_per_question={},
            new_claims_this_iteration=0,
            total_claims=0,
            iteration=0,
            budget_can_search=True,
        )
        assert result.novelty == 1.0
        assert result.decision == "ITERATE"
        assert result.coverage == 0.0


# ---------------------------------------------------------------------------
# Edge: empty sub_questions -> CONVERGED (nothing to cover)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases that arise from degenerate inputs."""

    def test_empty_sub_questions_converged(self) -> None:
        result = check_convergence(
            sub_questions=[],
            claims_per_question={},
            new_claims_this_iteration=0,
            total_claims=0,
            iteration=0,
            budget_can_search=True,
        )
        assert result.decision == "CONVERGED"
        assert result.coverage == 1.0  # vacuous truth
        assert result.gap_questions == ()

    def test_custom_thresholds(self) -> None:
        """Custom thresholds override defaults."""
        questions = ["Q1", "Q2"]
        result = check_convergence(
            sub_questions=questions,
            claims_per_question={"Q1": 1},
            new_claims_this_iteration=0,
            total_claims=5,
            iteration=2,
            budget_can_search=True,
            coverage_threshold=0.50,  # 1/2 = 0.50 meets this
            novelty_threshold=0.05,
        )
        assert result.decision == "CONVERGED"
        assert result.coverage == 0.5

    def test_single_question_covered(self) -> None:
        result = check_convergence(
            sub_questions=["Only question"],
            claims_per_question={"Only question": 3},
            new_claims_this_iteration=0,
            total_claims=3,
            iteration=1,
            budget_can_search=True,
        )
        assert result.decision == "CONVERGED"
        assert result.coverage == 1.0

    def test_single_question_not_covered(self) -> None:
        result = check_convergence(
            sub_questions=["Only question"],
            claims_per_question={},
            new_claims_this_iteration=0,
            total_claims=0,
            iteration=0,
            budget_can_search=True,
        )
        assert result.decision == "ITERATE"
        assert result.coverage == 0.0
        assert result.gap_questions == ("Only question",)
