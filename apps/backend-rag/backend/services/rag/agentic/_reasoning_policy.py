"""
Policy enforcement helpers for the ReAct reasoning engine.

Extracted from ``reasoning.py`` (refactor/split-reasoning) as pure,
stateless detectors so both the sync and streaming pipelines share the
same answer-content / tools-available logic without duplication.

The full tier1 / strict-abstain execution (which calls back into
``self._get_localized_stub`` and ``llm_gateway.send_message`` with 8+
parameters) intentionally stays in the engine methods — extracting it
would add more plumbing than it removes. The constants and predicates
live here so they're easy to tune in one place.

Public API:
    - PRICING_ANSWER_MARKERS: markers that indicate the LLM produced
      concrete pricing numbers in the final answer.
    - detect_pricing_data_in_answer: True if final answer contains any
      pricing marker (prices, IDR, juta, etc.). Bypasses evidence check.
    - detect_llm_has_tools: True if the LLM gateway has tools attached
      and can produce a tool-grounded answer.
    - should_apply_low_evidence_policy: True when the low-evidence
      override branch must run (answer exists, score below abstain
      threshold, not skip_rag, not trusted). Mirrors the predicate used
      identically in both sync and streaming pipelines.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PRICING_ANSWER_MARKERS: tuple[str, ...] = (
    "rp ",
    "rp.",
    "idr ",
    "usd ",
    "20.000.000",
    "15.000.000",
    "10.000.000",
    "5.000.000",
    "juta",
)


def detect_pricing_data_in_answer(final_answer: str | None) -> bool:
    """Return True if final_answer contains pricing markers.

    When the LLM has produced numbers like "Rp 20.000.000" or "IDR 500",
    it almost certainly used a tool result or system context — don't
    override it even if the keyword-based evidence score is low.
    """
    if not final_answer:
        return False
    answer_lower = final_answer.lower()
    if any(marker in answer_lower for marker in PRICING_ANSWER_MARKERS):
        logger.info(
            "🔍 [Answer Content] Final answer contains pricing data, "
            "bypassing evidence check",
        )
        return True
    return False


def detect_llm_has_tools(llm_gateway: Any) -> tuple[bool, int]:
    """Return (has_tools, tool_count) for the configured LLM gateway.

    When the LLM was given tools and chose to produce a direct answer,
    trust its judgment — it had the opportunity to call a tool and
    declined. Returning (True, N) triggers the trusted_tools_used
    bypass in both sync and streaming pipelines.
    """
    gemini_tools = getattr(llm_gateway, "_gemini_tools", None)
    if gemini_tools:
        return True, len(gemini_tools)
    return False, 0


def should_apply_low_evidence_policy(
    *,
    final_answer: str | None,
    evidence_score: float,
    abstain_threshold: float,
    skip_rag: bool,
    trusted_tools_used: bool,
) -> bool:
    """Return True when the low-evidence override branch must run.

    The predicate is identical between sync and streaming pipelines:
        - a final answer already exists, AND
        - its evidence score is below the abstain threshold, AND
        - this is not a general/skip_rag task, AND
        - no trusted tool produced the answer.

    Extracted so the two pipelines cannot drift on this gate.
    """
    return bool(
        final_answer
        and evidence_score < abstain_threshold
        and not skip_rag
        and not trusted_tools_used,
    )


def apply_shared_trusted_flippers(
    *,
    trusted_tools_used: bool,
    final_answer: str | None,
    llm_gateway: Any,
) -> bool:
    """Apply the trusted-path flippers shared between sync and streaming.

    Both pipelines apply these two late-stage checks after evidence score
    computation, in the same order, with the same semantics:

        1. Pricing-in-answer:    Rp / IDR / "juta" markers in final_answer
                                 imply tool output was consumed → trust it.
        2. LLM-had-tools:        gateway._gemini_tools non-empty AND
                                 final_answer non-empty → trust LLM's
                                 decision to answer directly.

    Extracted so neither pipeline can drift on the predicate. Callers
    retain responsibility for the stream-specific *pre-flippers*
    (detect_trusted_context_markers, detect_substantial_context) — those
    are an intentional streaming-only widening (see _reasoning_evidence.py
    docstrings).

    Args:
        trusted_tools_used: current value (may have been flipped True
            already by earlier checks).
        final_answer: state.final_answer at this point.
        llm_gateway: the gateway object (has `_gemini_tools` attribute).

    Returns:
        Possibly updated `trusted_tools_used` value. Never flips True→False.
    """
    # 1. Pricing in answer
    if not trusted_tools_used and detect_pricing_data_in_answer(final_answer):
        trusted_tools_used = True

    # 2. LLM had tools + produced answer → trust judgment
    if final_answer:
        has_tools, tool_count = detect_llm_has_tools(llm_gateway)
        if has_tools:
            logger.info(
                "🔍 [Tools Available] LLM had %d tools and produced answer, "
                "skipping strict evidence check",
                tool_count,
            )
            trusted_tools_used = True

    return trusted_tools_used
