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

``--autocatalog-direct-unknown-text``
    Selects wa-mirror DIRECT-chat queue rows whose saved classify payload is still
    ``doc_type=unknown`` but whose saved OCR has enough text for the local Qwen
    text classifier. It supersedes any existing ``review_pending`` proposal for
    those rows and applies the same v2 reset contract with a bumped pipeline
    version. The worker must run with ``INTAKE_TEXT_LLM_CLASSIFY_ENABLED=1`` so
    the rerun can promote doc_type into a normal Kita routing proposal.

``--autocatalog-preclassify-saved-ocr``
    Safer/faster variant for the same review bucket: it keeps the saved OCR,
    calls local Qwen text classification immediately, writes a fresh
    ``stage_output.classify`` payload only for known answers, sets the queue row
    to ``ocr_done``, and lets the normal worker continue extract/validate/route.
    This avoids re-running vision OCR and avoids churn for still-unknown docs.

``--autocatalog-preclassify-vision``
    Local vision variant for the direct unknown review bucket. It reads the
    original blob from local disk, rasterizes through the normal preprocessing
    path, downsizes pages for type classification (not OCR), asks local
    Qwen2.5VL for exactly one doc_type, and only resumes rows whose answer is a
    Kita-supported type. Unknown/errors are marked with PII-free attempt
    metadata so batches do not loop.

``--auto-attach-eligible``
    Selects existing wa-mirror ``review_pending`` proposals whose commit gate
    already says ``auto_attach_eligible=true`` and feeds them through the SAME
    double-concordance auto-attach module used by route_stage. Dry-run counts
    candidates only; ``--apply`` still honors ``INTAKE_AUTO_ATTACH_ENABLED`` and
    ``INTAKE_WRITER_ENABLED`` kill-switches before any CRM write can happen.

``--auto-attach-direct-phone``
    Selects existing wa-mirror direct-chat ``LINK_CANDIDATE`` proposals whose
    routing target came from the sender-phone policy and whose doc_type already
    maps to a known Kita category. Dry-run counts candidates only; ``--apply``
    still honors ``INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED`` and
    ``INTAKE_WRITER_ENABLED`` before any CRM write can happen.

``--promote-direct-new-prospects``
    Selects wa-mirror direct-chat ``NO_MATCH`` proposals with a sender phone and
    a Kita-supported doc_type. It reuses the live sweeper's phone-keyed CRM lead
    upsert, supersedes the stale NO_MATCH proposal, and resumes the queue row at
    ``validated`` with a bumped pipeline version so the normal worker re-routes
    it as a direct-phone candidate. Dry-run counts only; document writes still
    require the separate direct-phone auto-attach gates after re-route.

``--review-backlog-report``
    Read-only triage of the current wa-mirror review queue. It collapses to the
    latest proposal per queue row and reports aggregate automation buckets:
    already eligible auto-attach, direct-phone auto-catalog, direct new-prospect
    candidates, direct unknowns ready for local Qwen reclassification, group
    review, missing context, and remaining human review. It never logs client
    names, phones, blob paths, OCR text, or proposal payloads.

``--delivery-readiness-report``
    Read-only Pro→Fly/Kita readiness check for auto-attach delivery. It imports
    only the scoped WA Mirror delivery allowlist from ``~/.wa-mirror.env``, never
    logs secret values, reports writer/gate state, and sends the same empty-body
    service-write preflight used before bulk ``--apply``. It does not need DB.

``--scrub-group-phone``
    Historical wa-mirror group documents may still carry ``intake_queue.sender_phone``
    from before the group/direct split. Group sender numbers are participant
    phones, often Bali Zero teammates forwarding documents, so they must not be
    reused as client identity hints on reruns. This mode clears
    ``sender_phone`` and ``client_id_hint`` only for queue rows joined to
    ``whatsapp_message_context`` group chats.

``--backfill-source-context``
    Existing wa-mirror queue rows may predate migration 240. This mode annotates
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
import ast
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import asyncpg
import httpx

# Reuse the shipped, tested enqueue core (same import shim as the sweeper).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend.services.intake.classify import (
    VISION_CLASSIFY_CONF,
    TEXT_LLM_CLASSIFY_CONF,
    _VISION_CLASSIFY_NUM_PREDICT,
    _VISION_CLASSIFY_PROMPT,
    _parse_doc_type_answer,
    _parse_vision_answer,
    _score_types,
    _stay_permit_subtype,
    _text_llm_classify_prompt,
)
from backend.services.intake.preprocess import preprocess_blob
from backend.services.intake.auto_attach import try_auto_attach, try_direct_phone_auto_attach
from backend.services.intake.enqueue import enqueue
from backend.services.intake.writer import DOCUMENT_CATEGORY_MAP
from wa_mirror_intake_sweeper import _source_context as _wa_mirror_source_context
from wa_mirror_intake_sweeper import _upsert_client_by_phone as _upsert_wa_client_by_phone

logger = logging.getLogger("intake_reprocess_backlog")

_BACKEND_ROOT = Path(__file__).resolve().parent.parent / "apps" / "backend-rag" / "backend"
_INTAKE_SERVICES_DIR = _BACKEND_ROOT / "services" / "intake"

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_PIPELINE_VERSION = "v2.1-retro"
DEFAULT_AUTOCATALOG_PIPELINE_VERSION = "v2.2-qwen-text-autocatalog"
DEFAULT_STUB_REVIVE_VERSION = "v2.1-stub-revive"
DEFAULT_EMPTY_PDF_OCR_VERSION = "v2.2-empty-pdf-ocr"
DEFAULT_UNSCHEMATISED_RECOVERY_VERSION = "v2.3-unschematised-retry"
DEFAULT_TYPED_MISSING_FIELDS_VERSION = "v2.4-typed-fields-retry"
DEFAULT_MEDIA_TYPES = ("document", "image")
DEFAULT_AUTOCATALOG_TEXT_MIN_CHARS = 100
DEFAULT_AUTOCATALOG_LIMIT = 500
DEFAULT_AUTOCATALOG_PROVIDER = "ollama"
DEFAULT_AUTOCATALOG_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_AUTOCATALOG_TEXT_MODEL = "qwen3.5:9b"
DEFAULT_AUTOCATALOG_MLX_BASE_URL = "http://127.0.0.1:8080/v1"
DEFAULT_AUTOCATALOG_MLX_MODEL = "mlx-community/Qwen3-8B-4bit"
DEFAULT_AUTOCATALOG_VISION_MODEL = "qwen2.5vl:7b"
DEFAULT_AUTOCATALOG_VISION_MAX_PAGES = 2
DEFAULT_AUTOCATALOG_VISION_IMAGE_MAX_SIDE = 960
DEFAULT_AUTOCATALOG_VISION_OCR_MAX_CHARS = 1500
DEFAULT_AUTOCATALOG_TIMEOUT_SECONDS = 45.0
DEFAULT_AUTOCATALOG_OCR_MAX_CHARS = 6000
KEYWORD_CLASSIFY_MIN_CONFIDENCE = 0.30
KEYWORD_CLASSIFY_MODEL = "deterministic-keyword-v1"
KEYWORD_CLASSIFY_PROVIDER = "keyword"
DEFAULT_AUTO_ATTACH_LIMIT = 500
DEFAULT_NEW_PROSPECT_PIPELINE_VERSION = "v2.3-direct-prospect-promote"
DEFAULT_CRM_PUSH_BASE_URL = "https://nuzantara-rag.fly.dev"
DEFAULT_CRM_PUSH_PREFLIGHT_TIMEOUT_SECONDS = 12.0
WA_MIRROR_ENV_FILE = Path.home() / ".wa-mirror.env"
SCOPED_WA_MIRROR_DELIVERY_ENV_NAMES = (
    "WA_MIRROR_CRM_WRITE_KEY",
    "INTAKE_CRM_PUSH_WRITE_KEY",
    "INTAKE_CRM_PUSH_BASE_URL",
    "INTAKE_CRM_PUSH_ENABLED",
    "INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED",
)

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

# --reroute-drive-folder: Drive 0-candidate rows re-routed through the fixed
# m227 multi-segment folder matcher (PR #2664). ROUTE-ONLY resume: unlike
# REPROCESS_RESET_SQL this MUST NOT wipe stage_output — 97.7% of these rows'
# blobs are retention-evicted, so the saved OCR/extract fields are the ONLY
# copy; a full re-run would fail at preprocess AND destroy them. Resuming at
# status='validated' makes the worker run exactly one stage (route → fase4
# resolve_entity with source_path) against the preserved fields.
REROUTE_DRIVE_FOLDER_SELECT_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (q.id)
           p.id AS proposal_id, q.id AS queue_id, p.status AS proposal_status,
           p.entity_resolution AS entity_resolution
      FROM intake_queue q
      JOIN document_routing_proposal p ON p.queue_id = q.id
     WHERE q.source = 'drive'
       AND q.source_path IS NOT NULL
     ORDER BY q.id, p.id DESC
)
SELECT proposal_id, queue_id
  FROM latest
 WHERE proposal_status = 'review_pending'
   AND (entity_resolution->>'decision') = 'NO_MATCH'
   AND jsonb_array_length(
         COALESCE(entity_resolution->'candidates', '[]'::jsonb)) = 0
 ORDER BY queue_id
 LIMIT $1
"""

# Reset-eligibility lock (Codex round-2, m248): a queue row actively LEASED by
# the worker must never be yanked mid-flight, and the whole
# select→supersede→reset must be one transaction. FOR UPDATE SKIP LOCKED makes
# concurrent reroute invocations safe too.
REROUTE_ELIGIBLE_LOCK_SQL = """
SELECT id
  FROM intake_queue
 WHERE id = ANY($1::bigint[])
   AND (lease_owner IS NULL OR lease_expires_at <= now())
 FOR UPDATE SKIP LOCKED
"""

REROUTE_DRIVE_FOLDER_SUPERSEDE_SQL = """
UPDATE document_routing_proposal
   SET status = 'superseded'
 WHERE queue_id = ANY($1::bigint[])
   AND status = 'review_pending'
RETURNING queue_id
"""

REROUTE_DRIVE_FOLDER_RESET_SQL = """
UPDATE intake_queue
   SET status           = 'validated',
       stage            = 'validate',
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = now(),
       last_error       = NULL,
       pipeline_version = $2,
       updated_at       = now()
 WHERE id = ANY($1::bigint[])
"""

# m248: route-only resume of review_pending rows whose extracted npwp is a
# full 15/16-digit value — the person matcher now consults clients.npwp
# (previously invisible locally; 291 alive clients carry one after the
# 2026-07-18 snapshot refresh). No source / candidate-count filter: the docs
# that can gain the npwp strong-id signal already HAVE folder/fuzzy candidates
# (measured: 3/131 match a client; 0 in the 0-candidate pool). Reuses the
# folder-mode supersede+reset SQL (both are generic by queue_id; the reset
# NEVER touches stage_output).
REROUTE_NPWP_SELECT_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (q.id)
           p.id AS proposal_id, q.id AS queue_id, p.status AS proposal_status,
           COALESCE(
             p.routing->'fields'->'npwp_number'->>'value',
             p.routing->'fields'->>'npwp_number',
             q.stage_output->'extract'->'fields'->'npwp_number'->>'value',
             q.stage_output->'extract'->'fields'->>'npwp_number'
           ) AS npwp_raw
      FROM intake_queue q
      JOIN document_routing_proposal p ON p.queue_id = q.id
     ORDER BY q.id, p.id DESC
)
SELECT proposal_id, queue_id
  FROM latest
 WHERE proposal_status = 'review_pending'
   AND npwp_raw IS NOT NULL
   AND length(regexp_replace(npwp_raw, '[^0-9]', '', 'g')) IN (15, 16)
 ORDER BY queue_id
 LIMIT $1
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

DIRECT_UNKNOWN_TEXT_AUTOCATALOG_SELECT_SQL = """
WITH candidate_rows AS (
    SELECT q.id AS queue_id,
           (
             SELECT ARRAY_REMOVE(ARRAY_AGG(p.id), NULL)
               FROM document_routing_proposal p
              WHERE p.queue_id = q.id
                AND p.status = 'review_pending'
           ) AS proposal_ids,
           (
             SELECT COALESCE(SUM(LENGTH(
               CASE
                 WHEN jsonb_typeof(page.value) = 'object'
                 THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
                 WHEN jsonb_typeof(page.value) = 'string'
                 THEN trim(both '"' from page.value::text)
                 ELSE ''
               END
             )), 0)
               FROM jsonb_array_elements(
                 CASE
                   WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
                   THEN q.stage_output->'classify'->'ocr_text_per_page'
                   ELSE '[]'::jsonb
                 END
               ) AS page(value)
           ) AS ocr_chars
      FROM intake_queue q
      JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
       AND q.source_ref LIKE 'wa-mirror:%'
       AND q.status <> 'dead'
       AND COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') = 'unknown'
       AND (w.chat_type IS DISTINCT FROM 'group' AND w.group_jid IS NULL)
       AND EXISTS (
           SELECT 1
             FROM document_routing_proposal p
            WHERE p.queue_id = q.id
              AND p.status = 'review_pending'
       )
)
SELECT queue_id, proposal_ids, ocr_chars
  FROM candidate_rows
 WHERE ocr_chars >= $1
 ORDER BY queue_id
 LIMIT $2
"""

SAVED_OCR_PRECLASSIFY_SELECT_SQL = """
WITH candidate_rows AS (
    SELECT q.id AS queue_id,
           (
             SELECT ARRAY_REMOVE(ARRAY_AGG(p.id), NULL)
               FROM document_routing_proposal p
              WHERE p.queue_id = q.id
                AND p.status = 'review_pending'
           ) AS proposal_ids,
           q.stage_output,
           (
             SELECT COALESCE(SUM(LENGTH(
               CASE
                 WHEN jsonb_typeof(page.value) = 'object'
                 THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
                 WHEN jsonb_typeof(page.value) = 'string'
                 THEN trim(both '"' from page.value::text)
                 ELSE ''
               END
             )), 0)
               FROM jsonb_array_elements(
                 CASE
                   WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
                   THEN q.stage_output->'classify'->'ocr_text_per_page'
                   ELSE '[]'::jsonb
                 END
               ) AS page(value)
           ) AS ocr_chars
      FROM intake_queue q
      JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
       AND q.source_ref LIKE 'wa-mirror:%'
       AND q.status <> 'dead'
       AND COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') = 'unknown'
       AND (w.chat_type IS DISTINCT FROM 'group' AND w.group_jid IS NULL)
       AND EXISTS (
           SELECT 1
             FROM document_routing_proposal p
            WHERE p.queue_id = q.id
              AND p.status = 'review_pending'
       )
       AND NOT COALESCE(
           q.stage_output->'classify'->'local_text_llm_preclassify_attempts',
           '[]'::jsonb
       ) @> jsonb_build_array(
           jsonb_build_object('model', $2::text, 'pipeline_version', $3::text)
       )
)
SELECT queue_id, proposal_ids, stage_output, ocr_chars
  FROM candidate_rows
 WHERE ocr_chars >= $1
 ORDER BY queue_id
 LIMIT $4
"""

SAVED_OCR_PRECLASSIFY_UPDATE_SQL = """
UPDATE intake_queue
   SET status           = 'ocr_done',
       stage            = 'classify',
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = now(),
       stage_output     = jsonb_build_object('classify', $2::jsonb),
       pipeline_version = $3
 WHERE id = $1
"""

SAVED_OCR_PRECLASSIFY_ATTEMPT_SQL = """
UPDATE intake_queue
   SET stage_output = jsonb_set(
       COALESCE(stage_output, '{}'::jsonb),
       '{classify,local_text_llm_preclassify_attempts}',
       COALESCE(
           stage_output->'classify'->'local_text_llm_preclassify_attempts',
           '[]'::jsonb
       ) || jsonb_build_array($2::jsonb),
       true
   )
 WHERE id = $1
"""

SAVED_VISION_PRECLASSIFY_SELECT_SQL = """
WITH candidate_rows AS (
    SELECT q.id AS queue_id,
           (
             SELECT ARRAY_REMOVE(ARRAY_AGG(p.id), NULL)
               FROM document_routing_proposal p
              WHERE p.queue_id = q.id
                AND p.status = 'review_pending'
           ) AS proposal_ids,
           q.stage_output,
           q.blob_path,
           w.media_mime,
           (
             SELECT COALESCE(SUM(LENGTH(
               CASE
                 WHEN jsonb_typeof(page.value) = 'object'
                 THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
                 WHEN jsonb_typeof(page.value) = 'string'
                 THEN trim(both '"' from page.value::text)
                 ELSE ''
               END
             )), 0)
               FROM jsonb_array_elements(
                 CASE
                   WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
                   THEN q.stage_output->'classify'->'ocr_text_per_page'
                   ELSE '[]'::jsonb
                 END
               ) AS page(value)
           ) AS ocr_chars
      FROM intake_queue q
      JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
       AND q.source_ref LIKE 'wa-mirror:%'
       AND q.status <> 'dead'
       AND q.blob_path IS NOT NULL
       AND COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') = 'unknown'
       AND (w.chat_type IS DISTINCT FROM 'group' AND w.group_jid IS NULL)
       AND EXISTS (
           SELECT 1
             FROM document_routing_proposal p
            WHERE p.queue_id = q.id
              AND p.status = 'review_pending'
       )
       AND NOT COALESCE(
           q.stage_output->'classify'->'local_vision_preclassify_attempts',
           '[]'::jsonb
       ) @> jsonb_build_array(
           jsonb_build_object('model', $2::text, 'pipeline_version', $3::text)
       )
)
SELECT queue_id, proposal_ids, stage_output, blob_path, media_mime, ocr_chars
  FROM candidate_rows
 WHERE ocr_chars >= $1
 ORDER BY CASE
              WHEN media_mime LIKE 'image/%' THEN 0
              WHEN media_mime = 'application/pdf' THEN 1
              ELSE 2
          END,
          ocr_chars,
          queue_id
 LIMIT $4
"""

SAVED_VISION_PRECLASSIFY_ATTEMPT_SQL = """
UPDATE intake_queue
   SET stage_output = jsonb_set(
       COALESCE(stage_output, '{}'::jsonb),
       '{classify,local_vision_preclassify_attempts}',
       COALESCE(
           stage_output->'classify'->'local_vision_preclassify_attempts',
           '[]'::jsonb
       ) || jsonb_build_array($2::jsonb),
       true
   )
 WHERE id = $1
"""

AUTO_ATTACH_ELIGIBLE_SELECT_SQL = """
SELECT p.id, p.queue_id, p.doc_index, p.pipeline_version, p.status,
       p.entity_resolution, p.routing, p.commit_gate,
       q.sender_phone
  FROM document_routing_proposal p
  JOIN intake_queue q ON q.id = p.queue_id
 WHERE q.source = 'whatsapp'
   AND p.status = 'review_pending'
   AND COALESCE((p.commit_gate->>'auto_attach_eligible')::boolean, false) = true
 ORDER BY p.id
 LIMIT $1
"""

DIRECT_PHONE_AUTO_ATTACH_SELECT_SQL = """
SELECT p.id, p.queue_id, p.doc_index, p.pipeline_version, p.status,
       p.entity_resolution, p.routing, p.commit_gate,
       q.sender_phone, q.source_context
  FROM document_routing_proposal p
  JOIN intake_queue q ON q.id = p.queue_id
 WHERE q.source = 'whatsapp'
   AND p.status = 'review_pending'
   AND p.entity_resolution->>'decision' = 'LINK_CANDIDATE'
   AND q.source_context->>'chat_type' = 'direct'
   AND q.source_context->>'routing_identity_policy' = 'sender_phone_enabled'
   AND p.routing->>'client_id' IS NOT NULL
   AND p.routing->>'doc_type' = ANY($2::text[])
   AND COALESCE(
        p.entity_resolution->'reason'->>'reason',
        p.commit_gate->>'reason',
        p.routing->>'reason',
        ''
       ) LIKE 'sender phone%'
 ORDER BY p.id
 LIMIT $1
"""

DIRECT_NEW_PROSPECT_SELECT_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (q.id)
           p.id AS proposal_id,
           p.queue_id,
           p.status,
           p.entity_resolution,
           p.routing,
           p.commit_gate,
           p.created_at,
           q.sender_phone,
           q.source_context,
           q.source_ref,
           w.team_member_email,
           w.sender_push_name_snapshot,
           w.chat_type AS mirror_chat_type,
           w.group_jid AS mirror_group_jid,
           w.group_subject_snapshot
      FROM intake_queue q
      JOIN document_routing_proposal p ON p.queue_id = q.id
      LEFT JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
     ORDER BY q.id, p.created_at DESC, p.id DESC
),
review AS (
    SELECT latest.*,
           COALESCE(latest.entity_resolution->>'decision', latest.commit_gate->>'decision', 'proposal_only') AS decision,
           COALESCE(latest.routing->>'doc_type', '<missing>') AS doc_type,
           COALESCE(
               NULLIF(latest.source_context->>'chat_type', ''),
               CASE
                   WHEN latest.mirror_chat_type = 'group' OR latest.mirror_group_jid IS NOT NULL
                   THEN 'group'
                   WHEN latest.source_ref LIKE 'wa-mirror:%' AND latest.mirror_chat_type IS NOT NULL
                   THEN 'direct'
                   ELSE '<missing>'
               END
           ) AS chat_type
      FROM latest
     WHERE latest.status = 'review_pending'
)
SELECT proposal_id, queue_id, sender_phone, source_context, team_member_email,
       sender_push_name_snapshot, chat_type, mirror_group_jid,
       group_subject_snapshot, doc_type
  FROM review
 WHERE decision = 'NO_MATCH'
   AND chat_type = 'direct'
   AND sender_phone IS NOT NULL
   AND sender_phone <> ''
   AND doc_type = ANY($2::text[])
 ORDER BY proposal_id
 LIMIT $1
"""

DIRECT_NEW_PROSPECT_RESET_SQL = """
UPDATE intake_queue
   SET status           = 'validated',
       stage            = 'validate',
       lease_owner      = NULL,
       lease_expires_at = NULL,
       attempts         = 0,
       next_visible_at  = now(),
       client_id_hint   = $2,
       source_context   = CASE
                            WHEN source_context IS NULL OR source_context = '{}'::jsonb
                            THEN $3::jsonb
                            ELSE source_context
                          END,
       pipeline_version = $4,
       updated_at       = now()
 WHERE id = $1
"""

REVIEW_BACKLOG_REPORT_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (q.id)
           p.id AS proposal_id,
           p.queue_id,
           p.status,
           p.entity_resolution,
           p.routing,
           p.commit_gate,
           p.created_at,
           q.source_context,
           q.source_ref,
           q.sender_phone,
           q.stage_output,
           w.chat_type AS mirror_chat_type,
           w.group_jid AS mirror_group_jid
      FROM intake_queue q
      JOIN document_routing_proposal p ON p.queue_id = q.id
      LEFT JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
     WHERE q.source = 'whatsapp'
     ORDER BY q.id, p.created_at DESC, p.id DESC
),
review AS (
    SELECT latest.*,
           COALESCE(latest.entity_resolution->>'decision', latest.commit_gate->>'decision', 'proposal_only') AS decision,
           COALESCE(latest.routing->>'doc_type', '<missing>') AS doc_type,
           COALESCE(
               NULLIF(latest.source_context->>'chat_type', ''),
               CASE
                   WHEN latest.mirror_chat_type = 'group' OR latest.mirror_group_jid IS NOT NULL
                   THEN 'group'
                   WHEN latest.source_ref LIKE 'wa-mirror:%' AND latest.mirror_chat_type IS NOT NULL
                   THEN 'direct'
                   ELSE '<missing>'
               END
           ) AS chat_type,
           COALESCE(ocr.ocr_chars, 0) AS ocr_chars,
           COALESCE(
               latest.entity_resolution->'reason'->>'reason',
               latest.commit_gate->>'reason',
               latest.routing->>'reason',
               ''
           ) AS reason_text
      FROM latest
      LEFT JOIN LATERAL (
          SELECT COALESCE(SUM(LENGTH(
              CASE
                  WHEN jsonb_typeof(page.value) = 'object'
                  THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
                  WHEN jsonb_typeof(page.value) = 'string'
                  THEN trim(both '"' from page.value::text)
                  ELSE ''
              END
          )), 0)::integer AS ocr_chars
            FROM jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(latest.stage_output->'classify'->'ocr_text_per_page') = 'array'
                    THEN latest.stage_output->'classify'->'ocr_text_per_page'
                    ELSE '[]'::jsonb
                END
            ) AS page(value)
      ) AS ocr ON TRUE
     WHERE latest.status = 'review_pending'
),
bucketed AS (
    SELECT *,
           CASE
               WHEN COALESCE((commit_gate->>'auto_attach_eligible')::boolean, false) = true
               THEN 'auto_attach_eligible'
               WHEN chat_type = 'direct'
                    AND decision = 'LINK_CANDIDATE'
                    AND routing->>'client_id' IS NOT NULL
                    AND doc_type = ANY($2::text[])
                    AND source_context->>'routing_identity_policy' = 'sender_phone_enabled'
                    AND reason_text LIKE 'sender phone%'
               THEN 'direct_phone_auto_catalog'
               WHEN chat_type = 'direct'
                    AND decision = 'NO_MATCH'
                    AND sender_phone IS NOT NULL
                    AND doc_type = ANY($2::text[])
               THEN 'direct_new_prospect_candidate'
               WHEN chat_type = 'direct'
                    AND doc_type = 'unknown'
                    AND ocr_chars >= $1
               THEN 'direct_unknown_reclassify'
               WHEN chat_type = 'group'
               THEN 'group_human_review'
               WHEN chat_type = '<missing>'
               THEN 'missing_context_review'
               ELSE 'remaining_human_review'
           END AS automation_bucket
      FROM review
)
SELECT 'total' AS section, 'latest_review' AS key, COUNT(*)::integer AS count
  FROM bucketed
UNION ALL
SELECT 'decision' AS section, decision AS key, COUNT(*)::integer AS count
  FROM bucketed
 GROUP BY decision
UNION ALL
SELECT 'chat_decision' AS section, chat_type || ':' || decision AS key, COUNT(*)::integer AS count
  FROM bucketed
 GROUP BY chat_type, decision
UNION ALL
SELECT 'automation_bucket' AS section, automation_bucket AS key, COUNT(*)::integer AS count
  FROM bucketed
 GROUP BY automation_bucket
UNION ALL
SELECT 'unknown' AS section, decision || ':' || chat_type AS key, COUNT(*)::integer AS count
  FROM bucketed
 WHERE doc_type = 'unknown'
 GROUP BY decision, chat_type
ORDER BY section, count DESC, key
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

def _strip_env_file_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def load_scoped_wa_mirror_delivery_env(path: Path | None = None) -> tuple[str, ...]:
    """Load only the WA Mirror delivery keys from the local env file.

    ``~/.wa-mirror.env`` is consumed by historical WA scripts via manual parsing,
    not shell ``source``; it can contain spaces and unrelated values. Bulk intake
    delivery needs only the scoped CRM write bridge and its delivery flags, so
    import this tight allowlist and never log values.
    """
    env_path = path or WA_MIRROR_ENV_FILE
    if not env_path.exists():
        return ()

    allowed = set(SCOPED_WA_MIRROR_DELIVERY_ENV_NAMES)
    loaded: list[str] = []
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in allowed or os.environ.get(name):
            continue
        value = _strip_env_file_value(value)
        if not value:
            continue
        os.environ[name] = value
        loaded.append(name)
    return tuple(loaded)


class CrmServiceWritePreflightError(RuntimeError):
    """Raised when a bulk auto-attach apply would not be deliverable to Kita."""


def _env_enabled_default_on(name: str) -> bool:
    return os.environ.get(name, "1").strip().lower() not in {"0", "false", "no", "off"}


def _crm_push_base_url() -> str:
    return os.environ.get("INTAKE_CRM_PUSH_BASE_URL", "").strip() or DEFAULT_CRM_PUSH_BASE_URL


def _crm_push_write_key_from_env() -> str | None:
    load_scoped_wa_mirror_delivery_env()
    for name in ("INTAKE_CRM_PUSH_WRITE_KEY", "WA_MIRROR_CRM_WRITE_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _crm_service_write_preflight_accepted(status_code: int) -> bool:
    # Empty JSON with valid service-write auth must reach FastAPI body validation.
    return status_code == 422


def _compact_http_detail(text: str, *, max_chars: int = 200) -> str:
    return " ".join(text.split())[:max_chars]


async def assert_crm_service_write_preflight(
    *, client: httpx.AsyncClient | None = None
) -> None:
    """Fail before bulk auto-attach commits if Kita service-write is not ready.

    The auto-attach service treats Pro->Fly delivery as best-effort after the
    local commit. That is appropriate for human approvals, but unsafe for a bulk
    backlog run whose goal is specifically to put the file in Kita. This preflight
    sends no document and no PII: a valid service route should authenticate the
    request, then reject the empty JSON body with HTTP 422.
    """
    load_scoped_wa_mirror_delivery_env()
    if not _env_enabled_default_on("INTAKE_CRM_PUSH_ENABLED"):
        raise CrmServiceWritePreflightError("INTAKE_CRM_PUSH_ENABLED is disabled")

    key = _crm_push_write_key_from_env()
    if not key:
        raise CrmServiceWritePreflightError(
            "missing INTAKE_CRM_PUSH_WRITE_KEY/WA_MIRROR_CRM_WRITE_KEY"
        )

    base = _crm_push_base_url().rstrip("/")
    url = f"{base}/api/crm/internal/clients/1/documents/upload"
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_CRM_PUSH_PREFLIGHT_TIMEOUT_SECONDS)
        )
    try:
        try:
            response = await client.post(url, headers={"X-CRM-Write-Key": key}, json={})
        except httpx.HTTPError as exc:
            raise CrmServiceWritePreflightError(
                f"CRM service-write preflight unreachable: {type(exc).__name__}: {exc}"
            ) from exc
    finally:
        if owns_client:
            await client.aclose()

    if _crm_service_write_preflight_accepted(response.status_code):
        logger.info("[crm-push-preflight] service-write route accepted auth at %s", base)
        return

    raise CrmServiceWritePreflightError(
        "CRM service-write preflight failed: "
        f"HTTP {response.status_code}: {_compact_http_detail(response.text)}"
    )


def _env_enabled_default_off(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def run_delivery_readiness_report(
    *, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Read-only delivery readiness report for WA Mirror -> Kita bulk attach."""
    loaded = load_scoped_wa_mirror_delivery_env()
    report: dict[str, Any] = {
        "base_url": _crm_push_base_url(),
        "loaded_env_names": [name for name in loaded if not name.endswith("_KEY")],
        "crm_push_enabled": _env_enabled_default_on("INTAKE_CRM_PUSH_ENABLED"),
        "crm_write_key_present": _crm_push_write_key_from_env() is not None,
        "intake_writer_enabled": _env_enabled_default_off("INTAKE_WRITER_ENABLED"),
        "auto_attach_enabled": _env_enabled_default_off("INTAKE_AUTO_ATTACH_ENABLED"),
        "direct_phone_auto_attach_enabled": _env_enabled_default_off(
            "INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED"
        ),
        "preflight": "not_run",
    }
    if not report["crm_push_enabled"] or not report["crm_write_key_present"]:
        report["preflight"] = "skipped"
    else:
        try:
            await assert_crm_service_write_preflight(client=client)
        except CrmServiceWritePreflightError as exc:
            report["preflight"] = "failed"
            report["preflight_error"] = _compact_http_detail(str(exc), max_chars=240)
        else:
            report["preflight"] = "accepted"

    logger.info(
        "[delivery-readiness-report] %s",
        json.dumps(report, sort_keys=True, separators=(",", ":")),
    )
    return report


def _stage_output_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _saved_ocr_pages(stage_output: Any) -> list[dict[str, Any]]:
    """Return saved classify OCR pages in the shape downstream routing expects."""
    stage = _stage_output_dict(stage_output)
    classify = _stage_output_dict(stage.get("classify"))
    raw_pages = classify.get("ocr_text_per_page") or []
    if isinstance(raw_pages, str):
        raw_pages = [raw_pages]
    if not isinstance(raw_pages, list):
        return []

    pages: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_pages):
        if isinstance(item, dict):
            page = dict(item)
            text = page.get("text") or page.get("ocr_text") or ""
            page["text"] = str(text)
            page.setdefault("page", idx)
        else:
            page = {"page": idx, "text": str(item or "")}
        pages.append(page)
    return pages


def _ocr_text_from_pages(pages: list[dict[str, Any]], *, max_chars: int) -> str:
    chunks = [str(page.get("text") or "") for page in pages]
    return "\n".join(chunks).strip()[: max(max_chars, 1)]


def _keyword_classify_saved_ocr_text(ocr_text: str) -> tuple[str | None, float, dict[str, float]]:
    """Classify saved OCR with the production deterministic scorer, no model call."""
    text = ocr_text.strip()
    if not text:
        return None, 0.0, {}

    scores = _score_types(text)
    stay_subtype = _stay_permit_subtype(text)
    if stay_subtype and stay_subtype in DOCUMENT_CATEGORY_MAP:
        confidence = max(scores.get("kitas", 0.0), 0.55)
        return stay_subtype, round(confidence, 3), scores

    if not scores:
        return None, 0.0, {}
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    if best_score >= KEYWORD_CLASSIFY_MIN_CONFIDENCE and best_type in DOCUMENT_CATEGORY_MAP:
        return best_type, best_score, scores
    return None, best_score, scores


def _build_saved_ocr_preclassify_payload(
    stage_output: Any,
    *,
    doc_type: str,
    model: str,
    provider: str = DEFAULT_AUTOCATALOG_PROVIDER,
    ocr_max_chars: int = DEFAULT_AUTOCATALOG_OCR_MAX_CHARS,
    confidence: float = TEXT_LLM_CLASSIFY_CONF,
    type_scores: dict[str, float] | None = None,
    classified_via: str = "saved_ocr_local_text_llm_preclassify",
) -> dict[str, Any]:
    """Build a classify-stage payload from preserved OCR and a local Qwen type."""
    pages = _saved_ocr_pages(stage_output)
    safe_confidence = round(max(min(confidence, 1.0), 0.0), 3)
    payload: dict[str, Any] = {
        "doc_type": doc_type,
        "type_confidence": safe_confidence,
        "ocr_text_per_page": pages,
        "n_pages": len(pages),
        "source_page": None,
        "model": model,
        "provider": provider,
        "type_scores": type_scores or {doc_type: safe_confidence},
        "classified_via": classified_via,
        "ocr_max_chars": max(ocr_max_chars, 1),
        "_metric": {"model": model, "provider": provider, "confidence": safe_confidence},
    }
    if classified_via == "saved_ocr_keyword_preclassify":
        payload["classify_keyword_model"] = model
        payload["classify_keyword_provider"] = provider
        payload["classify_keyword_min_confidence"] = KEYWORD_CLASSIFY_MIN_CONFIDENCE
    else:
        payload["classify_llm_model"] = model
        payload["classify_llm_provider"] = provider
    return payload


def _build_saved_ocr_preclassify_attempt_payload(
    *,
    provider: str,
    model: str,
    pipeline_version: str,
    outcome: str,
    ocr_max_chars: int,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Build a PII-free marker so failed local attempts do not block batches."""
    payload: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "pipeline_version": pipeline_version,
        "outcome": outcome,
        "classified_via": "saved_ocr_local_text_llm_preclassify",
        "ocr_max_chars": max(ocr_max_chars, 1),
    }
    if error_type:
        payload["error_type"] = error_type
    return payload


def _build_saved_vision_preclassify_payload(
    stage_output: Any,
    *,
    doc_type: str,
    model: str,
    source_page: int | None,
    max_pages: int,
    image_max_side: int,
) -> dict[str, Any]:
    """Build a classify-stage payload from preserved OCR and a local vision type."""
    pages = _saved_ocr_pages(stage_output)
    return {
        "doc_type": doc_type,
        "type_confidence": VISION_CLASSIFY_CONF,
        "ocr_text_per_page": pages,
        "n_pages": len(pages),
        "source_page": source_page,
        "model": model,
        "provider": "ollama-vision",
        "type_scores": {doc_type: VISION_CLASSIFY_CONF},
        "classified_via": "saved_blob_local_vision_preclassify",
        "classify_vision_model": model,
        "classify_vision_provider": "ollama",
        "vision_max_pages": max(max_pages, 1),
        "vision_image_max_side": max(image_max_side, 1),
        "_metric": {
            "model": model,
            "provider": "ollama-vision",
            "confidence": VISION_CLASSIFY_CONF,
        },
    }


def _build_saved_vision_preclassify_attempt_payload(
    *,
    model: str,
    pipeline_version: str,
    outcome: str,
    max_pages: int,
    image_max_side: int,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Build a PII-free local-vision attempt marker."""
    payload: dict[str, Any] = {
        "provider": "ollama-vision",
        "model": model,
        "pipeline_version": pipeline_version,
        "outcome": outcome,
        "classified_via": "saved_blob_local_vision_preclassify",
        "vision_max_pages": max(max_pages, 1),
        "vision_image_max_side": max(image_max_side, 1),
    }
    if error_type:
        payload["error_type"] = error_type
    return payload


def _resize_png_for_vision_classify(png_bytes: bytes, *, max_side: int) -> bytes:
    """Downsize a page for doc-type classification while keeping it local."""
    safe_max_side = max(max_side, 32)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(png_bytes)) as im:
            im = im.convert("RGB")
            width, height = im.size
            if max(width, height) > safe_max_side:
                scale = safe_max_side / float(max(width, height))
                new_size = (
                    max(32, int(width * scale)),
                    max(32, int(height * scale)),
                )
                resample = getattr(Image, "Resampling", Image).LANCZOS
                im = im.resize(new_size, resample)
            out = io.BytesIO()
            im.save(out, format="PNG", optimize=True)
            return out.getvalue()
    except Exception:
        return png_bytes


def _vision_preclassify_prompt(ocr_text: str) -> str:
    """Build a local-only doc-type prompt from image plus saved OCR excerpt."""
    prompt = (
        _VISION_CLASSIFY_PROMPT
        + " Use the visual document layout first. The OCR excerpt below may be noisy; "
        "use it only to identify the document category, never to infer identity. "
        "Common cues: bank statement means account/balance/transaction pages; "
        "payment_receipt means proof of transfer/payment; travel_ticket means boarding "
        "pass/itinerary/ticket; medical_insurance means policy/insurance card; "
        "passport means passport booklet/MRZ; visa means visa/e-visa/permit notice."
    )
    excerpt = ocr_text.strip()[:DEFAULT_AUTOCATALOG_VISION_OCR_MAX_CHARS]
    if excerpt:
        prompt += "\n\nOCR excerpt:\n" + excerpt
    return prompt


async def _classify_vision_png(
    client: httpx.AsyncClient,
    *,
    ollama_url: str,
    model: str,
    png_bytes: bytes,
    ocr_text: str,
    timeout_seconds: float,
    image_max_side: int,
) -> str | None:
    """Classify one local PNG via Ollama vision; exact DOC_TYPES answer only."""
    if not png_bytes:
        return None
    resized = _resize_png_for_vision_classify(png_bytes, max_side=image_max_side)
    b64 = base64.b64encode(resized).decode("ascii")
    response = await client.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": _vision_preclassify_prompt(ocr_text),
            "images": [b64],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.0,
                "num_predict": _VISION_CLASSIFY_NUM_PREDICT,
            },
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    return _parse_vision_answer(data.get("response") or data.get("thinking"))


async def _classify_vision_pages(
    client: httpx.AsyncClient,
    pages: list[Any],
    *,
    ollama_url: str,
    model: str,
    ocr_text: str,
    timeout_seconds: float,
    max_pages: int,
    image_max_side: int,
) -> tuple[str | None, int | None, str]:
    """Try capped preprocessed pages, returning (doc_type, page_index, outcome)."""
    saw_unknown = False
    attempted = 0
    for page in pages[: max(max_pages, 1)]:
        png_bytes = getattr(page, "png_bytes", b"")
        if not png_bytes:
            continue
        attempted += 1
        answer = await _classify_vision_png(
            client,
            ollama_url=ollama_url,
            model=model,
            png_bytes=png_bytes,
            ocr_text=ocr_text,
            timeout_seconds=timeout_seconds,
            image_max_side=image_max_side,
        )
        if answer and answer != "unknown":
            return answer, getattr(page, "index", None), "known"
        if answer == "unknown":
            saw_unknown = True
    if saw_unknown:
        return "unknown", None, "unknown"
    return None, None, "malformed" if attempted else "no_image"


async def _classify_saved_ocr_text_ollama(
    client: httpx.AsyncClient,
    *,
    ollama_url: str,
    model: str,
    ocr_text: str,
    timeout_seconds: float,
) -> str | None:
    """Classify saved OCR text with local Ollama; exact-token answer only."""
    if not ocr_text.strip():
        return None
    response = await client.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": _text_llm_classify_prompt(ocr_text),
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_predict": 24},
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    return _parse_doc_type_answer(data.get("response") or data.get("thinking"))


def _openai_chat_completions_url(base_url: str) -> str:
    """Return a /chat/completions URL from a bare or /v1 base URL."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


async def _classify_saved_ocr_text_mlx(
    client: httpx.AsyncClient,
    *,
    mlx_base_url: str,
    model: str,
    ocr_text: str,
    timeout_seconds: float,
) -> str | None:
    """Classify saved OCR text with local MLX OpenAI-compatible chat endpoint."""
    if not ocr_text.strip():
        return None
    response = await client.post(
        _openai_chat_completions_url(mlx_base_url),
        json={
            "model": model,
            "messages": [{"role": "user", "content": _text_llm_classify_prompt(ocr_text)}],
            "temperature": 0.0,
            "max_tokens": 24,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    first = choices[0] if choices else {}
    message = first.get("message") or {}
    return _parse_doc_type_answer(message.get("content") or first.get("text"))


async def _classify_saved_ocr_text(
    client: httpx.AsyncClient,
    *,
    provider: str,
    ollama_url: str,
    mlx_base_url: str,
    model: str,
    ocr_text: str,
    timeout_seconds: float,
) -> str | None:
    """Classify saved OCR with a local provider."""
    if provider == "ollama":
        return await _classify_saved_ocr_text_ollama(
            client,
            ollama_url=ollama_url,
            model=model,
            ocr_text=ocr_text,
            timeout_seconds=timeout_seconds,
        )
    if provider == "mlx":
        return await _classify_saved_ocr_text_mlx(
            client,
            mlx_base_url=mlx_base_url,
            model=model,
            ocr_text=ocr_text,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"unsupported autocatalog provider: {provider}")


async def _mark_saved_ocr_preclassify_attempt(
    pool: asyncpg.Pool,
    *,
    queue_id: int,
    provider: str,
    model: str,
    pipeline_version: str,
    outcome: str,
    ocr_max_chars: int,
    error_type: str | None = None,
) -> int:
    """Persist a PII-free local-LLM attempt marker for a queue row."""
    payload = _build_saved_ocr_preclassify_attempt_payload(
        provider=provider,
        model=model,
        pipeline_version=pipeline_version,
        outcome=outcome,
        ocr_max_chars=ocr_max_chars,
        error_type=error_type,
    )
    async with pool.acquire() as conn:
        updated = await conn.execute(
            SAVED_OCR_PRECLASSIFY_ATTEMPT_SQL,
            queue_id,
            json.dumps(payload, sort_keys=True),
    )
    return int(updated.split()[-1]) if updated else 0


async def _mark_saved_vision_preclassify_attempt(
    pool: asyncpg.Pool,
    *,
    queue_id: int,
    model: str,
    pipeline_version: str,
    outcome: str,
    max_pages: int,
    image_max_side: int,
    error_type: str | None = None,
) -> int:
    """Persist a PII-free local-vision attempt marker for a queue row."""
    payload = _build_saved_vision_preclassify_attempt_payload(
        model=model,
        pipeline_version=pipeline_version,
        outcome=outcome,
        max_pages=max_pages,
        image_max_side=image_max_side,
        error_type=error_type,
    )
    async with pool.acquire() as conn:
        updated = await conn.execute(
            SAVED_VISION_PRECLASSIFY_ATTEMPT_SQL,
            queue_id,
            json.dumps(payload, sort_keys=True),
        )
    return int(updated.split()[-1]) if updated else 0


# --- Modes -------------------------------------------------------------------


async def run_reprocess(pool: asyncpg.Pool, pipeline_version: str, apply: bool) -> dict[str, int]:
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
                counts["proposals"],
                counts["queue_rows"],
                pipeline_version,
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
        counts.get("superseded", 0),
        counts.get("reset", 0),
        pipeline_version,
    )
    return counts


async def _run_route_only_reroute(
    pool: asyncpg.Pool,
    *,
    mode: str,
    select_sql: str,
    pipeline_version: str,
    limit: int,
    apply: bool,
) -> dict[str, int]:
    """Shared route-only reroute engine (m227 folder / m248 npwp).

    One transaction end-to-end (Codex round-2): the SELECT, the
    lease-eligibility lock (FOR UPDATE SKIP LOCKED — a row the worker is
    actively processing is skipped, never yanked), the proposal supersede and
    the queue reset all commit or roll back together. stage_output is NEVER
    touched (locked by contract test).
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(select_sql, limit)
            queue_ids = sorted({r["queue_id"] for r in rows})

            counts = {"proposals": len(rows), "queue_rows": len(queue_ids)}
            if not apply:
                logger.info(
                    "[%s][DRY-RUN] would supersede %d proposals and resume %d "
                    "queue rows at route (pipeline_version=%s, limit=%d) "
                    "(pass --apply to execute)",
                    mode, counts["proposals"], counts["queue_rows"],
                    pipeline_version, limit,
                )
                return counts

            eligible_rows = await conn.fetch(REROUTE_ELIGIBLE_LOCK_SQL, queue_ids)
            eligible = sorted(r["id"] for r in eligible_rows)
            counts["lease_skipped"] = len(queue_ids) - len(eligible)

            # Supersede first, RETURNING queue_id — only queue rows whose
            # proposal was ACTUALLY superseded get reset. A proposal a human
            # claimed between the SELECT and here (review_pending →
            # review_claimed) is left alone: no supersede, no reset (Codex
            # round-2: resetting it would spawn a duplicate proposal under a
            # reviewer's feet).
            superseded_rows = await conn.fetch(
                REROUTE_DRIVE_FOLDER_SUPERSEDE_SQL, eligible
            )
            superseded_qids = sorted({r["queue_id"] for r in superseded_rows})
            counts["claim_skipped"] = len(eligible) - len(superseded_qids)
            reset = await conn.execute(
                REROUTE_DRIVE_FOLDER_RESET_SQL, superseded_qids, pipeline_version
            )
        counts["superseded"] = len(superseded_rows)
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[%s] superseded=%d proposals, resumed=%d queue rows at route "
        "(pipeline_version=%s, lease_skipped=%d, claim_skipped=%d)",
        mode, counts.get("superseded", 0), counts.get("reset", 0),
        pipeline_version, counts.get("lease_skipped", 0),
        counts.get("claim_skipped", 0),
    )
    return counts


async def run_reroute_drive_folder(
    pool: asyncpg.Pool, pipeline_version: str, limit: int, apply: bool
) -> dict[str, int]:
    """Re-route Drive 0-candidate proposals through the fixed m227 folder matcher.

    Route-only resume (status='validated', stage_output PRESERVED — the saved
    OCR/extract fields are the only copy left after blob retention). Supersedes
    the stale NO_MATCH proposals and lets the live worker re-run fase-4
    resolve_entity with source_path, so client folders at any depth (PR #2664)
    produce LINK_CANDIDATE/AMBIGUOUS proposals. Candidates feed the normal
    review tier; any auto-attach still requires the concordance gates.
    """
    return await _run_route_only_reroute(
        pool,
        mode="reroute-drive-folder",
        select_sql=REROUTE_DRIVE_FOLDER_SELECT_SQL,
        pipeline_version=pipeline_version,
        limit=limit,
        apply=apply,
    )


async def run_reroute_npwp(
    pool: asyncpg.Pool, pipeline_version: str, limit: int, apply: bool
) -> dict[str, int]:
    """Re-route review_pending rows carrying a full extracted npwp (m248).

    Route-only resume, identical contract to --reroute-drive-folder
    (stage_output PRESERVED, supersede stale proposals, worker re-runs fase-4
    where _match_person_strong now consults clients.npwp). A unique npwp hit
    adds a CONF_STRONG_EXACT candidate; duplicate-npwp and person/company
    npwp collisions degrade to AMBIGUOUS downstream. NOTE: the live worker
    runs with the auto-attach killswitches ON — an AUTO_ATTACH decision plus
    phone/subject-name concordance CAN commit (reversible via
    intake_commit_audit + rollback_commit).
    """
    return await _run_route_only_reroute(
        pool,
        mode="reroute-npwp",
        select_sql=REROUTE_NPWP_SELECT_SQL,
        pipeline_version=pipeline_version,
        limit=limit,
        apply=apply,
    )


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
                counts["queue_rows"],
                include_groups,
                pipeline_version,
            )
            return counts

        async with conn.transaction():
            reset = await conn.execute(REPROCESS_RESET_SQL, queue_ids, pipeline_version)
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[revive-stub] reset=%d stub-skipped whatsapp queue rows (include_groups=%s, "
        "pipeline_version=%s) — the intake worker will re-OCR + re-route them",
        counts.get("reset", 0),
        include_groups,
        pipeline_version,
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

    counts = {
        "candidates": len(rows),
        "blob_missing": 0,
        "enqueued_new": 0,
        "already": 0,
        "errors": 0,
    }

    for r in rows:
        if not os.path.exists(r["media_stored_path"]):
            counts["blob_missing"] += 1
            continue
        if not apply:
            continue
        try:
            result = await enqueue(pool, **row_to_enqueue_kwargs(r))
        except Exception as exc:  # noqa: BLE001 — isolate per-row failure
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
            counts["candidates"],
            watermark,
            counts["blob_missing"],
            counts["candidates"] - counts["blob_missing"],
        )
    else:
        logger.info(
            "[backfill] candidates=%d new=%d dup=%d blob_missing=%d errors=%d",
            counts["candidates"],
            counts["enqueued_new"],
            counts["already"],
            counts["blob_missing"],
            counts["errors"],
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
                "[scrub-group-phone][DRY-RUN] candidates=%d by_status=%s (pass --apply to execute)",
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
                counts["candidates"],
                counts["direct"],
                counts["group"],
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
        counts["updated"],
        counts["direct"],
        counts["group"],
    )
    return counts


async def run_autocatalog_direct_unknown_text(
    pool: asyncpg.Pool,
    pipeline_version: str,
    min_ocr_chars: int,
    limit: int,
    apply: bool,
) -> dict[str, int]:
    """Reset direct unknown OCR-ready WA rows so local text LLM can classify them.

    This does not attach documents to CRM/Kita directly. It only restarts the v2
    worker path for a tightly scoped set; route still emits review proposals.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            DIRECT_UNKNOWN_TEXT_AUTOCATALOG_SELECT_SQL,
            min_ocr_chars,
            limit,
        )
        queue_ids = [r["queue_id"] for r in rows]
        proposal_ids = sorted(
            {pid for row in rows for pid in (row["proposal_ids"] or []) if pid is not None}
        )
        counts = {
            "queue_rows": len(queue_ids),
            "review_pending_proposals": len(proposal_ids),
            "min_ocr_chars": min_ocr_chars,
            "limit": limit,
        }
        if not apply:
            logger.info(
                "[autocatalog-direct-unknown-text][DRY-RUN] would reset %d direct "
                "unknown OCR-ready queue rows and supersede %d review_pending "
                "proposals to pipeline_version=%s; worker requires "
                "INTAKE_TEXT_LLM_CLASSIFY_ENABLED=1 (pass --apply)",
                counts["queue_rows"],
                counts["review_pending_proposals"],
                pipeline_version,
            )
            return counts

        async with conn.transaction():
            if proposal_ids:
                superseded = await conn.execute(REPROCESS_SUPERSEDE_SQL, proposal_ids)
            else:
                superseded = "UPDATE 0"
            reset = await conn.execute(REPROCESS_RESET_SQL, queue_ids, pipeline_version)
        counts["superseded"] = int(superseded.split()[-1]) if superseded else 0
        counts["reset"] = int(reset.split()[-1]) if reset else 0

    logger.info(
        "[autocatalog-direct-unknown-text] reset=%d queue rows, superseded=%d "
        "proposals (pipeline_version=%s). Ensure worker env "
        "INTAKE_TEXT_LLM_CLASSIFY_ENABLED=1.",
        counts.get("reset", 0),
        counts.get("superseded", 0),
        pipeline_version,
    )
    return counts


async def run_autocatalog_preclassify_saved_ocr(
    pool: asyncpg.Pool,
    pipeline_version: str,
    min_ocr_chars: int,
    limit: int,
    apply: bool,
    *,
    provider: str,
    ollama_url: str,
    mlx_base_url: str,
    model: str,
    timeout_seconds: float,
    ocr_max_chars: int,
) -> dict[str, int]:
    """Classify saved OCR once, then resume the normal worker at ``ocr_done``.

    Only known local-Qwen answers mutate queue rows. ``unknown`` or malformed
    answers leave the existing review proposal untouched, preventing review churn.
    Raw OCR text is sent only to local Ollama and is never logged.
    """
    safe_min_ocr_chars = max(min_ocr_chars, 1)
    safe_limit = max(limit, 1)
    safe_ocr_max_chars = max(ocr_max_chars, 1)
    safe_timeout = max(timeout_seconds, 1.0)
    safe_provider = provider.strip().lower()
    if safe_provider not in {"ollama", "mlx"}:
        raise ValueError("autocatalog provider must be 'ollama' or 'mlx'")

    fetch_limit = min(max(safe_limit * 20, safe_limit), 5000)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SAVED_OCR_PRECLASSIFY_SELECT_SQL,
            safe_min_ocr_chars,
            model,
            pipeline_version,
            fetch_limit,
        )

    ranked_rows: list[dict[str, Any]] = []
    for row in rows:
        pages = _saved_ocr_pages(row["stage_output"])
        ocr_text = _ocr_text_from_pages(pages, max_chars=safe_ocr_max_chars)
        keyword_answer, keyword_confidence, keyword_scores = _keyword_classify_saved_ocr_text(
            ocr_text
        )
        ranked_rows.append(
            {
                "row": row,
                "pages": pages,
                "ocr_text": ocr_text,
                "keyword_answer": keyword_answer,
                "keyword_confidence": keyword_confidence,
                "keyword_scores": keyword_scores,
            }
        )
    ranked_rows.sort(
        key=lambda item: (
            -float(item["keyword_confidence"]),
            int(item["row"]["queue_id"]),
        )
    )
    selected_rows = ranked_rows[:safe_limit]

    counts = {
        "candidates": len(selected_rows),
        "candidate_pool": len(rows),
        "attempted": 0,
        "known_answers": 0,
        "unknown_answers": 0,
        "malformed_answers": 0,
        "errors": 0,
        "marked_attempts": 0,
        "updated": 0,
        "superseded": 0,
        "keyword_answers": 0,
        "min_ocr_chars": safe_min_ocr_chars,
        "limit": safe_limit,
    }
    if not apply:
        logger.info(
            "[autocatalog-preclassify-saved-ocr][DRY-RUN] would local-classify "
            "%d direct review_pending unknown docs from pool=%d with saved OCR and resume "
            "known answers at status=ocr_done provider=%s model=%s "
            "pipeline_version=%s (pass --apply)",
            counts["candidates"],
            counts["candidate_pool"],
            safe_provider,
            model,
            pipeline_version,
        )
        return counts

    by_doc_type: Counter[str] = Counter()
    by_error: Counter[str] = Counter()
    async with httpx.AsyncClient() as client:
        for item in selected_rows:
            row = item["row"]
            ocr_text = item["ocr_text"]
            counts["attempted"] += 1
            keyword_answer = item["keyword_answer"]
            keyword_confidence = item["keyword_confidence"]
            keyword_scores = item["keyword_scores"]
            if keyword_answer:
                counts["known_answers"] += 1
                counts["keyword_answers"] += 1
                by_doc_type[keyword_answer] += 1
                proposal_ids = sorted(
                    {pid for pid in (row["proposal_ids"] or []) if pid is not None}
                )
                payload = _build_saved_ocr_preclassify_payload(
                    row["stage_output"],
                    doc_type=keyword_answer,
                    provider=KEYWORD_CLASSIFY_PROVIDER,
                    model=KEYWORD_CLASSIFY_MODEL,
                    ocr_max_chars=safe_ocr_max_chars,
                    confidence=keyword_confidence,
                    type_scores=keyword_scores,
                    classified_via="saved_ocr_keyword_preclassify",
                )
                async with pool.acquire() as conn, conn.transaction():
                    if proposal_ids:
                        superseded = await conn.execute(REPROCESS_SUPERSEDE_SQL, proposal_ids)
                        counts["superseded"] += (
                            int(superseded.split()[-1]) if superseded else 0
                        )
                    updated = await conn.execute(
                        SAVED_OCR_PRECLASSIFY_UPDATE_SQL,
                        row["queue_id"],
                        json.dumps(payload, sort_keys=True),
                        pipeline_version,
                    )
                    counts["updated"] += int(updated.split()[-1]) if updated else 0
                continue
            try:
                answer = await _classify_saved_ocr_text(
                    client,
                    provider=safe_provider,
                    ollama_url=ollama_url,
                    mlx_base_url=mlx_base_url,
                    model=model,
                    ocr_text=ocr_text,
                    timeout_seconds=safe_timeout,
                )
            except Exception as exc:  # aggregate only; no raw OCR / no row payload.
                counts["errors"] += 1
                by_error[type(exc).__name__] += 1
                counts["marked_attempts"] += await _mark_saved_ocr_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    provider=safe_provider,
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome="error",
                    ocr_max_chars=safe_ocr_max_chars,
                    error_type=type(exc).__name__,
                )
                continue

            if answer is None:
                counts["malformed_answers"] += 1
                counts["marked_attempts"] += await _mark_saved_ocr_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    provider=safe_provider,
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome="malformed",
                    ocr_max_chars=safe_ocr_max_chars,
                )
                continue
            if answer == "unknown":
                counts["unknown_answers"] += 1
                counts["marked_attempts"] += await _mark_saved_ocr_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    provider=safe_provider,
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome="unknown",
                    ocr_max_chars=safe_ocr_max_chars,
                )
                continue

            counts["known_answers"] += 1
            by_doc_type[answer] += 1
            proposal_ids = sorted({pid for pid in (row["proposal_ids"] or []) if pid is not None})
            payload = _build_saved_ocr_preclassify_payload(
                row["stage_output"],
                doc_type=answer,
                provider=safe_provider,
                model=model,
                ocr_max_chars=safe_ocr_max_chars,
            )
            async with pool.acquire() as conn, conn.transaction():
                if proposal_ids:
                    superseded = await conn.execute(REPROCESS_SUPERSEDE_SQL, proposal_ids)
                    counts["superseded"] += int(superseded.split()[-1]) if superseded else 0
                updated = await conn.execute(
                    SAVED_OCR_PRECLASSIFY_UPDATE_SQL,
                    row["queue_id"],
                    json.dumps(payload, sort_keys=True),
                    pipeline_version,
                )
                counts["updated"] += int(updated.split()[-1]) if updated else 0

    logger.info(
        "[autocatalog-preclassify-saved-ocr] candidates=%d attempted=%d "
        "pool=%d known=%d keyword=%d unknown=%d malformed=%d errors=%d marked_attempts=%d "
        "updated=%d superseded=%d "
        "by_doc_type=%s by_error=%s provider=%s model=%s pipeline_version=%s",
        counts["candidates"],
        counts["attempted"],
        counts["candidate_pool"],
        counts["known_answers"],
        counts["keyword_answers"],
        counts["unknown_answers"],
        counts["malformed_answers"],
        counts["errors"],
        counts["marked_attempts"],
        counts["updated"],
        counts["superseded"],
        dict(by_doc_type),
        dict(by_error),
        safe_provider,
        model,
        pipeline_version,
    )
    return counts


async def run_autocatalog_preclassify_vision(
    pool: asyncpg.Pool,
    pipeline_version: str,
    min_ocr_chars: int,
    limit: int,
    apply: bool,
    *,
    ollama_url: str,
    model: str,
    timeout_seconds: float,
    max_pages: int,
    image_max_side: int,
) -> dict[str, int]:
    """Classify direct unknown review docs with local vision on downsized pages.

    Only known local-Qwen vision answers mutate queue rows. Unknowns, empty
    images, malformed answers, and model errors leave the existing review
    proposal untouched and add only PII-free attempt metadata.
    """
    safe_min_ocr_chars = max(min_ocr_chars, 0)
    safe_limit = max(limit, 1)
    safe_timeout = max(timeout_seconds, 1.0)
    safe_max_pages = max(max_pages, 1)
    safe_image_max_side = max(image_max_side, 32)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SAVED_VISION_PRECLASSIFY_SELECT_SQL,
            safe_min_ocr_chars,
            model,
            pipeline_version,
            safe_limit,
        )

    counts = {
        "candidates": len(rows),
        "attempted": 0,
        "known_answers": 0,
        "unknown_answers": 0,
        "malformed_answers": 0,
        "no_image": 0,
        "unsupported_answers": 0,
        "errors": 0,
        "marked_attempts": 0,
        "updated": 0,
        "superseded": 0,
        "min_ocr_chars": safe_min_ocr_chars,
        "limit": safe_limit,
    }
    if not apply:
        logger.info(
            "[autocatalog-preclassify-vision][DRY-RUN] would local-vision-classify "
            "%d direct review_pending unknown docs and resume known answers at "
            "status=ocr_done model=%s max_pages=%d image_max_side=%d "
            "pipeline_version=%s (pass --apply)",
            counts["candidates"],
            model,
            safe_max_pages,
            safe_image_max_side,
            pipeline_version,
        )
        return counts

    by_doc_type: Counter[str] = Counter()
    by_error: Counter[str] = Counter()
    async with httpx.AsyncClient() as client:
        for row in rows:
            counts["attempted"] += 1
            try:
                preprocessed = await preprocess_blob(
                    row["blob_path"],
                    declared_mime=row["media_mime"],
                )
                saved_pages = _saved_ocr_pages(row["stage_output"])
                ocr_text = _ocr_text_from_pages(
                    saved_pages,
                    max_chars=DEFAULT_AUTOCATALOG_VISION_OCR_MAX_CHARS,
                )
                answer, source_page, outcome = await _classify_vision_pages(
                    client,
                    preprocessed.pages,
                    ollama_url=ollama_url,
                    model=model,
                    ocr_text=ocr_text,
                    timeout_seconds=safe_timeout,
                    max_pages=safe_max_pages,
                    image_max_side=safe_image_max_side,
                )
            except Exception as exc:  # aggregate only; no raw blob/OCR/path.
                counts["errors"] += 1
                by_error[type(exc).__name__] += 1
                counts["marked_attempts"] += await _mark_saved_vision_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome="error",
                    max_pages=safe_max_pages,
                    image_max_side=safe_image_max_side,
                    error_type=type(exc).__name__,
                )
                continue

            if answer is None or outcome in {"malformed", "no_image"}:
                bucket = "no_image" if outcome == "no_image" else "malformed_answers"
                counts[bucket] += 1
                counts["marked_attempts"] += await _mark_saved_vision_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome=outcome,
                    max_pages=safe_max_pages,
                    image_max_side=safe_image_max_side,
                )
                continue
            if answer == "unknown":
                counts["unknown_answers"] += 1
                counts["marked_attempts"] += await _mark_saved_vision_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome="unknown",
                    max_pages=safe_max_pages,
                    image_max_side=safe_image_max_side,
                )
                continue
            if answer not in DOCUMENT_CATEGORY_MAP:
                counts["unsupported_answers"] += 1
                counts["marked_attempts"] += await _mark_saved_vision_preclassify_attempt(
                    pool,
                    queue_id=row["queue_id"],
                    model=model,
                    pipeline_version=pipeline_version,
                    outcome="unsupported",
                    max_pages=safe_max_pages,
                    image_max_side=safe_image_max_side,
                )
                continue

            counts["known_answers"] += 1
            by_doc_type[answer] += 1
            proposal_ids = sorted({pid for pid in (row["proposal_ids"] or []) if pid is not None})
            payload = _build_saved_vision_preclassify_payload(
                row["stage_output"],
                doc_type=answer,
                model=model,
                source_page=source_page,
                max_pages=safe_max_pages,
                image_max_side=safe_image_max_side,
            )
            async with pool.acquire() as conn, conn.transaction():
                if proposal_ids:
                    superseded = await conn.execute(REPROCESS_SUPERSEDE_SQL, proposal_ids)
                    counts["superseded"] += int(superseded.split()[-1]) if superseded else 0
                updated = await conn.execute(
                    SAVED_OCR_PRECLASSIFY_UPDATE_SQL,
                    row["queue_id"],
                    json.dumps(payload, sort_keys=True),
                    pipeline_version,
                )
                counts["updated"] += int(updated.split()[-1]) if updated else 0

    logger.info(
        "[autocatalog-preclassify-vision] candidates=%d attempted=%d known=%d "
        "unknown=%d malformed=%d no_image=%d unsupported=%d errors=%d marked_attempts=%d "
        "updated=%d superseded=%d by_doc_type=%s by_error=%s model=%s "
        "pipeline_version=%s",
        counts["candidates"],
        counts["attempted"],
        counts["known_answers"],
        counts["unknown_answers"],
        counts["malformed_answers"],
        counts["no_image"],
        counts["unsupported_answers"],
        counts["errors"],
        counts["marked_attempts"],
        counts["updated"],
        counts["superseded"],
        dict(by_doc_type),
        dict(by_error),
        model,
        pipeline_version,
    )
    return counts


async def run_auto_attach_eligible(
    pool: asyncpg.Pool,
    limit: int,
    apply: bool,
) -> dict[str, Any]:
    """Run existing eligible review proposals through the auto-attach gate.

    This is only a backlog bridge for proposals born before route_stage consumed
    the gate. It does not bypass the double kill-switch: ``try_auto_attach``
    remains the only writer path.
    """
    safe_limit = max(limit, 1)
    async with pool.acquire() as conn:
        rows = await conn.fetch(AUTO_ATTACH_ELIGIBLE_SELECT_SQL, safe_limit)

    counts: dict[str, Any] = {
        "candidates": len(rows),
        "attempted": 0,
        "committed": 0,
        "errors": 0,
        "limit": safe_limit,
        "skipped": {},
        "outcomes": {},
    }
    if not apply:
        logger.info(
            "[auto-attach-eligible][DRY-RUN] would try %d review_pending "
            "eligible proposals through the double-concordance gate (pass --apply)",
            counts["candidates"],
        )
        return counts
    if counts["candidates"]:
        await assert_crm_service_write_preflight()

    skipped: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    by_error: Counter[str] = Counter()
    for row in rows:
        counts["attempted"] += 1
        try:
            verdict = await try_auto_attach(row, pool, sender_phone=row["sender_phone"])
        except Exception as exc:  # aggregate only; no proposal payload / no PII.
            counts["errors"] += 1
            by_error[type(exc).__name__] += 1
            continue

        if verdict.get("committed"):
            counts["committed"] += 1
        if verdict.get("skipped"):
            skipped[str(verdict["skipped"])] += 1
        if verdict.get("outcome"):
            outcomes[str(verdict["outcome"])] += 1

    counts["skipped"] = dict(skipped)
    counts["outcomes"] = dict(outcomes)
    counts["by_error"] = dict(by_error)
    logger.info(
        "[auto-attach-eligible] candidates=%d attempted=%d committed=%d "
        "skipped=%s outcomes=%s errors=%d by_error=%s",
        counts["candidates"],
        counts["attempted"],
        counts["committed"],
        counts["skipped"],
        counts["outcomes"],
        counts["errors"],
        counts["by_error"],
    )
    return counts


async def run_direct_phone_auto_attach(
    pool: asyncpg.Pool,
    limit: int,
    apply: bool,
) -> dict[str, Any]:
    """Run existing direct-chat phone candidates through the opt-in gate."""
    safe_limit = max(limit, 1)
    supported_doc_types = sorted(DOCUMENT_CATEGORY_MAP)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            DIRECT_PHONE_AUTO_ATTACH_SELECT_SQL,
            safe_limit,
            supported_doc_types,
        )

    counts: dict[str, Any] = {
        "candidates": len(rows),
        "attempted": 0,
        "committed": 0,
        "errors": 0,
        "limit": safe_limit,
        "skipped": {},
        "outcomes": {},
    }
    if not apply:
        logger.info(
            "[auto-attach-direct-phone][DRY-RUN] would try %d direct wa-mirror "
            "phone LINK_CANDIDATE proposals through the direct-phone gate "
            "(pass --apply)",
            counts["candidates"],
        )
        return counts
    if counts["candidates"]:
        await assert_crm_service_write_preflight()

    skipped: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    by_error: Counter[str] = Counter()
    for row in rows:
        counts["attempted"] += 1
        try:
            verdict = await try_direct_phone_auto_attach(
                row,
                pool,
                sender_phone=row["sender_phone"],
                source_context=row["source_context"],
            )
        except Exception as exc:  # aggregate only; no proposal payload / no PII.
            counts["errors"] += 1
            by_error[type(exc).__name__] += 1
            continue

        if verdict.get("committed"):
            counts["committed"] += 1
        if verdict.get("skipped"):
            skipped[str(verdict["skipped"])] += 1
        if verdict.get("outcome"):
            outcomes[str(verdict["outcome"])] += 1

    counts["skipped"] = dict(skipped)
    counts["outcomes"] = dict(outcomes)
    counts["by_error"] = dict(by_error)
    logger.info(
        "[auto-attach-direct-phone] candidates=%d attempted=%d committed=%d "
        "skipped=%s outcomes=%s errors=%d by_error=%s",
        counts["candidates"],
        counts["attempted"],
        counts["committed"],
        counts["skipped"],
        counts["outcomes"],
        counts["errors"],
        counts["by_error"],
    )
    return counts


async def run_promote_direct_new_prospects(
    pool: asyncpg.Pool,
    pipeline_version: str,
    limit: int,
    apply: bool,
) -> dict[str, Any]:
    """Create/resolve phone-keyed local leads for direct NO_MATCH backlog rows.

    This mode deliberately stops before document commit. It only makes the stale
    NO_MATCH rows routable by the existing sender-phone policy; the worker then
    emits a fresh LINK_CANDIDATE proposal, and ``--auto-attach-direct-phone`` is
    the only path that can write the document to Kita.
    """
    safe_limit = max(limit, 1)
    supported_doc_types = sorted(DOCUMENT_CATEGORY_MAP)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            DIRECT_NEW_PROSPECT_SELECT_SQL,
            safe_limit,
            supported_doc_types,
        )

    counts: dict[str, Any] = {
        "candidates": len(rows),
        "attempted": 0,
        "promoted": 0,
        "superseded": 0,
        "reset": 0,
        "errors": 0,
        "limit": safe_limit,
        "pipeline_version": pipeline_version,
        "by_error": {},
    }
    if not apply:
        logger.info(
            "[promote-direct-new-prospects][DRY-RUN] would upsert %d direct "
            "phone-keyed leads and re-route their NO_MATCH docs with "
            "pipeline_version=%s (pass --apply)",
            counts["candidates"],
            pipeline_version,
        )
        return counts

    by_error: Counter[str] = Counter()
    for row in rows:
        counts["attempted"] += 1
        try:
            async with pool.acquire() as conn, conn.transaction():
                client_id = await _upsert_wa_client_by_phone(
                    conn,
                    raw_phone=row["sender_phone"],
                    push_name=row["sender_push_name_snapshot"],
                    assigned_to=row["team_member_email"],
                    note_kind="historical media backlog",
                )
                if client_id is None:
                    by_error["no_phone"] += 1
                    continue

                superseded = await conn.execute(
                    REPROCESS_SUPERSEDE_SQL,
                    [row["proposal_id"]],
                )
                source_context = _wa_mirror_source_context(
                    {
                        "chat_type": row["chat_type"],
                        "group_jid": row["mirror_group_jid"],
                        "group_subject_snapshot": row["group_subject_snapshot"],
                        "sender_phone": row["sender_phone"],
                    }
                )
                reset = await conn.execute(
                    DIRECT_NEW_PROSPECT_RESET_SQL,
                    row["queue_id"],
                    client_id,
                    json.dumps(source_context, sort_keys=True),
                    pipeline_version,
                )

            counts["promoted"] += 1
            counts["superseded"] += int(superseded.split()[-1]) if superseded else 0
            counts["reset"] += int(reset.split()[-1]) if reset else 0
        except Exception as exc:  # aggregate only; no phone/proposal payload.
            counts["errors"] += 1
            by_error[type(exc).__name__] += 1

    counts["by_error"] = dict(by_error)
    logger.info(
        "[promote-direct-new-prospects] candidates=%d attempted=%d promoted=%d "
        "superseded=%d reset=%d errors=%d by_error=%s pipeline_version=%s",
        counts["candidates"],
        counts["attempted"],
        counts["promoted"],
        counts["superseded"],
        counts["reset"],
        counts["errors"],
        counts["by_error"],
        pipeline_version,
    )
    return counts


async def run_review_backlog_report(
    pool: asyncpg.Pool,
    min_ocr_chars: int,
) -> dict[str, Any]:
    """Report the current wa-mirror review backlog as aggregate automation buckets.

    The report intentionally uses the latest proposal per queue row so the count
    mirrors the review surface rather than historical/superseded proposals. It
    is read-only and PII-safe: rows contain only section/key/count aggregates.
    """
    safe_min_ocr_chars = max(min_ocr_chars, 1)
    supported_doc_types = sorted(DOCUMENT_CATEGORY_MAP)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            REVIEW_BACKLOG_REPORT_SQL,
            safe_min_ocr_chars,
            supported_doc_types,
        )

    report_rows = [
        {
            "section": str(row["section"]),
            "key": str(row["key"]),
            "count": int(row["count"]),
        }
        for row in rows
    ]
    counts: dict[str, Any] = {
        "min_ocr_chars": safe_min_ocr_chars,
        "supported_doc_types": len(supported_doc_types),
        "rows": report_rows,
    }
    logger.info(
        "[review-backlog-report] %s",
        json.dumps(counts, sort_keys=True, separators=(",", ":")),
    )
    return counts


# --- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Retroactive intake catalog v2 (dry-run by default; --apply to execute)."
    )
    p.add_argument(
        "--reprocess",
        action="store_true",
        help="supersede unknown/NO_MATCH review_pending proposals + reset queue rows",
    )
    p.add_argument(
        "--reroute-drive-folder",
        action="store_true",
        help=(
            "route-only resume of Drive 0-candidate review_pending rows through "
            "the fixed m227 folder matcher (stage_output preserved, never wiped)"
        ),
    )
    p.add_argument(
        "--reroute-npwp",
        action="store_true",
        help=(
            "route-only resume of review_pending rows with a full extracted "
            "npwp through the m248 person-npwp matcher (stage_output preserved)"
        ),
    )
    p.add_argument(
        "--reroute-limit",
        type=int,
        default=30000,
        help="max rows selected per --reroute-drive-folder / --reroute-npwp run",
    )
    p.add_argument(
        "--reroute-pipeline-version",
        default=None,
        help=(
            "pipeline_version stamped on rerouted rows (fresh routing_key); "
            "defaults per mode: v2.2-m227-folder (drive-folder), v2.3-npwp (npwp)"
        ),
    )
    p.add_argument(
        "--backfill",
        action="store_true",
        help="enqueue historical wa-mirror media skipped by the watermark seed",
    )
    p.add_argument(
        "--scrub-group-phone",
        action="store_true",
        help="clear sender_phone/client_id_hint from historical wa-mirror group queue rows",
    )
    p.add_argument(
        "--backfill-source-context",
        action="store_true",
        help="populate PII-safe direct/group source_context for wa-mirror queue rows",
    )
    p.add_argument(
        "--revive-stub",
        action="store_true",
        help="re-enqueue whatsapp docs the stub passthrough marked done with no proposal",
    )
    p.add_argument(
        "--retry-empty-pdf-ocr",
        action="store_true",
        help="reset whatsapp PDFs with rasterize_failed/raw_pdf_fallback and zero OCR text",
    )
    p.add_argument(
        "--retry-unschematised-supported",
        action="store_true",
        help="reset whatsapp docs skipped as unschematised but now extract-schema supported",
    )
    p.add_argument(
        "--retry-typed-missing-fields",
        action="store_true",
        help="reset typed whatsapp docs whose extract stage produced zero fields",
    )
    p.add_argument(
        "--quality-sample",
        action="store_true",
        help="read-only redacted OCR/interpretation quality snapshot",
    )
    p.add_argument(
        "--quality-sample-size",
        type=int,
        default=100,
        help="number of recent queue rows to sample for --quality-sample (default 100)",
    )
    p.add_argument(
        "--quality-source",
        default="whatsapp",
        help="intake_queue.source filter for --quality-sample (default whatsapp)",
    )
    p.add_argument(
        "--quality-pipeline-version",
        default=None,
        help="optional pipeline_version filter for --quality-sample",
    )
    p.add_argument(
        "--quality-statuses",
        default=None,
        help="optional comma list of intake_queue statuses for --quality-sample",
    )
    p.add_argument(
        "--quality-exclude-stub",
        action="store_true",
        help="for --quality-sample: exclude rows produced by stub handlers",
    )
    p.add_argument(
        "--autocatalog-direct-unknown-text",
        action="store_true",
        help="reset direct wa-mirror unknown docs with enough saved OCR for local Qwen text classification",
    )
    p.add_argument(
        "--autocatalog-preclassify-saved-ocr",
        action="store_true",
        help="use saved OCR + local Qwen now, then resume known answers at ocr_done without re-OCR",
    )
    p.add_argument(
        "--autocatalog-preclassify-vision",
        action="store_true",
        help="use local Qwen vision on downsized saved blobs, then resume known answers at ocr_done",
    )
    p.add_argument(
        "--auto-attach-eligible",
        action="store_true",
        help="try existing review_pending proposals whose gate already marks them auto_attach_eligible",
    )
    p.add_argument(
        "--auto-attach-direct-phone",
        action="store_true",
        help="try direct wa-mirror phone LINK_CANDIDATE proposals through the opt-in gate",
    )
    p.add_argument(
        "--promote-direct-new-prospects",
        action="store_true",
        help=(
            "upsert local phone-keyed leads for direct wa-mirror NO_MATCH docs, "
            "then re-route them through the normal worker"
        ),
    )
    p.add_argument(
        "--review-backlog-report",
        action="store_true",
        help="read-only aggregate triage of current wa-mirror review buckets",
    )
    p.add_argument(
        "--delivery-readiness-report",
        action="store_true",
        help="read-only check of CRM/Kita delivery env, gates, and service-write preflight",
    )
    p.add_argument(
        "--include-groups",
        action="store_true",
        help="for --revive-stub: also revive group-chat docs (default: 1:1 direct chats only)",
    )
    p.add_argument(
        "--stub-pipeline-version",
        default=DEFAULT_STUB_REVIVE_VERSION,
        help=f"bumped pipeline_version for --revive-stub (default {DEFAULT_STUB_REVIVE_VERSION})",
    )
    p.add_argument(
        "--empty-pdf-ocr-version",
        default=DEFAULT_EMPTY_PDF_OCR_VERSION,
        help=f"bumped pipeline_version for --retry-empty-pdf-ocr (default {DEFAULT_EMPTY_PDF_OCR_VERSION})",
    )
    p.add_argument(
        "--unschematised-pipeline-version",
        default=DEFAULT_UNSCHEMATISED_RECOVERY_VERSION,
        help=f"bumped pipeline_version for --retry-unschematised-supported (default {DEFAULT_UNSCHEMATISED_RECOVERY_VERSION})",
    )
    p.add_argument(
        "--typed-missing-fields-version",
        default=DEFAULT_TYPED_MISSING_FIELDS_VERSION,
        help=f"bumped pipeline_version for --retry-typed-missing-fields (default {DEFAULT_TYPED_MISSING_FIELDS_VERSION})",
    )
    p.add_argument(
        "--apply", action="store_true", help="actually write (default: dry-run, counts only)"
    )
    p.add_argument(
        "--pipeline-version",
        default=DEFAULT_PIPELINE_VERSION,
        help=f"bumped pipeline_version for --reprocess (default {DEFAULT_PIPELINE_VERSION})",
    )
    p.add_argument(
        "--autocatalog-pipeline-version",
        default=DEFAULT_AUTOCATALOG_PIPELINE_VERSION,
        help=f"bumped pipeline_version for --autocatalog-direct-unknown-text (default {DEFAULT_AUTOCATALOG_PIPELINE_VERSION})",
    )
    p.add_argument(
        "--autocatalog-min-ocr-chars",
        type=int,
        default=DEFAULT_AUTOCATALOG_TEXT_MIN_CHARS,
        help=f"minimum saved OCR chars for --autocatalog-direct-unknown-text (default {DEFAULT_AUTOCATALOG_TEXT_MIN_CHARS})",
    )
    p.add_argument(
        "--autocatalog-limit",
        type=int,
        default=DEFAULT_AUTOCATALOG_LIMIT,
        help=f"maximum rows touched by one autocatalog run (default {DEFAULT_AUTOCATALOG_LIMIT})",
    )
    p.add_argument(
        "--autocatalog-provider",
        choices=("ollama", "mlx"),
        default=DEFAULT_AUTOCATALOG_PROVIDER,
        help=(
            "local provider for --autocatalog-preclassify-saved-ocr "
            f"(default {DEFAULT_AUTOCATALOG_PROVIDER})"
        ),
    )
    p.add_argument(
        "--autocatalog-ollama-url",
        default=DEFAULT_AUTOCATALOG_OLLAMA_URL,
        help=f"local Ollama URL for --autocatalog-preclassify-saved-ocr (default {DEFAULT_AUTOCATALOG_OLLAMA_URL})",
    )
    p.add_argument(
        "--autocatalog-model",
        default=DEFAULT_AUTOCATALOG_TEXT_MODEL,
        help=f"local text model for --autocatalog-preclassify-saved-ocr (default {DEFAULT_AUTOCATALOG_TEXT_MODEL})",
    )
    p.add_argument(
        "--autocatalog-mlx-base-url",
        default=DEFAULT_AUTOCATALOG_MLX_BASE_URL,
        help=(
            "local MLX OpenAI-compatible base URL for --autocatalog-provider mlx "
            f"(default {DEFAULT_AUTOCATALOG_MLX_BASE_URL})"
        ),
    )
    p.add_argument(
        "--autocatalog-mlx-model",
        default=DEFAULT_AUTOCATALOG_MLX_MODEL,
        help=(
            "local MLX model for --autocatalog-provider mlx "
            f"(default {DEFAULT_AUTOCATALOG_MLX_MODEL})"
        ),
    )
    p.add_argument(
        "--autocatalog-vision-model",
        default=DEFAULT_AUTOCATALOG_VISION_MODEL,
        help=(
            "local Ollama vision model for --autocatalog-preclassify-vision "
            f"(default {DEFAULT_AUTOCATALOG_VISION_MODEL})"
        ),
    )
    p.add_argument(
        "--autocatalog-vision-max-pages",
        type=int,
        default=DEFAULT_AUTOCATALOG_VISION_MAX_PAGES,
        help=(
            "maximum preprocessed pages per doc for --autocatalog-preclassify-vision "
            f"(default {DEFAULT_AUTOCATALOG_VISION_MAX_PAGES})"
        ),
    )
    p.add_argument(
        "--autocatalog-vision-image-max-side",
        type=int,
        default=DEFAULT_AUTOCATALOG_VISION_IMAGE_MAX_SIDE,
        help=(
            "max resized image side for --autocatalog-preclassify-vision "
            f"(default {DEFAULT_AUTOCATALOG_VISION_IMAGE_MAX_SIDE})"
        ),
    )
    p.add_argument(
        "--autocatalog-timeout-seconds",
        type=float,
        default=DEFAULT_AUTOCATALOG_TIMEOUT_SECONDS,
        help=f"per-document timeout for --autocatalog-preclassify-saved-ocr (default {DEFAULT_AUTOCATALOG_TIMEOUT_SECONDS})",
    )
    p.add_argument(
        "--autocatalog-ocr-max-chars",
        type=int,
        default=DEFAULT_AUTOCATALOG_OCR_MAX_CHARS,
        help=f"saved OCR chars sent to local Qwen per doc (default {DEFAULT_AUTOCATALOG_OCR_MAX_CHARS})",
    )
    p.add_argument(
        "--auto-attach-limit",
        type=int,
        default=DEFAULT_AUTO_ATTACH_LIMIT,
        help=f"maximum eligible review proposals processed by one auto-attach run (default {DEFAULT_AUTO_ATTACH_LIMIT})",
    )
    p.add_argument(
        "--new-prospect-pipeline-version",
        default=DEFAULT_NEW_PROSPECT_PIPELINE_VERSION,
        help=(
            "bumped pipeline_version for --promote-direct-new-prospects "
            f"(default {DEFAULT_NEW_PROSPECT_PIPELINE_VERSION})"
        ),
    )
    p.add_argument(
        "--watermark",
        type=int,
        default=None,
        help="backfill ceiling id (default: read the sweeper watermark file)",
    )
    p.add_argument(
        "--media-types", default=None, help="comma list for --backfill (default document,image)"
    )
    return p


async def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("INTAKE_RETRO_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    args = build_parser().parse_args(argv)
    needs_db = (
        args.reprocess
        or args.reroute_drive_folder
        or args.reroute_npwp
        or args.backfill
        or args.scrub_group_phone
        or args.backfill_source_context
        or args.revive_stub
        or args.retry_empty_pdf_ocr
        or args.retry_unschematised_supported
        or args.retry_typed_missing_fields
        or args.quality_sample
        or args.autocatalog_direct_unknown_text
        or args.autocatalog_preclassify_saved_ocr
        or args.autocatalog_preclassify_vision
        or args.auto_attach_eligible
        or args.auto_attach_direct_phone
        or args.promote_direct_new_prospects
        or args.review_backlog_report
    )
    if not (needs_db or args.delivery_readiness_report):
        logger.error(
            "nothing to do: pass --backfill, --reprocess, --reroute-drive-folder, "
            "--reroute-npwp, --scrub-group-phone, "
            "--backfill-source-context, --revive-stub, "
            "--retry-empty-pdf-ocr, --retry-unschematised-supported, "
            "--retry-typed-missing-fields, --quality-sample, and/or "
            "--autocatalog-direct-unknown-text/--autocatalog-preclassify-saved-ocr/"
            "--autocatalog-preclassify-vision/"
            "--auto-attach-eligible/--auto-attach-direct-phone/"
            "--promote-direct-new-prospects/--review-backlog-report/"
            "--delivery-readiness-report"
        )
        return 2

    if args.delivery_readiness_report:
        await run_delivery_readiness_report()
        if not needs_db:
            return 0

    db_url = os.getenv("INTAKE_DATABASE_URL", os.getenv("DATABASE_URL", DEFAULT_DSN))
    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    try:
        # Backfill FIRST (puts historical rows in the queue), then reprocess
        # (resets the weak proposals) — matches the rollout runbook order.
        if args.backfill:
            watermark = args.watermark if args.watermark is not None else read_watermark()
            if watermark is None:
                logger.error("no watermark: %s missing and --watermark not given", WATERMARK_FILE)
                return 2
            await run_backfill(pool, watermark, _media_types(args.media_types), args.apply)
        if args.scrub_group_phone:
            await run_scrub_group_phone(pool, args.apply)
        if args.backfill_source_context:
            await run_backfill_source_context(pool, args.apply)
        if args.reprocess:
            await run_reprocess(pool, args.pipeline_version, args.apply)
        if args.reroute_drive_folder:
            await run_reroute_drive_folder(
                pool,
                args.reroute_pipeline_version or "v2.2-m227-folder",
                max(args.reroute_limit, 1),
                args.apply,
            )
        if args.reroute_npwp:
            await run_reroute_npwp(
                pool,
                args.reroute_pipeline_version or "v2.3-npwp",
                max(args.reroute_limit, 1),
                args.apply,
            )
        if args.autocatalog_direct_unknown_text:
            await run_autocatalog_direct_unknown_text(
                pool,
                args.autocatalog_pipeline_version,
                max(args.autocatalog_min_ocr_chars, 1),
                max(args.autocatalog_limit, 1),
                args.apply,
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
        if args.autocatalog_preclassify_saved_ocr:
            autocatalog_model = (
                args.autocatalog_mlx_model
                if args.autocatalog_provider == "mlx"
                else args.autocatalog_model
            )
            await run_autocatalog_preclassify_saved_ocr(
                pool,
                args.autocatalog_pipeline_version,
                max(args.autocatalog_min_ocr_chars, 1),
                max(args.autocatalog_limit, 1),
                args.apply,
                provider=args.autocatalog_provider,
                ollama_url=args.autocatalog_ollama_url,
                mlx_base_url=args.autocatalog_mlx_base_url,
                model=autocatalog_model,
                timeout_seconds=max(args.autocatalog_timeout_seconds, 1.0),
                ocr_max_chars=max(args.autocatalog_ocr_max_chars, 1),
            )
        if args.autocatalog_preclassify_vision:
            await run_autocatalog_preclassify_vision(
                pool,
                args.autocatalog_pipeline_version,
                max(args.autocatalog_min_ocr_chars, 0),
                max(args.autocatalog_limit, 1),
                args.apply,
                ollama_url=args.autocatalog_ollama_url,
                model=args.autocatalog_vision_model,
                timeout_seconds=max(args.autocatalog_timeout_seconds, 1.0),
                max_pages=max(args.autocatalog_vision_max_pages, 1),
                image_max_side=max(args.autocatalog_vision_image_max_side, 32),
            )
        if args.auto_attach_eligible:
            await run_auto_attach_eligible(pool, max(args.auto_attach_limit, 1), args.apply)
        if args.auto_attach_direct_phone:
            await run_direct_phone_auto_attach(pool, max(args.auto_attach_limit, 1), args.apply)
        if args.promote_direct_new_prospects:
            await run_promote_direct_new_prospects(
                pool,
                args.new_prospect_pipeline_version,
                max(args.auto_attach_limit, 1),
                args.apply,
            )
        if args.review_backlog_report:
            await run_review_backlog_report(pool, max(args.autocatalog_min_ocr_chars, 1))
        if args.revive_stub:
            await run_revive_stub(pool, args.stub_pipeline_version, args.include_groups, args.apply)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
