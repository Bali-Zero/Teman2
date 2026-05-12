"""Dynamic person-first evidence dossiers for the CRM workspace."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import asyncpg

from backend.services.crm.tax_company_pilot import (
    DriveConfidence,
    TaxCompanyPilotDocument,
    TaxCompanyPilotEntity,
    TaxCompanyPilotEvidenceLink,
    TaxCompanyPilotMap,
    TaxCompanyPilotPerson,
    TaxCompanyPilotStoryEvidence,
    TaxCompanyPilotTaxMember,
    get_tax_company_pilot_map,
)

_PORTAL_RULE = "Client portal: download approved documents only."
_TEAM_RULE = "Team workspace: open Drive evidence and shortcuts from kita."
_PILOT_KEYS = ("ocean", "bimala")


async def build_evidence_dossiers(
    pool: asyncpg.Pool,
    *,
    companies: Sequence[str] | None = None,
    limit: int = 10,
) -> list[TaxCompanyPilotMap]:
    """Build team-only CRM evidence dossiers from DB/KG rows.

    Falls back to the curated Ocean/Bimala pilot maps when no dynamic data is
    available for the requested pilot keys.
    """
    requested = _normalize_terms(companies)
    safe_limit = max(1, min(limit, 25))

    dynamic_maps = await _build_dynamic_maps(pool, requested, safe_limit)
    if dynamic_maps:
        missing_fallbacks = _pilot_fallbacks_missing_from(dynamic_maps, requested)
        return [*dynamic_maps, *missing_fallbacks]

    return _pilot_fallbacks(requested)


async def _build_dynamic_maps(
    pool: asyncpg.Pool,
    requested: list[str],
    limit: int,
) -> list[TaxCompanyPilotMap]:
    async with pool.acquire() as conn:
        company_rows = await conn.fetch(_COMPANY_SQL, requested, limit)
        if not company_rows:
            return []

        client_ids = sorted({int(row["client_id"]) for row in company_rows})
        document_rows = await conn.fetch(_DOCUMENT_SQL, client_ids)
        kg_rows = await conn.fetch(_KG_SQL, client_ids)

    documents_by_client: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in document_rows:
        documents_by_client[int(row["client_id"])].append(_row_dict(row))

    kg_by_client: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in kg_rows:
        kg_by_client[int(row["client_id"])].append(_row_dict(row))

    rows_by_company: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in company_rows:
        rows_by_company[int(row["company_id"])].append(_row_dict(row))

    return [
        _build_company_map(
            company_id=company_id,
            rows=rows,
            documents_by_client=documents_by_client,
            kg_by_client=kg_by_client,
        )
        for company_id, rows in rows_by_company.items()
    ]


def _build_company_map(
    *,
    company_id: int,
    rows: list[dict[str, Any]],
    documents_by_client: dict[int, list[dict[str, Any]]],
    kg_by_client: dict[int, list[dict[str, Any]]],
) -> TaxCompanyPilotMap:
    first = rows[0]
    client_ids = [int(row["client_id"]) for row in rows]
    all_docs = [
        doc
        for client_id in client_ids
        for doc in documents_by_client.get(client_id, [])
    ]
    all_kg = [
        kg
        for client_id in client_ids
        for kg in kg_by_client.get(client_id, [])
    ]

    people = [_person_from_link(row) for row in rows]
    documents = [_document_from_row(doc) for doc in all_docs]
    tax_owner = _tax_owner(rows)
    gaps = _gaps(rows, documents, all_kg, tax_owner)
    evidence_links = _evidence_links(rows, documents)

    return TaxCompanyPilotMap(
        key=f"dynamic-{company_id}",
        company=TaxCompanyPilotEntity(
            name=first["company_name"],
            aliases=_company_aliases(first),
        ),
        tax_member=TaxCompanyPilotTaxMember(
            name=tax_owner,
            workspace_branch="CRM live dossier",
            source_folder_url=_first_folder_url(rows),
        ),
        drive_folders=_drive_folders(rows),
        persons=people,
        documents=documents,
        evidence_stories=[
            _evidence_story(
                person=person,
                company_name=first["company_name"],
                tax_owner=tax_owner,
                documents=documents,
                kg_rows=all_kg,
                gaps=gaps,
            )
            for person in people
        ],
        duplicate_candidates=[],
        gaps=gaps,
        evidence_links=evidence_links,
        ai_recap=_ai_recap(first, people, documents, all_kg),
        read_only=True,
        confidence=_overall_confidence(documents, all_kg),
    )


def _person_from_link(row: dict[str, Any]) -> TaxCompanyPilotPerson:
    return TaxCompanyPilotPerson(
        name=row["client_name"],
        folder_url=_drive_folder(row.get("client_folder_id")),
        evidence=["CRM client-company link"],
        role=row.get("link_role"),
        role_confidence="confirmed" if row.get("link_role") else "medium",
        relationship_confidence="confirmed",
    )


def _document_from_row(row: dict[str, Any]) -> TaxCompanyPilotDocument:
    return TaxCompanyPilotDocument(
        name=row.get("file_name") or row.get("document_type") or "Document",
        group=_document_group(row),
        evidence_url=row.get("google_drive_file_url") or row.get("file_url"),
        sensitivity=_document_sensitivity(row),
        confidence="confirmed" if row.get("ocr_status") == "completed" else "medium",
    )


def _evidence_story(
    *,
    person: TaxCompanyPilotPerson,
    company_name: str,
    tax_owner: str,
    documents: list[TaxCompanyPilotDocument],
    kg_rows: list[dict[str, Any]],
    gaps: list[dict[str, str]],
) -> dict[str, Any]:
    items = [
        TaxCompanyPilotStoryEvidence(
            label="Person file",
            detail=", ".join(person.evidence),
            source_label="Person Drive folder" if person.folder_url else "CRM link",
            source_url=person.folder_url,
            source_kind="folder",
            confidence=person.relationship_confidence,
        )
    ]
    items.extend(_document_evidence_items(documents[:3]))
    items.extend(_kg_evidence_items(kg_rows[:3]))

    return {
        "person_name": person.name,
        "company_name": company_name,
        "tax_owner": tax_owner,
        "recap": (
            f"{person.name} is the CRM entry point for {company_name}; "
            f"{tax_owner} owns or reviews the tax workstream."
        ),
        "relationship_path": [person.name, company_name, f"Tax: {tax_owner}"],
        "evidence_items": items,
        "next_action": _next_action(documents, kg_rows, gaps),
        "portal_rule": _PORTAL_RULE,
        "team_rule": _TEAM_RULE,
        "confidence": person.relationship_confidence,
    }


def _document_evidence_items(
    documents: list[TaxCompanyPilotDocument],
) -> list[TaxCompanyPilotStoryEvidence]:
    return [
        TaxCompanyPilotStoryEvidence(
            label="Document",
            detail=f"{document.name} is classified as {document.group}.",
            source_label=document.name,
            source_url=document.evidence_url,
            source_kind=_source_kind(document.evidence_url),
            confidence=document.confidence,
        )
        for document in documents
    ]


def _kg_evidence_items(rows: list[dict[str, Any]]) -> list[TaxCompanyPilotStoryEvidence]:
    return [
        TaxCompanyPilotStoryEvidence(
            label="Knowledge graph",
            detail=(
                f"KG {row.get('edge_tier') or 'derived'} edge "
                f"{row.get('relationship_type')} -> {row.get('target_type')}"
            ),
            source_label=row.get("document_name") or row.get("document_file_id") or "KG edge",
            source_url=None,
            source_kind="document",
            confidence=_confidence_from_float(row.get("confidence")),
        )
        for row in rows
    ]


def _evidence_links(
    rows: list[dict[str, Any]],
    documents: list[TaxCompanyPilotDocument],
) -> list[TaxCompanyPilotEvidenceLink]:
    links: list[TaxCompanyPilotEvidenceLink] = []
    for row in rows:
        folder_url = _drive_folder(row.get("client_folder_id"))
        if folder_url:
            links.append(TaxCompanyPilotEvidenceLink(label=row["client_name"], url=folder_url, kind="folder"))
    for document in documents:
        if document.evidence_url:
            links.append(
                TaxCompanyPilotEvidenceLink(
                    label=document.name,
                    url=document.evidence_url,
                    kind=_source_kind(document.evidence_url),
                )
            )
    return links[:12]


def _gaps(
    rows: list[dict[str, Any]],
    documents: list[TaxCompanyPilotDocument],
    kg_rows: list[dict[str, Any]],
    tax_owner: str,
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if tax_owner == "Unassigned tax owner":
        gaps.append(
            {
                "code": "missing_tax_owner",
                "label": "Assign tax owner before using this story operationally.",
                "severity": "high",
            }
        )
    if not any(row.get("client_folder_id") for row in rows):
        gaps.append(
            {
                "code": "missing_person_folder",
                "label": "Connect the canonical person Drive folder.",
                "severity": "medium",
            }
        )
    if not documents:
        gaps.append({"code": "missing_documents", "label": "Attach source documents.", "severity": "high"})
    if documents and not any(document.group == "company" for document in documents):
        gaps.append(
            {
                "code": "missing_company_registry",
                "label": "Attach company registry evidence.",
                "severity": "medium",
            }
        )
    if documents and not any(document.group in ("tax", "lkpm", "coretax") for document in documents):
        gaps.append({"code": "missing_tax_trail", "label": "Attach tax or LKPM evidence.", "severity": "medium"})
    if not kg_rows:
        gaps.append({"code": "missing_kg_edges", "label": "Run OCR/KG linking for stronger relationships.", "severity": "low"})
    return gaps


def _ai_recap(
    company: dict[str, Any],
    people: list[TaxCompanyPilotPerson],
    documents: list[TaxCompanyPilotDocument],
    kg_rows: list[dict[str, Any]],
) -> list[str]:
    names = ", ".join(person.name for person in people[:3])
    return [
        f"Start from {names}, then open {company['company_name']} through confirmed CRM links.",
        f"{len(documents)} source documents and {len(kg_rows)} KG facts are available for team review.",
        "Client portal access remains limited to approved document downloads.",
    ]


def _next_action(
    documents: list[TaxCompanyPilotDocument],
    kg_rows: list[dict[str, Any]],
    gaps: list[dict[str, str]] | None = None,
) -> str:
    if gaps:
        return gaps[0]["label"]
    if not documents:
        return "Attach source documents before using this company story operationally."
    if not kg_rows:
        return "Run OCR/KG linking to strengthen the person-company evidence chain."
    return "Review evidence, confirm roles, and promote the story to the operational workspace."


def _document_group(row: dict[str, Any]) -> str:
    text = f"{row.get('document_category') or ''} {row.get('document_type') or ''} {row.get('file_name') or ''}".lower()
    if "lkpm" in text:
        return "lkpm"
    if "coretax" in text:
        return "coretax"
    if "tax" in text or "spt" in text or "npwp" in text:
        return "tax"
    if "akta" in text or "nib" in text or "company" in text or "perseroan" in text:
        return "company"
    if "passport" in text or "visa" in text or "itas" in text:
        return "person"
    return "company"


def _document_sensitivity(row: dict[str, Any]) -> str:
    text = f"{row.get('document_category') or ''} {row.get('document_type') or ''} {row.get('file_name') or ''}".lower()
    if "coretax" in text or "credential" in text:
        return "credential"
    if "finance" in text or "income" in text or "bank" in text:
        return "financial"
    if "passport" in text or "visa" in text:
        return "person"
    return "company"


def _company_aliases(row: dict[str, Any]) -> list[str]:
    aliases = []
    for key in ("company_type", "nib", "npwp_company", "kbli_code"):
        value = row.get(key)
        if value:
            aliases.append(str(value))
    return aliases


def _tax_owner(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        if row.get("tax_consultant"):
            return str(row["tax_consultant"])
    for row in rows:
        if row.get("assigned_to"):
            return str(row["assigned_to"])
    return "Unassigned tax owner"


def _first_folder_url(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        folder_url = _drive_folder(row.get("client_folder_id"))
        if folder_url:
            return folder_url
    return ""


def _drive_folders(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        row["client_name"]: folder_url
        for row in rows
        if (folder_url := _drive_folder(row.get("client_folder_id")))
    }


def _overall_confidence(
    documents: list[TaxCompanyPilotDocument],
    kg_rows: list[dict[str, Any]],
) -> DriveConfidence:
    if documents and kg_rows:
        return "high"
    if documents:
        return "medium"
    return "low"


def _confidence_from_float(value: Any) -> DriveConfidence:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return "medium"
    if confidence >= 1.0:
        return "confirmed"
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def _source_kind(url: str | None) -> str:
    if not url:
        return "document"
    if "spreadsheets/d/" in url:
        return "spreadsheet"
    if "document/d/" in url:
        return "document"
    if "/file/d/" in url:
        return "file"
    return "folder"


def _drive_folder(folder_id: str | None) -> str | None:
    if not folder_id:
        return None
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _normalize_terms(companies: Sequence[str] | None) -> list[str]:
    if not companies:
        return []
    terms: list[str] = []
    for company in companies:
        for part in str(company).split(","):
            normalized = part.strip()
            if normalized:
                terms.append(normalized)
    return terms


def _pilot_fallbacks(requested: list[str]) -> list[TaxCompanyPilotMap]:
    keys = _PILOT_KEYS if not requested else tuple(_pilot_key(term) for term in requested)
    maps: list[TaxCompanyPilotMap] = []
    seen: set[str] = set()
    for key in keys:
        if not key or key in seen:
            continue
        pilot = get_tax_company_pilot_map(key)
        if pilot is not None:
            maps.append(pilot)
            seen.add(key)
    return maps


def _pilot_fallbacks_missing_from(
    dynamic_maps: list[TaxCompanyPilotMap],
    requested: list[str],
) -> list[TaxCompanyPilotMap]:
    if not requested:
        return []
    dynamic_names = " ".join(dossier.company.name.lower() for dossier in dynamic_maps)
    missing = [
        key
        for key in (_pilot_key(term) for term in requested)
        if key and key not in dynamic_names
    ]
    if not missing:
        return []
    return _pilot_fallbacks(missing)


def _pilot_key(term: str) -> str | None:
    lowered = term.lower()
    if "ocean" in lowered:
        return "ocean"
    if "bimala" in lowered:
        return "bimala"
    return None


def _row_dict(row: Any) -> dict[str, Any]:
    return dict(row)


_COMPANY_SQL = """
SELECT
    cl.id AS client_id,
    cl.full_name AS client_name,
    cl.google_drive_folder_id AS client_folder_id,
    cl.assigned_to,
    cl.tax_consultant,
    co.id AS company_id,
    co.company_name,
    co.company_type,
    co.nib,
    co.npwp_company,
    co.kbli_code,
    co.status AS company_status,
    ccl.role AS link_role,
    ccl.is_primary
FROM client_company_links ccl
JOIN clients cl ON cl.id = ccl.client_id
JOIN companies co ON co.id = ccl.company_id
WHERE cl.deleted_at IS NULL
  AND (
    cardinality($1::text[]) = 0
    OR EXISTS (
        SELECT 1
        FROM unnest($1::text[]) AS term
        WHERE LOWER(co.company_name) LIKE '%' || LOWER(term) || '%'
           OR LOWER(cl.full_name) LIKE '%' || LOWER(term) || '%'
    )
  )
ORDER BY ccl.is_primary DESC, co.company_name, cl.full_name
LIMIT $2
"""

_DOCUMENT_SQL = """
SELECT
    client_id,
    file_name,
    document_type,
    document_category,
    file_id,
    google_drive_file_url,
    file_url,
    status,
    client_visible,
    ocr_status,
    expiry_date
FROM documents
WHERE client_id = ANY($1::int[])
  AND (is_archived IS NULL OR is_archived = false)
ORDER BY document_category, document_type, file_name
"""

_KG_SQL = """
SELECT
    client_node.client_id,
    document_node.file_id AS document_file_id,
    document_node.name AS document_name,
    target.entity_type AS target_type,
    target.name AS target_name,
    edge.relationship_type,
    edge.edge_tier,
    edge.confidence
FROM crm_kg_nodes client_node
JOIN crm_kg_edges belongs
    ON belongs.target_entity_id = client_node.entity_id
    AND belongs.relationship_type = 'BELONGS_TO'
JOIN crm_kg_nodes document_node
    ON document_node.entity_id = belongs.source_entity_id
    AND document_node.entity_type = 'crm_document'
    AND document_node.deleted_at IS NULL
LEFT JOIN crm_kg_edges edge
    ON edge.source_entity_id = document_node.entity_id
    AND edge.relationship_type IN ('DESCRIBES', 'PART_OF', 'CONTEMPORANEOUS', 'COWORKER_AT')
LEFT JOIN crm_kg_nodes target
    ON target.entity_id = edge.target_entity_id
    AND target.deleted_at IS NULL
WHERE client_node.entity_type = 'crm_client'
  AND client_node.deleted_at IS NULL
  AND client_node.client_id = ANY($1::int[])
ORDER BY client_node.client_id, document_node.name
"""
