"""Backfill existing CRM Drive documents into OCR and CRM KG.

This worker handles the archive that already exists in Drive/CRM. It does not
write to Drive. It either links already-OCRed documents into crm_kg, or sends
unprocessed documents through the existing OCR dispatcher.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from json import JSONDecodeError, loads
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 25
_MAX_LIMIT = 250


@dataclass(frozen=True)
class CrmDriveBackfillCandidate:
    """One current CRM document that can be OCRed or linked into KG."""

    document_id: int
    client_id: int
    file_id: str
    file_name: str
    document_type: str
    document_category: str | None
    practice_id: int | None
    drive_url: str | None
    ocr_status: str | None
    ocr_extracted_data: dict[str, Any]
    has_kg_node: bool


async def run_crm_drive_backfill(
    pool: asyncpg.Pool,
    *,
    limit: int = _DEFAULT_LIMIT,
    dry_run: bool = True,
    client_id: int | None = None,
    link_kg: bool = True,
) -> dict[str, Any]:
    """Run one bounded backfill pass over existing CRM Drive documents.

    Args:
        pool: Database pool.
        limit: Maximum candidates to inspect in this pass.
        dry_run: When true, only counts and previews candidates.
        client_id: Optional single-client scope.
        link_kg: Whether to create crm_kg edges after OCR/direct link.

    Returns:
        Summary counters safe for admin endpoints and cron logs.
    """
    candidates = await fetch_crm_drive_backfill_candidates(
        pool,
        limit=limit,
        client_id=client_id,
    )
    summary: dict[str, Any] = {
        "dry_run": dry_run,
        "candidate_count": len(candidates),
        "processed": 0,
        "ocr_dispatched": 0,
        "kg_linked": 0,
        "skipped": 0,
        "errors": [],
        "candidates": [_candidate_preview(candidate) for candidate in candidates[:10]],
    }

    if dry_run:
        return summary

    for candidate in candidates:
        try:
            outcome = await _process_candidate(pool, candidate, link_kg=link_kg)
        except Exception as exc:  # noqa: BLE001 - batch worker must continue
            logger.error(
                "CRM Drive backfill failed for document %s: %s",
                candidate.document_id,
                exc,
                exc_info=True,
            )
            summary["errors"].append(
                {"document_id": candidate.document_id, "error": str(exc)[:200]},
            )
            continue

        summary["processed"] += 1
        summary["ocr_dispatched"] += int(outcome.get("ocr_dispatched", 0))
        summary["kg_linked"] += int(outcome.get("kg_linked", 0))
        summary["skipped"] += int(outcome.get("skipped", 0))

    return summary


async def fetch_crm_drive_backfill_candidates(
    pool: asyncpg.Pool,
    *,
    limit: int = _DEFAULT_LIMIT,
    client_id: int | None = None,
) -> list[CrmDriveBackfillCandidate]:
    """Fetch existing Drive-backed documents that still need OCR or KG."""
    safe_limit = max(1, min(limit, _MAX_LIMIT))
    async with pool.acquire() as conn:
        rows = await conn.fetch(_CANDIDATE_SQL, client_id, safe_limit)
    return [_candidate_from_row(row) for row in rows]


async def _process_candidate(
    pool: asyncpg.Pool,
    candidate: CrmDriveBackfillCandidate,
    *,
    link_kg: bool,
) -> dict[str, int]:
    if _can_link_without_ocr(candidate):
        linked = await _link_candidate_to_kg(pool, candidate, candidate.document_type)
        return {"ocr_dispatched": 0, "kg_linked": int(linked), "skipped": int(not linked)}

    from backend.services.documents.ocr_dispatcher_service import dispatch_ocr_by_folder

    result = await dispatch_ocr_by_folder(
        db_pool=pool,
        client_id=candidate.client_id,
        file_id=candidate.file_id,
        folder_name=_folder_hint(candidate.document_category),
        filename=candidate.file_name,
        doc_id=candidate.document_id,
        document_type=candidate.document_type,
    )

    if not result.get("dispatched"):
        return {"ocr_dispatched": 0, "kg_linked": 0, "skipped": 1}

    linked = False
    if link_kg and not _dispatcher_links_kg():
        handler_name = str(result.get("handler") or candidate.document_type)
        linked = await _link_candidate_to_kg(
            pool,
            candidate,
            handler_name,
            extracted_fields=_extract_fields_from_dispatch(result),
        )

    return {"ocr_dispatched": 1, "kg_linked": int(linked), "skipped": 0}


async def _link_candidate_to_kg(
    pool: asyncpg.Pool,
    candidate: CrmDriveBackfillCandidate,
    document_type: str,
    extracted_fields: dict[str, Any] | None = None,
) -> bool:
    from backend.services.knowledge_graph.document_linker import kg_link_document

    result = await kg_link_document(
        pool,
        file_id=candidate.file_id,
        client_id=candidate.client_id,
        document_type=document_type,
        extracted_fields=extracted_fields or candidate.ocr_extracted_data,
        practice_id=candidate.practice_id,
        drive_url=candidate.drive_url,
        filename=candidate.file_name,
    )
    return bool(result.get("ok"))


def _candidate_from_row(row: Any) -> CrmDriveBackfillCandidate:
    data = dict(row)
    raw_ocr = _coerce_extracted_data(data.get("ocr_extracted_data"))
    return CrmDriveBackfillCandidate(
        document_id=int(data["document_id"]),
        client_id=int(data["client_id"]),
        file_id=str(data["file_id"]),
        file_name=str(data.get("file_name") or data.get("document_type") or "Document"),
        document_type=str(data.get("document_type") or "unknown"),
        document_category=data.get("document_category"),
        practice_id=data.get("practice_id"),
        drive_url=data.get("google_drive_file_url") or data.get("file_url"),
        ocr_status=data.get("ocr_status"),
        ocr_extracted_data=raw_ocr,
        has_kg_node=bool(data.get("has_kg_node")),
    )


def _can_link_without_ocr(candidate: CrmDriveBackfillCandidate) -> bool:
    return (
        candidate.ocr_status == "completed"
        and bool(candidate.ocr_extracted_data)
        and not candidate.has_kg_node
    )


def _extract_fields_from_dispatch(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result")
    if isinstance(payload, dict):
        extracted = payload.get("extracted") or payload.get("raw_response")
        if isinstance(extracted, dict):
            return extracted
        if "passport_number" in payload or "npwp" in payload or "npwp_company" in payload:
            return payload
    return {}


def _coerce_extracted_data(raw_ocr: Any) -> dict[str, Any]:
    if isinstance(raw_ocr, dict):
        return raw_ocr
    if isinstance(raw_ocr, str) and raw_ocr.strip():
        try:
            parsed = loads(raw_ocr)
        except JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _dispatcher_links_kg() -> bool:
    return os.environ.get("CRM_KG_ENABLED", "").lower() in ("true", "1", "yes", "on")


def _folder_hint(category: str | None) -> str:
    normalized = (category or "").lower()
    if normalized == "immigration":
        return "01_Immigration"
    if normalized == "company":
        return "02_Company"
    if normalized == "tax":
        return "03_Tax"
    if normalized == "family":
        return "04_Family"
    return "99_Misc"


def _candidate_preview(candidate: CrmDriveBackfillCandidate) -> dict[str, Any]:
    return {
        "document_id": candidate.document_id,
        "client_id": candidate.client_id,
        "file_name": candidate.file_name,
        "document_type": candidate.document_type,
        "document_category": candidate.document_category,
        "ocr_status": candidate.ocr_status,
        "has_kg_node": candidate.has_kg_node,
    }


_CANDIDATE_SQL = """
SELECT
    d.id AS document_id,
    d.client_id,
    d.file_id,
    d.file_name,
    d.document_type,
    d.document_category,
    d.practice_id,
    d.google_drive_file_url,
    d.file_url,
    d.ocr_status,
    d.ocr_extracted_data,
    kg.entity_id IS NOT NULL AS has_kg_node
FROM documents d
JOIN clients c ON c.id = d.client_id
LEFT JOIN crm_kg_nodes kg
    ON kg.file_id = d.file_id
    AND kg.entity_type = 'crm_document'
    AND kg.deleted_at IS NULL
WHERE c.deleted_at IS NULL
  AND d.client_id IS NOT NULL
  AND d.file_id IS NOT NULL
  AND d.file_id <> ''
  AND (d.is_archived IS NULL OR d.is_archived = false)
  AND ($1::int IS NULL OR d.client_id = $1::int)
  AND (
      kg.entity_id IS NULL
      OR d.ocr_status IS NULL
      OR d.ocr_status IN ('pending', 'processing', 'failed')
  )
ORDER BY
    CASE
        WHEN d.ocr_status = 'completed' AND kg.entity_id IS NULL THEN 0
        WHEN d.ocr_status IN ('pending', 'processing') THEN 1
        WHEN d.ocr_status IS NULL THEN 2
        ELSE 3
    END,
    d.updated_at DESC NULLS LAST,
    d.id DESC
LIMIT $2
"""
