#!/usr/bin/env python3
"""Retroactive intake catalog v2: reprocess weak proposals + backfill the watermark gap.

Two one-shot modes (combinable; run on the Pro against LOCAL nuzantara_dev):

``--backfill``
    The wa-mirror sweeper (scripts/wa_mirror_intake_sweeper.py) seeded its
    first-run watermark to max(id), so every historical inbound media row
    (id <= watermark, ~1,073 at audit time) was never enqueued. This mode
    anti-joins ``whatsapp_message_context`` against ``intake_queue`` on
    ``source_ref = 'wa-mirror:<baileys_message_id>'`` and enqueues the missing
    rows through the SAME code path the sweeper uses
    (backend.services.intake.enqueue — idempotent on intake_key), including
    ``sender_phone`` (m225) + ``received_by``.

``--reprocess``
    Today's review queue carries proposals that are useless to a reviewer:
    ``review_pending`` AND (doc_type=unknown OR entity NO_MATCH). This mode
    marks those proposals ``status='superseded'`` (m226) and resets their queue
    rows per the v2 worker reset contract (status='pending', stage=NULL, lease
    cleared, attempts=0, next_visible_at=now(), stage_output='{}') with a
    BUMPED ``pipeline_version`` (default ``v2.1-retro``) so
    ``routing._make_routing_key`` yields a FRESH routing_key → a new proposal
    from the improved pipeline (phone signal + vision classify fallback).

``--scrub-group-phone``
    Historical wa-mirror group documents may still carry ``intake_queue.sender_phone``
    from before the group/direct split. Group sender numbers are participant
    phones, often Bali Zero teammates forwarding documents, so they must not be
    reused as client identity hints on reruns. This mode clears
    ``sender_phone`` and ``client_id_hint`` only for queue rows joined to
    ``whatsapp_message_context`` group chats.

``--backfill-source-context``
    Existing wa-mirror queue rows may predate migration 232. This mode annotates
    them with PII-safe transport context (direct/group + identity policy) without
    copying raw group JIDs, raw group subjects, or extra phone values.

Law 2 / UU-PDP: everything local (local DB, local blobs, downstream OCR is
local Ollama). Sender phones are PII — never logged at INFO with the value.

DRY-RUN BY DEFAULT: prints counts only. Pass ``--apply`` to execute.

Environment:
- INTAKE_DATABASE_URL / DATABASE_URL (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import asyncpg

# Reuse the shipped, tested enqueue core (same import shim as the sweeper).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
from backend.services.intake.enqueue import enqueue

logger = logging.getLogger("intake_reprocess_backlog")

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_PIPELINE_VERSION = "v2.1-retro"
DEFAULT_MEDIA_TYPES = ("document", "image")

# Sweeper watermark file (the backfill ceiling: rows ABOVE it are the sweeper's).
WATERMARK_FILE = Path.home() / ".cell-bridge-state" / "wa_mirror_sweep_last_id.txt"

_SOURCE = "whatsapp"

# --- SQL (module-level constants: pure-testable) ---------------------------

# Proposals that are pending review but carry nothing a reviewer can act on.
REPROCESS_SELECT_SQL = """
SELECT p.id AS proposal_id, p.queue_id
FROM document_routing_proposal p
WHERE p.status = 'review_pending'
  AND ((p.routing->>'doc_type') = 'unknown'
       OR (p.entity_resolution->>'decision') = 'NO_MATCH')
ORDER BY p.queue_id, p.id
"""

REPROCESS_SUPERSEDE_SQL = """
UPDATE document_routing_proposal
   SET status = 'superseded'
 WHERE id = ANY($1::bigint[])
   AND status = 'review_pending'
"""

# v2 worker reset contract (services/intake/worker.py) + pipeline_version bump.
REPROCESS_RESET_SQL = """
UPDATE intake_queue
   SET status           = 'pending',
       stage            = NULL,
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = now(),
       stage_output     = '{}'::jsonb,
       pipeline_version = $2
 WHERE id = ANY($1::bigint[])
"""

# Historical inbound media with NO intake_queue row (anti-join on source_ref).
BACKFILL_SELECT_SQL = """
SELECT w.id, w.baileys_message_id, w.media_stored_path, w.media_mime,
       w.media_type, w.team_member_email, w.sender_phone, w.chat_type, w.group_jid,
       w.group_subject_snapshot
  FROM whatsapp_message_context w
 WHERE w.direction = 'inbound'
   AND w.media_stored_path IS NOT NULL
   AND w.media_type = ANY($1::text[])
   AND w.id <= $2
   AND w.baileys_message_id IS NOT NULL
   AND NOT EXISTS (
        SELECT 1 FROM intake_queue q
         WHERE q.source_ref = 'wa-mirror:' || w.baileys_message_id
   )
 ORDER BY w.id ASC
"""

SCRUB_GROUP_PHONE_SELECT_SQL = """
SELECT q.id, q.status
  FROM intake_queue q
  JOIN whatsapp_message_context w
    ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
 WHERE q.source = 'whatsapp'
   AND q.source_ref LIKE 'wa-mirror:%'
   AND (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
   AND (q.sender_phone IS NOT NULL OR q.client_id_hint IS NOT NULL)
 ORDER BY q.id
"""

SCRUB_GROUP_PHONE_APPLY_SQL = """
WITH target AS (
    SELECT q.id
      FROM intake_queue q
      JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
       AND q.source_ref LIKE 'wa-mirror:%'
       AND (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
       AND (q.sender_phone IS NOT NULL OR q.client_id_hint IS NOT NULL)
     ORDER BY q.id
)
UPDATE intake_queue q
   SET sender_phone = NULL,
       client_id_hint = NULL,
       updated_at = now()
  FROM target t
 WHERE q.id = t.id
RETURNING q.id
"""

SOURCE_CONTEXT_BACKFILL_SELECT_SQL = """
SELECT q.id AS queue_id, q.status,
       w.chat_type, w.group_jid, w.group_subject_snapshot, w.sender_phone
  FROM intake_queue q
  JOIN whatsapp_message_context w
    ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
 WHERE q.source = 'whatsapp'
   AND q.source_ref LIKE 'wa-mirror:%'
   AND (
        q.source_context = '{}'::jsonb
        OR q.source_context IS NULL
        OR q.source_context->>'transport' IS DISTINCT FROM 'wa-mirror'
       )
 ORDER BY q.id
"""

SOURCE_CONTEXT_BACKFILL_APPLY_SQL = """
UPDATE intake_queue
   SET source_context = $2::jsonb,
       updated_at = now()
 WHERE id = $1
"""


# --- Pure helpers (unit-testable without PG) --------------------------------

def read_watermark(path: Path = WATERMARK_FILE) -> int | None:
    """Read the sweeper watermark file; None when absent/unreadable."""
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip() or "0")
    except (ValueError, OSError) as exc:
        logger.warning("watermark file unreadable: %s", exc)
        return None


def row_to_enqueue_kwargs(row: Any) -> dict[str, Any]:
    """Map a whatsapp_message_context row to enqueue() keyword arguments.

    Mirrors the sweeper's call exactly (source_ref format is the dedup key —
    a drifted format would break the anti-join idempotency). Group rows are
    OCR/review-only here: do not carry participant phone into routing.
    """
    return {
        "source": _SOURCE,
        "source_ref": f"wa-mirror:{row['baileys_message_id']}",
        "blob_path": row["media_stored_path"],
        "mime_type": row["media_mime"],
        "received_by": row["team_member_email"],
        "sender_phone": _queue_sender_phone(row),
        "source_context": _source_context(row),
    }


def _record_get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except KeyError:
        return None


def _is_direct_chat(row: Any) -> bool:
    chat_type = str(_record_get(row, "chat_type") or "").strip().lower()
    group_jid = _record_get(row, "group_jid")
    if chat_type == "group" or group_jid:
        return False
    if chat_type == "direct":
        return True
    return True


def _queue_sender_phone(row: Any) -> str | None:
    if not _is_direct_chat(row):
        return None
    value = _record_get(row, "sender_phone")
    return str(value) if value else None


def _hash_token(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip().lower()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_context(row: Any) -> dict[str, object]:
    """PII-safe WA mirror context matching the live sweeper contract."""
    if _is_direct_chat(row):
        return {
            "transport": "wa-mirror",
            "context_version": "wa-mirror-v1",
            "chat_type": "direct",
            "crm_identity_policy": "phone_keyed_direct_chat",
            "routing_identity_policy": "sender_phone_enabled",
            "sender_phone_forwarded": _queue_sender_phone(row) is not None,
        }

    context: dict[str, object] = {
        "transport": "wa-mirror",
        "context_version": "wa-mirror-v1",
        "chat_type": "group",
        "group_scope": "unclassified",
        "crm_identity_policy": "disabled_for_group",
        "routing_identity_policy": "group_participant_phone_suppressed",
        "sender_phone_forwarded": False,
    }
    group_jid_hash = _hash_token(_record_get(row, "group_jid"))
    if group_jid_hash:
        context["group_jid_hash"] = group_jid_hash
    group_subject_hash = _hash_token(_record_get(row, "group_subject_snapshot"))
    if group_subject_hash:
        context["group_subject_present"] = True
        context["group_subject_hash"] = group_subject_hash
    else:
        context["group_subject_present"] = False
    return context


def _media_types(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_MEDIA_TYPES
    return tuple(t.strip() for t in raw.split(",") if t.strip()) or DEFAULT_MEDIA_TYPES


# --- Modes -------------------------------------------------------------------

async def run_reprocess(
    pool: asyncpg.Pool, pipeline_version: str, apply: bool
) -> dict[str, int]:
    """Supersede unknown/NO_MATCH review_pending proposals + reset their queue rows."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(REPROCESS_SELECT_SQL)
        proposal_ids = [r["proposal_id"] for r in rows]
        queue_ids = sorted({r["queue_id"] for r in rows})

        counts = {"proposals": len(proposal_ids), "queue_rows": len(queue_ids)}
        if not apply:
            logger.info(
                "[reprocess][DRY-RUN] would supersede %d proposals and reset %d "
                "queue rows to pipeline_version=%s (pass --apply to execute)",
                counts["proposals"], counts["queue_rows"], pipeline_version,
            )
            return counts

        async with conn.transaction():
            superseded = await conn.execute(REPROCESS_SUPERSEDE_SQL, proposal_ids)
            reset = await conn.execute(REPROCESS_RESET_SQL, queue_ids, pipeline_version)
        counts["superseded"] = int(superseded.split()[-1]) if superseded else 0
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[reprocess] superseded=%d proposals, reset=%d queue rows "
        "(pipeline_version=%s) — the intake worker will re-run them",
        counts.get("superseded", 0), counts.get("reset", 0), pipeline_version,
    )
    return counts


async def run_backfill(
    pool: asyncpg.Pool,
    watermark: int,
    media_types: tuple[str, ...],
    apply: bool,
) -> dict[str, int]:
    """Enqueue historical inbound media the sweeper's seed watermark skipped."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(BACKFILL_SELECT_SQL, list(media_types), watermark)

    counts = {"candidates": len(rows), "blob_missing": 0,
              "enqueued_new": 0, "already": 0, "errors": 0}

    for r in rows:
        if not os.path.exists(r["media_stored_path"]):
            counts["blob_missing"] += 1
            continue
        if not apply:
            continue
        try:
            result = await enqueue(pool, **row_to_enqueue_kwargs(r))
        except Exception as exc:
            counts["errors"] += 1
            logger.error("[backfill] enqueue failed for wmc row %d: %s", r["id"], exc)
            continue
        if result.was_new:
            counts["enqueued_new"] += 1
        else:
            counts["already"] += 1

    if not apply:
        logger.info(
            "[backfill][DRY-RUN] candidates=%d (id <= %d), blob_missing=%d, "
            "would_enqueue=%d (pass --apply to execute)",
            counts["candidates"], watermark, counts["blob_missing"],
            counts["candidates"] - counts["blob_missing"],
        )
    else:
        logger.info(
            "[backfill] candidates=%d new=%d dup=%d blob_missing=%d errors=%d",
            counts["candidates"], counts["enqueued_new"], counts["already"],
            counts["blob_missing"], counts["errors"],
        )
    return counts


async def run_scrub_group_phone(pool: asyncpg.Pool, apply: bool) -> dict[str, int]:
    """Clear unsafe historical group sender phones from already-enqueued rows."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(SCRUB_GROUP_PHONE_SELECT_SQL)
        counts = {"candidates": len(rows), "updated": 0}
        if not apply:
            by_status: dict[str, int] = {}
            for row in rows:
                status = str(row["status"] or "unknown")
                by_status[status] = by_status.get(status, 0) + 1
            logger.info(
                "[scrub-group-phone][DRY-RUN] candidates=%d by_status=%s "
                "(pass --apply to execute)",
                counts["candidates"],
                by_status,
            )
            return counts

        result = await conn.fetch(SCRUB_GROUP_PHONE_APPLY_SQL)
        counts["updated"] = len(result)

    logger.info("[scrub-group-phone] updated=%d group queue rows", counts["updated"])
    return counts


async def run_backfill_source_context(pool: asyncpg.Pool, apply: bool) -> dict[str, int]:
    """Annotate existing wa-mirror queue rows with direct/group source context."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(SOURCE_CONTEXT_BACKFILL_SELECT_SQL)
        counts = {"candidates": len(rows), "direct": 0, "group": 0, "updated": 0}
        for row in rows:
            if _is_direct_chat(row):
                counts["direct"] += 1
            else:
                counts["group"] += 1
        if not apply:
            logger.info(
                "[backfill-source-context][DRY-RUN] candidates=%d direct=%d group=%d "
                "(pass --apply to execute)",
                counts["candidates"], counts["direct"], counts["group"],
            )
            return counts

        for row in rows:
            await conn.execute(
                SOURCE_CONTEXT_BACKFILL_APPLY_SQL,
                row["queue_id"],
                json.dumps(_source_context(row), sort_keys=True),
            )
            counts["updated"] += 1

    logger.info(
        "[backfill-source-context] updated=%d direct=%d group=%d",
        counts["updated"], counts["direct"], counts["group"],
    )
    return counts


# --- CLI ----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Retroactive intake catalog v2 (dry-run by default; --apply to execute)."
    )
    p.add_argument("--reprocess", action="store_true",
                   help="supersede unknown/NO_MATCH review_pending proposals + reset queue rows")
    p.add_argument("--backfill", action="store_true",
                   help="enqueue historical wa-mirror media skipped by the watermark seed")
    p.add_argument("--scrub-group-phone", action="store_true",
                   help="clear sender_phone/client_id_hint from historical wa-mirror group queue rows")
    p.add_argument("--backfill-source-context", action="store_true",
                   help="populate PII-safe direct/group source_context for wa-mirror queue rows")
    p.add_argument("--apply", action="store_true",
                   help="actually write (default: dry-run, counts only)")
    p.add_argument("--pipeline-version", default=DEFAULT_PIPELINE_VERSION,
                   help=f"bumped pipeline_version for --reprocess (default {DEFAULT_PIPELINE_VERSION})")
    p.add_argument("--watermark", type=int, default=None,
                   help="backfill ceiling id (default: read the sweeper watermark file)")
    p.add_argument("--media-types", default=None,
                   help="comma list for --backfill (default document,image)")
    return p


async def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("INTAKE_RETRO_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    args = build_parser().parse_args(argv)
    if not (
        args.reprocess or args.backfill or args.scrub_group_phone
        or args.backfill_source_context
    ):
        logger.error(
            "nothing to do: pass --backfill, --reprocess, --scrub-group-phone, "
            "and/or --backfill-source-context"
        )
        return 2

    db_url = os.getenv(
        "INTAKE_DATABASE_URL", os.getenv("DATABASE_URL", DEFAULT_DSN)
    )
    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    try:
        # Backfill FIRST (puts historical rows in the queue), then reprocess
        # (resets the weak proposals) — matches the rollout runbook order.
        if args.backfill:
            watermark = args.watermark if args.watermark is not None else read_watermark()
            if watermark is None:
                logger.error(
                    "no watermark: %s missing and --watermark not given", WATERMARK_FILE
                )
                return 2
            await run_backfill(pool, watermark, _media_types(args.media_types), args.apply)
        if args.scrub_group_phone:
            await run_scrub_group_phone(pool, args.apply)
        if args.backfill_source_context:
            await run_backfill_source_context(pool, args.apply)
        if args.reprocess:
            await run_reprocess(pool, args.pipeline_version, args.apply)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
