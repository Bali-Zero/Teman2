#!/usr/bin/env python3
"""Read-only WA Mirror direct-document parser audit.

This is the batch/ops counterpart of the WA dashboard Intake tab. It answers:

- which direct-chat documents already have a usable document type;
- which docs still need a parser / review / routing proposal;
- which Kita workspace bucket each known document type would land in;
- whether a local Ollama/Qwen text-only classifier can improve a small sample.

Law 2 / UU-PDP: the report is aggregate-only. The SQL deliberately avoids raw
phones, group subjects, filenames, and OCR text in printed output. Optional
Qwen sampling sends saved OCR text only to local Ollama on the Pro and returns
counts only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

DEFAULT_DB_URL = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_QWEN_MODEL = "qwen3.5:9b"
DEFAULT_QWEN_OCR_MAX_CHARS = 2000
DEFAULT_QWEN_MIN_CANDIDATE_RATE = 0.25
DEFAULT_QWEN_MIN_CLASSIFIED_ATTEMPTS = 5
DEFAULT_QWEN_MIN_WORKSPACE_ACCURACY = 0.70
HIGH_CONFIDENCE_THRESHOLD = 0.70
TEXT_PARSER_MIN_CHARS = 100
AUTOCATALOG_DRY_RUN_COMMAND = (
    "cd ~/Desktop/nuzantara && source apps/backend-rag/.venv/bin/activate && "
    "python scripts/intake_reprocess_backlog.py --autocatalog-preclassify-saved-ocr"
)
AUTOCATALOG_APPLY_COMMAND = f"{AUTOCATALOG_DRY_RUN_COMMAND} --apply"

DOC_TYPES: tuple[str, ...] = (
    "passport",
    "kitas",
    "itas",
    "itap",
    "itk",
    "visa",
    "birth_certificate",
    "medical_insurance",
    "travel_ticket",
    "nib",
    "akta_pendirian",
    "oss",
    "sk_kemenkumham",
    "profil_perseroan",
    "skt",
    "npwp",
    "bank_statement",
    "payment_receipt",
    "ktp",
    "unknown",
)

WORKSPACE_DOC_TYPES: dict[str, tuple[str, ...]] = {
    "immigration": (
        "passport",
        "kitas",
        "itas",
        "itap",
        "itk",
        "visa",
        "birth_certificate",
        "medical_insurance",
        "travel_ticket",
    ),
    "company": (
        "nib",
        "akta_pendirian",
        "oss",
        "sk_kemenkumham",
        "profil_perseroan",
        "skt",
    ),
    "tax": ("npwp",),
    "finance": ("bank_statement", "payment_receipt"),
    "identity": ("ktp",),
}

DIRECT_DOC_ROWS_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (queue_id)
           queue_id,
           status AS proposal_status,
           entity_resolution->>'decision' AS entity_decision
      FROM document_routing_proposal
     ORDER BY queue_id, created_at DESC, id DESC
),
direct_docs AS (
    SELECT
      q.id,
      q.status AS queue_status,
      COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') AS doc_type,
      CASE
        WHEN COALESCE(q.stage_output->'classify'->>'type_confidence', '') ~ '^[0-9]+(\\.[0-9]+)?$'
        THEN (q.stage_output->'classify'->>'type_confidence')::numeric
        ELSE 0
      END AS type_confidence,
      COALESCE((q.stage_output ? 'extract') AND NOT COALESCE((q.stage_output->'extract'->>'stub')::boolean, false), false) AS extracted_non_stub,
      COALESCE((q.stage_output ? 'route') AND NOT COALESCE((q.stage_output->'route'->>'stub')::boolean, false), false) AS routed_non_stub,
      COALESCE((
        SELECT SUM(length(
          CASE
            WHEN jsonb_typeof(page.value) = 'object' THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
            WHEN jsonb_typeof(page.value) = 'string' THEN trim(both '"' from page.value::text)
            ELSE ''
          END
        ))
        FROM jsonb_array_elements(
          CASE
            WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
            THEN q.stage_output->'classify'->'ocr_text_per_page'
            ELSE '[]'::jsonb
          END
        ) AS page(value)
      ), 0) AS ocr_chars,
      COALESCE(l.proposal_status, 'NO_PROPOSAL') AS proposal_status,
      COALESCE(l.entity_decision, 'NO_PROPOSAL') AS entity_decision,
      w.media_type
    FROM intake_queue q
    JOIN whatsapp_message_context w
      ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
    LEFT JOIN latest l ON l.queue_id = q.id
    WHERE q.source = 'whatsapp'
      AND q.source_ref LIKE 'wa-mirror:%'
      AND NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
)
SELECT *
  FROM direct_docs
 ORDER BY id DESC
"""

DIRECT_DOC_QWEN_SAMPLE_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (queue_id)
           queue_id,
           status AS proposal_status,
           entity_resolution->>'decision' AS entity_decision
      FROM document_routing_proposal
     ORDER BY queue_id, created_at DESC, id DESC
),
direct_docs AS (
    SELECT
      q.id,
      q.status AS queue_status,
      COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') AS doc_type,
      CASE
        WHEN COALESCE(q.stage_output->'classify'->>'type_confidence', '') ~ '^[0-9]+(\\.[0-9]+)?$'
        THEN (q.stage_output->'classify'->>'type_confidence')::numeric
        ELSE 0
      END AS type_confidence,
      COALESCE((q.stage_output ? 'extract') AND NOT COALESCE((q.stage_output->'extract'->>'stub')::boolean, false), false) AS extracted_non_stub,
      COALESCE((q.stage_output ? 'route') AND NOT COALESCE((q.stage_output->'route'->>'stub')::boolean, false), false) AS routed_non_stub,
      COALESCE((
        SELECT SUM(length(
          CASE
            WHEN jsonb_typeof(page.value) = 'object' THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
            WHEN jsonb_typeof(page.value) = 'string' THEN trim(both '"' from page.value::text)
            ELSE ''
          END
        ))
        FROM jsonb_array_elements(
          CASE
            WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
            THEN q.stage_output->'classify'->'ocr_text_per_page'
            ELSE '[]'::jsonb
          END
        ) AS page(value)
      ), 0) AS ocr_chars,
      COALESCE(l.proposal_status, 'NO_PROPOSAL') AS proposal_status,
      COALESCE(l.entity_decision, 'NO_PROPOSAL') AS entity_decision,
      w.media_type,
      q.stage_output
    FROM intake_queue q
    JOIN whatsapp_message_context w
      ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
    LEFT JOIN latest l ON l.queue_id = q.id
    WHERE q.source = 'whatsapp'
      AND q.source_ref LIKE 'wa-mirror:%'
      AND NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
)
SELECT *
  FROM direct_docs
 WHERE doc_type = 'unknown'
   AND ocr_chars >= $2
 ORDER BY id DESC
 LIMIT $1
"""

DIRECT_DOC_QWEN_KNOWN_BENCHMARK_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (queue_id)
           queue_id,
           status AS proposal_status,
           entity_resolution->>'decision' AS entity_decision
      FROM document_routing_proposal
     ORDER BY queue_id, created_at DESC, id DESC
),
direct_docs AS (
    SELECT
      q.id,
      q.status AS queue_status,
      COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') AS doc_type,
      CASE
        WHEN COALESCE(q.stage_output->'classify'->>'type_confidence', '') ~ '^[0-9]+(\\.[0-9]+)?$'
        THEN (q.stage_output->'classify'->>'type_confidence')::numeric
        ELSE 0
      END AS type_confidence,
      COALESCE((q.stage_output ? 'extract') AND NOT COALESCE((q.stage_output->'extract'->>'stub')::boolean, false), false) AS extracted_non_stub,
      COALESCE((q.stage_output ? 'route') AND NOT COALESCE((q.stage_output->'route'->>'stub')::boolean, false), false) AS routed_non_stub,
      COALESCE((
        SELECT SUM(length(
          CASE
            WHEN jsonb_typeof(page.value) = 'object' THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
            WHEN jsonb_typeof(page.value) = 'string' THEN trim(both '"' from page.value::text)
            ELSE ''
          END
        ))
        FROM jsonb_array_elements(
          CASE
            WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
            THEN q.stage_output->'classify'->'ocr_text_per_page'
            ELSE '[]'::jsonb
          END
        ) AS page(value)
      ), 0) AS ocr_chars,
      COALESCE(l.proposal_status, 'NO_PROPOSAL') AS proposal_status,
      COALESCE(l.entity_decision, 'NO_PROPOSAL') AS entity_decision,
      w.media_type,
      q.stage_output
    FROM intake_queue q
    JOIN whatsapp_message_context w
      ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
    LEFT JOIN latest l ON l.queue_id = q.id
    WHERE q.source = 'whatsapp'
      AND q.source_ref LIKE 'wa-mirror:%'
      AND NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
)
SELECT *
  FROM direct_docs
 WHERE doc_type <> 'unknown'
   AND ocr_chars >= $2
   AND type_confidence >= $3
 ORDER BY id DESC
 LIMIT $1
"""

_ANSWER_RE = re.compile(r"[a-z_]+")


def _record_get(row: Mapping[str, Any] | Any, key: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _records(rows: Iterable[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def workspace_bucket_for_doc_type(doc_type: str | None) -> str:
    """Map a document type to the same workspace bucket used by the dashboard."""
    key = str(doc_type or "unknown").lower()
    for bucket, values in WORKSPACE_DOC_TYPES.items():
        if key in values:
            return bucket
    return "review"


def parser_bucket_for_row(row: Mapping[str, Any] | Any) -> str:
    """Return the next-action bucket for one direct document row."""
    doc_type = str(_record_get(row, "doc_type", "unknown") or "unknown")
    proposal_status = str(_record_get(row, "proposal_status", "NO_PROPOSAL") or "NO_PROPOSAL")
    entity_decision = str(_record_get(row, "entity_decision", "NO_PROPOSAL") or "NO_PROPOSAL")
    confidence = _to_float(_record_get(row, "type_confidence", 0))
    routed_non_stub = _to_bool(_record_get(row, "routed_non_stub", False))

    if _record_get(row, "queue_status") == "dead":
        return "failed_pipeline"
    if doc_type == "unknown":
        return "needs_doc_type_parser"
    if confidence < HIGH_CONFIDENCE_THRESHOLD:
        return "low_confidence_review"
    if proposal_status == "routed":
        return "already_routed"
    if entity_decision in {"AUTO_ATTACH", "LINK_CANDIDATE"} or routed_non_stub:
        return "workspace_review_ready"
    return "needs_routing_proposal"


def action_bucket_for_row(row: Mapping[str, Any] | Any) -> str:
    """Return the operational next action, splitting unknown docs by OCR readiness."""
    if _record_get(row, "queue_status") == "dead":
        return "failed_pipeline"

    doc_type = str(_record_get(row, "doc_type", "unknown") or "unknown")
    if doc_type != "unknown":
        return parser_bucket_for_row(row)

    ocr_chars = int(_to_float(_record_get(row, "ocr_chars", 0)))
    if ocr_chars <= 0:
        return "needs_ocr_vision_batch"
    if ocr_chars < TEXT_PARSER_MIN_CHARS:
        return "needs_manual_review_short_ocr"
    return "needs_text_parser_qwen_candidate"


def parse_qwen_doc_type_answer(raw: str | None) -> str | None:
    """Accept only a single known document type token from local Qwen."""
    if not raw:
        return None
    cleaned = raw.strip().strip(".,:;!\"'`").lower()
    if not _ANSWER_RE.fullmatch(cleaned):
        return None
    return cleaned if cleaned in DOC_TYPES else None


def _count_rows(counter: Counter[str], *, key_name: str) -> list[dict[str, int | str]]:
    positions = {key: idx for idx, key in enumerate(counter.keys())}
    return [
        {key_name: key, "docs": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], positions[item[0]]))
    ]


def _placement_preview_rows(counter: Counter[tuple[str, str, str]]) -> list[dict[str, int | str]]:
    positions = {key: idx for idx, key in enumerate(counter.keys())}
    return [
        {
            "from_doc_type": old_type,
            "proposed_doc_type": new_type,
            "workspace_bucket": workspace,
            "docs": count,
        }
        for (old_type, new_type, workspace), count in sorted(
            counter.items(), key=lambda item: (-item[1], positions[item[0]])
        )
    ]


def _confusion_preview_rows(
    counter: Counter[tuple[str, str, str, str]],
) -> list[dict[str, int | str]]:
    positions = {key: idx for idx, key in enumerate(counter.keys())}
    return [
        {
            "expected_doc_type": expected_type,
            "predicted_doc_type": predicted_type,
            "expected_workspace_bucket": expected_workspace,
            "predicted_workspace_bucket": predicted_workspace,
            "docs": count,
        }
        for (
            expected_type,
            predicted_type,
            expected_workspace,
            predicted_workspace,
        ), count in sorted(counter.items(), key=lambda item: (-item[1], positions[item[0]]))
    ]


def _qwen_acceptance_gate(
    *,
    classified_attempts: int,
    kita_workspace_candidates: int,
    min_candidate_rate: float,
    min_classified_attempts: int,
) -> dict[str, int | float | str]:
    safe_min_candidate_rate = min(max(min_candidate_rate, 0.0), 1.0)
    safe_min_classified_attempts = max(min_classified_attempts, 1)
    candidate_rate = (
        round(kita_workspace_candidates / classified_attempts, 4)
        if classified_attempts > 0
        else 0.0
    )
    if classified_attempts < safe_min_classified_attempts:
        status = "insufficient_sample"
        reason = "not_enough_classified_attempts"
    elif candidate_rate >= safe_min_candidate_rate:
        status = "candidate_batch_ready"
        reason = "candidate_rate_met"
    else:
        status = "review_only"
        reason = "candidate_rate_below_threshold"
    return {
        "status": status,
        "reason": reason,
        "candidate_rate": candidate_rate,
        "min_candidate_rate": safe_min_candidate_rate,
        "classified_attempts": classified_attempts,
        "min_classified_attempts": safe_min_classified_attempts,
    }


def _qwen_benchmark_gate(
    *,
    classified_attempts: int,
    workspace_matches: int,
    min_workspace_accuracy: float,
    min_classified_attempts: int,
) -> dict[str, int | float | str]:
    safe_min_workspace_accuracy = min(max(min_workspace_accuracy, 0.0), 1.0)
    safe_min_classified_attempts = max(min_classified_attempts, 1)
    workspace_accuracy = (
        round(workspace_matches / classified_attempts, 4) if classified_attempts > 0 else 0.0
    )
    if classified_attempts < safe_min_classified_attempts:
        status = "insufficient_sample"
        reason = "not_enough_classified_attempts"
    elif workspace_accuracy >= safe_min_workspace_accuracy:
        status = "workspace_benchmark_ready"
        reason = "workspace_accuracy_met"
    else:
        status = "workspace_benchmark_review"
        reason = "workspace_accuracy_below_threshold"
    return {
        "status": status,
        "reason": reason,
        "workspace_accuracy": workspace_accuracy,
        "min_workspace_accuracy": safe_min_workspace_accuracy,
        "classified_attempts": classified_attempts,
        "min_classified_attempts": safe_min_classified_attempts,
    }


def _bucket_docs(rows: Iterable[Mapping[str, Any]], bucket: str) -> int:
    return sum(int(_to_float(row.get("docs", 0))) for row in rows if row.get("bucket") == bucket)


def _project_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    total_docs: int,
    denominator: int,
    key_fields: tuple[str, ...],
) -> list[dict[str, int | str]]:
    if total_docs <= 0 or denominator <= 0:
        return []
    projected: list[dict[str, int | str]] = []
    for row in rows:
        sample_docs = int(_to_float(row.get("docs", 0)))
        if sample_docs <= 0:
            continue
        item: dict[str, int | str] = {field: str(row.get(field, "")) for field in key_fields}
        item["sample_docs"] = sample_docs
        item["projected_docs"] = round(total_docs * sample_docs / denominator)
        projected.append(item)
    return projected


def build_autocatalog_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build an aggregate-only plan for moving unknown direct docs toward Kita buckets."""
    direct_actions = list(report.get("direct_actions") or [])
    qwen_sample = report.get("qwen_text_sample") or {}
    qwen_gate = qwen_sample.get("acceptance_gate") or {}
    qwen_known = report.get("qwen_known_benchmark") or {}
    benchmark_gate = qwen_known.get("benchmark_gate") or {}

    qwen_text_docs = _bucket_docs(direct_actions, "needs_text_parser_qwen_candidate")
    vision_docs = _bucket_docs(direct_actions, "needs_ocr_vision_batch")
    short_ocr_docs = _bucket_docs(direct_actions, "needs_manual_review_short_ocr")
    low_confidence_docs = _bucket_docs(direct_actions, "low_confidence_review")
    routing_docs = _bucket_docs(direct_actions, "needs_routing_proposal")
    workspace_review_docs = _bucket_docs(direct_actions, "workspace_review_ready")
    already_routed_docs = _bucket_docs(direct_actions, "already_routed")
    failed_docs = _bucket_docs(direct_actions, "failed_pipeline")

    qwen_status = str(qwen_gate.get("status") or "probe_required")
    benchmark_status = str(benchmark_gate.get("status") or "benchmark_required")
    if qwen_text_docs <= 0:
        status = "no_text_candidates"
        reason = "no_unknown_direct_docs_with_enough_saved_ocr"
    elif qwen_status == "candidate_batch_ready" and benchmark_status == "workspace_benchmark_ready":
        status = "ready_for_staged_autocatalog"
        reason = "qwen_text_gate_and_known_doc_benchmark_passed"
    elif qwen_status == "probe_required":
        status = "needs_qwen_text_probe"
        reason = "qwen_text_probe_missing"
    elif benchmark_status == "benchmark_required":
        status = "needs_known_doc_benchmark"
        reason = "known_doc_benchmark_missing"
    elif qwen_status in {"insufficient_sample", "review_only"}:
        status = "text_batch_review_only"
        reason = str(qwen_gate.get("reason") or "qwen_text_gate_not_ready")
    elif benchmark_status != "workspace_benchmark_ready":
        status = "benchmark_review"
        reason = str(benchmark_gate.get("reason") or "qwen_known_doc_benchmark_not_ready")
    else:
        status = "needs_more_sampling"
        reason = "qwen_gates_inconclusive"

    denominator = int(
        _to_float(qwen_gate.get("classified_attempts", qwen_sample.get("classified_attempts", 0)))
    )
    candidate_rate = _to_float(qwen_gate.get("candidate_rate", 0))
    projected_kita_docs = round(qwen_text_docs * candidate_rate) if denominator > 0 else 0
    projected_review_docs = (
        max(qwen_text_docs - projected_kita_docs, 0) if denominator > 0 else qwen_text_docs
    )

    return {
        "status": status,
        "reason": reason,
        "scope": "direct_whatsapp_docs_only_groups_excluded",
        "write_mode": "proposal_only_no_crm_mutation",
        "worker_required_env": {
            "INTAKE_TEXT_LLM_CLASSIFY_ENABLED": "1",
            "INTAKE_TEXT_LLM_MODEL": DEFAULT_QWEN_MODEL,
            "INTAKE_TEXT_LLM_MIN_CHARS": str(TEXT_PARSER_MIN_CHARS),
            "INTAKE_TEXT_LLM_TIMEOUT_SECONDS": "45",
        },
        "dry_run_command": AUTOCATALOG_DRY_RUN_COMMAND,
        "apply_command": AUTOCATALOG_APPLY_COMMAND,
        "safe_to_apply_without_existing_gate": False,
        "can_create_kita_proposals": status == "ready_for_staged_autocatalog",
        "can_auto_attach_without_review": False,
        "qwen_text_gate_status": qwen_status,
        "known_doc_benchmark_status": benchmark_status,
        "totals": {
            "qwen_text_candidate_docs": qwen_text_docs,
            "ocr_vision_candidate_docs": vision_docs,
            "short_ocr_review_docs": short_ocr_docs,
            "low_confidence_review_docs": low_confidence_docs,
            "routing_proposal_needed_docs": routing_docs,
            "workspace_review_ready_docs": workspace_review_docs,
            "already_routed_docs": already_routed_docs,
            "failed_pipeline_docs": failed_docs,
            "projected_qwen_text_to_kita_docs": projected_kita_docs,
            "projected_qwen_text_to_review_docs": projected_review_docs,
        },
        "projected_qwen_workspace_buckets": _project_rows(
            qwen_sample.get("workspace_buckets") or [],
            total_docs=qwen_text_docs,
            denominator=denominator,
            key_fields=("bucket",),
        ),
        "projected_qwen_placements": _project_rows(
            qwen_sample.get("placement_preview") or [],
            total_docs=qwen_text_docs,
            denominator=denominator,
            key_fields=("from_doc_type", "proposed_doc_type", "workspace_bucket"),
        ),
        "stages": [
            {
                "stage": "qwen_text_autocatalog",
                "docs": qwen_text_docs,
                "source_bucket": "needs_text_parser_qwen_candidate",
                "llm": DEFAULT_QWEN_MODEL,
                "destination": "document_routing_proposal_then_kita_workspace_by_doc_type",
                "allowed_when": "candidate_batch_ready_and_workspace_benchmark_ready",
                "expected_kita_docs": projected_kita_docs,
                "expected_review_docs": projected_review_docs,
                "auto_attach_allowed": False,
            },
            {
                "stage": "vision_ocr_autocatalog",
                "docs": vision_docs,
                "source_bucket": "needs_ocr_vision_batch",
                "llm": "qwen2.5vl_local_ocr_then_qwen_text_router",
                "destination": "same_proposal_path_after_ocr",
                "allowed_when": "local_vision_ocr_available_on_pro",
                "expected_kita_docs": 0,
                "expected_review_docs": vision_docs,
                "auto_attach_allowed": False,
            },
            {
                "stage": "short_ocr_resolution",
                "docs": short_ocr_docs,
                "source_bucket": "needs_manual_review_short_ocr",
                "llm": "vision_retry_or_manual_review",
                "destination": "review_or_same_proposal_path_after_better_ocr",
                "allowed_when": "ocr_text_below_threshold",
                "expected_kita_docs": 0,
                "expected_review_docs": short_ocr_docs,
                "auto_attach_allowed": False,
            },
            {
                "stage": "known_doc_routing",
                "docs": routing_docs,
                "source_bucket": "needs_routing_proposal",
                "llm": "none",
                "destination": "document_routing_proposal_review_pending",
                "allowed_when": "known_doc_type_high_confidence",
                "expected_kita_docs": routing_docs,
                "expected_review_docs": 0,
                "auto_attach_allowed": False,
            },
            {
                "stage": "workspace_operator_review",
                "docs": workspace_review_docs + low_confidence_docs,
                "source_bucket": "workspace_review_ready_or_low_confidence_review",
                "llm": "none",
                "destination": "kita_review_queue",
                "allowed_when": "operator_or_existing_auto_attach_gate",
                "expected_kita_docs": workspace_review_docs,
                "expected_review_docs": low_confidence_docs,
                "auto_attach_allowed": False,
            },
        ],
    }


def summarize_direct_rows(
    rows: Iterable[Mapping[str, Any] | Any], *, top_doc_types: int = 30
) -> dict[str, Any]:
    """Aggregate direct-document parser and workspace placement state."""
    parser_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    workspace_counts: Counter[str] = Counter()
    doc_type_counts: dict[tuple[str, str], dict[str, Any]] = {}
    doc_type_positions: dict[tuple[str, str], int] = {}
    matrix: dict[tuple[str, str], int] = {}
    unknown_ocr_quality = {
        "unknown_docs": 0,
        "ocr_empty": 0,
        "ocr_1_99": 0,
        "ocr_100_499": 0,
        "ocr_500_plus": 0,
    }

    totals = {
        "direct_docs": 0,
        "known_doc_type": 0,
        "unknown_doc_type": 0,
        "high_confidence": 0,
        "low_confidence_known": 0,
    }

    for row in rows:
        totals["direct_docs"] += 1
        doc_type = str(_record_get(row, "doc_type", "unknown") or "unknown").lower()
        confidence = _to_float(_record_get(row, "type_confidence", 0))
        workspace = workspace_bucket_for_doc_type(doc_type)
        parser_bucket = parser_bucket_for_row(row)
        action_bucket = action_bucket_for_row(row)

        if doc_type == "unknown":
            totals["unknown_doc_type"] += 1
            unknown_ocr_quality["unknown_docs"] += 1
            ocr_chars = int(_to_float(_record_get(row, "ocr_chars", 0)))
            if ocr_chars <= 0:
                unknown_ocr_quality["ocr_empty"] += 1
            elif ocr_chars <= 99:
                unknown_ocr_quality["ocr_1_99"] += 1
            elif ocr_chars <= 499:
                unknown_ocr_quality["ocr_100_499"] += 1
            else:
                unknown_ocr_quality["ocr_500_plus"] += 1
        else:
            totals["known_doc_type"] += 1
            if confidence >= HIGH_CONFIDENCE_THRESHOLD:
                totals["high_confidence"] += 1
            else:
                totals["low_confidence_known"] += 1

        parser_counts[parser_bucket] += 1
        action_counts[action_bucket] += 1
        workspace_counts[workspace] += 1
        matrix[(workspace, parser_bucket)] = matrix.get((workspace, parser_bucket), 0) + 1

        doc_key = (doc_type, workspace)
        if doc_key not in doc_type_positions:
            doc_type_positions[doc_key] = len(doc_type_positions)
        existing = doc_type_counts.setdefault(
            doc_key,
            {
                "doc_type": doc_type,
                "workspace_bucket": workspace,
                "docs": 0,
                "high_confidence": 0,
                "extracted_non_stub": 0,
                "routed_non_stub": 0,
            },
        )
        existing["docs"] += 1
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            existing["high_confidence"] += 1
        if _to_bool(_record_get(row, "extracted_non_stub", False)):
            existing["extracted_non_stub"] += 1
        if _to_bool(_record_get(row, "routed_non_stub", False)):
            existing["routed_non_stub"] += 1

    return {
        "totals": totals,
        "unknown_ocr_quality": unknown_ocr_quality,
        "direct_actions": _count_rows(action_counts, key_name="bucket"),
        "direct_parser": _count_rows(parser_counts, key_name="bucket"),
        "workspace_buckets": _count_rows(workspace_counts, key_name="bucket"),
        "placement_matrix": [
            {"workspace_bucket": workspace, "parser_bucket": parser_bucket, "docs": docs}
            for (workspace, parser_bucket), docs in sorted(
                matrix.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
            )
        ],
        "direct_doc_types": sorted(
            doc_type_counts.values(),
            key=lambda row: (
                -int(row["docs"]),
                doc_type_positions[(str(row["doc_type"]), str(row["workspace_bucket"]))],
            ),
        )[:top_doc_types],
    }


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


def _saved_ocr_text(stage_output: Any, *, max_chars: int = 6000) -> str:
    stage = _stage_output_dict(stage_output)
    classify = _stage_output_dict(stage.get("classify"))
    raw_pages = classify.get("ocr_text_per_page") or []
    if isinstance(raw_pages, str):
        text = raw_pages
    elif isinstance(raw_pages, list):
        chunks: list[str] = []
        for item in raw_pages:
            if isinstance(item, dict):
                chunks.append(str(item.get("text") or item.get("ocr_text") or ""))
            elif isinstance(item, str):
                chunks.append(item)
        text = "\n".join(chunks)
    else:
        text = ""
    return text[:max_chars]


def _qwen_prompt(ocr_text: str) -> str:
    types = ", ".join(DOC_TYPES)
    return (
        "Classify this Indonesian administrative document OCR text. "
        "Answer with EXACTLY ONE token from this list: "
        f"{types}. If uncertain, answer unknown.\n\nOCR:\n{ocr_text}"
    )


async def _qwen_classify_text(
    client: httpx.AsyncClient,
    *,
    ollama_url: str,
    model: str,
    ocr_text: str,
    timeout_seconds: float,
) -> str | None:
    if not ocr_text.strip():
        return None
    payload = {
        "model": model,
        "prompt": _qwen_prompt(ocr_text),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 24},
    }
    response = await client.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    return parse_qwen_doc_type_answer(data.get("response") or data.get("thinking"))


async def run_qwen_text_sample(
    rows: Iterable[Mapping[str, Any] | Any],
    *,
    ollama_url: str,
    model: str,
    timeout_seconds: float,
    ocr_max_chars: int = DEFAULT_QWEN_OCR_MAX_CHARS,
    min_candidate_rate: float = DEFAULT_QWEN_MIN_CANDIDATE_RATE,
    min_classified_attempts: int = DEFAULT_QWEN_MIN_CLASSIFIED_ATTEMPTS,
) -> dict[str, Any]:
    """Run local Qwen over saved OCR text and return aggregate transitions only."""
    transitions: Counter[str] = Counter()
    workspaces: Counter[str] = Counter()
    placements: Counter[tuple[str, str, str]] = Counter()
    errors: Counter[str] = Counter()
    attempted = 0
    failed_attempts = 0
    improved_unknown_to_known = 0
    still_unknown = 0
    kita_workspace_candidates = 0
    review_after_qwen = 0
    safe_ocr_max_chars = max(ocr_max_chars, 1)

    async with httpx.AsyncClient() as client:
        for row in rows:
            attempted += 1
            old_type = str(_record_get(row, "doc_type", "unknown") or "unknown").lower()
            try:
                answer = await _qwen_classify_text(
                    client,
                    ollama_url=ollama_url,
                    model=model,
                    ocr_text=_saved_ocr_text(
                        _record_get(row, "stage_output"), max_chars=safe_ocr_max_chars
                    ),
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:  # local diagnostic only; aggregate class name.
                failed_attempts += 1
                errors[type(exc).__name__] += 1
                transitions[f"{old_type}->error"] += 1
                continue

            new_type = answer or "unknown"
            workspace = workspace_bucket_for_doc_type(new_type)
            transitions[f"{old_type}->{new_type}"] += 1
            workspaces[workspace] += 1
            placements[(old_type, new_type, workspace)] += 1
            if old_type == "unknown" and new_type != "unknown":
                improved_unknown_to_known += 1
            if new_type == "unknown":
                still_unknown += 1
            if workspace == "review":
                review_after_qwen += 1
            else:
                kita_workspace_candidates += 1

    classified_attempts = attempted - failed_attempts
    return {
        "mode": "local_ollama_text_only_saved_ocr",
        "model": model,
        "ocr_max_chars": safe_ocr_max_chars,
        "attempted": attempted,
        "classified_attempts": classified_attempts,
        "failed_attempts": failed_attempts,
        "not_classified_due_error": failed_attempts,
        "improved_unknown_to_known": improved_unknown_to_known,
        "still_unknown": still_unknown,
        "kita_workspace_candidates": kita_workspace_candidates,
        "review_after_qwen": review_after_qwen,
        "acceptance_gate": _qwen_acceptance_gate(
            classified_attempts=classified_attempts,
            kita_workspace_candidates=kita_workspace_candidates,
            min_candidate_rate=min_candidate_rate,
            min_classified_attempts=min_classified_attempts,
        ),
        "transitions": dict(transitions),
        "placement_preview": _placement_preview_rows(placements),
        "workspace_buckets": _count_rows(workspaces, key_name="bucket"),
        "errors": dict(errors),
    }


async def run_qwen_known_doc_benchmark(
    rows: Iterable[Mapping[str, Any] | Any],
    *,
    ollama_url: str,
    model: str,
    timeout_seconds: float,
    ocr_max_chars: int = DEFAULT_QWEN_OCR_MAX_CHARS,
    min_workspace_accuracy: float = DEFAULT_QWEN_MIN_WORKSPACE_ACCURACY,
    min_classified_attempts: int = DEFAULT_QWEN_MIN_CLASSIFIED_ATTEMPTS,
) -> dict[str, Any]:
    """Benchmark local Qwen against known direct docs without exposing raw OCR."""
    expected_workspaces: Counter[str] = Counter()
    predicted_workspaces: Counter[str] = Counter()
    confusion: Counter[tuple[str, str, str, str]] = Counter()
    errors: Counter[str] = Counter()
    attempted = 0
    failed_attempts = 0
    exact_doc_type_matches = 0
    workspace_matches = 0
    unknown_predictions = 0
    safe_ocr_max_chars = max(ocr_max_chars, 1)

    async with httpx.AsyncClient() as client:
        for row in rows:
            attempted += 1
            expected_type = str(_record_get(row, "doc_type", "unknown") or "unknown").lower()
            expected_workspace = workspace_bucket_for_doc_type(expected_type)
            expected_workspaces[expected_workspace] += 1
            try:
                answer = await _qwen_classify_text(
                    client,
                    ollama_url=ollama_url,
                    model=model,
                    ocr_text=_saved_ocr_text(
                        _record_get(row, "stage_output"), max_chars=safe_ocr_max_chars
                    ),
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:  # local diagnostic only; aggregate class name.
                failed_attempts += 1
                errors[type(exc).__name__] += 1
                continue

            predicted_type = answer or "unknown"
            predicted_workspace = workspace_bucket_for_doc_type(predicted_type)
            predicted_workspaces[predicted_workspace] += 1
            confusion[(expected_type, predicted_type, expected_workspace, predicted_workspace)] += 1
            if predicted_type == expected_type:
                exact_doc_type_matches += 1
            if predicted_workspace == expected_workspace:
                workspace_matches += 1
            if predicted_type == "unknown":
                unknown_predictions += 1

    classified_attempts = attempted - failed_attempts
    exact_doc_type_accuracy = (
        round(exact_doc_type_matches / classified_attempts, 4) if classified_attempts > 0 else 0.0
    )
    workspace_accuracy = (
        round(workspace_matches / classified_attempts, 4) if classified_attempts > 0 else 0.0
    )
    return {
        "mode": "local_ollama_text_only_known_doc_benchmark",
        "model": model,
        "ocr_max_chars": safe_ocr_max_chars,
        "attempted": attempted,
        "classified_attempts": classified_attempts,
        "failed_attempts": failed_attempts,
        "not_classified_due_error": failed_attempts,
        "exact_doc_type_matches": exact_doc_type_matches,
        "workspace_matches": workspace_matches,
        "unknown_predictions": unknown_predictions,
        "exact_doc_type_accuracy": exact_doc_type_accuracy,
        "workspace_accuracy": workspace_accuracy,
        "benchmark_gate": _qwen_benchmark_gate(
            classified_attempts=classified_attempts,
            workspace_matches=workspace_matches,
            min_workspace_accuracy=min_workspace_accuracy,
            min_classified_attempts=min_classified_attempts,
        ),
        "confusion_preview": _confusion_preview_rows(confusion),
        "expected_workspace_buckets": _count_rows(expected_workspaces, key_name="bucket"),
        "predicted_workspace_buckets": _count_rows(predicted_workspaces, key_name="bucket"),
        "errors": dict(errors),
    }


async def run_audit(
    database_url: str,
    *,
    limit: int = 0,
    top_doc_types: int = 30,
    qwen_text_sample: int = 0,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    qwen_model: str = DEFAULT_QWEN_MODEL,
    qwen_timeout_seconds: float = 45.0,
    qwen_ocr_max_chars: int = DEFAULT_QWEN_OCR_MAX_CHARS,
    qwen_min_candidate_rate: float = DEFAULT_QWEN_MIN_CANDIDATE_RATE,
    qwen_min_classified_attempts: int = DEFAULT_QWEN_MIN_CLASSIFIED_ATTEMPTS,
    qwen_known_sample: int = 0,
    qwen_min_workspace_accuracy: float = DEFAULT_QWEN_MIN_WORKSPACE_ACCURACY,
) -> dict[str, Any]:
    pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            if limit > 0:
                direct_rows = _records(await conn.fetch(DIRECT_DOC_ROWS_SQL + "\nLIMIT $1", limit))
            else:
                direct_rows = _records(await conn.fetch(DIRECT_DOC_ROWS_SQL))
            qwen_rows = (
                _records(
                    await conn.fetch(
                        DIRECT_DOC_QWEN_SAMPLE_SQL, qwen_text_sample, TEXT_PARSER_MIN_CHARS
                    )
                )
                if qwen_text_sample > 0
                else []
            )
            qwen_known_rows = (
                _records(
                    await conn.fetch(
                        DIRECT_DOC_QWEN_KNOWN_BENCHMARK_SQL,
                        qwen_known_sample,
                        TEXT_PARSER_MIN_CHARS,
                        HIGH_CONFIDENCE_THRESHOLD,
                    )
                )
                if qwen_known_sample > 0
                else []
            )
    finally:
        await pool.close()

    report: dict[str, Any] = {
        "audit": "intake_direct_doc_parser",
        "pii_policy": "aggregate_only_no_raw_phone_no_raw_group_subject_no_raw_ocr",
        "source": "intake_queue + whatsapp_message_context + document_routing_proposal",
        "limited_rows": limit if limit > 0 else None,
        **summarize_direct_rows(direct_rows, top_doc_types=top_doc_types),
    }
    if qwen_rows:
        report["qwen_text_sample"] = await run_qwen_text_sample(
            qwen_rows,
            ollama_url=ollama_url,
            model=qwen_model,
            timeout_seconds=qwen_timeout_seconds,
            ocr_max_chars=qwen_ocr_max_chars,
            min_candidate_rate=qwen_min_candidate_rate,
            min_classified_attempts=qwen_min_classified_attempts,
        )
    if qwen_known_rows:
        report["qwen_known_benchmark"] = await run_qwen_known_doc_benchmark(
            qwen_known_rows,
            ollama_url=ollama_url,
            model=qwen_model,
            timeout_seconds=qwen_timeout_seconds,
            ocr_max_chars=qwen_ocr_max_chars,
            min_workspace_accuracy=qwen_min_workspace_accuracy,
            min_classified_attempts=qwen_min_classified_attempts,
        )
    report["autocatalog_plan"] = build_autocatalog_plan(report)
    return report


def build_dashboard_snapshot(
    report: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "pii_policy": str(
            report.get("pii_policy", "aggregate_only_no_raw_phone_no_raw_group_subject_no_raw_ocr")
        ),
        "qwen_text_sample": report.get("qwen_text_sample") or {},
        "qwen_known_benchmark": report.get("qwen_known_benchmark") or {},
        "autocatalog_plan": report.get("autocatalog_plan") or build_autocatalog_plan(report),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only WA Mirror direct-doc parser audit")
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "INTAKE_DATABASE_URL",
            os.getenv("LOCAL_DATABASE_URL", DEFAULT_DB_URL),
        ),
        help="local Postgres DSN (default: INTAKE_DATABASE_URL/LOCAL_DATABASE_URL/nuzantara_dev)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="limit direct rows for quick aggregate sampling; 0 scans all direct docs",
    )
    parser.add_argument(
        "--top-doc-types",
        type=int,
        default=30,
        help="number of doc-type rows to include",
    )
    parser.add_argument(
        "--qwen-text-sample",
        type=int,
        default=0,
        help="run local Ollama/Qwen over this many unknown docs with enough saved OCR text",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.getenv("INTAKE_OLLAMA_URL", os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)),
        help="local Ollama URL for optional qwen text sample",
    )
    parser.add_argument(
        "--qwen-model",
        default=os.getenv("INTAKE_QWEN_TEXT_MODEL", DEFAULT_QWEN_MODEL),
        help="Ollama text model for optional qwen sample",
    )
    parser.add_argument(
        "--qwen-timeout-seconds",
        type=float,
        default=45.0,
        help="per-document timeout for optional qwen text sample",
    )
    parser.add_argument(
        "--qwen-ocr-max-chars",
        type=int,
        default=DEFAULT_QWEN_OCR_MAX_CHARS,
        help="maximum saved OCR characters sent to local Qwen per sampled document",
    )
    parser.add_argument(
        "--qwen-min-candidate-rate",
        type=float,
        default=DEFAULT_QWEN_MIN_CANDIDATE_RATE,
        help="minimum non-review workspace candidate rate before marking qwen batch candidate-ready",
    )
    parser.add_argument(
        "--qwen-min-classified-attempts",
        type=int,
        default=DEFAULT_QWEN_MIN_CLASSIFIED_ATTEMPTS,
        help="minimum successful qwen classifications before evaluating candidate readiness",
    )
    parser.add_argument(
        "--qwen-known-sample",
        type=int,
        default=0,
        help="run local Ollama/Qwen benchmark over this many known high-confidence docs",
    )
    parser.add_argument(
        "--qwen-min-workspace-accuracy",
        type=float,
        default=DEFAULT_QWEN_MIN_WORKSPACE_ACCURACY,
        help="minimum workspace-bucket accuracy before marking qwen benchmark ready",
    )
    parser.add_argument(
        "--write-dashboard-snapshot",
        default="",
        help="optional path for a non-PII qwen gate snapshot consumed by wa-dashboard",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    return parser


async def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = await run_audit(
        args.database_url,
        limit=max(args.limit, 0),
        top_doc_types=max(args.top_doc_types, 1),
        qwen_text_sample=max(args.qwen_text_sample, 0),
        ollama_url=args.ollama_url,
        qwen_model=args.qwen_model,
        qwen_timeout_seconds=max(args.qwen_timeout_seconds, 1.0),
        qwen_ocr_max_chars=max(args.qwen_ocr_max_chars, 1),
        qwen_min_candidate_rate=min(max(args.qwen_min_candidate_rate, 0.0), 1.0),
        qwen_min_classified_attempts=max(args.qwen_min_classified_attempts, 1),
        qwen_known_sample=max(args.qwen_known_sample, 0),
        qwen_min_workspace_accuracy=min(max(args.qwen_min_workspace_accuracy, 0.0), 1.0),
    )
    if args.write_dashboard_snapshot:
        snapshot_path = Path(args.write_dashboard_snapshot).expanduser()
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(build_dashboard_snapshot(report), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    indent = 2 if args.pretty else None
    sys.stdout.write(json.dumps(report, indent=indent, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
