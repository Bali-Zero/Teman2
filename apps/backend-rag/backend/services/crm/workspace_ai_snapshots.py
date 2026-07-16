"""Workspace AI facts for CRM evidence dossiers.

Rows start as draft intake from NotebookLM/Gemini. Evidence dossiers only read
approved facts, so raw AI output cannot leak into the team UI or client portal.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

import asyncpg
from pydantic import BaseModel, Field

from backend.services.crm.tax_company_pilot import (
    TaxCompanyPilotWorkspaceAiFact,
    TaxCompanyPilotWorkspaceAiSnapshot,
)

logger = logging.getLogger(__name__)

AUTO_APPROVE_POLICY_VERSION = "workspace-ai-v2-consultant-narrative"
_AUTO_APPROVE_SYSTEM_ACTOR = f"system:auto-approve:{AUTO_APPROVE_POLICY_VERSION}"
_AUTO_APPROVE_FACT_CATEGORIES = frozenset(
    {"identity", "person", "compliance", "gap", "next_action"}
)
_CONSULTANT_NARRATIVE_CATEGORIES = frozenset({"compliance", "next_action"})
_RAW_DRIVE_REFERENCE_MARKERS = (
    "drive.google.com",
    "docs.google.com",
    "/file/d/",
    "/folders/",
    "open?id=",
)
_DOCUMENT_GAP_PATTERN = re.compile(
    r"\b(document|record|file|npwp|nib|akta|profile|folder)\b.*"
    r"\b(missing|required|needed|absent|not found|not indexed|gap)\b|"
    r"\b(missing|required|needed|absent|not found|not indexed|gap)\b.*"
    r"\b(document|record|file|npwp|nib|akta|profile|folder)\b",
    re.IGNORECASE,
)
_CREDENTIAL_OR_PORTAL_SECRET_PATTERN = re.compile(
    r"\b("
    r"efin|password|passcode|otp|credential|credentials|username|login|"
    r"tax portal|djp/coretax|coretax access|portal access|accessed via|"
    r"npwp ending|individual accounts|personal tax oversight"
    r")\b|[\w.+-]+@(?:gmail|yahoo|hotmail|outlook)\.[\w.-]+",
    re.IGNORECASE,
)
_BACKSTAGE_SOURCE_REFERENCE_PATTERN = re.compile(
    r"\b(sources?|source files?)\s*:|"
    r"\b(file_id|folder_id|transaction_history)\b|"
    r"\.(?:pdf|jpe?g|png|xlsx?|csv)\b",
    re.IGNORECASE,
)
_ABSOLUTE_COMPLIANCE_PATTERN = re.compile(
    r"\b("
    r"fully compliant|compliant with all|legal and regulatory excellence|"
    r"no compliance risk|no legal risk|no risk|guaranteed|legally safe|"
    r"cleared by (?:the )?tax office|free of liabilities"
    r")\b",
    re.IGNORECASE,
)
_SENSITIVE_FINANCIAL_AMOUNT_PATTERN = re.compile(
    r"\b(?:pph|ppn|vat|tax|pajak|omzet|withholding|salary|salaries|"
    r"revenue|income|profit|loss|debt|balance|invoice|fee|royalty)"
    r"\b.{0,80}\b(?:rp|idr)\s*\d|"
    r"\b(?:rp|idr)\s*\d.{0,80}\b(?:pph|ppn|vat|tax|pajak|omzet|"
    r"withholding|salary|salaries|revenue|income|profit|loss|debt|"
    r"balance|invoice|fee|royalty)\b",
    re.IGNORECASE | re.DOTALL,
)
_UNSAFE_ADVICE_PATTERN = re.compile(
    r"\b(?:client|company|director|commissioner|shareholder|they|you)\s+"
    r"(?:should|must|need to|required to|has to)\b|"
    r"\b("
    r"amended tax return|legal opinion|liable|liability|penalty|sanction|"
    r"suspicion|suspected|fraud"
    r")\b",
    re.IGNORECASE,
)


class WorkspaceAiSnapshotCreate(BaseModel):
    company_id: int | None = None
    client_id: int | None = None
    company_name: str = Field(min_length=1)
    provider: Literal["notebooklm", "gemini", "manual"] = "notebooklm"
    notebook_id: str | None = None
    note_id: str | None = None
    source_file_ids: list[str] = Field(default_factory=list)
    facts: list[TaxCompanyPilotWorkspaceAiFact] = Field(default_factory=list)


class WorkspaceAiSnapshotResponse(WorkspaceAiSnapshotCreate):
    id: str
    status: str
    created_by: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str


class WorkspaceAiAutoApproveDecision(BaseModel):
    snapshot_id: str
    company_id: int | None = None
    company_name: str
    policy_version: str = AUTO_APPROVE_POLICY_VERSION
    eligible: bool
    approved: bool = False
    reason: str
    blocked_reasons: list[str] = Field(default_factory=list)
    fact_count: int


class WorkspaceAiAutoApproveResult(BaseModel):
    policy_version: str = AUTO_APPROVE_POLICY_VERSION
    dry_run: bool
    evaluated: int
    eligible_count: int
    blocked_count: int
    approved_count: int
    decisions: list[WorkspaceAiAutoApproveDecision]


async def fetch_latest_workspace_ai_snapshots(
    conn: asyncpg.Connection,
    company_ids: list[int],
) -> dict[int, TaxCompanyPilotWorkspaceAiSnapshot]:
    """Return the latest approved Workspace AI facts for each company id."""
    if not company_ids:
        return {}

    try:
        rows = await conn.fetch(_LATEST_BY_COMPANY_SQL, company_ids)
    except asyncpg.UndefinedTableError:
        logger.info("crm_workspace_ai_snapshots table is not available yet")
        return {}

    snapshots: dict[int, TaxCompanyPilotWorkspaceAiSnapshot] = {}
    for row in rows:
        data = dict(row)
        company_id = data.get("company_id")
        if company_id is None:
            continue
        snapshots[int(company_id)] = _snapshot_from_row(data)
    return snapshots


async def create_workspace_ai_snapshot(
    pool: asyncpg.Pool,
    payload: WorkspaceAiSnapshotCreate,
    *,
    created_by: str | None,
) -> WorkspaceAiSnapshotResponse:
    """Persist draft Workspace AI facts for later human review."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            _INSERT_SQL,
            payload.company_id,
            payload.client_id,
            payload.company_name.strip(),
            payload.provider,
            payload.notebook_id,
            payload.note_id,
            payload.source_file_ids,
            json.dumps(
                [fact.model_dump(mode="json") for fact in payload.facts],
                default=str,
            ),
            created_by,
        )

    return _response_from_row(row)


async def fetch_workspace_ai_review_queue(
    pool: asyncpg.Pool,
    *,
    status: Literal["draft", "approved", "rejected"] = "draft",
    limit: int = 25,
) -> list[WorkspaceAiSnapshotResponse]:
    """Return Workspace AI snapshots for the team review inbox."""
    safe_limit = max(1, min(int(limit), 100))
    async with pool.acquire() as conn:
        rows = await conn.fetch(_REVIEW_QUEUE_SQL, status, safe_limit)

    return [_response_from_row(row) for row in rows]


async def approve_workspace_ai_snapshot(
    pool: asyncpg.Pool,
    *,
    snapshot_id: str,
    approved_by: str | None,
) -> WorkspaceAiSnapshotResponse:
    """Approve one draft Workspace AI snapshot for Business Story use."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_APPROVE_SQL, snapshot_id, approved_by)

    if row is None:
        raise LookupError("workspace_ai_snapshot_not_found_or_not_draft")

    return _response_from_row(row)


def evaluate_workspace_ai_auto_approve_snapshot(
    snapshot: WorkspaceAiSnapshotResponse,
) -> WorkspaceAiAutoApproveDecision:
    """Decide whether a draft snapshot is safe for policy auto-approval.

    The policy is intentionally type/evidence based. Model confidence is not a
    gate because factual CRM inventory should pass even when the model labels it
    low confidence, while recommendations must remain human-reviewed.
    """
    blocked_reasons: list[str] = []
    if snapshot.status != "draft":
        blocked_reasons.append(f"status_not_draft:{snapshot.status}")
    if not snapshot.facts:
        blocked_reasons.append("missing_facts")

    for fact in snapshot.facts:
        category = str(fact.category)
        text = _normalise_fact_text(fact)
        if category not in _AUTO_APPROVE_FACT_CATEGORIES:
            blocked_reasons.append(f"unknown_category:{category}")
        elif category == "gap" and not _is_document_gap_fact(text):
            blocked_reasons.append("gap_not_document_inventory")

        if not (fact.source_file_ids or snapshot.source_file_ids):
            blocked_reasons.append("missing_explicit_evidence")
        if _contains_raw_drive_reference(text):
            blocked_reasons.append("raw_drive_reference")
        if _contains_credential_or_portal_secret(text):
            blocked_reasons.append("credential_or_portal_secret")
        if _contains_backstage_source_reference(text):
            blocked_reasons.append("backstage_source_reference")
        if _contains_absolute_compliance_claim(text):
            blocked_reasons.append("absolute_compliance_claim")
        if _contains_sensitive_financial_amount(text):
            blocked_reasons.append("sensitive_financial_amount")
        if _contains_unsafe_advice_claim(text):
            blocked_reasons.append("unsafe_advice_claim")

    unique_blocked_reasons = list(dict.fromkeys(blocked_reasons))
    eligible = len(unique_blocked_reasons) == 0
    has_consultant_narrative = any(
        str(fact.category) in _CONSULTANT_NARRATIVE_CATEGORIES for fact in snapshot.facts
    )
    return WorkspaceAiAutoApproveDecision(
        snapshot_id=snapshot.id,
        company_id=snapshot.company_id,
        company_name=snapshot.company_name,
        eligible=eligible,
        reason=(
            "consultant_narrative_snapshot"
            if eligible and has_consultant_narrative
            else "factual_structural_snapshot"
            if eligible
            else "policy_blocked"
        ),
        blocked_reasons=unique_blocked_reasons,
        fact_count=len(snapshot.facts),
    )


async def auto_approve_workspace_ai_snapshots(
    pool: asyncpg.Pool,
    *,
    limit: int = 25,
    dry_run: bool = True,
    approved_by: str | None = None,
) -> WorkspaceAiAutoApproveResult:
    """Evaluate draft snapshots and optionally approve policy-safe rows."""
    snapshots = await fetch_workspace_ai_review_queue(
        pool,
        status="draft",
        limit=limit,
    )
    actor = approved_by or _AUTO_APPROVE_SYSTEM_ACTOR
    decisions: list[WorkspaceAiAutoApproveDecision] = []
    approved_count = 0

    for snapshot in snapshots:
        decision = evaluate_workspace_ai_auto_approve_snapshot(snapshot)
        if decision.eligible and not dry_run:
            try:
                await approve_workspace_ai_snapshot(
                    pool,
                    snapshot_id=snapshot.id,
                    approved_by=actor,
                )
            except LookupError:
                logger.warning(
                    "Workspace AI snapshot auto-approval skipped because row is no longer draft",
                    extra={
                        "snapshot_id": snapshot.id,
                        "policy_version": AUTO_APPROVE_POLICY_VERSION,
                    },
                )
                decision = decision.model_copy(
                    update={
                        "eligible": False,
                        "reason": "approval_failed",
                        "blocked_reasons": [
                            *decision.blocked_reasons,
                            "approval_failed:not_draft",
                        ],
                    }
                )
            else:
                approved_count += 1
                decision = decision.model_copy(update={"approved": True})
        decisions.append(decision)

    eligible_count = sum(1 for decision in decisions if decision.eligible)
    return WorkspaceAiAutoApproveResult(
        dry_run=dry_run,
        evaluated=len(decisions),
        eligible_count=eligible_count,
        blocked_count=len(decisions) - eligible_count,
        approved_count=approved_count,
        decisions=decisions,
    )


def _response_from_row(row: Any) -> WorkspaceAiSnapshotResponse:
    approved_at = row["approved_at"]
    return WorkspaceAiSnapshotResponse(
        id=str(row["id"]),
        company_id=row["company_id"],
        client_id=row["client_id"],
        company_name=row["company_name"],
        provider=row["provider"],
        notebook_id=row["notebook_id"],
        note_id=row["note_id"],
        source_file_ids=list(row["source_file_ids"] or []),
        facts=_facts_from_db_value(row["facts"]),
        status=row["status"],
        created_by=row["created_by"],
        approved_by=row["approved_by"],
        approved_at=approved_at.isoformat() if approved_at else None,
        created_at=row["created_at"].isoformat(),
    )


def _snapshot_from_row(row: Any) -> TaxCompanyPilotWorkspaceAiSnapshot:
    data = dict(row)
    created_at = data.get("created_at")
    approved_at = data.get("approved_at")
    return TaxCompanyPilotWorkspaceAiSnapshot(
        provider=data.get("provider") or "notebooklm",
        notebook_id=data.get("notebook_id"),
        note_id=data.get("note_id"),
        source_file_ids=list(data.get("source_file_ids") or []),
        facts=_facts_from_db_value(data.get("facts")),
        approved_by=data.get("approved_by"),
        approved_at=approved_at.isoformat() if hasattr(approved_at, "isoformat") else approved_at,
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    )


def _facts_from_db_value(value: Any) -> list[TaxCompanyPilotWorkspaceAiFact]:
    if not value:
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    return [TaxCompanyPilotWorkspaceAiFact.model_validate(fact) for fact in parsed]


def _normalise_fact_text(fact: TaxCompanyPilotWorkspaceAiFact) -> str:
    return " ".join(
        [
            fact.category,
            fact.label,
            fact.detail,
        ]
    ).strip()


def _is_document_gap_fact(text: str) -> bool:
    return bool(_DOCUMENT_GAP_PATTERN.search(text))


def _contains_raw_drive_reference(text: str) -> bool:
    lower_text = text.lower()
    return any(marker in lower_text for marker in _RAW_DRIVE_REFERENCE_MARKERS)


def _contains_credential_or_portal_secret(text: str) -> bool:
    return bool(_CREDENTIAL_OR_PORTAL_SECRET_PATTERN.search(text))


def _contains_backstage_source_reference(text: str) -> bool:
    return bool(_BACKSTAGE_SOURCE_REFERENCE_PATTERN.search(text))


def _contains_absolute_compliance_claim(text: str) -> bool:
    return bool(_ABSOLUTE_COMPLIANCE_PATTERN.search(text))


def _contains_sensitive_financial_amount(text: str) -> bool:
    return bool(_SENSITIVE_FINANCIAL_AMOUNT_PATTERN.search(text))


def _contains_unsafe_advice_claim(text: str) -> bool:
    return bool(_UNSAFE_ADVICE_PATTERN.search(text))


_LATEST_BY_COMPANY_SQL = """
SELECT DISTINCT ON (company_id)
    company_id,
    provider,
    notebook_id,
    note_id,
    source_file_ids,
    facts,
    approved_by,
    approved_at,
    created_at
FROM crm_workspace_ai_snapshots
WHERE company_id = ANY($1::int[])
  AND status = 'approved'
ORDER BY company_id, approved_at DESC, created_at DESC
"""


_INSERT_SQL = """
INSERT INTO crm_workspace_ai_snapshots (
    company_id,
    client_id,
    company_name,
    provider,
    notebook_id,
    note_id,
    source_file_ids,
    facts,
    created_by
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::text::jsonb, $9)
RETURNING
    id,
    company_id,
    client_id,
    company_name,
    provider,
    notebook_id,
    note_id,
    source_file_ids,
    facts,
    status,
    created_by,
    approved_by,
    approved_at,
    created_at
"""


_REVIEW_QUEUE_SQL = """
SELECT
    id,
    company_id,
    client_id,
    company_name,
    provider,
    notebook_id,
    note_id,
    source_file_ids,
    facts,
    status,
    created_by,
    approved_by,
    approved_at,
    created_at
FROM crm_workspace_ai_snapshots
WHERE status = $1
ORDER BY created_at DESC
LIMIT $2
"""


_APPROVE_SQL = """
UPDATE crm_workspace_ai_snapshots
SET
    status = 'approved',
    approved_by = $2,
    approved_at = NOW(),
    updated_at = NOW()
WHERE id = $1::uuid
  AND status = 'draft'
RETURNING
    id,
    company_id,
    client_id,
    company_name,
    provider,
    notebook_id,
    note_id,
    source_file_ids,
    facts,
    status,
    created_by,
    approved_by,
    approved_at,
    created_at
"""
