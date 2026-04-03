"""CRAG-Light — fast keyword-based relevance gate.

Runs after each search dispatch inside the orchestrator loop.
Pure keyword overlap, no LLM calls. Sub-millisecond latency.

Actions:
    PASS      — sources are relevant enough, proceed.
    RETRY     — marginal overlap, reformulate the query and re-search.
    ESCALATE  — sources are irrelevant or absent, try a different search strategy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_MIN_WORD_LEN = 3
_MIN_SUBSTANCE_LEN = 100


@dataclass(frozen=True)
class CragDecision:
    """Immutable verdict from the relevance gate."""

    action: str  # PASS | RETRY | ESCALATE
    reason: str
    relevance_score: float


def _extract_words(text: str) -> set[str]:
    """Extract lowercase words with >= _MIN_WORD_LEN characters."""
    return {
        w.lower()
        for w in _WORD_RE.findall(text)
        if len(w) >= _MIN_WORD_LEN
    }


def crag_evaluate(
    sub_question: str,
    sources_content: list[str],
    pass_threshold: float = 0.30,
    retry_threshold: float = 0.15,
) -> CragDecision:
    """Evaluate whether search results are relevant to the sub-question.

    Args:
        sub_question: The query / sub-question that was searched.
        sources_content: Text content of each retrieved source.
        pass_threshold: Minimum keyword overlap ratio to PASS.
        retry_threshold: Minimum keyword overlap ratio to RETRY (below → ESCALATE).

    Returns:
        CragDecision with action, reason, and relevance_score.
    """
    # --- empty / whitespace-only sources → immediate ESCALATE ---------------
    combined = " ".join(sources_content).strip()
    if not combined:
        return CragDecision(
            action="ESCALATE",
            reason="no sources",
            relevance_score=0.0,
        )

    # --- extract keyword sets -----------------------------------------------
    question_words = _extract_words(sub_question)
    if not question_words:
        return CragDecision(
            action="ESCALATE",
            reason="no extractable keywords in question",
            relevance_score=0.0,
        )

    content_words = _extract_words(combined)
    intersection = question_words & content_words
    overlap = len(intersection) / len(question_words)

    # --- substance check: combined content > 100 chars ----------------------
    has_substance = len(combined) >= _MIN_SUBSTANCE_LEN

    # --- decision -----------------------------------------------------------
    if overlap >= pass_threshold and has_substance:
        return CragDecision(
            action="PASS",
            reason=f"keyword overlap {overlap:.2f} with substance",
            relevance_score=overlap,
        )

    if overlap >= retry_threshold:
        reason = (
            f"keyword overlap {overlap:.2f}, "
            f"{'no substance' if not has_substance else 'below pass threshold'}"
        )
        return CragDecision(
            action="RETRY",
            reason=f"reformulate query — {reason}",
            relevance_score=overlap,
        )

    return CragDecision(
        action="ESCALATE",
        reason=f"sources irrelevant — keyword overlap {overlap:.2f}",
        relevance_score=overlap,
    )
