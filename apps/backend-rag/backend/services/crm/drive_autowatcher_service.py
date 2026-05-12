"""Autonomous CRM Drive watcher orchestration.

This service combines the existing Drive/OCR/KG workers into one bounded pass
and prepares human-reviewable Workspace AI draft snapshots. It never approves
facts and never writes to Google Drive.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from backend.services.crm.tax_company_pilot import TaxCompanyPilotWorkspaceAiFact
from backend.services.crm.workspace_ai_snapshots import (
    WorkspaceAiSnapshotCreate,
    create_workspace_ai_snapshot,
)
from backend.services.documents.crm_drive_backfill_service import (
    run_crm_drive_backfill,
)

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 25
_MAX_LIMIT = 100
_SNAPSHOT_PROVIDER = "gemini"
_NOTE_PREFIX = "crm-drive-autowatcher:v1"


@dataclass(frozen=True)
class DriveEvidenceDocument:
    """One Drive-backed CRM document used to prepare a review draft."""

    file_id: str
    file_name: str
    document_type: str | None
    document_category: str | None
    ocr_status: str | None
    has_kg_node: bool


@dataclass(frozen=True)
class CompanyDriveEvidence:
    """Person-first evidence bundle for one linked company."""

    company_id: int
    company_name: str
    client_ids: list[int]
    people: list[str]
    tax_owner: str
    documents: list[DriveEvidenceDocument] = field(default_factory=list)
    kg_edge_count: int = 0


async def run_crm_drive_autowatch(
    pool: asyncpg.Pool,
    *,
    limit: int = _DEFAULT_LIMIT,
    dry_run: bool = True,
    client_id: int | None = None,
    allow_ocr: bool = False,
    story_drafts: bool = True,
    created_by: str | None = "crm-drive-autowatcher",
) -> dict[str, Any]:
    """Run one bounded autonomous pass over Drive-backed CRM evidence.

    The pass has two phases:
    1. Backfill current Drive documents into OCR/KG using the existing worker.
    2. Create draft Workspace AI snapshots from indexed evidence, deduped by
       deterministic note_id fingerprint.

    Draft snapshots are intentionally not consumed by Business Story until a
    team member approves them.
    """
    safe_limit = _safe_limit(limit)
    backfill = await run_crm_drive_backfill(
        pool,
        limit=safe_limit,
        dry_run=dry_run,
        client_id=client_id,
        link_kg=True,
        allow_ocr=allow_ocr,
    )

    summary: dict[str, Any] = {
        "status": "ok",
        "dry_run": dry_run,
        "allow_ocr": allow_ocr,
        "story_drafts": story_drafts,
        "limit": safe_limit,
        "client_id": client_id,
        "backfill": backfill,
        "snapshot_candidates": 0,
        "snapshots_created": 0,
        "snapshots_skipped_existing": 0,
        "snapshot_previews": [],
        "errors": [],
    }

    if not story_drafts:
        return summary

    evidence_items = await fetch_drive_evidence_for_story_drafts(
        pool,
        limit=safe_limit,
        client_id=client_id,
    )
    summary["snapshot_candidates"] = len(evidence_items)

    for evidence in evidence_items:
        payload = build_workspace_ai_snapshot_payload(evidence)
        summary["snapshot_previews"].append(_snapshot_preview(payload))

        if dry_run:
            continue

        try:
            if payload.note_id and await workspace_ai_snapshot_exists(pool, payload.note_id):
                summary["snapshots_skipped_existing"] += 1
                continue
            await create_workspace_ai_snapshot(pool, payload, created_by=created_by)
            summary["snapshots_created"] += 1
        except Exception as exc:  # noqa: BLE001 - batch must continue
            logger.error(
                "CRM Drive autowatcher failed creating snapshot for company %s: %s",
                evidence.company_id,
                exc,
                exc_info=True,
            )
            summary["errors"].append(
                {"company_id": evidence.company_id, "error": str(exc)[:200]},
            )

    return summary


async def fetch_drive_evidence_for_story_drafts(
    pool: asyncpg.Pool,
    *,
    limit: int = _DEFAULT_LIMIT,
    client_id: int | None = None,
) -> list[CompanyDriveEvidence]:
    """Fetch current person/company/document evidence for draft snapshots."""
    safe_limit = _safe_limit(limit)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                _EVIDENCE_SQL,
                client_id,
                safe_limit,
                f"{_NOTE_PREFIX}:%",
            )
    except asyncpg.UndefinedTableError:
        logger.info("CRM Drive autowatcher skipped: required CRM tables missing")
        return []
    return _evidence_from_rows(rows)


async def workspace_ai_snapshot_exists(
    pool: asyncpg.Pool,
    note_id: str,
) -> bool:
    """Return true when this exact autowatcher fingerprint already exists."""
    try:
        async with pool.acquire() as conn:
            return bool(
                await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM crm_workspace_ai_snapshots WHERE note_id = $1)",
                    note_id,
                )
            )
    except asyncpg.UndefinedTableError:
        return False


def build_workspace_ai_snapshot_payload(
    evidence: CompanyDriveEvidence,
) -> WorkspaceAiSnapshotCreate:
    """Build a draft Workspace AI snapshot from indexed Drive evidence."""
    source_file_ids = _ordered_file_ids(evidence.documents)
    note_id = _snapshot_note_id(evidence)
    facts = _facts_from_evidence(evidence)
    return WorkspaceAiSnapshotCreate(
        company_id=evidence.company_id,
        client_id=evidence.client_ids[0] if evidence.client_ids else None,
        company_name=evidence.company_name,
        provider=_SNAPSHOT_PROVIDER,
        notebook_id=None,
        note_id=note_id,
        source_file_ids=source_file_ids,
        facts=facts,
    )


def _facts_from_evidence(
    evidence: CompanyDriveEvidence,
) -> list[TaxCompanyPilotWorkspaceAiFact]:
    people = _human_join(evidence.people, fallback="the linked person")
    groups = _document_group_counts(evidence.documents)
    missing = _missing_groups(groups, evidence.kg_edge_count)

    identity_detail = (
        f"{evidence.company_name} has {len(evidence.documents)} indexed source "
        f"document{'s' if len(evidence.documents) != 1 else ''} in the CRM workspace."
    )
    person_detail = (
        f"Start from {people}; then open {evidence.company_name} through the confirmed CRM relationship."
    )
    compliance_detail = (
        f"Evidence currently covers {_coverage_sentence(groups)}. "
        f"Tax owner: {evidence.tax_owner}."
    )
    gap_detail = (
        "Missing or weak evidence: " + ", ".join(missing) + "."
        if missing
        else "Company, tax, person, and relationship evidence are all present for team review."
    )
    next_action_detail = (
        "Review this draft, confirm the roles and source documents, then approve it for the Business Story."
    )

    return [
        TaxCompanyPilotWorkspaceAiFact(
            category="identity",
            label="Company evidence",
            detail=_clean_detail(identity_detail),
            source_file_ids=_source_ids_for_groups(evidence.documents, ("company", "tax", "person")),
            confidence=_confidence_for(evidence.documents, evidence.kg_edge_count),
        ),
        TaxCompanyPilotWorkspaceAiFact(
            category="person",
            label="Person-first entry",
            detail=_clean_detail(person_detail),
            source_file_ids=_source_ids_for_groups(evidence.documents, ("person", "company")),
            confidence="high" if evidence.people else "medium",
        ),
        TaxCompanyPilotWorkspaceAiFact(
            category="compliance",
            label="Evidence coverage",
            detail=_clean_detail(compliance_detail),
            source_file_ids=_source_ids_for_groups(evidence.documents, ("company", "tax")),
            confidence=_confidence_for(evidence.documents, evidence.kg_edge_count),
        ),
        TaxCompanyPilotWorkspaceAiFact(
            category="gap",
            label="Review gaps",
            detail=_clean_detail(gap_detail),
            source_file_ids=[],
            confidence="medium",
        ),
        TaxCompanyPilotWorkspaceAiFact(
            category="next_action",
            label="Next action",
            detail=next_action_detail,
            source_file_ids=[],
            confidence="confirmed",
        ),
    ]


def _evidence_from_rows(rows: list[Any]) -> list[CompanyDriveEvidence]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        company_id = int(data["company_id"])
        bucket = grouped.setdefault(
            company_id,
            {
                "company_id": company_id,
                "company_name": str(data["company_name"]),
                "client_ids": set(),
                "people": [],
                "tax_owners": [],
                "documents": {},
                "kg_edge_count": 0,
            },
        )
        bucket["client_ids"].add(int(data["client_id"]))
        _append_unique(bucket["people"], str(data["client_name"]))
        if data.get("tax_owner"):
            _append_unique(bucket["tax_owners"], str(data["tax_owner"]))
        if data.get("file_id"):
            file_id = str(data["file_id"])
            bucket["documents"][file_id] = DriveEvidenceDocument(
                file_id=file_id,
                file_name=str(data.get("file_name") or "Document"),
                document_type=data.get("document_type"),
                document_category=data.get("document_category"),
                ocr_status=data.get("ocr_status"),
                has_kg_node=bool(data.get("has_kg_node")),
            )
        bucket["kg_edge_count"] = max(
            int(bucket["kg_edge_count"]),
            int(data.get("kg_edge_count") or 0),
        )

    evidence: list[CompanyDriveEvidence] = []
    for bucket in grouped.values():
        documents = sorted(
            bucket["documents"].values(),
            key=lambda doc: (doc.file_name.lower(), doc.file_id),
        )
        evidence.append(
            CompanyDriveEvidence(
                company_id=bucket["company_id"],
                company_name=bucket["company_name"],
                client_ids=sorted(bucket["client_ids"]),
                people=bucket["people"],
                tax_owner=bucket["tax_owners"][0] if bucket["tax_owners"] else "Unassigned",
                documents=documents,
                kg_edge_count=int(bucket["kg_edge_count"]),
            )
        )
    return evidence


def _snapshot_note_id(evidence: CompanyDriveEvidence) -> str:
    fingerprint = hashlib.sha256(
        "|".join(
            [
                str(evidence.company_id),
                evidence.company_name,
                ",".join(
                    f"{doc.file_id}:{doc.ocr_status or 'none'}:{int(doc.has_kg_node)}"
                    for doc in sorted(evidence.documents, key=lambda item: item.file_id)
                ),
                str(evidence.kg_edge_count),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"{_NOTE_PREFIX}:{evidence.company_id}:{fingerprint}"


def _document_group_counts(documents: list[DriveEvidenceDocument]) -> dict[str, int]:
    groups: dict[str, int] = {}
    for document in documents:
        group = _document_group(document)
        groups[group] = groups.get(group, 0) + 1
    return groups


def _document_group(document: DriveEvidenceDocument) -> str:
    text = f"{document.document_category or ''} {document.document_type or ''} {document.file_name}".lower()
    if any(marker in text for marker in ("spt", "lkpm", "tax", "pajak", "npwp")):
        return "tax"
    if any(marker in text for marker in ("passport", "paspor", "visa", "itas", "kitas", "kitap")):
        return "person"
    if any(marker in text for marker in ("akta", "nib", "company", "perseroan", "oss")):
        return "company"
    return "company"


def _coverage_sentence(groups: dict[str, int]) -> str:
    labels = []
    if groups.get("company"):
        labels.append(f"company files ({groups['company']})")
    if groups.get("tax"):
        labels.append(f"tax files ({groups['tax']})")
    if groups.get("person"):
        labels.append(f"person files ({groups['person']})")
    return _human_join(labels, fallback="no classified files yet")


def _missing_groups(groups: dict[str, int], kg_edge_count: int) -> list[str]:
    missing: list[str] = []
    if not groups.get("company"):
        missing.append("company registry")
    if not groups.get("tax"):
        missing.append("tax trail")
    if not groups.get("person"):
        missing.append("person file")
    if kg_edge_count <= 0:
        missing.append("relationship links")
    return missing


def _source_ids_for_groups(
    documents: list[DriveEvidenceDocument],
    groups: tuple[str, ...],
) -> list[str]:
    return [
        document.file_id
        for document in documents
        if _document_group(document) in groups
    ][:12]


def _ordered_file_ids(documents: list[DriveEvidenceDocument]) -> list[str]:
    seen: set[str] = set()
    file_ids: list[str] = []
    for document in documents:
        if document.file_id and document.file_id not in seen:
            seen.add(document.file_id)
            file_ids.append(document.file_id)
    return file_ids


def _confidence_for(
    documents: list[DriveEvidenceDocument],
    kg_edge_count: int,
) -> str:
    if documents and kg_edge_count > 0 and all(doc.ocr_status == "completed" for doc in documents):
        return "high"
    if documents and kg_edge_count > 0:
        return "medium"
    if documents:
        return "medium"
    return "low"


def _snapshot_preview(payload: WorkspaceAiSnapshotCreate) -> dict[str, Any]:
    return {
        "company_id": payload.company_id,
        "client_id": payload.client_id,
        "company_name": payload.company_name,
        "note_id": payload.note_id,
        "source_file_count": len(payload.source_file_ids),
        "facts": [fact.model_dump(mode="json") for fact in payload.facts],
    }


def _human_join(items: list[str], *, fallback: str) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return fallback
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _clean_detail(value: str) -> str:
    no_urls = re.sub(r"https?://\S+", "[internal source]", value)
    return no_urls.replace("Drive", "source").replace("OCR", "document reading").replace("KG", "relationship")


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _safe_limit(limit: int) -> int:
    return max(1, min(int(limit), _MAX_LIMIT))


_EVIDENCE_SQL = """
WITH company_scope AS (
    SELECT
        co.id AS company_id,
        co.company_name,
        BOOL_OR(snap.id IS NOT NULL) AS has_autowatcher_snapshot
    FROM client_company_links ccl
    JOIN clients cl ON cl.id = ccl.client_id
    JOIN companies co ON co.id = ccl.company_id
    JOIN documents d ON d.client_id = cl.id
    LEFT JOIN crm_workspace_ai_snapshots snap
        ON snap.company_id = co.id
        AND snap.note_id LIKE $3::text
    WHERE cl.deleted_at IS NULL
      AND d.file_id IS NOT NULL
      AND d.file_id <> ''
      AND (d.is_archived IS NULL OR d.is_archived = false)
      AND ($1::int IS NULL OR cl.id = $1::int)
    GROUP BY co.id, co.company_name
    ORDER BY has_autowatcher_snapshot ASC, co.company_name
    LIMIT $2
)
SELECT
    scope.company_id,
    scope.company_name,
    cl.id AS client_id,
    cl.full_name AS client_name,
    COALESCE(cl.tax_consultant, cl.assigned_to, '') AS tax_owner,
    d.file_id,
    d.file_name,
    d.document_type,
    d.document_category,
    d.ocr_status,
    kg.entity_id IS NOT NULL AS has_kg_node,
    COUNT(edge.relationship_id) OVER (PARTITION BY scope.company_id) AS kg_edge_count
FROM company_scope scope
JOIN client_company_links ccl ON ccl.company_id = scope.company_id
JOIN clients cl ON cl.id = ccl.client_id
JOIN documents d ON d.client_id = cl.id
LEFT JOIN crm_kg_nodes kg
    ON kg.file_id = d.file_id
    AND kg.entity_type = 'crm_document'
    AND kg.deleted_at IS NULL
LEFT JOIN crm_kg_edges edge
    ON edge.source_entity_id = kg.entity_id
WHERE cl.deleted_at IS NULL
  AND d.file_id IS NOT NULL
  AND d.file_id <> ''
  AND (d.is_archived IS NULL OR d.is_archived = false)
  AND ($1::int IS NULL OR cl.id = $1::int)
ORDER BY scope.company_name, cl.full_name, d.file_name
"""
