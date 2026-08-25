"""Facade between Visa Check (deterministic wizard) and Visa Oracle (RAG chat).

Reads the canonical visa_checks row by hash and produces a typed FunnelContext
that the Oracle chat endpoint uses to augment its system prompt with
ground-truth visa + cost. No state of its own; no new migration.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

logger = logging.getLogger(__name__)

_CONTEXT_TTL = timedelta(days=30)


@dataclass(frozen=True)
class FunnelContext:
    """Snapshot of a wizard completion, safe to inject into an LLM prompt.

    `branch` discriminates the two shapes a `visa_checks` row can take
    (see `backend/db/migrations_v2/124_visa_checks.sql` — one table,
    nullable per-branch columns):

    - ``"match"``: the planning wizard's output — nationality/purpose/
      duration/budget, a recommended visa, and (when PricingTool resolved
      one) a cost. The match-only fields below are populated; the
      clock-only fields are None.
    - ``"clock"``: the in-country countdown tool's output — permit type,
      entry/expiry dates, extensions. `backend/services/visa_check/
      repository.py::save_clock` writes NO cost at all for this branch —
      `estimated_cost_idr` must stay None here, never a fabricated 0.
      The match-only fields are None.

    Fields outside the active branch stay at their `None`/empty default —
    never an empty string or a zero standing in for "not applicable". A
    context that lies about facts it doesn't have is worse than the 410
    it replaces.
    """

    check_hash: str
    referral_mode: bool
    branch: Literal["match", "clock"] = "match"

    # match-branch fields — populated only when branch == "match".
    nationality: str | None = None
    purpose: str | None = None
    duration_months: int | None = None
    budget_band: str | None = None
    recommended_visa: str | None = None
    estimated_cost_idr: int | None = None
    alternatives: list[str] = field(default_factory=list)

    # clock-branch fields — populated only when branch == "clock".
    visa_type: str | None = None
    entry_date: date | None = None
    expiry_date: date | None = None
    extensions_possible: int | None = None
    extension_days: int | None = None


async def get_funnel_context(check_hash: str, pool: Any) -> FunnelContext | None:
    """Load the wizard snapshot for `check_hash`.

    Returns None when the row is absent or older than _CONTEXT_TTL.
    The TTL is a safety net against long-held JWTs replaying ancient
    wizard state; authoritative freshness comes from the JWT's `exp`.

    Queries by hash ALONE — a hardcoded ``AND branch = 'match'`` used to
    sit here, so every clock-branch hash (in-country visitors: overstay,
    extension, conversion questions — the people who call Bali Zero most
    urgently) fetched no row and the chat endpoint 410'd. The row's own
    `branch` column now discriminates which shape to build.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT hash, branch, nationality, purpose, duration_months, budget_band,
                   recommended_visa, recommendation_reason, alternatives,
                   estimated_cost_idr, visa_type, entry_date, expiry_date,
                   extensions_possible, extension_days, created_at
              FROM visa_checks
             WHERE hash = $1
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

    if row["branch"] == "clock":
        return FunnelContext(
            check_hash=row["hash"],
            branch="clock",
            # A clock row is a deterministic lookup of the visitor's own
            # permit — there is no "wizard abstained" state for it.
            referral_mode=False,
            visa_type=row["visa_type"],
            entry_date=row["entry_date"],
            expiry_date=row["expiry_date"],
            extensions_possible=row["extensions_possible"],
            extension_days=row["extension_days"],
        )

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
        branch="match",
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
    """Prepend wizard/clock ground-truth to an Oracle chat system prompt.

    For a clock-branch context, the augmentation states the visitor's own
    permit facts (type, entry, expiry, extensions remaining) so the model
    cannot contradict their countdown. A clock row carries NO cost at all
    (`visa_check/repository.py::save_clock` never writes one) — the
    preamble says so explicitly rather than staying silent on price.

    For a match-branch, normal (non-abstained) completion, the augmentation
    names the recommended visa, the Bali Zero IDR cost (when PricingTool
    resolved one), and the ranked alternatives, so the LLM cannot
    contradict the wizard or invent prices. When no cost was resolved, the
    preamble says so explicitly instead of instructing the model to quote a
    number it was never given (SYSTEM_PROMPT's blanket price ban applies
    here too — this is the one carve-out it names).

    For wizard_abstained completions, the augmentation explicitly tells
    the LLM NOT to produce a recommendation: it should gather details
    for a WhatsApp handoff instead.
    """
    if context.branch == "clock":
        preamble = (
            "The user just checked their visa status with our Clock tool. "
            f"Ground truth for THIS visitor: permit type {context.visa_type}, "
            f"entered Indonesia on {context.entry_date}, current permit "
            f"expires {context.expiry_date}, with "
            f"{context.extensions_possible if context.extensions_possible is not None else 'an unknown number of'} "
            "extension(s) of up to "
            f"{context.extension_days if context.extension_days is not None else 'an unspecified number of'} "
            "day(s) each still available under this permit. Use these exact "
            "facts — never recompute or contradict the visitor's own "
            "countdown. This tool carries NO cost information: do not state "
            "or invent a price for anything here — say the Bali Zero team "
            "will confirm the exact cost on WhatsApp.\n\n"
        )
        return preamble + base_prompt

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

    has_cost = bool(context.estimated_cost_idr)
    cost_line = (
        f" Cost from PricingTool: IDR {context.estimated_cost_idr:,}."
        if has_cost
        else " No cost is on file for this recommendation."
    )
    alts = (
        f" Alternatives already surfaced: {', '.join(context.alternatives)}."
        if context.alternatives
        else ""
    )
    price_instruction = (
        "Always quote this recommended visa and cost unless the user "
        "explicitly asks for an updated price; in that case say Bali Zero "
        "will confirm on WhatsApp."
        if has_cost
        else "Do not state or invent a price for it — say the Bali Zero "
        "team will confirm the exact cost on WhatsApp."
    )
    preamble = (
        "The user just completed our visa wizard. "
        f"Recommended visa: {context.recommended_visa}."
        f"{cost_line}{alts} {price_instruction} Do not invent alternative "
        "visas beyond the ones listed above.\n\n"
    )
    return preamble + base_prompt


__all__ = [
    "FunnelContext",
    "augment_chat_system_prompt",
    "get_funnel_context",
]
