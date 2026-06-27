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
import asyncio
import hashlib
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
    TEXT_LLM_CLASSIFY_CONF,
    _parse_doc_type_answer,
    _text_llm_classify_prompt,
)
from backend.services.intake.auto_attach import try_auto_attach, try_direct_phone_auto_attach
from backend.services.intake.enqueue import enqueue
from backend.services.intake.writer import DOCUMENT_CATEGORY_MAP
from wa_mirror_intake_sweeper import _source_context as _wa_mirror_source_context
from wa_mirror_intake_sweeper import _upsert_client_by_phone as _upsert_wa_client_by_phone

logger = logging.getLogger("intake_reprocess_backlog")

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_PIPELINE_VERSION = "v2.1-retro"
DEFAULT_AUTOCATALOG_PIPELINE_VERSION = "v2.2-qwen-text-autocatalog"
DEFAULT_STUB_REVIVE_VERSION = "v2.1-stub-revive"
DEFAULT_MEDIA_TYPES = ("document", "image")
DEFAULT_AUTOCATALOG_TEXT_MIN_CHARS = 100
DEFAULT_AUTOCATALOG_LIMIT = 500
DEFAULT_AUTOCATALOG_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_AUTOCATALOG_TEXT_MODEL = "qwen3.5:9b"
DEFAULT_AUTOCATALOG_TIMEOUT_SECONDS = 45.0
DEFAULT_AUTOCATALOG_OCR_MAX_CHARS = 6000
DEFAULT_AUTO_ATTACH_LIMIT = 500
DEFAULT_NEW_PROSPECT_PIPELINE_VERSION = "v2.3-direct-prospect-promote"
DEFAULT_CRM_PUSH_BASE_URL = "https://nuzantara-rag.fly.dev"
DEFAULT_CRM_PUSH_PREFLIGHT_TIMEOUT_SECONDS = 12.0

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


class CrmServiceWritePreflightError(RuntimeError):
    """Raised when a bulk auto-attach apply would not be deliverable to Kita."""


def _env_enabled_default_on(name: str) -> bool:
    return os.environ.get(name, "1").strip().lower() not in {"0", "false", "no", "off"}


def _crm_push_base_url() -> str:
    return os.environ.get("INTAKE_CRM_PUSH_BASE_URL", "").strip() or DEFAULT_CRM_PUSH_BASE_URL


def _crm_push_write_key_from_env() -> str | None:
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


def _build_saved_ocr_preclassify_payload(
    stage_output: Any,
    *,
    doc_type: str,
    model: str,
    ocr_max_chars: int = DEFAULT_AUTOCATALOG_OCR_MAX_CHARS,
) -> dict[str, Any]:
    """Build a classify-stage payload from preserved OCR and a local Qwen type."""
    pages = _saved_ocr_pages(stage_output)
    return {
        "doc_type": doc_type,
        "type_confidence": TEXT_LLM_CLASSIFY_CONF,
        "ocr_text_per_page": pages,
        "n_pages": len(pages),
        "source_page": None,
        "model": model,
        "type_scores": {doc_type: TEXT_LLM_CLASSIFY_CONF},
        "classified_via": "saved_ocr_local_text_llm_preclassify",
        "classify_llm_model": model,
        "ocr_max_chars": max(ocr_max_chars, 1),
        "_metric": {"model": model, "confidence": TEXT_LLM_CLASSIFY_CONF},
    }


def _build_saved_ocr_preclassify_attempt_payload(
    *,
    model: str,
    pipeline_version: str,
    outcome: str,
    ocr_max_chars: int,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Build a PII-free marker so failed local attempts do not block batches."""
    payload: dict[str, Any] = {
        "model": model,
        "pipeline_version": pipeline_version,
        "outcome": outcome,
        "classified_via": "saved_ocr_local_text_llm_preclassify",
        "ocr_max_chars": max(ocr_max_chars, 1),
    }
    if error_type:
        payload["error_type"] = error_type
    return payload


async def _classify_saved_ocr_text(
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


async def _mark_saved_ocr_preclassify_attempt(
    pool: asyncpg.Pool,
    *,
    queue_id: int,
    model: str,
    pipeline_version: str,
    outcome: str,
    ocr_max_chars: int,
    error_type: str | None = None,
) -> int:
    """Persist a PII-free local-LLM attempt marker for a queue row."""
    payload = _build_saved_ocr_preclassify_attempt_payload(
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
    ollama_url: str,
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

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SAVED_OCR_PRECLASSIFY_SELECT_SQL,
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
        "errors": 0,
        "marked_attempts": 0,
        "updated": 0,
        "superseded": 0,
        "min_ocr_chars": safe_min_ocr_chars,
        "limit": safe_limit,
    }
    if not apply:
        logger.info(
            "[autocatalog-preclassify-saved-ocr][DRY-RUN] would local-classify "
            "%d direct review_pending unknown docs with saved OCR and resume "
            "known answers at status=ocr_done pipeline_version=%s (pass --apply)",
            counts["candidates"],
            pipeline_version,
        )
        return counts

    by_doc_type: Counter[str] = Counter()
    by_error: Counter[str] = Counter()
    async with httpx.AsyncClient() as client:
        for row in rows:
            pages = _saved_ocr_pages(row["stage_output"])
            ocr_text = _ocr_text_from_pages(pages, max_chars=safe_ocr_max_chars)
            counts["attempted"] += 1
            try:
                answer = await _classify_saved_ocr_text(
                    client,
                    ollama_url=ollama_url,
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
        "known=%d unknown=%d malformed=%d errors=%d marked_attempts=%d updated=%d superseded=%d "
        "by_doc_type=%s by_error=%s pipeline_version=%s",
        counts["candidates"],
        counts["attempted"],
        counts["known_answers"],
        counts["unknown_answers"],
        counts["malformed_answers"],
        counts["errors"],
        counts["marked_attempts"],
        counts["updated"],
        counts["superseded"],
        dict(by_doc_type),
        dict(by_error),
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
    if not (
        args.reprocess
        or args.backfill
        or args.scrub_group_phone
        or args.backfill_source_context
        or args.revive_stub
        or args.autocatalog_direct_unknown_text
        or args.autocatalog_preclassify_saved_ocr
        or args.auto_attach_eligible
        or args.auto_attach_direct_phone
        or args.promote_direct_new_prospects
        or args.review_backlog_report
    ):
        logger.error(
            "nothing to do: pass --backfill, --reprocess, --scrub-group-phone, "
            "--backfill-source-context, --revive-stub, and/or "
            "--autocatalog-direct-unknown-text/--autocatalog-preclassify-saved-ocr/"
            "--auto-attach-eligible/--auto-attach-direct-phone/"
            "--promote-direct-new-prospects/--review-backlog-report"
        )
        return 2

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
        if args.autocatalog_direct_unknown_text:
            await run_autocatalog_direct_unknown_text(
                pool,
                args.autocatalog_pipeline_version,
                max(args.autocatalog_min_ocr_chars, 1),
                max(args.autocatalog_limit, 1),
                args.apply,
            )
        if args.autocatalog_preclassify_saved_ocr:
            await run_autocatalog_preclassify_saved_ocr(
                pool,
                args.autocatalog_pipeline_version,
                max(args.autocatalog_min_ocr_chars, 1),
                max(args.autocatalog_limit, 1),
                args.apply,
                ollama_url=args.autocatalog_ollama_url,
                model=args.autocatalog_model,
                timeout_seconds=max(args.autocatalog_timeout_seconds, 1.0),
                ocr_max_chars=max(args.autocatalog_ocr_max_chars, 1),
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
