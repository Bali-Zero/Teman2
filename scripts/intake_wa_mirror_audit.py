#!/usr/bin/env python3
"""Read-only WA Mirror -> intake audit.

This answers the operational questions around the first intake ring without
printing client PII:

- which WhatsApp mirror rows pass the technical media filter;
- how many queued documents are direct vs group;
- whether direct documents map to no/one/multiple CRM clients by phone;
- whether any group documents still carry unsafe phone/client hints;
- what the latest routing proposal bucket looks like.

Run on the Pro against the local DB. The script performs no writes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger("intake_wa_mirror_audit")

DEFAULT_MEDIA_TYPES = ("document", "image")
DEFAULT_DB_URL = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"


SOURCE_CONTEXT_COLUMN_SQL = """
SELECT EXISTS (
    SELECT 1
      FROM information_schema.columns
     WHERE table_name = 'intake_queue'
       AND column_name = 'source_context'
) AS present
"""

SOURCE_FUNNEL_SQL = """
WITH base AS (
    SELECT
        CASE
            WHEN chat_type = 'group' OR group_jid IS NOT NULL THEN 'group'
            WHEN chat_type = 'direct' OR (chat_type IS NULL AND group_jid IS NULL) THEN 'direct'
            ELSE 'unknown'
        END AS chat_scope,
        direction,
        media_stored_path,
        media_type,
        baileys_message_id
      FROM whatsapp_message_context
)
SELECT chat_scope,
       count(*) AS all_messages,
       count(*) FILTER (WHERE direction = 'inbound') AS inbound_messages,
       count(*) FILTER (
           WHERE direction = 'inbound'
             AND media_stored_path IS NOT NULL
       ) AS inbound_with_blob_path,
       count(*) FILTER (
           WHERE direction = 'inbound'
             AND media_stored_path IS NOT NULL
             AND media_type = ANY($1::text[])
       ) AS eligible_media,
       count(*) FILTER (
           WHERE direction = 'inbound'
             AND media_stored_path IS NOT NULL
             AND media_type = ANY($1::text[])
             AND baileys_message_id IS NOT NULL
       ) AS eligible_with_baileys_id
  FROM base
 GROUP BY chat_scope
 ORDER BY chat_scope
"""

BLOB_PATH_CANDIDATE_SQL = """
SELECT media_stored_path
  FROM whatsapp_message_context
 WHERE direction = 'inbound'
   AND media_stored_path IS NOT NULL
   AND media_type = ANY($1::text[])
   AND baileys_message_id IS NOT NULL
"""

INTAKE_STATUS_WITH_CONTEXT_SQL = """
SELECT
    CASE
        WHEN w.chat_type = 'group' OR w.group_jid IS NOT NULL THEN 'group'
        WHEN w.chat_type = 'direct' OR (w.chat_type IS NULL AND w.group_jid IS NULL) THEN 'direct'
        ELSE 'unknown'
    END AS chat_scope,
    q.status,
    count(*) AS queue_rows,
    count(*) FILTER (WHERE q.sender_phone IS NOT NULL) AS with_sender_phone,
    count(*) FILTER (WHERE q.client_id_hint IS NOT NULL) AS with_client_id_hint,
    count(*) FILTER (WHERE q.source_context <> '{}'::jsonb) AS with_source_context
  FROM intake_queue q
  JOIN whatsapp_message_context w
    ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
 WHERE q.source = 'whatsapp'
   AND q.source_ref LIKE 'wa-mirror:%'
 GROUP BY chat_scope, q.status
 ORDER BY chat_scope, q.status
"""

INTAKE_STATUS_WITHOUT_CONTEXT_SQL = """
SELECT
    CASE
        WHEN w.chat_type = 'group' OR w.group_jid IS NOT NULL THEN 'group'
        WHEN w.chat_type = 'direct' OR (w.chat_type IS NULL AND w.group_jid IS NULL) THEN 'direct'
        ELSE 'unknown'
    END AS chat_scope,
    q.status,
    count(*) AS queue_rows,
    count(*) FILTER (WHERE q.sender_phone IS NOT NULL) AS with_sender_phone,
    count(*) FILTER (WHERE q.client_id_hint IS NOT NULL) AS with_client_id_hint,
    0::bigint AS with_source_context
  FROM intake_queue q
  JOIN whatsapp_message_context w
    ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
 WHERE q.source = 'whatsapp'
   AND q.source_ref LIKE 'wa-mirror:%'
 GROUP BY chat_scope, q.status
 ORDER BY chat_scope, q.status
"""

GROUP_SAFETY_SQL = """
SELECT count(*) AS group_queue_rows,
       count(*) FILTER (WHERE q.sender_phone IS NOT NULL) AS unsafe_sender_phone_rows,
       count(*) FILTER (WHERE q.client_id_hint IS NOT NULL) AS unsafe_client_id_hint_rows
  FROM intake_queue q
  JOIN whatsapp_message_context w
    ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
 WHERE q.source = 'whatsapp'
   AND q.source_ref LIKE 'wa-mirror:%'
   AND (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
"""

DIRECT_CRM_MATCH_SQL = """
WITH direct_docs AS (
    SELECT q.id AS queue_id,
           regexp_replace(
               COALESCE(
                   NULLIF(w.sender_phone, ''),
                   NULLIF(w.counterpart_phone, ''),
                   NULLIF(w.phone_number, ''),
                   ''
               ),
               '[^0-9]', '', 'g'
           ) AS phone_digits
      FROM intake_queue q
      JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
       AND q.source_ref LIKE 'wa-mirror:%'
       AND NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
),
client_phones AS (
    SELECT id AS client_id,
           regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') AS phone_digits
      FROM clients
     WHERE deleted_at IS NULL
       AND COALESCE(phone_normalized, '') <> ''
    UNION
    SELECT id AS client_id,
           regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') AS phone_digits
      FROM clients
     WHERE deleted_at IS NULL
       AND COALESCE(phone, '') <> ''
    UNION
    SELECT id AS client_id,
           regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g') AS phone_digits
      FROM clients
     WHERE deleted_at IS NULL
       AND COALESCE(whatsapp, '') <> ''
),
team_phones AS (
    SELECT regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') AS phone_digits
      FROM whatsapp_contacts
     WHERE contact_type = 'team'
       AND COALESCE(phone_normalized, '') <> ''
    UNION
    SELECT DISTINCT regexp_replace(COALESCE(team_member_phone, ''), '[^0-9]', '', 'g') AS phone_digits
      FROM whatsapp_message_context
     WHERE COALESCE(team_member_phone, '') <> ''
),
matched AS (
    SELECT d.queue_id,
           d.phone_digits,
           count(DISTINCT c.client_id) AS client_matches,
           EXISTS (
               SELECT 1
                 FROM team_phones t
                WHERE t.phone_digits = d.phone_digits
                  AND t.phone_digits <> ''
           ) AS has_team_phone_signal
      FROM direct_docs d
      LEFT JOIN client_phones c
        ON c.phone_digits = d.phone_digits
       AND c.phone_digits <> ''
     GROUP BY d.queue_id, d.phone_digits
)
SELECT CASE
           WHEN phone_digits = '' THEN 'missing_phone'
           WHEN client_matches = 0 THEN 'prospect_no_client'
           WHEN client_matches = 1 THEN 'lead_one_client'
           ELSE 'ambiguous_multi_client'
       END AS match_bucket,
       count(*) AS queue_rows,
       count(DISTINCT NULLIF(phone_digits, '')) AS distinct_phone_keys,
       count(*) FILTER (WHERE has_team_phone_signal) AS team_phone_rows
  FROM matched
 GROUP BY match_bucket
 ORDER BY match_bucket
"""

ROUTING_PROPOSAL_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (queue_id)
           queue_id,
           status,
           entity_resolution->>'decision' AS entity_decision
      FROM document_routing_proposal
     ORDER BY queue_id, created_at DESC, id DESC
)
SELECT
    CASE
        WHEN w.chat_type = 'group' OR w.group_jid IS NOT NULL THEN 'group'
        WHEN w.chat_type = 'direct' OR (w.chat_type IS NULL AND w.group_jid IS NULL) THEN 'direct'
        ELSE 'unknown'
    END AS chat_scope,
    COALESCE(l.status, 'NO_PROPOSAL') AS proposal_status,
    COALESCE(l.entity_decision, 'NO_PROPOSAL') AS entity_decision,
    count(*) AS queue_rows
  FROM intake_queue q
  JOIN whatsapp_message_context w
    ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
  LEFT JOIN latest l
    ON l.queue_id = q.id
 WHERE q.source = 'whatsapp'
   AND q.source_ref LIKE 'wa-mirror:%'
 GROUP BY chat_scope, proposal_status, entity_decision
 ORDER BY chat_scope, proposal_status, entity_decision
"""


def _media_types(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_MEDIA_TYPES
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    return values or DEFAULT_MEDIA_TYPES


def _records(rows: list[asyncpg.Record]) -> list[dict[str, int | str | bool | None]]:
    return [dict(row) for row in rows]


async def _column_exists(conn: asyncpg.Connection) -> bool:
    return bool(await conn.fetchval(SOURCE_CONTEXT_COLUMN_SQL))


async def _disk_check(conn: asyncpg.Connection, media_types: tuple[str, ...]) -> dict[str, int]:
    rows = await conn.fetch(BLOB_PATH_CANDIDATE_SQL, list(media_types))
    missing = 0
    for row in rows:
        path = row["media_stored_path"]
        if path and not Path(str(path)).exists():
            missing += 1
    return {"eligible_blob_paths_checked": len(rows), "eligible_blob_paths_missing_on_disk": missing}


async def run_audit(
    database_url: str,
    *,
    media_types: tuple[str, ...] = DEFAULT_MEDIA_TYPES,
    check_disk: bool = False,
) -> dict[str, Any]:
    pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            source_context_available = await _column_exists(conn)
            source_funnel = _records(await conn.fetch(SOURCE_FUNNEL_SQL, list(media_types)))
            intake_status_sql = (
                INTAKE_STATUS_WITH_CONTEXT_SQL
                if source_context_available
                else INTAKE_STATUS_WITHOUT_CONTEXT_SQL
            )
            intake_status = _records(await conn.fetch(intake_status_sql))
            group_safety = dict(await conn.fetchrow(GROUP_SAFETY_SQL))
            direct_crm_match = _records(await conn.fetch(DIRECT_CRM_MATCH_SQL))
            routing_proposals = _records(await conn.fetch(ROUTING_PROPOSAL_SQL))
            disk = await _disk_check(conn, media_types) if check_disk else None
    finally:
        await pool.close()

    report: dict[str, Any] = {
        "audit": "intake_wa_mirror",
        "pii_policy": "counts_only_no_raw_phone_no_raw_group_subject",
        "media_types": list(media_types),
        "schema": {"source_context_available": source_context_available},
        "source_funnel": source_funnel,
        "intake_status": intake_status,
        "group_safety": group_safety,
        "direct_crm_match": direct_crm_match,
        "routing_proposals": routing_proposals,
    }
    if disk is not None:
        report["disk_check"] = disk
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only PII-safe WA Mirror intake audit")
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "INTAKE_DATABASE_URL",
            os.getenv("LOCAL_DATABASE_URL", DEFAULT_DB_URL),
        ),
        help="local Postgres DSN (default: INTAKE_DATABASE_URL/LOCAL_DATABASE_URL/nuzantara_dev)",
    )
    parser.add_argument(
        "--media-types",
        default=",".join(DEFAULT_MEDIA_TYPES),
        help="comma-separated whatsapp_message_context media_type values",
    )
    parser.add_argument(
        "--check-disk",
        action="store_true",
        help="also check whether eligible media_stored_path files exist on this machine",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    return parser


async def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("INTAKE_WA_MIRROR_AUDIT_LOG_LEVEL", "WARNING"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    args = build_parser().parse_args(argv)
    report = await run_audit(
        args.database_url,
        media_types=_media_types(args.media_types),
        check_disk=args.check_disk,
    )
    indent = 2 if args.pretty else None
    sys.stdout.write(json.dumps(report, indent=indent, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
