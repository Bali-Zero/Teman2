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

# Word-form durations: ("two months", "one year", "three days", etc.)
# Captures both cardinal words (one..twelve) and digit numbers, plus common
# variants (half, couple). This is intentionally narrow — the goal is to
# normalize durations, not to be a general NLP number parser.
_WORD_NUMBER_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "a": 1, "an": 1, "half": 0,
    # Indonesian cardinals (common in visa KB)
    "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
}
_WORD_NUMBER_PATTERN = re.compile(
    r"\b(" + "|".join(_WORD_NUMBER_MAP.keys()) + r")\s+"
    r"(days?|months?|years?|hari|bulan|tahun)\b",
    re.IGNORECASE,
)

# Normalize all durations to days so "60 days" and "two months" map to the
# same canonical value. Months = 30 days, years = 365 days (both standard
# heuristics; the grader only needs equality on normalized values).
_UNIT_TO_DAYS = {
    "day": 1,
    "hari": 1,
    "month": 30,
    "bulan": 30,
    "year": 365,
    "tahun": 365,
}

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


def _normalize_unit(raw: str) -> str:
    """Map a raw unit token to a canonical name, stripping plurals."""
    u = raw.lower().rstrip("s")
    # Map Indonesian to English for the canonical unit name
    return {
        "hari": "day",
        "bulan": "month",
        "tahun": "year",
    }.get(u, u)


def _normalize_value(value: int, unit: str) -> tuple[int, str]:
    """Normalize a (value, unit) pair.

    Durations are converted to days so "60 days" ≡ "2 months". Non-duration
    units (usd, idr, eur) are returned unchanged.
    """
    if unit in _UNIT_TO_DAYS:
        return (value * _UNIT_TO_DAYS[unit], "day")
    return (value, unit)


def _extract_numbers_with_unit(text: str) -> set[tuple[int, str]]:
    """Return {(value, unit)} tuples found in text.

    Durations are normalized to days. Word-form numbers like "two months"
    are recognized. Each (value, unit) pair is the NORMALIZED canonical
    form — the caller compares equality of normalized values directly.
    """
    out: set[tuple[int, str]] = set()

    # Digit + unit
    for m in _NUMBER_PATTERN.finditer(text):
        try:
            raw_value = int(m.group(1))
            unit = _normalize_unit(m.group(2))
            out.add(_normalize_value(raw_value, unit))
        except (ValueError, IndexError):
            continue

    # Word + duration-unit ("two months", "satu tahun")
    for m in _WORD_NUMBER_PATTERN.finditer(text):
        word = m.group(1).lower()
        unit = _normalize_unit(m.group(2))
        value = _WORD_NUMBER_MAP.get(word)
        if value is None:
            continue
        out.add(_normalize_value(value, unit))

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


# Relative tolerance when comparing normalized durations. 12 months and
# 1 year differ by ~1.4% under our 30-day/365-day approximation — they
# are the same duration in practice. 2 months and 90 days differ by ~50%.
# 5% tolerance cleanly separates the two cases.
_DURATION_TOLERANCE = 0.05


def _values_match(a: int, b: int, unit: str) -> bool:
    """Return True if a and b are equivalent within the unit's tolerance."""
    if a == b:
        return True
    if unit == "day":
        # Durations: allow 5% slack to absorb month=30 vs year=365 rounding
        larger = max(a, b)
        if larger == 0:
            return False
        return abs(a - b) / larger <= _DURATION_TOLERANCE
    return False


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
        prior_same_unit = [p_val for p_val, p_unit in prior if p_unit == c_unit]
        if not prior_same_unit:
            continue
        total += 1
        if not any(_values_match(c_val, p_val, c_unit) for p_val in prior_same_unit):
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
