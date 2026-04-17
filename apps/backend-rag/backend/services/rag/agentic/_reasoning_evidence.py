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
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

EVIDENCE_SCORE_TRUSTED_TOOL: float = 0.85

_CONTEXT_MIN_LEN_FOR_TRUSTED_OBS: int = 50
_SUBSTANTIAL_CONTEXT_THRESHOLD: int = 200

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
) -> bool:
    """Return True if any step used a trusted tool with substantial output.

    A step qualifies when:
        - step.action.tool_name is in trusted_tool_names
        - step.observation exists
        - observation does not contain error / not-found / no-relevant markers
        - observation length > 50 chars
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
        obs_lower = observation.lower()
        has_content = (
            "error" not in obs_lower
            and "not found" not in obs_lower
            and "no relevant" not in obs_lower
            and len(observation) > _CONTEXT_MIN_LEN_FOR_TRUSTED_OBS
        )
        if has_content:
            logger.info(
                "🔧 [%s] %s used successfully "
                "(obs_len=%d), bypassing keyword evidence check",
                log_prefix,
                tool_name,
                len(observation),
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
            "🔍 [Trusted Tools] KG data found in context_gathered, "
            "bypassing evidence check",
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
