"""Facade between Visa Check (deterministic wizard) and Visa Oracle (RAG chat).

Reads the canonical visa_checks row by hash and produces a typed FunnelContext
that the Oracle chat endpoint uses to augment its system prompt with
ground-truth visa + cost. No state of its own; no new migration.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CONTEXT_TTL = timedelta(days=30)


@dataclass(frozen=True)
class FunnelContext:
    """Snapshot of a wizard completion, safe to inject into an LLM prompt."""

    check_hash: str
    nationality: str
    purpose: str
    duration_months: int
    budget_band: str
    recommended_visa: str | None
    estimated_cost_idr: int | None
    alternatives: list[str]
    referral_mode: bool


async def get_funnel_context(check_hash: str, pool: Any) -> FunnelContext | None:
    """Load the wizard snapshot for `check_hash`.

    Returns None when the row is absent or older than _CONTEXT_TTL.
    The TTL is a safety net against long-held JWTs replaying ancient
    wizard state; authoritative freshness comes from the JWT's `exp`.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT hash, nationality, purpose, duration_months, budget_band,
                   recommended_visa, recommendation_reason, alternatives,
                   estimated_cost_idr, created_at
              FROM visa_checks
             WHERE hash = $1 AND branch = 'match'
            """,
            check_hash,
        )
    if row is None:
        return None

    created_at = row["created_at"]
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if created_at and datetime.now(timezone.utc) - created_at > _CONTEXT_TTL:
        logger.info("funnel context expired for hash=%s", check_hash)
        return None

    alts_raw = row["alternatives"]
    if isinstance(alts_raw, str):
        try:
            alternatives = list(json.loads(alts_raw) or [])
        except json.JSONDecodeError:
            alternatives = []
    else:
        alternatives = list(alts_raw or [])

    recommended = row["recommended_visa"]
    return FunnelContext(
        check_hash=row["hash"],
        nationality=row["nationality"] or "",
        purpose=row["purpose"] or "",
        duration_months=int(row["duration_months"] or 0),
        budget_band=row["budget_band"] or "",
        recommended_visa=recommended,
        estimated_cost_idr=row["estimated_cost_idr"],
        alternatives=alternatives,
        referral_mode=(recommended is None),
    )


def augment_chat_system_prompt(context: FunnelContext, base_prompt: str) -> str:
    """Prepend wizard ground-truth to an Oracle chat system prompt.

    For normal (non-abstained) completions, the augmentation names the
    recommended visa, the Bali Zero IDR cost, and the ranked alternatives,
    so the LLM cannot contradict the wizard or invent prices.

    For wizard_abstained completions, the augmentation explicitly tells
    the LLM NOT to produce a recommendation: it should gather details
    for a WhatsApp handoff instead.
    """
    if context.referral_mode:
        preamble = (
            "The user just completed our visa wizard and their case did not "
            "match any deterministic branch (purpose=`other`, unsupported "
            "duration, or under-budget investor). Do NOT recommend a visa "
            "yourself. Instead, gather 1-2 clarifying details about their "
            "situation and suggest a WhatsApp handoff to the Bali Zero human "
            "team for a tailored answer. Keep the reply under 4 sentences.\n\n"
        )
        return preamble + base_prompt

    cost_line = (
        f" Cost from PricingTool: IDR {context.estimated_cost_idr:,}."
        if context.estimated_cost_idr
        else ""
    )
    alts = (
        f" Alternatives already surfaced: {', '.join(context.alternatives)}."
        if context.alternatives
        else ""
    )
    preamble = (
        "The user just completed our visa wizard. "
        f"Recommended visa: {context.recommended_visa}."
        f"{cost_line}{alts} Always quote this recommended visa and cost "
        "unless the user explicitly asks for an updated price; in that case "
        "say Bali Zero will confirm on WhatsApp. Do not invent alternative "
        "visas beyond the ones listed above.\n\n"
    )
    return preamble + base_prompt


__all__ = [
    "FunnelContext",
    "get_funnel_context",
    "augment_chat_system_prompt",
]
