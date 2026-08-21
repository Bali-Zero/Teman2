"""Team WhatsApp sender — resolves a Bali Zero team member's WhatsApp number
server-side and sends free-form text via the Meta WhatsApp Business Cloud API.

Built for scripts/s7_yield_dispatch.py (S7 Yield WhatsApp digest, Law-2
derogation authorized 2026-08-21, `SYMBIOSIS.md` — "il cancello vive anche
lato server"): the caller is a cron script running off-Fly that has
`NUZANTARA_API_KEY` but not `WHATSAPP_ACCESS_TOKEN`, and it must never
resolve or hold a phone number itself — only an `@balizero.com` email. This
module re-derives `active` + `whatsapp` from `team_members` on EVERY call, so
a caller cannot bypass an inactive or unknown assignee even if its own
client-side gate has a bug — the same fact is checked twice, independently.

NOT a general-purpose team-messaging primitive with its own opinions about
WHO should receive WHAT — that judgment belongs entirely to the caller (the
S7 dispatcher's fail-closed delivery gate). This module enforces only two
structural facts: the row exists and is active, and it has a phone number on
file. No fallback recipient exists anywhere in this file.
"""

from __future__ import annotations

import logging
from typing import Any

from asyncpg import Pool

from backend.services.integrations.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class TeamMemberNotFound(Exception):
    """No `team_members` row for that email, or it is not active."""


class TeamMemberNoWhatsApp(Exception):
    """The row resolved (active, in roster) but has no WhatsApp number on file."""


def normalize_phone(phone: str) -> str:
    """Digit-only — matches WhatsAppService/Meta Cloud API's expected format
    (country code, no leading +, no separators)."""
    return "".join(ch for ch in phone if ch.isdigit())


async def send_to_team_member(db_pool: Pool, team_email: str, text: str) -> dict[str, Any]:
    """Resolve `team_email` to an active `team_members` row + phone, then send
    `text` via WhatsAppService.send_message. Raises TeamMemberNotFound /
    TeamMemberNoWhatsApp rather than silently falling back to any other
    recipient — there is no default number anywhere in this function.
    """
    email = (team_email or "").strip().lower()
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email, active, whatsapp FROM team_members WHERE lower(email) = $1",
            email,
        )
    # `is not True` (not `is False`) also rejects a NULL active flag —
    # unknown activity status is treated the same as inactive, never as a
    # pass. This function's only two verdicts are "send" and "refuse".
    if row is None or row["active"] is not True:
        raise TeamMemberNotFound(email)
    phone = (row["whatsapp"] or "").strip()
    if not phone:
        raise TeamMemberNoWhatsApp(email)
    normalized = normalize_phone(phone)
    result = await whatsapp_service.send_message(phone=normalized, text=text)
    logger.info("team_whatsapp: sent to an active roster row")  # never the email/phone in logs
    return {"sent": True, "meta_response_ok": bool(result)}
