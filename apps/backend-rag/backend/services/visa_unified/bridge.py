"""Facade between Visa Check (deterministic wizard) and Visa Oracle (RAG chat).

Reads the canonical visa_checks row by hash and produces a typed FunnelContext
that the Oracle chat endpoint uses to augment its system prompt with
ground-truth visa + cost. No state of its own; no new migration.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CONTEXT_TTL = timedelta(days=30)


@dataclass(frozen=True)
class FunnelContext:
    """Snapshot of a wizard completion or a Visa Clock run, safe to inject into an LLM prompt."""

    check_hash: str
    nationality: str
    purpose: str
    duration_months: int
    budget_band: str
    recommended_visa: str | None
    estimated_cost_idr: int | None
    alternatives: list[str]
    referral_mode: bool
    branch: str = "match"
    visa_type: str | None = None
    entry_date: date | None = None
    expiry_date: date | None = None
    extensions_possible: int | None = None
    extension_days: int | None = None


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


async def get_funnel_context(check_hash: str, pool: Any) -> FunnelContext | None:
    """Load the wizard / Visa Clock snapshot for `check_hash`.

    Returns None when the row is absent, or when a match row is older than
    _CONTEXT_TTL. The TTL is a safety net against long-held JWTs replaying
    ancient wizard state; authoritative freshness comes from the JWT's `exp`.
    Clock rows have no TTL: GET /api/visa/clock/{hash} re-issues a fresh JWT
    for them at any age.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT hash, branch, nationality, purpose, duration_months, budget_band,
                   recommended_visa, recommendation_reason, alternatives,
                   estimated_cost_idr, created_at,
                   visa_type, entry_date, expiry_date,
                   extensions_possible, extension_days
              FROM visa_checks
             WHERE hash = $1
            """,
            check_hash,
        )
    if row is None:
        return None

    if row.get("branch") == "clock":
        return FunnelContext(
            check_hash=row["hash"],
            nationality="",
            purpose="",
            duration_months=0,
            budget_band="",
            recommended_visa=None,
            estimated_cost_idr=None,
            alternatives=[],
            referral_mode=False,
            branch="clock",
            visa_type=row["visa_type"],
            entry_date=_as_date(row["entry_date"]),
            expiry_date=_as_date(row["expiry_date"]),
            extensions_possible=row["extensions_possible"],
            extension_days=row["extension_days"],
        )

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


def _clock_preamble(context: FunnelContext) -> str:
    """Ground-truth preamble for a visitor who ran the Visa Clock (no identifiers)."""
    today = datetime.now(timezone.utc).date()
    facts: list[str] = []
    if context.visa_type:
        facts.append(f"visa type {context.visa_type}")
    if context.entry_date:
        facts.append(f"entry date {context.entry_date.isoformat()}")
    ended = False
    if context.expiry_date:
        days = (context.expiry_date - today).days
        ended = days < 0
        if ended:
            remaining = f"already ended {-days} day{'s' if days != -1 else ''} ago"
        elif days == 0:
            remaining = "ends today"
        else:
            remaining = f"{days} day{'s' if days != 1 else ''} remaining"
        facts.append(f"permitted stay ends {context.expiry_date.isoformat()} ({remaining})")
    if context.extensions_possible is not None:
        if context.extensions_possible and context.extension_days:
            facts.append(
                f"the catalogue allows {context.extensions_possible} extension(s) "
                f"of {context.extension_days} days each"
            )
        elif not context.extensions_possible:
            facts.append("the catalogue lists no extension for this visa")
    preamble = (
        "The user is already in Indonesia and just used our Visa Clock. "
        f"Ground truth from the clock: {'; '.join(facts) or 'no dates recorded'}. "
        "Always quote these dates as given. Never invent dates, fees, fines or "
        "penalties, and give no prices in chat: say Bali Zero will confirm on "
        "WhatsApp."
    )
    if ended:
        preamble += (
            " The permitted stay has already ended: give no procedural advice "
            "and direct the user to the Bali Zero visa team today."
        )
    return preamble + "\n\n"


def augment_chat_system_prompt(context: FunnelContext, base_prompt: str) -> str:
    """Prepend wizard / Visa Clock ground-truth to an Oracle chat system prompt.

    For normal (non-abstained) completions, the augmentation names the
    recommended visa, the Bali Zero IDR cost, and the ranked alternatives,
    so the LLM cannot contradict the wizard or invent prices.

    For wizard_abstained completions, the augmentation explicitly tells
    the LLM NOT to produce a recommendation: it should gather details
    for a WhatsApp handoff instead.

    For Visa Clock runs, the augmentation states the visa type, the entry
    and permitted-stay dates, and the days remaining, and forbids invented
    dates, fees or penalties.
    """
    if context.branch == "clock":
        return _clock_preamble(context) + base_prompt

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
    "augment_chat_system_prompt",
    "get_funnel_context",
]
