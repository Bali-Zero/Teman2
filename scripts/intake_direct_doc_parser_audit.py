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
from typing import Any

import asyncpg
import httpx

DEFAULT_DB_URL = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_QWEN_MODEL = "qwen3.5:9b"
HIGH_CONFIDENCE_THRESHOLD = 0.70

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
      AND (
        COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') = 'unknown'
        OR CASE
             WHEN COALESCE(q.stage_output->'classify'->>'type_confidence', '') ~ '^[0-9]+(\\.[0-9]+)?$'
             THEN (q.stage_output->'classify'->>'type_confidence')::numeric
             ELSE 0
           END < 0.70
      )
)
SELECT *
  FROM direct_docs
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


def summarize_direct_rows(
    rows: Iterable[Mapping[str, Any] | Any], *, top_doc_types: int = 30
) -> dict[str, Any]:
    """Aggregate direct-document parser and workspace placement state."""
    parser_counts: Counter[str] = Counter()
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
) -> dict[str, Any]:
    """Run local Qwen over saved OCR text and return aggregate transitions only."""
    transitions: Counter[str] = Counter()
    workspaces: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    attempted = 0
    improved_unknown_to_known = 0
    still_unknown = 0

    async with httpx.AsyncClient() as client:
        for row in rows:
            attempted += 1
            old_type = str(_record_get(row, "doc_type", "unknown") or "unknown").lower()
            try:
                answer = await _qwen_classify_text(
                    client,
                    ollama_url=ollama_url,
                    model=model,
                    ocr_text=_saved_ocr_text(_record_get(row, "stage_output")),
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:  # local diagnostic only; aggregate class name.
                errors[type(exc).__name__] += 1
                continue

            new_type = answer or "unknown"
            transitions[f"{old_type}->{new_type}"] += 1
            workspaces[workspace_bucket_for_doc_type(new_type)] += 1
            if old_type == "unknown" and new_type != "unknown":
                improved_unknown_to_known += 1
            if new_type == "unknown":
                still_unknown += 1

    return {
        "mode": "local_ollama_text_only_saved_ocr",
        "model": model,
        "attempted": attempted,
        "improved_unknown_to_known": improved_unknown_to_known,
        "still_unknown": still_unknown,
        "transitions": dict(transitions),
        "workspace_buckets": _count_rows(workspaces, key_name="bucket"),
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
) -> dict[str, Any]:
    pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            if limit > 0:
                direct_rows = _records(await conn.fetch(DIRECT_DOC_ROWS_SQL + "\nLIMIT $1", limit))
            else:
                direct_rows = _records(await conn.fetch(DIRECT_DOC_ROWS_SQL))
            qwen_rows = (
                _records(await conn.fetch(DIRECT_DOC_QWEN_SAMPLE_SQL, qwen_text_sample))
                if qwen_text_sample > 0
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
        )
    return report


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
        help="run local Ollama/Qwen over this many unknown/low-confidence saved-OCR docs",
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
    )
    indent = 2 if args.pretty else None
    sys.stdout.write(json.dumps(report, indent=indent, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
