"""
Evidence scoring helpers for the ReAct reasoning engine.

Extracted from ``reasoning.py`` (refactor/split-reasoning) as pure, stateless
functions so both the sync and streaming pipelines share the same logic
without duplication. Behaviour preserved exactly; no policy changes.

Public API:
    - EVIDENCE_SCORE_TRUSTED_TOOL: high-confidence score assigned when a
      trusted tool produced substantial output.
    - detect_trusted_tool_usage: walk AgentState steps, return True if any
      step used a trusted tool with non-error, non-empty observation.
    - detect_quotable_relevance_veto: hard-veto signal (independent of
      detect_trusted_tool_usage's OR-semantics) for callers that need to
      stop the shared trust flippers (_reasoning_policy.py) from
      re-granting trust after a quotable tool's own output goes unreflected
      in final_answer. See its docstring for why this exists.
    - detect_trusted_context_markers: scan context_gathered strings for
      pricing/team/KG markers (streaming pipeline fallback).
    - detect_substantial_context: return True if total context length
      exceeds threshold (streaming pipeline fallback).
    - compute_evidence_score: 0.85 if trusted_tools_used else keyword-based.
    - emit_low_confidence_event: defensive wrapper around low_confidence
      bridge; swallows failures to never break the RAG path.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any

from backend.services.rag.agentic._tool_denial import is_denial_observation

logger = logging.getLogger(__name__)

EVIDENCE_SCORE_TRUSTED_TOOL: float = 0.85

_CONTEXT_MIN_LEN_FOR_TRUSTED_OBS: int = 50
_SUBSTANTIAL_CONTEXT_THRESHOLD: int = 200

# Tools whose observations carry quotable numeric/structured data (a price, a
# client amount, a timesheet total, a computed result) that a final_answer can
# be checked against for literal overlap. `team_knowledge`/`vector_search`
# return free-text/qualitative content with no reliable literal to anchor on —
# they are deliberately excluded and keep unconditional trust (see
# detect_trusted_tool_usage below).
_QUOTABLE_TOOL_NAMES: frozenset[str] = frozenset(
    {"get_pricing", "crm_query", "timesheet", "calculator"}
)

_GROUPED_NUMBER_RX = re.compile(r"\d{1,3}(?:[.,]\d{3})+|\d+")


def _extract_literal_tokens(text: str | None) -> frozenset[str]:
    """Extract normalized numeric tokens from text for a relevance overlap check.

    Handles three real formats seen in this codebase: plain digit runs
    (json.dumps of a Python int), comma-grouped (CalculatorTool's `:,}`
    format spec — ALWAYS comma, never dot), and Indonesian dot-grouped
    (bot's final_answer may write "Rp 5.000.000"). Strips group separators
    so "5,000,000" / "5.000.000" / "5000000" all normalize to "5000000".
    Tokens under 3 digits are dropped — too easy to coincidentally match
    (page numbers, list indices, percentages) and not what this check is
    trying to catch (this is a deliberate, declared precision/recall
    trade-off, not a bug: the check is a heuristic upgrade over "zero
    correlation with final_answer", not a precise parser).
    """
    if not text:
        return frozenset()
    tokens = set()
    for raw in _GROUPED_NUMBER_RX.findall(text):
        normalized = raw.replace(",", "").replace(".", "")
        if len(normalized) >= 3:
            tokens.add(normalized)
    return frozenset(tokens)

_PRICING_MARKERS: tuple[str, ...] = (
    "bali_zero_official_prices",
    "service_type",
    "total_price",
    "pricing",
    "rp ",
    "idr ",
    "harga",
)
_TEAM_MARKERS: tuple[str, ...] = (
    "team_member",
    "specialties",
    "role:",
    "department",
)
_KG_MARKERS: tuple[str, ...] = (
    "subgraph",
    "nodes,",
    "edges)",
    "focus]",
    "knowledge graph",
)


def detect_trusted_tool_usage(
    steps: Iterable[Any],
    trusted_tool_names: Iterable[str],
    log_prefix: str = "Trusted Tools",
    *,
    final_answer: str | None = None,
) -> bool:
    """Return True if any step used a trusted tool with substantial output.

    A step qualifies when:
        - step.action.tool_name is in trusted_tool_names
        - step.observation exists
        - observation does not contain error / not-found / no-relevant markers
        - observation length > 50 chars

    ``final_answer`` is an optional, keyword-only relevance check on top of
    the qualification above. When it is omitted (``None``), behavior is
    IDENTICAL to before this parameter existed — this is the deliberate
    safe default for the one known caller (the streaming pipeline's
    crm_query early-exit, reasoning.py) that invokes this function before
    state.final_answer has been generated, and for any other caller that
    does not pass it.

    When ``final_answer`` IS supplied, a qualifying step for a tool NOT in
    ``_QUOTABLE_TOOL_NAMES`` (team_knowledge, vector_search — free-text,
    nothing literal to check) still grants trust unconditionally, exactly
    as before. For a qualifying step on one of the 4 quotable tools
    (get_pricing, crm_query, timesheet, calculator), trust additionally
    requires that the observation's literal numeric tokens (see
    ``_extract_literal_tokens``) overlap with ``final_answer``'s — i.e. the
    LLM actually reported a number the tool returned, not a hallucinated
    one. A step whose observation has no extractable numeric token at all
    is not punished (nothing to check against) and still grants trust. A
    quotable-tool step that fails the overlap check does NOT return True
    for that step alone — the loop continues to see if another step
    qualifies (OR-semantics preserved); only if no step ever qualifies does
    this return False, falling through to the pre-existing keyword-based
    `calculate_evidence_score` path.
    """
    trusted_names = frozenset(trusted_tool_names)
    for step in steps:
        action = getattr(step, "action", None)
        observation = getattr(step, "observation", None)
        if not action or not observation:
            continue
        tool_name = getattr(action, "tool_name", None)
        if tool_name not in trusted_names:
            continue
        if is_denial_observation(observation):
            # A REFUSED call is not a successful one. The checks below scan
            # prose for failure words, and the anonymous denial deliberately
            # contains none of them while being 54 chars — 4 over the floor —
            # so it used to score 0.85, the highest evidence in the system.
            # Measured in prod 2026-08-10; see _tool_denial.py.
            logger.info(
                "🚫 [%s] %s was DENIED — not counted as trusted-tool evidence",
                log_prefix,
                tool_name,
            )
            continue
        obs_lower = observation.lower()
        has_content = (
            "error" not in obs_lower
            and "not found" not in obs_lower
            and "no relevant" not in obs_lower
            and len(observation) > _CONTEXT_MIN_LEN_FOR_TRUSTED_OBS
        )
        if not has_content:
            continue

        if final_answer is None or tool_name not in _QUOTABLE_TOOL_NAMES:
            logger.info(
                "🔧 [%s] %s used successfully (obs_len=%d), bypassing keyword evidence check",
                log_prefix,
                tool_name,
                len(observation),
            )
            return True

        observation_tokens = _extract_literal_tokens(observation)
        if not observation_tokens:
            logger.info(
                "🔧 [%s] %s used successfully (obs_len=%d, no checkable literal), "
                "bypassing keyword evidence check",
                log_prefix,
                tool_name,
                len(observation),
            )
            return True

        if observation_tokens & _extract_literal_tokens(final_answer):
            logger.info(
                "🔧 [%s] %s used successfully (obs_len=%d, final_answer agrees), "
                "bypassing keyword evidence check",
                log_prefix,
                tool_name,
                len(observation),
            )
            return True

        logger.info(
            "🔧 [%s] %s output not reflected in final_answer — not trusting this step",
            log_prefix,
            tool_name,
        )
    return False


def detect_quotable_relevance_veto(
    steps: Iterable[Any],
    quotable_tool_names: frozenset[str] = _QUOTABLE_TOOL_NAMES,
    *,
    final_answer: str | None = None,
    log_prefix: str = "Trusted Tools",
) -> bool:
    """Return True if a quotable tool ran with checkable content whose
    literal tokens are absent from final_answer — a hard veto signal.

    ``detect_trusted_tool_usage`` has OR-semantics: if ANY step qualifies
    for trust (including a non-quotable tool like team_knowledge, or a
    quotable tool with no extractable literal), it returns True even when a
    DIFFERENT quotable-tool step's own output goes unreflected in
    final_answer. That's correct for its purpose (deciding the base trust
    signal) but leaves a gap: `apply_shared_trusted_flippers`
    (_reasoning_policy.py) applies two more permissive heuristics
    afterwards — a bare pricing-marker-in-answer check and an
    LLM-had-tools-available check — neither of which has any visibility
    into per-tool literal overlap. A quotable tool whose number/amount was
    NOT reflected in final_answer (i.e. the LLM likely reported a
    hallucinated figure instead of the tool's real one) would still get
    re-trusted by those flippers on the back of an unrelated marker or the
    mere presence of tools, silently undoing the relevance check.

    Callers should compute this once per pipeline (same inputs as
    ``detect_trusted_tool_usage``) and force ``trusted_tools_used = False``
    after ``apply_shared_trusted_flippers`` runs when this returns True —
    a confirmed per-tool mismatch is stronger negative evidence than the
    flippers' generic heuristics are positive evidence, so it should win.

    Returns False (no veto) when final_answer is falsy — mirrors
    ``detect_trusted_tool_usage``'s own safe default for the caller that
    invokes this before final_answer exists (streaming crm_query
    early-exit).
    """
    if not final_answer:
        return False
    quotable = frozenset(quotable_tool_names)
    for step in steps:
        action = getattr(step, "action", None)
        observation = getattr(step, "observation", None)
        if not action or not observation:
            continue
        tool_name = getattr(action, "tool_name", None)
        if tool_name not in quotable:
            continue
        # NOT given the denial check that detect_trusted_tool_usage above
        # got, and this asymmetry is deliberate — measured, not overlooked.
        # The symmetric change reads right ("a denial carries no output, so
        # there is nothing to have quoted") but for the denial that actually
        # bit us it is a NO-OP: `_extract_literal_tokens` finds no number in
        # "This capability is not available in this conversation.", so the
        # `if not observation_tokens: continue` below already skips it. The
        # only case it would change is an authenticated denial whose *detail*
        # carries a 3+ digit number ("...quota 1000 exceeded"), and there it
        # would SUPPRESS a veto — i.e. loosen a guard, in a case nobody has
        # measured. This function's job is to block trust, so the safe
        # default is to leave it blocking.
        obs_lower = observation.lower()
        has_content = (
            "error" not in obs_lower
            and "not found" not in obs_lower
            and "no relevant" not in obs_lower
            and len(observation) > _CONTEXT_MIN_LEN_FOR_TRUSTED_OBS
        )
        if not has_content:
            continue
        observation_tokens = _extract_literal_tokens(observation)
        if not observation_tokens:
            # Nothing checkable — not this function's concern (mirrors
            # detect_trusted_tool_usage's own "nothing to check" trust grant).
            continue
        if not (observation_tokens & _extract_literal_tokens(final_answer)):
            logger.info(
                "🚫 [%s] %s output not reflected in final_answer — "
                "veto on trust flippers",
                log_prefix,
                tool_name,
            )
            return True
    return False


def detect_trusted_context_markers(
    context_gathered: list[str] | None,
) -> tuple[bool, str | None]:
    """Scan joined context for pricing/team/KG output markers.

    Streaming-only fallback (the sync pipeline does not use this).
    Returns (True, marker_kind) if any marker matches, else (False, None).
    """
    if not context_gathered:
        return False, None
    context_text = " ".join(context_gathered).lower()
    if any(marker in context_text for marker in _PRICING_MARKERS):
        logger.info("🔍 [Trusted Tools - Stream] Pricing data found in context_gathered")
        return True, "pricing"
    if any(marker in context_text for marker in _TEAM_MARKERS):
        logger.info("🔍 [Trusted Tools - Stream] Team data found in context_gathered")
        return True, "team"
    if any(marker in context_text for marker in _KG_MARKERS):
        logger.info(
            "🔍 [Trusted Tools] KG data found in context_gathered, bypassing evidence check",
        )
        return True, "kg"
    return False, None


def detect_substantial_context(
    context_gathered: list[str] | None,
    threshold: int = _SUBSTANTIAL_CONTEXT_THRESHOLD,
) -> bool:
    """Return True if total context length exceeds threshold.

    Streaming-only fallback; treats "ReAct loop gathered substantial context"
    as implicit evidence that the LLM had something to work with.
    """
    if not context_gathered:
        return False
    total_len = sum(len(c) for c in context_gathered)
    if total_len > threshold:
        logger.info(
            "🔍 [Context Evidence] Substantial context gathered (%d chars), "
            "bypassing strict evidence check",
            total_len,
        )
        return True
    return False


def compute_evidence_score(
    *,
    trusted_tools_used: bool,
    sources: list[Any] | None,
    context_gathered: list[str] | None,
    query: str,
    log_prefix: str = "Evidence",
) -> float:
    """Return 0.85 if trusted tools succeeded, else keyword-based score."""
    if trusted_tools_used:
        logger.info(
            "🛡️ [%s] Trusted tools used: score=%.2f",
            log_prefix,
            EVIDENCE_SCORE_TRUSTED_TOOL,
        )
        return EVIDENCE_SCORE_TRUSTED_TOOL
    # Lookup via the reasoning module so tests that patch
    # `backend.services.rag.agentic.reasoning.calculate_evidence_score`
    # continue to intercept the call.
    from backend.services.rag.agentic import reasoning as _reasoning_module

    evidence_score = _reasoning_module.calculate_evidence_score(
        sources,
        context_gathered,
        query,
    )
    logger.info("🛡️ [%s] Keyword-based score: %.2f", log_prefix, evidence_score)
    return evidence_score


async def emit_low_confidence_event(
    pool: Any,
    query: str,
    evidence_score: float,
    *,
    log_context: str = "",
) -> None:
    """Defensive wrapper around the low-confidence outbox bridge.

    Swallows any exception — never break the RAG path on outbox failure.
    ``pool`` may be None (bridge skipped in that case).
    """
    if pool is None:
        return
    try:
        from backend.services.bridge.low_confidence_emitter import (
            maybe_emit_low_confidence,
        )

        await maybe_emit_low_confidence(pool, query, evidence_score)
    except Exception as exc:
        suffix = f" ({log_context})" if log_context else ""
        logger.warning("Low-confidence emit skipped%s: %s", suffix, exc)
