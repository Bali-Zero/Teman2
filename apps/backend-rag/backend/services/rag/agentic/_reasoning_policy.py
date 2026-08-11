"""
Policy enforcement helpers for the ReAct reasoning engine.

Extracted from ``reasoning.py`` (refactor/split-reasoning) as pure,
stateless detectors so both the sync and streaming pipelines share the
same low-evidence policy without duplication.

The full tier1 / strict-abstain execution (which calls back into
``self._get_localized_stub`` and ``llm_gateway.send_message`` with 8+
parameters) intentionally stays in the engine methods — extracting it
would add more plumbing than it removes. The constants and predicates
live here so they're easy to tune in one place.

Public API:
    - should_apply_low_evidence_policy: True when the low-evidence
      override branch must run (answer exists, score below abstain
      threshold, not skip_rag, not trusted). Mirrors the predicate used
      identically in both sync and streaming pipelines.
    - apply_shared_trusted_flippers: compatibility boundary shared by the
      sync and streaming paths. It preserves trust already earned from an
      executed tool; prose and configured-but-unused tools cannot create it.
"""

from __future__ import annotations

from typing import Any


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
    """Preserve execution-backed trust across sync and streaming.

    A price written in the answer is only a claim. Likewise, tools attached
    to the gateway are only capabilities: they say nothing about whether a
    relevant source was actually retrieved. Neither may upgrade an untrusted
    answer. Actual successful tool execution is detected upstream by
    ``detect_trusted_tool_usage`` and arrives here as ``trusted_tools_used``.

    The compatibility boundary remains shared so neither pipeline can drift
    on the policy. Callers
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
        The unchanged `trusted_tools_used` value.
    """
    # Keep the parameters for the shared sync/stream call contract. They are
    # deliberately not evidence inputs after BOT-KBLI grounding hardening.
    _ = final_answer, llm_gateway
    return trusted_tools_used
