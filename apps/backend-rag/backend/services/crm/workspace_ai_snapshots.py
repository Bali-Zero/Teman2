"""Workspace AI facts for CRM evidence dossiers.

Rows start as draft intake from NotebookLM/Gemini. Evidence dossiers only read
approved facts, so raw AI output cannot leak into the team UI or client portal.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import asyncpg
from pydantic import BaseModel, Field

from backend.services.crm.tax_company_pilot import (
    TaxCompanyPilotWorkspaceAiFact,
    TaxCompanyPilotWorkspaceAiSnapshot,
)

logger = logging.getLogger(__name__)


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
            [fact.model_dump(mode="json") for fact in payload.facts],
            created_by,
        )

    return WorkspaceAiSnapshotResponse(
        id=str(row["id"]),
        company_id=row["company_id"],
        client_id=row["client_id"],
        company_name=row["company_name"],
        provider=row["provider"],
        notebook_id=row["notebook_id"],
        note_id=row["note_id"],
        source_file_ids=list(row["source_file_ids"] or []),
        facts=[
            TaxCompanyPilotWorkspaceAiFact.model_validate(fact)
            for fact in (row["facts"] or [])
        ],
        status=row["status"],
        created_by=row["created_by"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"].isoformat() if row["approved_at"] else None,
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
        facts=[
            TaxCompanyPilotWorkspaceAiFact.model_validate(fact)
            for fact in (data.get("facts") or [])
        ],
        approved_by=data.get("approved_by"),
        approved_at=approved_at.isoformat() if hasattr(approved_at, "isoformat") else approved_at,
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    )


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
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
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
