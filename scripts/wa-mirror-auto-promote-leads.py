#!/usr/bin/env python3
"""wa-mirror auto-promote leads → clients CRM (v2 - smarter matching)

Strategy v2:
1. Phone match in `clients` (any deleted_at) → ENRICH archived record (no new INSERT)
   - Restore (deleted_at=NULL) if was archived
   - Update full_name only if current is shorter / generic
   - Append a human WhatsApp recap to notes, never raw snippets/log text
2. Phone NOT in clients at all → INSERT new lead
3. Phone is team member (whatsapp_contacts.contact_type='team') → SKIP
4. Phone is Zero → SKIP

Settings:
- Threshold: 3 inbound minimum
- Cron: every 5min
- Silent (no Telegram)

Audit: ~/logs/wa-mirror-auto-promote.jsonl
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import asyncpg

ENV_FILE = Path.home() / ".wa-mirror.env"
DB_URL = None
WA_MIRROR_INTERNAL_KEY = None
WA_MIRROR_CRM_WRITE_KEY = None  # scoped key for POST /api/crm/clients/upsert-by-phone
for raw_line in ENV_FILE.read_text().splitlines():
    line = raw_line.strip()
    if line.startswith("WA_MIRROR_DATABASE_URL="):
        DB_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
    elif line.startswith("WA_MIRROR_INTERNAL_KEY="):
        WA_MIRROR_INTERNAL_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
    elif line.startswith("WA_MIRROR_CRM_WRITE_KEY="):
        WA_MIRROR_CRM_WRITE_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
if not DB_URL:
    print("ERR: WA_MIRROR_DATABASE_URL missing", file=sys.stderr)
    sys.exit(2)
# W50/W51-family fix 2026-06-06: removed vestigial "@localhost:15432" (Fly proxy)
# rewrite. WA_MIRROR_DATABASE_URL was repointed to local nuzantara_dev at the
# 2026-05-24 wa-mirror→local cutover; forcing :15432 sent local trust creds
# (no password) to the Fly server → asyncpg InvalidPasswordError. Use DSN as-is.
DB_URL = DB_URL.replace("postgres://", "postgresql://")

THRESHOLD_INBOUND = 3
DRY_RUN = os.environ.get("WA_AUTO_PROMOTE_DRY_RUN", "0") == "1"
AUDIT_LOG = Path.home() / "logs" / "wa-mirror-auto-promote.jsonl"
AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

# Backend endpoint for ensure-drive-folder (idempotent). When WA_MIRROR_INTERNAL_KEY
# is set, the script will call this endpoint AFTER each successful INSERT to trigger
# the same Drive folder structure that POST /api/crm/clients creates. Without the
# key, the inserted clients remain orphaned (Drive-wise) — that's how it was until
# 2026-05-21, when a backfill + this hardening landed (cicatrix scar 2026-05-21).
BACKEND_BASE_URL = os.environ.get("WA_MIRROR_BACKEND_URL", "https://nuzantara-rag.fly.dev")

TOPIC_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("visa, KITAS, or stay permit", ("visa", "kitas", "kitap", "permit", "evisa", "voa", "immigration")),
    ("extension or renewal", ("extension", "extend", "renew", "renewal", "perpanjang", "scadenza", "expire")),
    ("pricing, payment, or bank transfer", ("price", "cost", "fee", "harga", "berapa", "paid", "payment", "transfer", "bank")),
    ("documents to review", ("document", "passport", "npwp", "nib", "certificate", "dokumen", "surat")),
    ("address or address change", ("address", "alamat", "domicile", "changed")),
    ("family, birth, or children", ("baby", "babies", "pregnan", "obgyn", "hospital", "children", "spouse", "family")),
    ("timing or status update", ("when", "kapan", "quanto tempo", "how many days", "update", "status")),
    ("tax or company matter", ("tax", "pajak", "company", "pt pma", "director", "shareholder")),
]

TEAM_NAME_TOKENS = {
    "adit",
    "ari",
    "asya",
    "candra",
    "damar",
    "dea",
    "krisna",
    "lisa",
    "rina",
    "ruslana",
    "sahira",
    "sindy",
    "surya",
    "vino",
}


async def resolve_lid_messages(conn: asyncpg.Connection) -> dict[str, int]:
    """Resolve safe `(team_member_phone, LID) -> phone` evidence before CRM promotion.

    WhatsApp `@lid` identifiers are not phones. We only normalize rows when the
    same team/LID pair has exactly one phone signal elsewhere in the captured
    data or in `whatsapp_lid_phone_map`. Team phones are resolved for timeline
    readability but are not matched to client records.
    """
    async with conn.transaction():
        await conn.execute(
            """
            CREATE TEMP TABLE wa_mirror_lid_resolution ON COMMIT DROP AS
            WITH phone_evidence AS (
              SELECT team_member_phone,
                     counterpart_lid AS lid,
                     counterpart_phone AS phone,
                     sender_push_name_snapshot AS pushname,
                     message_date AS first_seen,
                     message_date AS last_seen
                FROM whatsapp_message_context
               WHERE source = 'wa_mirror'
                 AND counterpart_lid IS NOT NULL
                 AND counterpart_phone IS NOT NULL

              UNION ALL

              SELECT team_member_phone,
                     sender_lid AS lid,
                     sender_phone AS phone,
                     sender_push_name_snapshot AS pushname,
                     message_date AS first_seen,
                     message_date AS last_seen
                FROM whatsapp_message_context
               WHERE source = 'wa_mirror'
                 AND sender_lid IS NOT NULL
                 AND sender_phone IS NOT NULL

              UNION ALL

              SELECT team_member_phone,
                     lid,
                     jid_phone AS phone,
                     pushname,
                     first_seen,
                     last_seen
                FROM whatsapp_lid_phone_map
               WHERE jid_phone IS NOT NULL
            ),
            resolved_lids AS (
              SELECT team_member_phone,
                     lid,
                     MIN(phone) AS phone,
                     MAX(NULLIF(pushname, '')) AS pushname,
                     MIN(first_seen) AS first_seen,
                     MAX(last_seen) AS last_seen,
                     COUNT(DISTINCT phone) AS phone_count
                FROM phone_evidence
               WHERE phone IS NOT NULL
                 AND NULLIF(phone, '') IS NOT NULL
               GROUP BY team_member_phone, lid
            ),
            resolution_rows AS (
              SELECT w.id,
                     w.team_member_phone,
                     w.counterpart_lid AS lid,
                     r.phone,
                     r.pushname,
                     r.first_seen,
                     r.last_seen,
                     REGEXP_REPLACE(r.phone, '\\D', '', 'g') AS phone_digits,
                     CASE
                       WHEN REGEXP_REPLACE(r.phone, '\\D', '', 'g') LIKE '62%'
                       THEN '0' || SUBSTRING(REGEXP_REPLACE(r.phone, '\\D', '', 'g') FROM 3)
                       ELSE NULL
                     END AS local_digits
                FROM whatsapp_message_context w
                JOIN resolved_lids r
                  ON r.team_member_phone = w.team_member_phone
                 AND r.lid = w.counterpart_lid
                 AND r.phone_count = 1
               WHERE w.source = 'wa_mirror'
                 AND w.needs_lid_resolve IS TRUE
            ),
            classified AS (
              SELECT rr.*,
                     EXISTS (
                       SELECT 1
                         FROM whatsapp_contacts wc
                        WHERE wc.contact_type = 'team'
                          AND REGEXP_REPLACE(COALESCE(wc.phone_normalized, ''), '\\D', '', 'g')
                              IN (rr.phone_digits, rr.local_digits)
                     )
                     OR EXISTS (
                       SELECT 1
                         FROM whatsapp_team_sessions ts
                        WHERE REGEXP_REPLACE(COALESCE(ts.team_member_phone, ''), '\\D', '', 'g')
                              IN (rr.phone_digits, rr.local_digits)
                     ) AS is_team_phone
                FROM resolution_rows rr
            )
            SELECT c.id,
                   c.team_member_phone,
                   c.lid,
                   c.phone,
                   c.pushname,
                   c.first_seen,
                   c.last_seen,
                   c.is_team_phone,
                   cm.client_id
              FROM classified c
              LEFT JOIN LATERAL (
                SELECT cl.id AS client_id
                  FROM clients cl
                 WHERE c.is_team_phone IS FALSE
                   AND (
                     REGEXP_REPLACE(COALESCE(cl.phone_normalized, ''), '\\D', '', 'g') IN (c.phone_digits, c.local_digits)
                     OR REGEXP_REPLACE(COALESCE(cl.whatsapp, ''), '\\D', '', 'g') IN (c.phone_digits, c.local_digits)
                     OR REGEXP_REPLACE(COALESCE(cl.phone, ''), '\\D', '', 'g') IN (c.phone_digits, c.local_digits)
                   )
                 ORDER BY cl.id DESC
                 LIMIT 1
              ) cm ON TRUE
            """
        )

        stats = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS rows,
                   COUNT(DISTINCT team_member_phone || ':' || lid)::int AS team_lids,
                   COUNT(client_id)::int AS client_matched_rows,
                   COUNT(*) FILTER (WHERE is_team_phone IS TRUE)::int AS team_phone_rows
              FROM wa_mirror_lid_resolution
            """
        )

        out = {
            "updated_rows": int(stats["rows"] or 0),
            "resolved_team_lids": int(stats["team_lids"] or 0),
            "client_matched_rows": int(stats["client_matched_rows"] or 0),
            "team_phone_rows": int(stats["team_phone_rows"] or 0),
        }
        if DRY_RUN or out["updated_rows"] == 0:
            return out

        await conn.execute(
            """
            INSERT INTO whatsapp_lid_phone_map
              (team_member_phone, lid, jid_phone, pushname, source, first_seen, last_seen, resolved_at)
            SELECT team_member_phone,
                   lid,
                   phone,
                   MAX(NULLIF(pushname, '')) AS pushname,
                   'message_signal' AS source,
                   MIN(first_seen) AS first_seen,
                   MAX(last_seen) AS last_seen,
                   NOW() AS resolved_at
              FROM wa_mirror_lid_resolution
             GROUP BY team_member_phone, lid, phone
            ON CONFLICT (team_member_phone, lid) DO UPDATE
              SET jid_phone = COALESCE(whatsapp_lid_phone_map.jid_phone, EXCLUDED.jid_phone),
                  pushname = COALESCE(EXCLUDED.pushname, whatsapp_lid_phone_map.pushname),
                  last_seen = GREATEST(whatsapp_lid_phone_map.last_seen, EXCLUDED.last_seen),
                  resolved_at = COALESCE(whatsapp_lid_phone_map.resolved_at, EXCLUDED.resolved_at),
                  source = CASE
                    WHEN whatsapp_lid_phone_map.jid_phone IS NULL THEN 'message_signal'
                    ELSE whatsapp_lid_phone_map.source
                  END
            """
        )

        await conn.execute(
            """
            UPDATE whatsapp_message_context w
               SET counterpart_phone = r.phone,
                   phone_number = r.phone,
                   client_id = COALESCE(w.client_id, r.client_id),
                   needs_lid_resolve = FALSE,
                   updated_at = NOW()
              FROM wa_mirror_lid_resolution r
             WHERE w.id = r.id
            """
        )
        return out


async def find_candidates(conn: asyncpg.Connection) -> list[dict]:
    """All phones with ≥THRESHOLD inbound, not team / not Zero.
    Returns existing_client_id when phone matches a `clients` row (any state)."""
    # PERF (2026-06-20): the original query applied REGEXP_REPLACE per-row inside a
    # correlated scalar subquery against `clients` (11.5k rows) for EVERY candidate
    # phone (~300) — O(candidates × clients × regexp), non-sargable, which grew from
    # seconds (May, smaller `clients`) to 6+ MINUTES and hung the cron (faulthandler
    # caught it parked in asyncio select on this fetch). Fix: pre-normalize the phone
    # columns of clients / whatsapp_contacts / whatsapp_team_sessions ONCE in
    # MATERIALIZED CTEs, then match against the precomputed values via LEFT JOIN
    # LATERAL. Verified A/B on the live Pro DB: 379s → 8.7s (~43×), identical 297
    # candidates / 229 CRM matches. The command_timeout on the pool (see main) now
    # bounds any residual slow run so a cron tick dies clean instead of accumulating
    # zombie processes.
    rows = await conn.fetch(
        """
        WITH clients_norm AS MATERIALIZED (
          SELECT c.*,
                 REGEXP_REPLACE(COALESCE(c.phone_normalized, ''), '\\D', '', 'g') AS _pn,
                 REGEXP_REPLACE(COALESCE(c.whatsapp, ''), '\\D', '', 'g')         AS _wa,
                 REGEXP_REPLACE(COALESCE(c.phone, ''), '\\D', '', 'g')            AS _ph
            FROM clients c
        ),
        team_phones AS MATERIALIZED (
          SELECT REGEXP_REPLACE(COALESCE(wc.phone_normalized, wc.phone, ''), '\\D', '', 'g') AS phone
            FROM whatsapp_contacts wc
           WHERE wc.contact_type = 'team'
          UNION
          SELECT REGEXP_REPLACE(COALESCE(ts.phone_normalized, ts.team_member_phone, ''), '\\D', '', 'g') AS phone
            FROM whatsapp_team_sessions ts
        ),
        message_phone AS (
          SELECT
            NULLIF(REGEXP_REPLACE(COALESCE(counterpart_phone, ''), '\\D', '', 'g'), '') AS phone,
            direction,
            created_at,
            body,
            message_text,
            team_member_email,
            CASE
              WHEN direction = 'inbound'
               AND REGEXP_REPLACE(COALESCE(sender_phone, ''), '\\D', '', 'g')
                   NOT IN (SELECT phone FROM team_phones)
              THEN NULLIF(sender_push_name_snapshot, '')
              ELSE NULL
            END AS inbound_push_name
          FROM whatsapp_message_context
          WHERE source = 'wa_mirror'
            AND counterpart_phone IS NOT NULL
            AND needs_lid_resolve IS DISTINCT FROM TRUE
            AND COALESCE(chat_type, 'direct') <> 'group'
        ),
        per_phone AS (
          SELECT
            phone,
            COUNT(*) FILTER (WHERE direction = 'inbound') AS n_inbound,
            COUNT(*) AS n_total,
            MAX(created_at) AS last_seen,
            MIN(created_at) AS first_seen,
            (ARRAY_AGG(DISTINCT inbound_push_name)
              FILTER (WHERE inbound_push_name IS NOT NULL))[1] AS push_name,
            (ARRAY_AGG(DISTINCT team_member_email)
              FILTER (WHERE team_member_email IS NOT NULL AND direction = 'outbound'))[1] AS first_team_email,
            STRING_AGG(
              CASE WHEN direction='inbound' THEN COALESCE(NULLIF(body,''), NULLIF(message_text,''), '')
              ELSE NULL END,
              ' | ' ORDER BY created_at
            ) AS inbound_bodies
          FROM message_phone
          WHERE phone IS NOT NULL
            AND phone ~ '^[0-9]{6,}$'
          GROUP BY phone
          HAVING COUNT(*) FILTER (WHERE direction = 'inbound') >= $1
        ),
        with_keys AS (
          SELECT pp.*,
                 CASE
                   WHEN pp.phone LIKE '62%' THEN '0' || SUBSTRING(pp.phone FROM 3)
                   ELSE NULL
                 END AS local_phone
            FROM per_phone pp
        ),
        with_crm AS (
          SELECT pp.*,
                 -- Pick the BEST clients record for this phone (live > archived,
                 -- richer data > stub, latest updated_at wins). Matches against the
                 -- pre-normalized clients_norm (no per-row regexp) via LATERAL.
                 m.crm_match,
                 (
                   pp.phone IN (SELECT phone FROM team_phones)
                   OR pp.local_phone IN (SELECT phone FROM team_phones)
                 ) AS is_team,
                 (pp.phone = '628213107363') AS is_zero
          FROM with_keys pp
          LEFT JOIN LATERAL (
            -- strip the technical _pn/_wa/_ph helper columns so crm_match keeps the
            -- exact `clients` row shape the original row_to_json(c.*) produced. Cast
            -- back to `json` (text on the wire) so the Python `json.loads` path below
            -- is byte-for-byte unchanged from the original row_to_json behaviour.
            SELECT (to_jsonb(cn.*) - '_pn' - '_wa' - '_ph')::json AS crm_match
              FROM clients_norm cn
             WHERE cn._pn IN (pp.phone, pp.local_phone)
                OR cn._wa IN (pp.phone, pp.local_phone)
                OR cn._ph IN (pp.phone, pp.local_phone)
             ORDER BY
               (cn.deleted_at IS NOT NULL),       -- live records first
               (LENGTH(COALESCE(cn.full_name,'')) >= 5) DESC,
               cn.updated_at DESC NULLS LAST,
               cn.id DESC
             LIMIT 1
          ) m ON TRUE
        )
        SELECT * FROM with_crm
        WHERE NOT is_team AND NOT is_zero
        ORDER BY n_inbound DESC, last_seen DESC
        """,
        THRESHOLD_INBOUND,
    )
    out = []
    for r in rows:
        d = dict(r)
        d["crm_match"] = json.loads(d["crm_match"]) if d["crm_match"] else None
        out.append(d)
    return out


def looks_junk(name: str | None) -> bool:
    """pushName is unusable as full_name?"""
    if not name:
        return True
    n = name.strip()
    if not n or n.startswith(("wa:", "+")):
        return True
    if all(not ch.isalnum() for ch in n):  # emoji-only
        return True
    if "bali zero" in n.lower() or "bayu santero" in n.lower():
        return True
    normalized = re.sub(r"\s+", " ", n.lower()).strip()
    if normalized in TEAM_NAME_TOKENS:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    if tokens & TEAM_NAME_TOKENS and tokens & {"bali", "zero", "balizero", "bz", "team"}:
        return True
    return False


def pick_better_name(current: str | None, candidate: str | None) -> str | None:
    """Return candidate iff it's strictly more informative than current."""
    if looks_junk(candidate):
        return None
    if not current or current.startswith(("Lead +", "wa:", "+")) or current == ",":
        return candidate
    # Candidate must have a space (= first+last) and current must not
    if " " in candidate and " " not in current:
        return candidate
    # Candidate strictly longer + starts with current (e.g. "Davide Bisognini" vs "Davide")
    if candidate.lower().startswith(current.lower()) and len(candidate) > len(current) + 2:
        return candidate
    return None


def compact_text(value: str) -> str:
    """Collapse whitespace while keeping the content readable for internal notes."""
    return re.sub(r"\s+", " ", value).strip()


def is_low_signal_message(value: str) -> bool:
    """True for empty/media-only/emoji-only fragments that should not drive a recap."""
    text = compact_text(value)
    if not text:
        return True
    if len(text) <= 2:
        return True
    return not any(ch.isalnum() for ch in text)


def split_inbound_bodies(raw_bodies: str | None) -> list[str]:
    """Return deduped meaningful WhatsApp fragments from STRING_AGG output."""
    if not raw_bodies:
        return []
    seen: set[str] = set()
    messages: list[str] = []
    for part in raw_bodies.split(" | "):
        text = compact_text(part)
        if is_low_signal_message(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        messages.append(text)
    return messages


def infer_topics(messages: list[str]) -> list[str]:
    """Infer broad CRM themes without copying private WhatsApp text into notes."""
    haystack = " ".join(messages).lower()
    topics: list[str] = []
    for label, needles in TOPIC_PATTERNS:
        if any(needle in haystack for needle in needles):
            topics.append(label)
    return topics[:3]


def humanize_short_phrase(value: str) -> str:
    """Small phrase cleanup for deterministic, non-LLM recap sentences."""
    text = compact_text(value).strip(" .")
    text = re.sub(r"^the\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^trevor's address$", "Trevor's address", text, flags=re.IGNORECASE)
    text = re.sub(r"^babies$", "the baby-related steps", text, flags=re.IGNORECASE)
    text = re.sub(r"^the babies$", "the baby-related steps", text, flags=re.IGNORECASE)
    return text


def humanize_change_phrase(condition: str) -> str:
    return f"the change to {condition}"


def infer_specific_signal(messages: list[str]) -> str | None:
    """Return one human sentence when the conversation has a clear operational signal."""
    for message in messages:
        wait_after = re.search(
            r"after (?P<condition>.+?) has been changed.*?wait for (?P<next>.+)$",
            message,
            flags=re.IGNORECASE,
        )
        if wait_after:
            condition = humanize_short_phrase(wait_after.group("condition"))
            next_step = humanize_short_phrase(wait_after.group("next"))
            return (
                f"The conversation suggests they are waiting for {humanize_change_phrase(condition)} "
                f"before moving forward with {next_step}."
            )

    haystack = " ".join(messages).lower()
    if "need to understand" in haystack and "visa" in haystack:
        return "The conversation is about comparing visa options and what each option allows in practice."
    if "bank transfer" in haystack or "pay" in haystack or "payment" in haystack:
        return "The conversation is about payment or bank transfer coordination."
    if "any update" in haystack or "how it's going" in haystack or "status" in haystack:
        return "The conversation is asking for an update on the case status."
    return None


def format_seen_range(cand: dict[str, Any]) -> str:
    first_seen = cand["first_seen"].strftime("%Y-%m-%d")
    last_seen = cand["last_seen"].strftime("%Y-%m-%d")
    if first_seen == last_seen:
        return f"on {first_seen}"
    return f"between {first_seen} and {last_seen}"


def build_human_whatsapp_recap(cand: dict[str, Any], *, existing: bool) -> str:
    """Create CRM-safe human language for `clients.notes`.

    This intentionally avoids words like "auto-promoted", "inbound", "snippet",
    raw phone dumps, and raw transcript blocks. The full conversation belongs in
    the WhatsApp timeline; the client note should be a useful consultant recap.
    """
    messages = split_inbound_bodies(cand.get("inbound_bodies"))
    specific_signal = infer_specific_signal(messages)
    topics = infer_topics(messages)
    n_in = int(cand["n_inbound"])
    seen_range = format_seen_range(cand)
    today = datetime.now(timezone.utc).date().isoformat()

    opening = (
        f"WhatsApp conversation update, {today}: {n_in} client messages were received {seen_range}."
        if existing
        else f"WhatsApp lead created on {today} after {n_in} client messages received {seen_range}."
    )
    if specific_signal:
        topic_line = specific_signal
    elif topics:
        topic_line = "Main theme: " + ", ".join(topics) + "."
    elif messages:
        topic_line = (
            "The conversation contains useful signals, but the WhatsApp timeline should be "
            "reviewed before deciding the correct case."
        )
    else:
        topic_line = (
            "The messages are very short or do not contain enough text; review the timeline "
            "before creating a case."
        )

    next_step = "Next step: review the WhatsApp timeline, confirm the client and case, then decide the follow-up."
    return f"{opening} {topic_line} {next_step}"


async def enrich_existing(conn: asyncpg.Connection, cand: dict, crm: dict) -> dict:
    """Update an existing clients record (live or archived) with new info.

    Idempotency:
    - SKIP if already enriched within 24h AND n_inbound unchanged AND not archived.
    - Restore-from-archive is always allowed (priority signal).
    - Name upgrade is always allowed if pick_better_name returns truthy.
    - Audit note is appended ONLY when something material changed.
    """
    phone = cand["phone"]
    cid = crm["id"]
    push_name = cand.get("push_name")
    n_in = cand["n_inbound"]
    was_archived = bool(crm.get("deleted_at"))

    # --- Idempotency probe: skip if nothing material to do ---------------------
    # Check the last enrich audit log entry for this phone.
    last_audit = await conn.fetchrow(
        """
        SELECT updated_at,
               (SELECT COUNT(*)::int
                  FROM whatsapp_message_context m
                  WHERE NULLIF(REGEXP_REPLACE(COALESCE(m.counterpart_phone, ''), '\\D', '', 'g'), '') = $1
                    AND m.direction='inbound'
                    AND m.created_at <= clients.updated_at
               ) AS n_inbound_at_last_update
        FROM clients
        WHERE id = $2
        """,
        phone, cid,
    )
    prev_n = (last_audit["n_inbound_at_last_update"] if last_audit else None) or 0
    last_upd = last_audit["updated_at"] if last_audit else None
    age = (datetime.now(timezone.utc) - last_upd) if last_upd else None

    better = pick_better_name(crm.get("full_name"), push_name)

    # Skip conditions: live record, recent update (<24h), no new inbound, no name upgrade
    if (
        not was_archived
        and not better
        and age is not None
        and age < timedelta(hours=24)
        and n_in <= prev_n
    ):
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phone": phone, "existing_id": cid,
            "action": "SKIPPED_IDEMPOTENT",
            "prev_n": prev_n, "n_inbound": n_in,
            "age_hours": round(age.total_seconds()/3600, 1) if age else None,
        }

    updates: list[str] = []
    params: list = []
    p_idx = 1

    # Restore from archive (material change)
    if was_archived:
        updates.append("deleted_at = NULL")
        updates.append("deleted_by = NULL")

    # Improve full_name (material change)
    if better:
        updates.append(f"full_name = ${p_idx}")
        params.append(better)
        p_idx += 1

    # Audit note: append ONLY if (a) first time ever for this phone OR
    # (b) archived→live restore OR (c) name upgrade OR (d) ≥24h since last update
    # AND there are NEW inbound. This is the rule that previously was missing.
    should_append_note = (
        was_archived or better is not None
        or last_upd is None
        or (age is not None and age >= timedelta(hours=24) and n_in > prev_n)
    )
    if should_append_note:
        note_addendum = "\n\n" + build_human_whatsapp_recap(cand, existing=True)
        updates.append(f"notes = COALESCE(NULLIF(notes,''),'') || ${p_idx}")
        params.append(note_addendum)
        p_idx += 1

    if not updates:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "phone": phone, "existing_id": cid,
            "action": "SKIPPED_NO_CHANGE",
            "n_inbound": n_in,
        }

    updates.append("updated_at = NOW()")
    updates.append("updated_by = 'wa-mirror-auto-promote'")

    audit = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phone": phone,
        "existing_id": cid,
        "existing_name": crm.get("full_name"),
        "was_archived": was_archived,
        "name_improved_to": better,
        "n_inbound": n_in,
        "prev_n_inbound": prev_n,
        "note_appended": should_append_note,
    }

    if DRY_RUN:
        audit["action"] = "DRY_RUN_ENRICH"
        return audit

    sql = f"UPDATE clients SET {', '.join(updates)} WHERE id = ${p_idx} RETURNING id"
    params.append(cid)
    await conn.fetchval(sql, *params)
    audit["action"] = "ENRICHED"
    audit["restored"] = was_archived
    return audit


async def insert_new(conn: asyncpg.Connection, cand: dict) -> dict:
    """INSERT a brand new lead (no clients record at all)."""
    phone = cand["phone"]
    push_name = cand.get("push_name")
    full_name = push_name if push_name and not looks_junk(push_name) else f"Lead +{phone}"
    n_in = cand["n_inbound"]
    assigned = cand.get("first_team_email")
    notes = build_human_whatsapp_recap(cand, existing=False)

    audit = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phone": phone,
        "full_name": full_name,
        "n_inbound": n_in,
        "assigned_to": assigned,
    }

    if DRY_RUN:
        audit["action"] = "DRY_RUN_INSERT"
        return audit

    async with conn.transaction():
        # Race-safe re-check
        exists = await conn.fetchval(
            "SELECT 1 FROM clients WHERE phone_normalized = $1 LIMIT 1", phone
        )
        if exists:
            audit["action"] = "SKIPPED_RACE"
            return audit
        new_id = await conn.fetchval(
            """
            INSERT INTO clients (
              full_name, phone, whatsapp, phone_normalized,
              status, client_type, lead_source, assigned_to,
              created_by, updated_by, notes
            ) VALUES (
              $1, '+' || $2, '+' || $2, $2,
              'lead', 'individual', 'whatsapp_auto', $3,
              'wa-mirror-auto-promote', 'wa-mirror-auto-promote', $4
            )
            RETURNING id
            """,
            full_name, phone, assigned, notes,
        )
    audit["action"] = "INSERTED"
    audit["new_id"] = new_id

    # Trigger Drive folder creation via backend (idempotent — endpoint is no-op
    # if folder already exists). Fire-and-forget: failure here MUST NOT block
    # the insert audit (we already have the lead in DB). The daily
    # reconciliation cron catches any drift.
    audit["drive_folder"] = await _trigger_drive_folder(new_id)
    return audit


async def _trigger_drive_folder(client_id: int) -> dict:
    """POST /api/crm/clients/{id}/ensure-drive-folder via X-Internal-Key."""
    if not WA_MIRROR_INTERNAL_KEY:
        return {"action": "SKIPPED_NO_KEY"}
    try:
        import httpx
    except ImportError:
        return {"action": "SKIPPED_NO_HTTPX"}

    url = f"{BACKEND_BASE_URL.rstrip('/')}/api/crm/clients/{client_id}/ensure-drive-folder"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                url,
                headers={"X-Internal-Key": WA_MIRROR_INTERNAL_KEY},
            )
        if r.status_code == 200:
            body = r.json()
            return {
                "action": "CREATED" if body.get("created") else "ALREADY_EXISTS",
                "folder_id": body.get("folder_id"),
            }
        return {
            "action": "HTTP_ERROR",
            "status": r.status_code,
            "detail": (r.text or "")[:200],
        }
    except Exception as e:
        return {"action": "EXCEPTION", "error": str(e)[:200]}


def write_audit(record: dict[str, Any]) -> None:
    """Append persistent audit only for real runs; dry-run stays read-only."""
    if DRY_RUN:
        return
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


async def upsert_via_api(cand: dict) -> dict:
    """Promote a candidate to the FLY CRM via POST /api/crm/clients/upsert-by-phone.

    Post 2026-06-06: the wa-corpus lives LOCAL (Law 2) but the CRM of record is Fly,
    so writes go through the backend (which does the authoritative phone-match,
    enrich-or-insert, cache invalidation). This script is now a "dumb pipe": it reads
    wa-corpus locally, builds a SANITIZED payload (name + human recap — never raw log
    text), and lets the endpoint decide. Supersedes enrich_existing()/insert_new()
    (kept below for reference; no longer called).
    """
    phone = cand["phone"]
    push_name = cand.get("push_name")
    full_name = push_name if (push_name and not looks_junk(push_name)) else f"Lead +{phone}"
    # crm_match is now only a LOCAL advisory hint for recap WORDING — never the write
    # decision (the endpoint matches against the authoritative Fly CRM).
    existing_hint = bool(cand.get("crm_match"))
    notes = build_human_whatsapp_recap(cand, existing=existing_hint)
    assigned = cand.get("first_team_email")

    audit: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phone": phone,
        "full_name": full_name,
        "n_inbound": cand.get("n_inbound"),
        "assigned_to": assigned,
    }
    if DRY_RUN:
        audit["action"] = "DRY_RUN_UPSERT"
        return audit
    if not WA_MIRROR_CRM_WRITE_KEY:
        audit["action"] = "SKIPPED_NO_WRITE_KEY"
        return audit
    try:
        import httpx
    except ImportError:
        audit["action"] = "SKIPPED_NO_HTTPX"
        return audit

    url = f"{BACKEND_BASE_URL.rstrip('/')}/api/crm/clients/upsert-by-phone"
    payload = {
        "phone_normalized": phone,
        "full_name": full_name,
        "lead_source": "whatsapp_auto",
        "assigned_to": assigned,
        "notes_append": notes,
        "create_if_missing": True,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                url,
                headers={"X-CRM-Write-Key": WA_MIRROR_CRM_WRITE_KEY},
                json=payload,
            )
    except Exception as e:
        audit["action"] = "HTTP_EXCEPTION"
        audit["error"] = str(e)[:200]
        return audit
    if r.status_code != 200:
        audit["action"] = "HTTP_ERROR"
        audit["status"] = r.status_code
        audit["detail"] = (r.text or "")[:200]
        return audit

    body = r.json()
    audit["action"] = str(body.get("action", "unknown")).upper()  # INSERTED/ENRICHED/SKIPPED_*
    audit["client_id"] = body.get("client_id")
    audit["was_created"] = body.get("was_created")
    audit["matched_count"] = body.get("matched_count")
    audit["recap_applied"] = body.get("recap_applied")
    # Drive folder for genuinely-new leads only (endpoint is idempotent).
    if body.get("was_created") and body.get("client_id"):
        audit["drive_folder"] = await _trigger_drive_folder(body["client_id"])
    return audit


async def main() -> None:
    started = datetime.now(timezone.utc)
    # command_timeout bounds EVERY query: a slow/hung read (the 2026-06-20 incident:
    # find_candidates parked >6min and the cron accumulated zombie processes under
    # StartInterval) now raises asyncpg.QueryCanceledError instead of hanging forever,
    # so a tick dies clean. 90s is comfortably above the optimized find_candidates
    # (~9s on a cold local PG) but well below the StartInterval cadence.
    # Self-heal visibility #1: a missing write key used to make EVERY candidate return
    # SKIPPED_NO_WRITE_KEY, which is NOT audited (write_audit skips SKIPPED_*) — the
    # log stayed green while ZERO leads reached Fly for 15 days (the 2026-06-20
    # incident: key evaporated from ~/.wa-mirror.env ~05-27, last real push 06-05).
    # Emit a LOUD, always-audited DEGRADED record so a watcher can detect the silent
    # outage. DRY_RUN is exempt (no key needed to preview).
    if not DRY_RUN and not WA_MIRROR_CRM_WRITE_KEY:
        degraded = {
            "ts": started.isoformat(),
            "action": "DEGRADED_NO_WRITE_KEY",
            "detail": "WA_MIRROR_CRM_WRITE_KEY absent from env — every candidate would "
            "SKIP and NOT reach Fly. Restore the key in ~/.wa-mirror.env.",
        }
        print(json.dumps(degraded))
        write_audit(degraded)

    # Self-heal #3: the local Postgres may be DOWN at startup (the 2026-06-17 incident:
    # the Pro was powered off ~8h; this script then hammered a dead DB and spat 23 raw
    # OSError tracebacks to stderr until PG came back — Connect call failed
    # 127.0.0.1:5432). create_pool fails BEFORE command_timeout and BEFORE the read
    # guard above, so wrap it in a bounded retry-with-backoff (superscar #8 — a network
    # service touched without retry). If PG is still unreachable after the retries,
    # emit a clean, always-audited DEGRADED_DB_UNREACHABLE and exit; the next tick (or
    # a recovered DB) succeeds — no raw traceback, no half-state.
    pool = None
    last_db_err: Exception | None = None
    for attempt in range(3):
        try:
            pool = await asyncpg.create_pool(
                DB_URL, min_size=1, max_size=2, ssl=False, command_timeout=90.0
            )
            break
        except (
            OSError,
            asyncpg.PostgresError,
            asyncpg.InterfaceError,  # sibling of PostgresError, NOT subclass — the
            # stale-connection class (W29/W32/W34 silent-death); a reconnect after a
            # PG restart raises this, not PostgresError.
            asyncio.TimeoutError,
        ) as exc:
            last_db_err = exc
            if attempt < 2:
                await asyncio.sleep(2.0 * (attempt + 1))  # 2s, 4s backoff
    if pool is None:
        degraded = {
            "ts": started.isoformat(),
            "action": "DEGRADED_DB_UNREACHABLE",
            "detail": f"local Postgres unreachable after 3 attempts "
            f"({type(last_db_err).__name__}: {str(last_db_err)[:160]}) — likely the "
            "Pro just rebooted and PG is not up yet; tick aborted clean, retries next "
            "cycle.",
        }
        print(json.dumps(degraded))
        write_audit(degraded)
        return
    try:
        async with pool.acquire() as conn:
            try:
                lid_resolution = await resolve_lid_messages(conn)
                candidates = await find_candidates(conn)
            except (asyncpg.QueryCanceledError, asyncio.TimeoutError) as exc:
                # Self-heal #2: a query that exceeds command_timeout (the find_candidates
                # hang) now dies clean and LOUD instead of parking forever and breeding
                # zombie processes under StartInterval. The next tick retries.
                degraded = {
                    "ts": started.isoformat(),
                    "action": "DEGRADED_QUERY_TIMEOUT",
                    "detail": f"{type(exc).__name__}: read query exceeded "
                    "command_timeout — tick aborted clean, will retry next cycle.",
                }
                print(json.dumps(degraded))
                write_audit(degraded)
                return

            inserted = enriched_archive = enriched_live = skipped_idem = 0
            for cand in candidates:
                # Write goes to the FLY CRM via the backend API (the endpoint is the
                # authoritative matcher/enricher). conn is used ONLY for the local
                # wa-corpus reads above (find_candidates / resolve_lid_messages).
                rec = await upsert_via_api(cand)
                act = rec["action"]
                if act == "INSERTED":
                    inserted += 1
                elif act == "ENRICHED":
                    enriched_live += 1
                elif act.startswith("SKIPPED") or act.startswith("DRY_RUN"):
                    skipped_idem += 1
                # Audit non-skip / non-dry events only (cuts log noise 90%+)
                if not act.startswith("SKIPPED") and not act.startswith("DRY_RUN"):
                    write_audit(rec)

            summary = {
                "ts": started.isoformat(),
                "candidates": len(candidates),
                "inserted_new": inserted,
                "enriched_archive_restored": enriched_archive,
                "enriched_live": enriched_live,
                "skipped_idempotent": skipped_idem,
                "lid_resolution": lid_resolution,
                "dry_run": DRY_RUN,
            }
            print(json.dumps(summary, default=str))
            write_audit(summary)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
