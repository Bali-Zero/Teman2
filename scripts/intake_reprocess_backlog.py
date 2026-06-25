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
    after re-OCR. The reset preserves FIFO urgency by making the rows visible at
    their original ``created_at`` rather than ``now()``; otherwise this targeted
    recovery sits behind newer pending WhatsApp jobs.

``--retry-unschematised-supported``
    Historical WhatsApp rows whose extract stage skipped
    ``unschematised_doc_type`` even though today's extractor can canonicalize
    the classified type (for example ``itap``/``itk``/``ktp``/``oss``/``itas``)
    are reset to ``pending`` with a bumped pipeline version. Existing
    review/quarantine proposals are superseded so the worker emits a fresh
    extracted/routed proposal after rerun.

Law 2 / UU-PDP: everything local (local DB, local blobs, downstream OCR is
local Ollama). Sender phones are PII — never logged at INFO with the value.

DRY-RUN BY DEFAULT: prints counts only. Pass ``--apply`` to execute.

Environment:
- INTAKE_DATABASE_URL / DATABASE_URL (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
"""
from __future__ import annotations

import argparse
import ast
import asyncio
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

_BACKEND_ROOT = Path(__file__).resolve().parent.parent / "apps" / "backend-rag" / "backend"
_INTAKE_SERVICES_DIR = _BACKEND_ROOT / "services" / "intake"

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_PIPELINE_VERSION = "v2.1-retro"
DEFAULT_STUB_REVIVE_VERSION = "v2.1-stub-revive"
DEFAULT_EMPTY_PDF_OCR_VERSION = "v2.2-empty-pdf-ocr"
DEFAULT_UNSCHEMATISED_RECOVERY_VERSION = "v2.3-unschematised-retry"
DEFAULT_TYPED_MISSING_FIELDS_VERSION = "v2.4-typed-fields-retry"
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
       last_error      = NULL,
       pipeline_version = $2
 WHERE id = ANY($1::bigint[])
"""

# Same v2 reset contract, but for targeted retry lanes that must be observable
# immediately in production tests. The worker orders pending WhatsApp jobs by
# next_visible_at, so resetting historical rows to now() parks them behind newer
# pending backlog. Using created_at preserves their original FIFO position while
# keeping future-dated rows safe.
PRIORITY_RETRY_RESET_SQL = """
UPDATE intake_queue
   SET status           = 'pending',
       stage            = NULL,
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = LEAST(COALESCE(created_at, now()), now()),
       stage_output     = '{}'::jsonb,
       last_error      = NULL,
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

UNSCHEMATISED_SUPPORTED_SELECT_SQL = """
SELECT q.id
FROM intake_queue q
CROSS JOIN LATERAL (
    SELECT COALESCE(q.stage_output->'classify'->>'doc_type', '') AS doc_type
) classified
WHERE q.source = 'whatsapp'
  AND COALESCE(q.stage_output->'extract'->>'skipped', '') = 'unschematised_doc_type'
  AND classified.doc_type = ANY($1::text[])
  AND NOT EXISTS (
      SELECT 1
      FROM document_routing_proposal p
      WHERE p.queue_id = q.id
        AND p.status NOT IN ('review_pending', 'quarantine', 'superseded')
  )
ORDER BY q.id
"""

UNSCHEMATISED_SUPPORTED_SUPERSEDE_SQL = """
UPDATE document_routing_proposal
   SET status = 'superseded'
 WHERE queue_id = ANY($1::bigint[])
   AND status IN ('review_pending', 'quarantine')
"""

TYPED_MISSING_FIELDS_SELECT_SQL = """
SELECT q.id
FROM intake_queue q
CROSS JOIN LATERAL (
    SELECT
        COALESCE(NULLIF(q.stage_output->'classify'->>'doc_type', ''), 'missing') AS doc_type,
        COALESCE((
            SELECT COUNT(*)
            FROM jsonb_each(COALESCE(q.stage_output->'extract'->'fields', '{}'::jsonb)) AS field(key, value)
            WHERE NULLIF(trim(COALESCE(value->>'value', '')), '') IS NOT NULL
        ), 0) AS filled_fields
) extracted
WHERE q.source = 'whatsapp'
  AND q.status IN ('extracted', 'validated', 'done')
  AND extracted.doc_type = ANY($1::text[])
  AND extracted.doc_type NOT IN ('unknown', 'missing')
  AND extracted.filled_fields = 0
  AND NOT EXISTS (
      SELECT 1
      FROM document_routing_proposal p
      WHERE p.queue_id = q.id
        AND p.status NOT IN ('review_pending', 'quarantine', 'superseded')
  )
ORDER BY q.id
"""

TYPED_MISSING_FIELDS_SUPERSEDE_SQL = """
UPDATE document_routing_proposal
   SET status = 'superseded'
 WHERE queue_id = ANY($1::bigint[])
   AND status IN ('review_pending', 'quarantine')
"""

# Read-only q100-style OCR/interpretation quality snapshot. The sample is chosen
# in Postgres and the query returns aggregate counts only: no OCR text, names,
# phone numbers, source refs, or blob paths leave the DB.
QUALITY_SAMPLE_SQL = """
WITH sampled AS (
    SELECT
        q.id,
        q.status,
        COALESCE(q.stage, '') AS stage,
        q.pipeline_version,
        q.stage_output,
        q.last_error
    FROM intake_queue q
    WHERE q.source = $1
      AND ($2::text IS NULL OR q.pipeline_version = $2)
      AND ($4::text[] IS NULL OR q.status = ANY($4::text[]))
      AND (
          $5::bool IS FALSE
          OR NOT (
              COALESCE(q.stage_output->'classify'->>'stub', 'false') = 'true'
              OR COALESCE(q.stage_output->'extract'->>'stub', 'false') = 'true'
              OR COALESCE(q.stage_output->'validate'->>'stub', 'false') = 'true'
              OR COALESCE(q.stage_output->'route'->>'stub', 'false') = 'true'
          )
      )
    ORDER BY q.id DESC
    LIMIT $3
),
latest_proposal AS (
    SELECT DISTINCT ON (p.queue_id)
        p.queue_id,
        p.status AS proposal_status,
        COALESCE(p.entity_resolution->>'decision', '') AS decision
    FROM document_routing_proposal p
    JOIN sampled s ON s.id = p.queue_id
    ORDER BY p.queue_id, p.id DESC
),
derived AS (
    SELECT
        s.status,
        s.stage,
        COALESCE(NULLIF(s.stage_output->'classify'->>'doc_type', ''), 'missing') AS doc_type,
        COALESCE(NULLIF(s.stage_output->'extract'->>'extraction_model', ''), 'missing') AS extraction_model,
        COALESCE(NULLIF(s.stage_output->'extract'->>'skipped', ''), 'none') AS extract_skipped,
        COALESCE(lp.proposal_status, 'missing') AS proposal_status,
        COALESCE(NULLIF(lp.decision, ''), 'missing') AS decision,
        (
            COALESCE(s.stage_output->'classify'->>'stub', 'false') = 'true'
            OR COALESCE(s.stage_output->'extract'->>'stub', 'false') = 'true'
            OR COALESCE(s.stage_output->'validate'->>'stub', 'false') = 'true'
            OR COALESCE(s.stage_output->'route'->>'stub', 'false') = 'true'
        ) AS has_stub_stage,
        COALESCE((
            SELECT SUM(length(trim(COALESCE(page->>'text', ''))))
            FROM jsonb_array_elements(
                COALESCE(s.stage_output->'classify'->'ocr_text_per_page', '[]'::jsonb)
            ) AS page
        ), 0) AS ocr_chars,
        COALESCE((
            SELECT COUNT(*)
            FROM jsonb_each(COALESCE(s.stage_output->'extract'->'fields', '{}'::jsonb)) AS field(key, value)
            WHERE NULLIF(trim(COALESCE(value->>'value', '')), '') IS NOT NULL
        ), 0) AS filled_fields,
        CASE
            WHEN s.last_error IS NULL OR trim(s.last_error) = '' THEN 'none'
            WHEN lower(s.last_error) LIKE '%timeout%' THEN 'timeout'
            WHEN lower(s.last_error) LIKE '%rasterize%' THEN 'rasterize'
            WHEN lower(s.last_error) LIKE '%ollama%' THEN 'ollama'
            WHEN lower(s.last_error) LIKE '%validate%' THEN 'validate'
            ELSE 'other'
        END AS last_error_category
    FROM sampled s
    LEFT JOIN latest_proposal lp ON lp.queue_id = s.id
),
buckets AS (
    SELECT
        *,
        CASE
            WHEN ocr_chars = 0 THEN '0_empty'
            WHEN ocr_chars < 20 THEN '1_noise'
            WHEN ocr_chars < 100 THEN '2_short'
            ELSE '3_legible'
        END AS ocr_bucket,
        CASE
            WHEN has_stub_stage THEN 'stub_stage'
            WHEN doc_type = 'unknown' AND ocr_chars < 20 THEN 'empty_ocr_unknown'
            WHEN doc_type = 'unknown' AND ocr_chars >= 20 THEN 'legible_unknown'
            WHEN extract_skipped = 'unschematised_doc_type' THEN 'unsupported_doc_type'
            WHEN doc_type NOT IN ('unknown', 'missing')
              AND status IN ('extracted', 'validated', 'done')
              AND filled_fields = 0 THEN 'typed_missing_fields'
            WHEN decision = 'NO_MATCH' THEN 'routed_no_match'
            WHEN status = 'dead' THEN 'dead'
            ELSE 'ok_or_pending'
        END AS quality_issue
    FROM derived
)
SELECT jsonb_build_object(
    'sample_rows', (SELECT COUNT(*) FROM buckets),
    'source', $1,
    'pipeline_version_filter', COALESCE($2, 'all'),
    'by_status', COALESCE((
        SELECT jsonb_object_agg(status, n)
        FROM (SELECT status, COUNT(*) AS n FROM buckets GROUP BY status ORDER BY status) x
    ), '{}'::jsonb),
    'by_stage', COALESCE((
        SELECT jsonb_object_agg(stage, n)
        FROM (SELECT stage, COUNT(*) AS n FROM buckets GROUP BY stage ORDER BY stage) x
    ), '{}'::jsonb),
    'by_doc_type', COALESCE((
        SELECT jsonb_object_agg(doc_type, n)
        FROM (SELECT doc_type, COUNT(*) AS n FROM buckets GROUP BY doc_type ORDER BY n DESC, doc_type) x
    ), '{}'::jsonb),
    'by_ocr_bucket', COALESCE((
        SELECT jsonb_object_agg(ocr_bucket, n)
        FROM (SELECT ocr_bucket, COUNT(*) AS n FROM buckets GROUP BY ocr_bucket ORDER BY ocr_bucket) x
    ), '{}'::jsonb),
    'by_extraction_model', COALESCE((
        SELECT jsonb_object_agg(extraction_model, n)
        FROM (
            SELECT extraction_model, COUNT(*) AS n
            FROM buckets
            GROUP BY extraction_model
            ORDER BY n DESC, extraction_model
        ) x
    ), '{}'::jsonb),
    'by_extract_skipped', COALESCE((
        SELECT jsonb_object_agg(extract_skipped, n)
        FROM (
            SELECT extract_skipped, COUNT(*) AS n
            FROM buckets
            GROUP BY extract_skipped
            ORDER BY n DESC, extract_skipped
        ) x
    ), '{}'::jsonb),
    'by_proposal_status', COALESCE((
        SELECT jsonb_object_agg(proposal_status, n)
        FROM (
            SELECT proposal_status, COUNT(*) AS n
            FROM buckets
            GROUP BY proposal_status
            ORDER BY proposal_status
        ) x
    ), '{}'::jsonb),
    'by_decision', COALESCE((
        SELECT jsonb_object_agg(decision, n)
        FROM (SELECT decision, COUNT(*) AS n FROM buckets GROUP BY decision ORDER BY decision) x
    ), '{}'::jsonb),
    'quality_issues', COALESCE((
        SELECT jsonb_object_agg(quality_issue, n)
        FROM (
            SELECT quality_issue, COUNT(*) AS n
            FROM buckets
            GROUP BY quality_issue
            ORDER BY quality_issue
        ) x
    ), '{}'::jsonb),
    'quality_issue_by_doc_type', COALESCE((
        SELECT jsonb_object_agg(quality_issue, doc_counts)
        FROM (
            SELECT quality_issue, jsonb_object_agg(doc_type, n) AS doc_counts
            FROM (
                SELECT quality_issue, doc_type, COUNT(*) AS n
                FROM buckets
                GROUP BY quality_issue, doc_type
                ORDER BY quality_issue, n DESC, doc_type
            ) issue_docs
            GROUP BY quality_issue
        ) x
    ), '{}'::jsonb),
    'extract_skipped_by_doc_type', COALESCE((
        SELECT jsonb_object_agg(extract_skipped, doc_counts)
        FROM (
            SELECT extract_skipped, jsonb_object_agg(doc_type, n) AS doc_counts
            FROM (
                SELECT extract_skipped, doc_type, COUNT(*) AS n
                FROM buckets
                GROUP BY extract_skipped, doc_type
                ORDER BY extract_skipped, n DESC, doc_type
            ) skipped_docs
            GROUP BY extract_skipped
        ) x
    ), '{}'::jsonb),
    'last_error_category', COALESCE((
        SELECT jsonb_object_agg(last_error_category, n)
        FROM (
            SELECT last_error_category, COUNT(*) AS n
            FROM buckets
            GROUP BY last_error_category
            ORDER BY last_error_category
        ) x
    ), '{}'::jsonb)
) AS report
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


def _quality_statuses(raw: str | None) -> tuple[str, ...] | None:
    if not raw:
        return None
    statuses = tuple(t.strip() for t in raw.split(",") if t.strip())
    return statuses or None


def _literal_assigned_value(module_path: Path, name: str) -> Any:
    """Read a literal module constant without importing app settings."""
    tree = ast.parse(module_path.read_text(), filename=str(module_path))
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            value = node.value
        if value is not None:
            return ast.literal_eval(value)
    raise RuntimeError(f"{name} not found in {module_path}")


def _canonical_doc_type(
    doc_type: str | None,
    doc_type_fields: dict[str, Any],
    aliases: dict[str, str],
) -> str | None:
    if not doc_type:
        return None
    key = doc_type.strip().lower()
    key = aliases.get(key, key)
    return key if key in doc_type_fields else None


def _recoverable_unschematised_doc_types() -> tuple[str, ...]:
    """Classify doc_type values that today's extractor can canonicalize."""
    doc_types = _literal_assigned_value(_INTAKE_SERVICES_DIR / "classify.py", "DOC_TYPES")
    doc_type_fields = _literal_assigned_value(
        _INTAKE_SERVICES_DIR / "extract.py", "DOC_TYPE_FIELDS"
    )
    aliases = _literal_assigned_value(_INTAKE_SERVICES_DIR / "extract.py", "_DOC_TYPE_ALIASES")
    candidates = set(doc_types) | set(doc_type_fields) | set(aliases)
    return tuple(
        sorted(
            doc_type
            for doc_type in candidates
            if doc_type != "unknown"
            and _canonical_doc_type(doc_type, doc_type_fields, aliases) is not None
        )
    )


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
            reset = await conn.execute(PRIORITY_RETRY_RESET_SQL, queue_ids, pipeline_version)
        counts["superseded"] = int(superseded.split()[-1]) if superseded else 0
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[retry-empty-pdf-ocr] superseded=%d proposals, reset=%d whatsapp PDF queue "
        "rows (pipeline_version=%s) — the intake worker will re-run classify/OCR",
        counts.get("superseded", 0), counts.get("reset", 0), pipeline_version,
    )
    return counts


async def run_retry_unschematised_supported(
    pool: asyncpg.Pool, pipeline_version: str, apply: bool
) -> dict[str, int]:
    """Reset WhatsApp rows skipped as unschematised but now schema-supported."""
    doc_types = _recoverable_unschematised_doc_types()
    async with pool.acquire() as conn:
        rows = await conn.fetch(UNSCHEMATISED_SUPPORTED_SELECT_SQL, list(doc_types))
        queue_ids = [r["id"] for r in rows]
        counts = {"queue_rows": len(queue_ids), "doc_types": len(doc_types)}
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
                "[retry-unschematised-supported][DRY-RUN] would supersede %d "
                "review/quarantine proposals and reset %d whatsapp queue rows "
                "across %d supported doc_type labels to pipeline_version=%s "
                "(pass --apply)",
                counts["active_proposals"],
                counts["queue_rows"],
                counts["doc_types"],
                pipeline_version,
            )
            return counts

        async with conn.transaction():
            superseded = await conn.execute(
                UNSCHEMATISED_SUPPORTED_SUPERSEDE_SQL, queue_ids
            )
            reset = await conn.execute(PRIORITY_RETRY_RESET_SQL, queue_ids, pipeline_version)
        counts["superseded"] = int(superseded.split()[-1]) if superseded else 0
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[retry-unschematised-supported] superseded=%d proposals, reset=%d "
        "whatsapp queue rows (pipeline_version=%s) — the intake worker will "
        "re-run extract/validate/route",
        counts.get("superseded", 0),
        counts.get("reset", 0),
        pipeline_version,
    )
    return counts


async def run_retry_typed_missing_fields(
    pool: asyncpg.Pool, pipeline_version: str, apply: bool
) -> dict[str, int]:
    """Reset WhatsApp rows with known doc_type but zero extracted fields."""
    doc_types = _recoverable_unschematised_doc_types()
    async with pool.acquire() as conn:
        rows = await conn.fetch(TYPED_MISSING_FIELDS_SELECT_SQL, list(doc_types))
        queue_ids = [r["id"] for r in rows]
        counts = {"queue_rows": len(queue_ids), "doc_types": len(doc_types)}
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
                "[retry-typed-missing-fields][DRY-RUN] would supersede %d "
                "review/quarantine proposals and reset %d typed whatsapp rows "
                "with zero extracted fields across %d supported doc_type labels "
                "to pipeline_version=%s (pass --apply)",
                counts["active_proposals"],
                counts["queue_rows"],
                counts["doc_types"],
                pipeline_version,
            )
            return counts

        async with conn.transaction():
            superseded = await conn.execute(
                TYPED_MISSING_FIELDS_SUPERSEDE_SQL, queue_ids
            )
            reset = await conn.execute(PRIORITY_RETRY_RESET_SQL, queue_ids, pipeline_version)
        counts["superseded"] = int(superseded.split()[-1]) if superseded else 0
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[retry-typed-missing-fields] superseded=%d proposals, reset=%d "
        "typed whatsapp rows with zero extracted fields (pipeline_version=%s) — "
        "the intake worker will re-run extract/validate/route",
        counts.get("superseded", 0),
        counts.get("reset", 0),
        pipeline_version,
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


async def run_quality_sample(
    pool: asyncpg.Pool,
    source: str,
    pipeline_version: str | None,
    sample_size: int,
    statuses: tuple[str, ...] | None = None,
    exclude_stub: bool = False,
) -> dict[str, Any]:
    """Return a redacted OCR/interpretation quality snapshot for recent rows."""
    bounded_sample_size = max(1, min(sample_size, 1000))
    async with pool.acquire() as conn:
        raw = await conn.fetchval(
            QUALITY_SAMPLE_SQL,
            source,
            pipeline_version,
            bounded_sample_size,
            list(statuses) if statuses else None,
            exclude_stub,
        )

    if isinstance(raw, str):
        report: dict[str, Any] = json.loads(raw)
    else:
        report = dict(raw or {})

    logger.info("[quality-sample] %s", json.dumps(report, sort_keys=True))
    return report


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
    p.add_argument("--retry-unschematised-supported", action="store_true",
                   help="reset whatsapp docs skipped as unschematised but now extract-schema supported")
    p.add_argument("--retry-typed-missing-fields", action="store_true",
                   help="reset typed whatsapp docs whose extract stage produced zero fields")
    p.add_argument("--quality-sample", action="store_true",
                   help="read-only redacted OCR/interpretation quality snapshot")
    p.add_argument("--quality-sample-size", type=int, default=100,
                   help="number of recent queue rows to sample for --quality-sample (default 100)")
    p.add_argument("--quality-source", default="whatsapp",
                   help="intake_queue.source filter for --quality-sample (default whatsapp)")
    p.add_argument("--quality-pipeline-version", default=None,
                   help="optional pipeline_version filter for --quality-sample")
    p.add_argument("--quality-statuses", default=None,
                   help="optional comma list of intake_queue statuses for --quality-sample")
    p.add_argument("--quality-exclude-stub", action="store_true",
                   help="for --quality-sample: exclude rows produced by stub handlers")
    p.add_argument("--include-groups", action="store_true",
                   help="for --revive-stub: also revive group-chat docs (default: 1:1 direct chats only)")
    p.add_argument("--stub-pipeline-version", default=DEFAULT_STUB_REVIVE_VERSION,
                   help=f"bumped pipeline_version for --revive-stub (default {DEFAULT_STUB_REVIVE_VERSION})")
    p.add_argument("--empty-pdf-ocr-version", default=DEFAULT_EMPTY_PDF_OCR_VERSION,
                   help=f"bumped pipeline_version for --retry-empty-pdf-ocr (default {DEFAULT_EMPTY_PDF_OCR_VERSION})")
    p.add_argument("--unschematised-pipeline-version", default=DEFAULT_UNSCHEMATISED_RECOVERY_VERSION,
                   help=f"bumped pipeline_version for --retry-unschematised-supported (default {DEFAULT_UNSCHEMATISED_RECOVERY_VERSION})")
    p.add_argument("--typed-missing-fields-version", default=DEFAULT_TYPED_MISSING_FIELDS_VERSION,
                   help=f"bumped pipeline_version for --retry-typed-missing-fields (default {DEFAULT_TYPED_MISSING_FIELDS_VERSION})")
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
        or args.retry_unschematised_supported
        or args.retry_typed_missing_fields
        or args.quality_sample
    ):
        logger.error(
            "nothing to do: pass --backfill and/or --reprocess and/or "
            "--revive-stub and/or --retry-empty-pdf-ocr and/or "
            "--retry-unschematised-supported and/or --retry-typed-missing-fields "
            "and/or --quality-sample"
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
        if args.retry_unschematised_supported:
            await run_retry_unschematised_supported(
                pool, args.unschematised_pipeline_version, args.apply
            )
        if args.retry_typed_missing_fields:
            await run_retry_typed_missing_fields(
                pool, args.typed_missing_fields_version, args.apply
            )
        if args.quality_sample:
            await run_quality_sample(
                pool,
                args.quality_source,
                args.quality_pipeline_version,
                args.quality_sample_size,
                _quality_statuses(args.quality_statuses),
                args.quality_exclude_stub,
            )
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
