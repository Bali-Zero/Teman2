#!/usr/bin/env python3
"""Retroactive intake catalog v2: targeted backlog recovery modes.

One-shot modes (combinable; run on the Pro against LOCAL nuzantara_dev):

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

``--retry-empty-pdf-ocr``
    Historical WhatsApp PDFs whose classify stage recorded
    ``rasterize_failed,raw_pdf_fallback`` and zero OCR text are reset to
    ``pending`` with a bumped pipeline version. Existing review/quarantine
    proposals for those rows are superseded so the worker emits a fresh proposal
    after re-OCR.

Law 2 / UU-PDP: everything local (local DB, local blobs, downstream OCR is
local Ollama). Sender phones are PII — never logged at INFO with the value.

DRY-RUN BY DEFAULT: prints counts only. Pass ``--apply`` to execute.

Environment:
- INTAKE_DATABASE_URL / DATABASE_URL (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
"""
from __future__ import annotations

import argparse
import asyncio
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
DEFAULT_STUB_REVIVE_VERSION = "v2.1-stub-revive"
DEFAULT_EMPTY_PDF_OCR_VERSION = "v2.2-empty-pdf-ocr"
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

# WhatsApp docs the stub passthrough stage (worker._stub_stage) marked 'done'
# with NO real OCR/classify/route — so no proposal was ever created and the doc
# never reached /review (silently lost). Created during the 2026-06 stub-handler
# window. Recover them by applying the SAME v2 reset contract so the live worker
# (real handlers) re-runs them end-to-end and emits a fresh proposal.
#
# Scope guards (each load-bearing, verified live 2026-06-21 against nuzantara_dev):
#   - source='whatsapp'                       → own-channel docs only, never the
#                                               Drive/Dropbox admin dump.
#   - sender_phone present                    → a real sender exists (an owner).
#   - NO proposal at all (NOT EXISTS)         → exclude rows that already carry a
#                                               proposal (399 had a LIVE one, in
#                                               /review); re-enqueuing dups them.
#   - $1 include_groups OR not under /groups/ → 1:1 direct chats by default; group
#                                               docs are mixed-confidence (client
#                                               groups AND team/vendor noise) and
#                                               can flood a reviewer's /review, so
#                                               they are opt-in only.
REVIVE_STUB_SELECT_SQL = """
SELECT iq.id
FROM intake_queue iq
WHERE iq.status = 'done'
  AND iq.stage_output->'route'->>'stub' = 'true'
  AND iq.source = 'whatsapp'
  AND iq.sender_phone IS NOT NULL AND iq.sender_phone <> ''
  AND ($1::bool OR iq.blob_path NOT LIKE '%/groups/%')
  AND NOT EXISTS (
      SELECT 1 FROM document_routing_proposal p WHERE p.queue_id = iq.id
  )
ORDER BY iq.id
"""

# WhatsApp PDFs that produced zero OCR text only because preprocessing fell back
# to the raw PDF bytes (historical pypdfium/rasterize environment failure).
# Current Pro can rasterize the sampled PDFs again, so reset these rows to rerun
# classify/OCR with a fresh pipeline_version. Guards are intentionally narrow:
#   - WhatsApp only (client-facing lane).
#   - doc_type is the anti-hallucination floor "unknown".
#   - both rasterize_failed + raw_pdf_fallback notes present.
#   - OCR char count is exactly zero.
#   - no human-terminal / actively claimed proposal exists for the queue row.
EMPTY_PDF_OCR_SELECT_SQL = """
SELECT q.id
FROM intake_queue q
WHERE q.source = 'whatsapp'
  AND COALESCE(q.stage_output->'classify'->>'doc_type', '') = 'unknown'
  AND COALESCE(q.stage_output->'classify'->>'preprocess_notes', '') LIKE '%rasterize_failed%'
  AND COALESCE(q.stage_output->'classify'->>'preprocess_notes', '') LIKE '%raw_pdf_fallback%'
  AND COALESCE((
        SELECT SUM(length(COALESCE(page->>'text', '')))
        FROM jsonb_array_elements(
            COALESCE(q.stage_output->'classify'->'ocr_text_per_page', '[]'::jsonb)
        ) AS page
      ), 0) = 0
  AND NOT EXISTS (
      SELECT 1
      FROM document_routing_proposal p
      WHERE p.queue_id = q.id
        AND p.status NOT IN ('review_pending', 'quarantine', 'superseded')
  )
ORDER BY q.id
"""

EMPTY_PDF_OCR_SUPERSEDE_SQL = """
UPDATE document_routing_proposal
   SET status = 'superseded'
 WHERE queue_id = ANY($1::bigint[])
   AND status IN ('review_pending', 'quarantine')
"""

# Historical inbound media with NO intake_queue row (anti-join on source_ref).
BACKFILL_SELECT_SQL = """
SELECT w.id, w.baileys_message_id, w.media_stored_path, w.media_mime,
       w.media_type, w.team_member_email, w.sender_phone
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
    a drifted format would break the anti-join idempotency).
    """
    return {
        "source": _SOURCE,
        "source_ref": f"wa-mirror:{row['baileys_message_id']}",
        "blob_path": row["media_stored_path"],
        "mime_type": row["media_mime"],
        "received_by": row["team_member_email"],
        "sender_phone": row["sender_phone"],
    }


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


async def run_revive_stub(
    pool: asyncpg.Pool, pipeline_version: str, include_groups: bool, apply: bool
) -> dict[str, int]:
    """Re-enqueue whatsapp docs the stub passthrough marked done with no proposal.

    Applies the v2 worker reset contract (same as --reprocess) so the live worker
    re-runs OCR/classify/route end-to-end and emits a fresh proposal into /review.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(REVIVE_STUB_SELECT_SQL, include_groups)
        queue_ids = [r["id"] for r in rows]
        counts = {"queue_rows": len(queue_ids)}
        if not apply:
            logger.info(
                "[revive-stub][DRY-RUN] would reset %d stub-skipped whatsapp queue "
                "rows (include_groups=%s) to pipeline_version=%s (pass --apply)",
                counts["queue_rows"], include_groups, pipeline_version,
            )
            return counts

        async with conn.transaction():
            reset = await conn.execute(REPROCESS_RESET_SQL, queue_ids, pipeline_version)
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[revive-stub] reset=%d stub-skipped whatsapp queue rows (include_groups=%s, "
        "pipeline_version=%s) — the intake worker will re-OCR + re-route them",
        counts.get("reset", 0), include_groups, pipeline_version,
    )
    return counts


async def run_retry_empty_pdf_ocr(
    pool: asyncpg.Pool, pipeline_version: str, apply: bool
) -> dict[str, int]:
    """Reset WhatsApp PDFs whose historical classify pass had zero OCR text.

    This is intentionally narrower than --reprocess: it only targets rows where
    preprocess recorded rasterize_failed/raw_pdf_fallback, OCR text is empty,
    and no terminal/claimed human proposal exists. Existing review_pending or
    quarantine proposals are superseded so the rerun leaves one fresh proposal.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(EMPTY_PDF_OCR_SELECT_SQL)
        queue_ids = [r["id"] for r in rows]
        counts = {"queue_rows": len(queue_ids)}
        if not apply:
            if queue_ids:
                proposal_count = await conn.fetchval(
                    """
                    SELECT count(*)
                    FROM document_routing_proposal
                    WHERE queue_id = ANY($1::bigint[])
                      AND status IN ('review_pending', 'quarantine')
                    """,
                    queue_ids,
                )
            else:
                proposal_count = 0
            counts["active_proposals"] = int(proposal_count or 0)
            logger.info(
                "[retry-empty-pdf-ocr][DRY-RUN] would supersede %d review/quarantine "
                "proposals and reset %d whatsapp PDF queue rows to pipeline_version=%s "
                "(pass --apply)",
                counts["active_proposals"], counts["queue_rows"], pipeline_version,
            )
            return counts

        async with conn.transaction():
            superseded = await conn.execute(EMPTY_PDF_OCR_SUPERSEDE_SQL, queue_ids)
            reset = await conn.execute(REPROCESS_RESET_SQL, queue_ids, pipeline_version)
        counts["superseded"] = int(superseded.split()[-1]) if superseded else 0
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[retry-empty-pdf-ocr] superseded=%d proposals, reset=%d whatsapp PDF queue "
        "rows (pipeline_version=%s) — the intake worker will re-run classify/OCR",
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
        except Exception as exc:  # isolate per-row failure
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


# --- CLI ----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Retroactive intake catalog v2 (dry-run by default; --apply to execute)."
    )
    p.add_argument("--reprocess", action="store_true",
                   help="supersede unknown/NO_MATCH review_pending proposals + reset queue rows")
    p.add_argument("--backfill", action="store_true",
                   help="enqueue historical wa-mirror media skipped by the watermark seed")
    p.add_argument("--revive-stub", action="store_true",
                   help="re-enqueue whatsapp docs the stub passthrough marked done with no proposal")
    p.add_argument("--retry-empty-pdf-ocr", action="store_true",
                   help="reset whatsapp PDFs with rasterize_failed/raw_pdf_fallback and zero OCR text")
    p.add_argument("--include-groups", action="store_true",
                   help="for --revive-stub: also revive group-chat docs (default: 1:1 direct chats only)")
    p.add_argument("--stub-pipeline-version", default=DEFAULT_STUB_REVIVE_VERSION,
                   help=f"bumped pipeline_version for --revive-stub (default {DEFAULT_STUB_REVIVE_VERSION})")
    p.add_argument("--empty-pdf-ocr-version", default=DEFAULT_EMPTY_PDF_OCR_VERSION,
                   help=f"bumped pipeline_version for --retry-empty-pdf-ocr (default {DEFAULT_EMPTY_PDF_OCR_VERSION})")
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
        args.reprocess
        or args.backfill
        or args.revive_stub
        or args.retry_empty_pdf_ocr
    ):
        logger.error(
            "nothing to do: pass --backfill and/or --reprocess and/or "
            "--revive-stub and/or --retry-empty-pdf-ocr"
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
        if args.reprocess:
            await run_reprocess(pool, args.pipeline_version, args.apply)
        if args.revive_stub:
            await run_revive_stub(
                pool, args.stub_pipeline_version, args.include_groups, args.apply
            )
        if args.retry_empty_pdf_ocr:
            await run_retry_empty_pdf_ocr(
                pool, args.empty_pdf_ocr_version, args.apply
            )
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
