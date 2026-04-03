"""Convergence detector for the Naga research loop.

Decides whether the research loop should stop (CONVERGED), continue
(ITERATE), or give up (TIMEOUT) based on coverage, novelty, and budget.

The default thresholds (coverage=0.80, novelty=0.10) come from NagaConfig
and are passed through by the orchestrator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConvergenceResult:
    """Immutable outcome of a convergence check.

    Attributes:
        decision: One of CONVERGED, ITERATE, TIMEOUT.
        reason: Human-readable explanation of the decision.
        coverage: Fraction of sub-questions with at least one claim.
        novelty: Fraction of total claims that are new this iteration.
        gap_questions: Sub-questions that still have zero claims.
    """

    decision: str  # CONVERGED | ITERATE | TIMEOUT
    reason: str
    coverage: float
    novelty: float
    gap_questions: tuple[str, ...]


def check_convergence(
    sub_questions: list[str],
    claims_per_question: dict[str, int],
    new_claims_this_iteration: int,
    total_claims: int,
    iteration: int,
    budget_can_search: bool,
    coverage_threshold: float = 0.80,
    novelty_threshold: float = 0.10,
) -> ConvergenceResult:
    """Decide whether to stop, continue, or timeout the research loop.

    Args:
        sub_questions: The decomposed sub-questions being researched.
        claims_per_question: Number of verified claims per sub-question.
        new_claims_this_iteration: Claims added in the latest iteration.
        total_claims: Cumulative claim count across all iterations.
        iteration: Current iteration index (0-based).
        budget_can_search: Whether the budget allows another search round.
        coverage_threshold: Minimum coverage to declare convergence.
        novelty_threshold: Maximum novelty to declare convergence.

    Returns:
        ConvergenceResult with decision, reason, metrics, and gap questions.
    """
    # -- Metrics ----------------------------------------------------------
    if not sub_questions:
        coverage = 1.0
        gap_questions: tuple[str, ...] = ()
    else:
        covered = sum(
            1 for q in sub_questions if claims_per_question.get(q, 0) >= 1
        )
        coverage = covered / len(sub_questions)
        gap_questions = tuple(
            q for q in sub_questions if claims_per_question.get(q, 0) == 0
        )

    novelty = (
        new_claims_this_iteration / total_claims if total_claims > 0 else 1.0
    )

    # -- Decision logic ---------------------------------------------------
    # 0. Empty sub-questions -> CONVERGED (nothing to cover)
    if not sub_questions:
        reason = "No sub-questions to cover — vacuously converged."
        logger.info("Convergence: CONVERGED — %s", reason)
        return ConvergenceResult(
            decision="CONVERGED",
            reason=reason,
            coverage=coverage,
            novelty=novelty,
            gap_questions=gap_questions,
        )

    # 1. Budget exhausted -> TIMEOUT
    if not budget_can_search:
        reason = (
            f"Search budget exhausted after iteration {iteration}. "
            f"Coverage {coverage:.0%}, {len(gap_questions)} gap(s) remain."
        )
        logger.info("Convergence: TIMEOUT — %s", reason)
        return ConvergenceResult(
            decision="TIMEOUT",
            reason=reason,
            coverage=coverage,
            novelty=novelty,
            gap_questions=gap_questions,
        )

    # 2. Coverage >= threshold AND novelty < threshold -> CONVERGED
    if coverage >= coverage_threshold and novelty < novelty_threshold:
        reason = (
            f"Coverage {coverage:.0%} >= {coverage_threshold:.0%} "
            f"and novelty {novelty:.0%} < {novelty_threshold:.0%}. "
            f"Research has converged after iteration {iteration}."
        )
        logger.info("Convergence: CONVERGED — %s", reason)
        return ConvergenceResult(
            decision="CONVERGED",
            reason=reason,
            coverage=coverage,
            novelty=novelty,
            gap_questions=gap_questions,
        )

    # 3. Otherwise -> ITERATE
    reason = (
        f"Coverage {coverage:.0%} or novelty {novelty:.0%} not at threshold. "
        f"{len(gap_questions)} gap question(s) remain."
    )
    logger.info("Convergence: ITERATE — %s", reason)
    return ConvergenceResult(
        decision="ITERATE",
        reason=reason,
        coverage=coverage,
        novelty=novelty,
        gap_questions=gap_questions,
    )
