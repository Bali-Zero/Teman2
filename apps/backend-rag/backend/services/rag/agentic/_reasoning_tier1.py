"""
Tier 1 fallback + strict-abstain helpers for the ReAct reasoning engine.

Extracted from ``reasoning.py`` (refactor/split-reasoning).

The low-evidence policy branch repeats the same building blocks up to
four times across the sync and streaming pipelines (policy-enforcement
override AND final-answer-generation path, × sync AND stream):

    1. Build a Transparency Protocol prompt that instructs the LLM to
       answer from general knowledge while clearly flagging the lack of
       verified documents.
    2. Invoke the LLM with function-calling disabled.
    3. Emit Prometheus metrics for activation / success / failure /
       duration, plus the "strict abstain" pair when the query is on a
       critical domain.

Each occurrence varies slightly (log prefix, token-usage accumulation,
which fallback stub to use), so the helpers here expose the pure /
small primitives — prompt construction and metric emission — and leave
the LLM invocation + control flow inline in the engine methods.

Public API:
    - TRANSPARENCY_INSTRUCTION_DEFAULT: the canonical 5-point prompt
      used across all four occurrences (plus a 4-point variant used by
      the policy-enforcement override; see
      TRANSPARENCY_INSTRUCTION_POLICY_OVERRIDE).
    - build_tier1_prompt: assemble the transparency prompt + context
      section + user query into the final LLM input string.
    - emit_strict_abstain_metrics: emit the two counters for the
      critical-domain strict-abstain branch.
    - emit_tier1_activation_metrics: emit the activation + optional
      "tier1_fallback" abstain_decision_total on entry.
    - emit_tier1_success_metrics: emit duration + success counter.
    - emit_tier1_failure_metrics: emit duration + failure counter
      (labelled with the exception type name).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

TRANSPARENCY_INSTRUCTION_DEFAULT: str = """
[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]
CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with: "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
"""

TRANSPARENCY_INSTRUCTION_FINAL: str = """
[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]
CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with this EXACT phrase (translated to user's language):
   "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
5. If the question is about Bali Zero services, pricing, or specific procedures, suggest contacting the team for verified information.
"""

TRANSPARENCY_INSTRUCTION_NO_CONTEXT: str = """
[SYSTEM NOTICE: NO INTERNAL DOCUMENTS FOUND]
CRITICAL INSTRUCTION: No verified documents were found in the internal knowledge base.

1. DO NOT say "I cannot answer" or "Mi dispiace, non ho trovato".
2. Answer the user's question using your GENERAL KNOWLEDGE.
3. MUST START your response with: "Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale..."
4. Be helpful but clearly distinguish between "Internal Verified Fact" (missing) and "General Knowledge" (present).
"""

_CONTEXT_HEADER = "Retrieved Context (limited):"
_NO_CONTEXT_NOTE = "No verified documents found in internal knowledge base."
_PROMPT_TAIL = (
    "Provide a helpful answer using your general knowledge, but clearly state "
    "that this is not verified internal information."
)


def build_tier1_prompt(
    query: str,
    context_gathered: list[str] | None,
    *,
    transparency_instruction: str = TRANSPARENCY_INSTRUCTION_DEFAULT,
    include_context_section: bool = True,
) -> str:
    """Assemble the full Tier 1 prompt sent to the LLM.

    Structure (preserved from the original occurrences):
        <transparency_instruction>
        User Query: <query>
        <context section — either "Retrieved Context (limited):\\n..." or
        "No verified documents found in internal knowledge base.">
        <standard tail: ask for helpful general-knowledge answer>

    ``include_context_section=False`` suppresses the context section
    entirely (used by the no-context-gathered branches where the
    transparency instruction itself already says "NO INTERNAL
    DOCUMENTS FOUND" — avoids the redundant "No verified documents
    found..." line).
    """
    if not include_context_section:
        return f"""
{transparency_instruction}

User Query: {query}

{_PROMPT_TAIL}
"""

    if context_gathered:
        context = "\n\n".join(context_gathered)
        context_section = f"{_CONTEXT_HEADER}\n{context}"
    else:
        context_section = _NO_CONTEXT_NOTE

    return f"""
{transparency_instruction}

User Query: {query}
{context_section}

{_PROMPT_TAIL}
"""


def _metrics():
    """Return the reasoning module so we can read metrics live.

    Metrics are resolved via the reasoning module at call time so tests
    that patch ``backend.services.rag.agentic.reasoning.<metric>``
    continue to intercept the increments (same late-lookup pattern used
    for ``calculate_evidence_score`` and ``parse_tool_call``).
    """
    from backend.services.rag.agentic import reasoning as _reasoning_module
    return _reasoning_module


def emit_strict_abstain_metrics(intent_type: str, domain_type: str) -> None:
    """Emit the two counters for a critical-domain strict-abstain decision."""
    m = _metrics()
    m.strict_abstain_critical_total.labels(
        intent_type=intent_type,
        domain_type=domain_type,
    ).inc()
    m.abstain_decision_total.labels(decision_type="strict_abstain").inc()


def emit_tier1_activation_metrics(
    intent_type: str,
    *,
    has_context: bool,
    also_emit_abstain_decision: bool = False,
) -> None:
    """Emit activation counter + optionally the tier1_fallback abstain decision.

    ``also_emit_abstain_decision`` mirrors the streaming pipeline's extra
    ``abstain_decision_total.labels(decision_type="tier1_fallback").inc()``
    call, which the sync pipeline historically did not emit. Callers opt
    in explicitly so the asymmetry is visible at the call site.
    """
    m = _metrics()
    m.tier1_fallback_activated_total.labels(
        intent_type=intent_type,
        has_context=str(has_context).lower(),
    ).inc()
    if also_emit_abstain_decision:
        m.abstain_decision_total.labels(decision_type="tier1_fallback").inc()


def emit_tier1_success_metrics(intent_type: str, duration_seconds: float) -> None:
    """Emit duration observation + success counter."""
    m = _metrics()
    m.tier1_response_duration.observe(duration_seconds)
    m.tier1_fallback_success_total.labels(intent_type=intent_type).inc()


def emit_tier1_failure_metrics(
    intent_type: str,
    duration_seconds: float,
    exception: BaseException,
) -> None:
    """Emit duration observation + failure counter labelled with exception type."""
    m = _metrics()
    m.tier1_response_duration.observe(duration_seconds)
    m.tier1_fallback_failed_total.labels(
        intent_type=intent_type,
        error_type=type(exception).__name__,
    ).inc()


__all__ = [
    "TRANSPARENCY_INSTRUCTION_DEFAULT",
    "TRANSPARENCY_INSTRUCTION_FINAL",
    "TRANSPARENCY_INSTRUCTION_NO_CONTEXT",
    "build_tier1_prompt",
    "emit_strict_abstain_metrics",
    "emit_tier1_activation_metrics",
    "emit_tier1_failure_metrics",
    "emit_tier1_success_metrics",
]
