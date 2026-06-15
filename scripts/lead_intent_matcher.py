"""Lead intent → clients matcher cron.

Air OpenClaw schedule: `*/5 * * * *`

What it does
------------
Pass 1 — deterministic (Filo 2, 2026-06-11):
1. Pulls ALL unmatched, unexpired `lead_intents` (7-day TTL).
2. Scans inbound WhatsApp text from the last 48h (`meta_inbox_messages`
   for the Meta business number; `whatsapp_message_context` for the
   wa-mirror) for the `Lead ID: li_…` token the deeplink pre-fills.
3. Exact-key match → resolve sender to a client (row client_id or
   digits-suffix phone match) → record with match_method="lead_id".

Pass 2 — probabilistic fallback:
1. Pulls `lead_intents` rows created in the last 35 min that have no
   matched_client_id yet.
2. Pulls `clients` rows created OR touched in the last 35 min via WhatsApp
   channel (i.e. inbound WA message).
3. Correlates on phone-number match (after normalisation) + WA arrival
   strictly AFTER the intent's created_at (a message that arrived BEFORE
   the handoff cannot be the reply to it).

Both passes update `lead_intents.matched_client_id` + `clients.lead_source`
+ `clients.lead_metadata` (JSONB merge, match_method included).

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
    # or (Pro, LaunchAgent com.nuzantara.lead-intent-matcher every 5 min):
    bash scripts/lead_intent_matcher_run.sh
    # Runbook: docs/runbooks/lead-intent-matcher.md
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

import asyncpg

logger = logging.getLogger("lead_intent_matcher")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


_MATCH_WINDOW = timedelta(minutes=30)
_FETCH_LOOKBACK = timedelta(minutes=35)  # small buffer for cron drift

# Deterministic pass: the wa.me deeplink body embeds "Lead ID: li_<nanoid>".
# When the customer sends that prefilled text, the id is an exact key — no
# time-window guessing needed, so both lookbacks can be generous.
_LEAD_ID_RE = re.compile(r"\bli_[a-z0-9]{6,20}\b")
_LEAD_ID_MSG_LOOKBACK = timedelta(hours=48)
_MIN_NATIONAL_DIGITS = 7  # refuse suffix phone-matching on shorter fragments


# ----------------------------------------------------------------------
# Phone normalisation
# ----------------------------------------------------------------------

_PHONE_RE = re.compile(r"[^\d]")


def parse_jsonb(value: Any, default: Any) -> Any:
    """Decode a jsonb column read through a codec-less asyncpg pool.

    Handles three shapes seen in prod `lead_intents`:
    - dict/None (pool with codec, or already decoded) → as-is
    - JSON text ('{"slug": ...}') → one json.loads
    - double-encoded JSON text ('"{\\"slug\\": ...}"', rows written while the
      repository json.dumps-ed on top of the pool codec, pre-fix 2026-06-11)
      → two json.loads
    Anything else (or invalid JSON) → `default`.
    """
    for _ in range(2):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value or "null")
        except ValueError:
            return default
    if value is None:
        return default
    return value if isinstance(value, dict) else default


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


def extract_lead_ids(text: str | None) -> list[str]:
    """All `li_<nanoid>` tokens in a message body, unique, in order."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for token in _LEAD_ID_RE.findall(text):
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


# ----------------------------------------------------------------------
# Main cron entry point
# ----------------------------------------------------------------------


async def run(dsn: str) -> dict[str, int]:
    """Single pass: deterministic Lead-ID matching first, then the
    phone+time-window fallback. Returns counts for observability logs."""
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        # ── Pass 1: deterministic — "Lead ID: li_…" in inbound WA text ──
        async with pool.acquire() as conn:
            ttl_intents = await _fetch_unmatched_intents_full_ttl(conn)
            lead_id_msgs = await _fetch_lead_id_messages(conn)

        unmatched = {i["id"]: i for i in ttl_intents}
        det_matched = 0
        det_unresolved = 0
        for msg in lead_id_msgs:
            for lead_id in extract_lead_ids(msg["text"]):
                intent = unmatched.get(lead_id)
                if intent is None:
                    continue
                async with pool.acquire() as conn:
                    client_id = msg["client_id"]
                    if client_id is None:
                        client_id = await _resolve_client_by_phone(
                            conn, normalise_phone(msg["phone"])
                        )
                    if client_id is None:
                        # Sender has no client row yet — retried while the
                        # message stays inside _LEAD_ID_MSG_LOOKBACK.
                        det_unresolved += 1
                        logger.info(
                            "lead_id %s seen (src=%s) but sender has no client row yet",
                            lead_id,
                            msg["source_table"],
                        )
                        continue
                    await _record_match(
                        conn,
                        intent=intent,
                        client={"id": client_id, "lead_metadata": None},
                        match_method="lead_id",
                    )
                unmatched.pop(lead_id, None)
                det_matched += 1

        # ── Pass 2: probabilistic fallback (phone + 30-min window) ──
        # Re-fetched from DB, so intents matched in pass 1 are excluded.
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
            "ttl_intents_seen": len(ttl_intents),
            "lead_id_messages_seen": len(lead_id_msgs),
            "matched_lead_id": det_matched,
            "lead_id_unresolved_sender": det_unresolved,
            "intents_seen": len(intents),
            "wa_touches_seen": len(messages),
            "matched_window": matched,
            "skipped": skipped,
        }
    finally:
        await pool.close()


async def _fetch_unmatched_intents_full_ttl(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Unmatched intents across the whole TTL (7 days) — safe for the
    deterministic pass because the Lead ID is an exact key."""
    rows = await conn.fetch(
        """
        SELECT id, source, context, utm, fingerprint, created_at
          FROM lead_intents
         WHERE matched_client_id IS NULL
           AND expires_at > NOW()
         ORDER BY created_at DESC
         LIMIT 500
        """,
    )
    return [
        {
            "id": r["id"],
            "source": r["source"],
            "context": parse_jsonb(r["context"], {}),
            "utm": parse_jsonb(r["utm"], None),
            "fingerprint": r["fingerprint"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def _fetch_lead_id_messages(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Inbound WA messages (last 48h) whose text contains a `li_` token.

    Two sources, queried separately (schemas differ):
    - meta_inbox_messages: the Meta business number webhook (live).
    - whatsapp_message_context: the wa-mirror of team numbers (sync to this
      DB stale since 2026-05-25, kept covered for when it revives).
    """
    cutoff = datetime.now(timezone.utc) - _LEAD_ID_MSG_LOOKBACK
    out: list[dict[str, Any]] = []

    rows = await conn.fetch(
        """
        SELECT m.body AS text, t.counterpart_phone AS phone,
               NULL AS client_id, m.created_at AS msg_at
          FROM meta_inbox_messages m
          JOIN meta_inbox_threads t ON t.thread_id = m.thread_id
         WHERE m.direction = 'inbound'
           AND m.created_at >= $1
           AND strpos(COALESCE(m.body, ''), 'li_') > 0
         ORDER BY m.created_at DESC
         LIMIT 500
        """,
        cutoff,
    )
    out.extend(
        {
            "text": r["text"],
            "phone": r["phone"],
            "client_id": r["client_id"],
            "msg_at": r["msg_at"],
            "source_table": "meta_inbox",
        }
        for r in rows
    )

    rows = await conn.fetch(
        """
        SELECT COALESCE(NULLIF(body, ''), message_text) AS text,
               COALESCE(counterpart_phone, sender_phone) AS phone,
               client_id,
               COALESCE(message_date, created_at) AS msg_at
          FROM whatsapp_message_context
         WHERE direction IN ('inbound', 'received')
           AND COALESCE(message_date, created_at) >= $1
           AND strpos(COALESCE(NULLIF(body, ''), message_text, ''), 'li_') > 0
         ORDER BY COALESCE(message_date, created_at) DESC
         LIMIT 500
        """,
        cutoff,
    )
    out.extend(
        {
            "text": r["text"],
            "phone": r["phone"],
            "client_id": r["client_id"],
            "msg_at": r["msg_at"],
            "source_table": "wa_mirror",
        }
        for r in rows
    )
    return out


async def _resolve_client_by_phone(
    conn: asyncpg.Connection, phone_norm: str | None
) -> Any | None:
    """clients.id whose phone/whatsapp ends with the national number.

    Suffix match on digits-only values tolerates +62/0/spacing variants.
    Prefers active clients, then most recent."""
    if not phone_norm or len(phone_norm) < _MIN_NATIONAL_DIGITS:
        return None
    row = await conn.fetchrow(
        r"""
        SELECT id
          FROM clients
         WHERE deleted_at IS NULL
           AND (
                regexp_replace(COALESCE(phone, ''), '\D', '', 'g') LIKE '%' || $1
             OR regexp_replace(COALESCE(whatsapp, ''), '\D', '', 'g') LIKE '%' || $1
           )
         ORDER BY CASE status
                    WHEN 'active' THEN 0
                    WHEN 'lead' THEN 1
                    WHEN 'prospect' THEN 2
                    ELSE 3
                  END,
                  created_at DESC
         LIMIT 1
        """,
        phone_norm,
    )
    return row["id"] if row else None


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
            "context": parse_jsonb(r["context"], {}),
            "utm": parse_jsonb(r["utm"], None),
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
    except (
        asyncpg.PostgresError,
        asyncpg.InterfaceError,  # W34: sibling of PostgresError, NOT subclass
    ):
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
    match_method: str = "phone_window",
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

        patch = {
            "lead_intent_id": intent["id"],
            "source_app": intent["source"],
            "context": intent["context"],
            "utm": intent["utm"],
            "match_method": match_method,
            "matched_at": datetime.now(timezone.utc).isoformat(),
        }

        new_source = f"{intent['source']}_handoff"
        # SQL-side merge: preserves pre-existing lead_metadata keys without a
        # read-modify-write race (this pool has no jsonb codec, so the patch
        # travels as JSON text + ::jsonb cast).
        await conn.execute(
            """
            UPDATE clients
               SET lead_source   = COALESCE(
                    NULLIF(lead_source, 'unknown'),
                    lead_source,
                    $1
                   ),
                   lead_metadata = COALESCE(lead_metadata, '{}'::jsonb) || $2::jsonb
             WHERE id = $3
            """,
            new_source,
            json.dumps(patch),
            client["id"],
        )

    logger.info(
        "matched intent_id=%s client_id=%s source=%s method=%s",
        intent["id"],
        client["id"],
        intent["source"],
        match_method,
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
