"""Lead intent → clients matcher cron.

Air OpenClaw schedule: `*/5 * * * *`

What it does
------------
1. Pulls `lead_intents` rows created in the last 35 min that have no
   matched_client_id yet.
2. Pulls `clients` rows created OR touched in the last 35 min via WhatsApp
   channel (i.e. inbound WA message).
3. Correlates on phone-number match (after normalisation) + WA arrival
   strictly AFTER the intent's created_at (a message that arrived BEFORE
   the handoff cannot be the reply to it).
4. Updates `lead_intents.matched_client_id` + `clients.lead_source` +
   `clients.lead_metadata` (JSONB patch).

Design notes
------------
- Read-only outside the two updates — safe to run on 5-min cadence.
- No side effects if the intent and the WA message don't match within
  the 35-min overlap window; next run handles them.
- The phone normaliser strips '+', spaces, hyphens, and a leading '0'
  for Indonesian numbers so '+62 812 345' and '0812345' compare equal.

Usage
-----
    PYTHONPATH=apps/backend-rag python -m scripts.lead_intent_matcher
    # or:
    ~/scripts/cron-agent.sh exec lead_intent_matcher \
        python /Users/antonellosiano/Projects/nuzantara/scripts/lead_intent_matcher.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger("lead_intent_matcher")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


_MATCH_WINDOW = timedelta(minutes=30)
_FETCH_LOOKBACK = timedelta(minutes=35)  # small buffer for cron drift


# ----------------------------------------------------------------------
# Phone normalisation
# ----------------------------------------------------------------------

_PHONE_RE = re.compile(r"[^\d]")


def normalise_phone(raw: str | None) -> str | None:
    """Reduce a phone number to digits only. Also strip Indonesia leading 0
    and replace a leading 62 with '' so '+62 812' matches '0812'."""
    if not raw:
        return None
    digits = _PHONE_RE.sub("", raw)
    if not digits:
        return None
    # Indonesian mobile: drop leading 62/0.
    if digits.startswith("62"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return digits or None


# ----------------------------------------------------------------------
# Main cron entry point
# ----------------------------------------------------------------------


async def run(dsn: str) -> dict[str, int]:
    """Single pass. Returns counts for observability logs."""
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            intents = await _fetch_unmatched_intents(conn)
            messages = await _fetch_recent_wa_touches(conn)

        matched = 0
        skipped = 0
        for intent in intents:
            best = _pick_match(intent, messages)
            if best is None:
                skipped += 1
                continue
            async with pool.acquire() as conn:
                await _record_match(conn, intent=intent, client=best)
            matched += 1

        return {
            "intents_seen": len(intents),
            "wa_touches_seen": len(messages),
            "matched": matched,
            "skipped": skipped,
        }
    finally:
        await pool.close()


async def _fetch_unmatched_intents(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - _FETCH_LOOKBACK
    rows = await conn.fetch(
        """
        SELECT id, source, context, utm, fingerprint, created_at
          FROM lead_intents
         WHERE matched_client_id IS NULL
           AND created_at >= $1
         ORDER BY created_at DESC
         LIMIT 500
        """,
        cutoff,
    )
    return [
        {
            "id": r["id"],
            "source": r["source"],
            "context": r["context"] if isinstance(r["context"], dict) else json.loads(r["context"] or "{}"),
            "utm": r["utm"] if isinstance(r["utm"], (dict, type(None))) else json.loads(r["utm"] or "null"),
            "fingerprint": r["fingerprint"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def _fetch_recent_wa_touches(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Return clients whose first_touch_at (or last update) fell in the
    last FETCH_LOOKBACK window AND whose source is WhatsApp.

    We rely on `clients.first_touch_at` set by the WA webhook handler
    (migration 118). If the column is not present yet, the query
    falls back to `created_at`.
    """
    cutoff = datetime.now(timezone.utc) - _FETCH_LOOKBACK

    # Try the first_touch_at path first; fall back on ProgrammingError.
    try:
        rows = await conn.fetch(
            """
            SELECT id, phone, whatsapp,
                   COALESCE(first_touch_at, created_at) AS touched_at,
                   lead_source, lead_metadata
              FROM clients
             WHERE COALESCE(first_touch_at, created_at) >= $1
               AND (lead_source IS NULL OR lead_source IN ('whatsapp', 'whatsapp_inbound', 'website', 'unknown'))
             ORDER BY touched_at DESC
             LIMIT 500
            """,
            cutoff,
        )
    except asyncpg.PostgresError:
        logger.warning("fallback to created_at; first_touch_at missing?")
        rows = await conn.fetch(
            """
            SELECT id, phone, whatsapp, created_at AS touched_at,
                   lead_source, NULL AS lead_metadata
              FROM clients
             WHERE created_at >= $1
             ORDER BY created_at DESC
             LIMIT 500
            """,
            cutoff,
        )

    out: list[dict[str, Any]] = []
    for r in rows:
        phone = normalise_phone(r["phone"]) or normalise_phone(r["whatsapp"])
        if not phone:
            continue
        out.append(
            {
                "id": r["id"],
                "phone_norm": phone,
                "touched_at": r["touched_at"],
                "lead_source": r["lead_source"],
                "lead_metadata": r["lead_metadata"],
            }
        )
    return out


def _pick_match(
    intent: dict[str, Any], messages: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """The business rule: match first client whose phone appears in the
    intent context AND whose touched_at falls in the match window AFTER
    the intent's created_at."""
    ctx = intent["context"] or {}
    intent_phones = {
        normalise_phone(ctx.get(k))
        for k in ("phone", "whatsapp", "mobile")
    }
    intent_phones.discard(None)

    # If the intent didn't carry a phone, we can still match if *only one*
    # WA touch landed in a tight window — it's the natural candidate.
    window_start = intent["created_at"]
    window_end = window_start + _MATCH_WINDOW

    in_window = [
        m for m in messages if window_start <= m["touched_at"] <= window_end
    ]
    if not in_window:
        return None

    if intent_phones:
        for m in in_window:
            if m["phone_norm"] in intent_phones:
                return m
        return None

    # No phone on the intent. If exactly one candidate in the window,
    # accept it as the match. Multiple candidates → ambiguous, skip.
    return in_window[0] if len(in_window) == 1 else None


async def _record_match(
    conn: asyncpg.Connection,
    *,
    intent: dict[str, Any],
    client: dict[str, Any],
) -> None:
    """Two updates, same transaction. Idempotent: the WHERE clauses
    guarantee we only write once even if a retry loops."""
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE lead_intents
               SET matched_client_id = $1,
                   matched_at        = NOW()
             WHERE id = $2
               AND matched_client_id IS NULL
            """,
            client["id"],
            intent["id"],
        )

        # Merge into clients.lead_metadata without overwriting existing keys.
        existing = client.get("lead_metadata") or {}
        if isinstance(existing, str):
            try:
                existing = json.loads(existing)
            except ValueError:
                existing = {}

        patch = {
            "lead_intent_id": intent["id"],
            "source_app": intent["source"],
            "context": intent["context"],
            "utm": intent["utm"],
            "matched_at": datetime.now(timezone.utc).isoformat(),
        }
        merged = {**existing, **patch}

        new_source = f"{intent['source']}_handoff"
        await conn.execute(
            """
            UPDATE clients
               SET lead_source   = COALESCE(
                    NULLIF(lead_source, 'unknown'),
                    lead_source,
                    $1
                   ),
                   lead_metadata = $2::jsonb
             WHERE id = $3
            """,
            new_source,
            json.dumps(merged),
            client["id"],
        )

    logger.info(
        "matched intent_id=%s client_id=%s source=%s",
        intent["id"],
        client["id"],
        intent["source"],
    )


# ----------------------------------------------------------------------
# CLI entry
# ----------------------------------------------------------------------


def main() -> int:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2
    try:
        result = asyncio.run(run(dsn))
    except Exception:
        logger.exception("lead_intent_matcher: top-level failure")
        return 1
    logger.info("cron pass complete: %s", result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
