"""Contradiction grader for visa planner evidence.

NOT a BaseGrader subclass — those write to state.grades, which the main
graph consumes. Contradiction grading is planner-internal and should not
bleed into the main flow.

Heuristic: combines
  1. Direct negation flip (X vs "not X") on overlapping token sets
  2. Number disagreement on the same unit (e.g. "30 days" vs "60 days")

Returns a score in [0, 1]. Score > 0.4 is treated as a genuine
contradiction worth re-planning.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from nuzantara_graph.subgraphs.visa.types import NodeEvidence

logger = structlog.get_logger()

_NUMBER_PATTERN = re.compile(
    r"(\d+)\s*(days?|months?|years?|usd|idr|eur)",
    re.IGNORECASE,
)

_NEGATION_MARKERS = (
    "not ",
    "no ",
    "never ",
    "cannot ",
    "can't ",
    "tidak ",
    "bukan ",
)

_COMMON_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "have",
    "will",
    "about",
    "would",
    "could",
    "should",
    "their",
    "there",
    "which",
    "where",
    "after",
    "before",
    "other",
    "because",
    "through",
    "between",
    "under",
    "yang",
    "dari",
    "dalam",
    "dengan",
}


def _extract_numbers_with_unit(text: str) -> set[tuple[int, str]]:
    """Return {(value, unit)} tuples found in text."""
    out: set[tuple[int, str]] = set()
    for m in _NUMBER_PATTERN.finditer(text):
        try:
            out.add((int(m.group(1)), m.group(2).lower().rstrip("s")))
        except (ValueError, IndexError):
            continue
    return out


def _significant_tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"\w{5,}", text.lower())
        if t not in _COMMON_WORDS
    }


def _has_negation_flip(a: str, b: str) -> bool:
    """Detect whether a and b express opposite polarity on overlapping terms."""
    a_low = a.lower()
    b_low = b.lower()

    a_negated = any(marker in a_low for marker in _NEGATION_MARKERS)
    b_negated = any(marker in b_low for marker in _NEGATION_MARKERS)

    if a_negated == b_negated:
        return False

    overlap = len(_significant_tokens(a) & _significant_tokens(b))
    return overlap >= 2


def _number_disagreement_score(
    current: set[tuple[int, str]],
    prior: set[tuple[int, str]],
) -> float:
    """Return 0..1 indicating disagreement on numeric claims with the same unit."""
    if not current or not prior:
        return 0.0

    disagreements = 0
    total = 0
    for c_val, c_unit in current:
        prior_same_unit = {p_val for p_val, p_unit in prior if p_unit == c_unit}
        if not prior_same_unit:
            continue
        total += 1
        if c_val not in prior_same_unit:
            disagreements += 1

    if total == 0:
        return 0.0
    return disagreements / total


class ContradictionGrader:
    """Heuristic contradiction detector for visa planner evidence."""

    def __init__(
        self,
        negation_weight: float = 0.6,
        number_weight: float = 0.6,
    ) -> None:
        self.negation_weight = negation_weight
        self.number_weight = number_weight

    def score(
        self,
        node_evidence: "NodeEvidence",
        prior_evidence: list["NodeEvidence"],
    ) -> float:
        """Return contradiction score in [0, 1]."""
        if not prior_evidence:
            return 0.0

        current_text = " ".join(
            [node_evidence.answer_fragment]
            + [c.content for c in node_evidence.chunks]
        )
        current_numbers = _extract_numbers_with_unit(current_text)

        max_score = 0.0
        for prior in prior_evidence:
            prior_text = " ".join(
                [prior.answer_fragment] + [c.content for c in prior.chunks]
            )
            prior_numbers = _extract_numbers_with_unit(prior_text)

            num_score = _number_disagreement_score(current_numbers, prior_numbers)
            neg_flip = _has_negation_flip(current_text, prior_text)

            combined = num_score * self.number_weight
            if neg_flip:
                combined += self.negation_weight
            max_score = max(max_score, min(1.0, combined))

        logger.debug(
            "contradiction_score",
            score=round(max_score, 3),
            sub_q=node_evidence.sub_question.idx,
        )
        return max_score
