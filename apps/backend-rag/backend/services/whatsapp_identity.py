"""WhatsApp sender identity resolver.

Resolves an inbound WhatsApp phone number to one of four roles —
``owner`` / ``team`` / ``client`` / ``unknown`` — so the reply pipeline
can address Zero as the owner, Bali Zero team members as colleagues, and
known CRM clients as known clients, instead of treating everyone as a
cold lead (gap found 2026-06-11: CREATOR_PERSONA/TEAM_PERSONA existed
but were only wired into the web RAG path, never into WhatsApp).

Sources, in precedence order:

1. owner — env ``WHATSAPP_OWNER_NUMBERS`` (comma-separated). Defaults to
   Zero's personal number, which is already public in the lead-capture
   wa.me fallback.
2. team — env ``WHATSAPP_TEAM_NUMBERS`` (``"628...:Name,628...:Name"``).
3. client — read-only lookup on ``clients.phone`` / ``clients.whatsapp``
   with conservative exact normalized matching (NO fuzzy/suffix match —
   a wrong identity match is a privacy incident).

Fail-safe by design: any error resolves to ``{"role": "unknown"}`` so
identity resolution can never break the reply path.
"""

from __future__ import annotations

import os
import re
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

_DIGITS_RE = re.compile(r"[^\d]")

_DEFAULT_OWNER_NUMBERS = "6282230102328"

_CLIENT_LOOKUP_SQL = """
SELECT id, full_name, status
  FROM clients
 WHERE NULLIF(regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g'), '')
       IN ($1, '62' || $1, '0' || $1)
    OR NULLIF(regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g'), '')
       IN ($1, '62' || $1, '0' || $1)
 ORDER BY CASE status
            WHEN 'active' THEN 0
            WHEN 'lead' THEN 1
            WHEN 'prospect' THEN 2
            ELSE 3
          END,
          id
 LIMIT 1
"""


def normalize_phone(raw: str | None) -> str | None:
    """Reduce a phone number to bare national digits.

    Strips everything non-numeric, then a leading ``62`` (Indonesia
    country code) or ``0`` (national prefix) so ``+62 821-345``,
    ``0821345`` and ``62821345`` all compare equal.
    """
    if not raw:
        return None
    digits = _DIGITS_RE.sub("", raw)
    if not digits:
        return None
    if digits.startswith("62"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return digits or None


def _owner_numbers() -> set[str]:
    raw = os.getenv("WHATSAPP_OWNER_NUMBERS", _DEFAULT_OWNER_NUMBERS)
    return {
        norm
        for norm in (normalize_phone(part) for part in raw.split(","))
        if norm
    }


def _team_numbers() -> dict[str, str]:
    """Parse ``WHATSAPP_TEAM_NUMBERS`` (``"628...:Name,628...:Name"``)."""
    raw = os.getenv("WHATSAPP_TEAM_NUMBERS", "")
    mapping: dict[str, str] = {}
    for entry in raw.split(","):
        number, _, name = entry.partition(":")
        norm = normalize_phone(number)
        if norm:
            mapping[norm] = name.strip() or "team member"
    return mapping


async def resolve_sender_identity(
    phone: str | None,
    db_pool: asyncpg.Pool | None,
) -> dict[str, Any]:
    """Resolve the sender role for an inbound WhatsApp message.

    Returns one of:
    - ``{"role": "owner"}``
    - ``{"role": "team", "team_member": "<Name>"}``
    - ``{"role": "client", "client_id": int, "client_name": str | None,
        "client_status": str | None}``
    - ``{"role": "unknown"}``
    """
    try:
        norm = normalize_phone(phone)
        if not norm:
            return {"role": "unknown"}

        if norm in _owner_numbers():
            return {"role": "owner"}

        team = _team_numbers()
        if norm in team:
            return {"role": "team", "team_member": team[norm]}

        if db_pool is not None:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(_CLIENT_LOOKUP_SQL, norm)
            if row:
                return {
                    "role": "client",
                    "client_id": row["id"],
                    "client_name": row["full_name"],
                    "client_status": row["status"],
                }
    except (
        asyncpg.PostgresError,
        asyncpg.InterfaceError,  # W34: sibling of PostgresError, NOT a subclass
        OSError,
        TimeoutError,
    ):
        logger.warning("Sender identity lookup failed for phone=%s", phone, exc_info=True)
    except Exception:
        logger.exception("Sender identity resolution failed for phone=%s", phone)

    return {"role": "unknown"}
