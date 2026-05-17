"""Team-only CRM intelligence endpoints."""

from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.dependencies import get_database_pool, require_team_member
from backend.services.crm.evidence_dossier import build_evidence_dossiers
from backend.services.crm.tax_company_pilot import TaxCompanyPilotMap
from backend.services.crm.workspace_ai_snapshots import (
    WorkspaceAiSnapshotCreate,
    WorkspaceAiSnapshotResponse,
    approve_workspace_ai_snapshot,
    create_workspace_ai_snapshot,
    fetch_workspace_ai_review_queue,
)

router = APIRouter(prefix="/api/crm/intelligence", tags=["crm-intelligence"])


@router.get("/evidence-dossiers", response_model=list[TaxCompanyPilotMap])
async def get_evidence_dossiers(
    company: Annotated[
        list[str] | None,
        Query(description="Optional company filters; repeat for multiple values."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _current_user: dict = Depends(require_team_member),
) -> list[TaxCompanyPilotMap]:
    """Return person-first evidence dossiers for the team workspace."""
    return await build_evidence_dossiers(pool, companies=company, limit=limit)


@router.post("/workspace-ai-snapshots", response_model=WorkspaceAiSnapshotResponse)
async def create_workspace_ai_snapshot_draft(
    payload: WorkspaceAiSnapshotCreate,
    pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(require_team_member),
) -> WorkspaceAiSnapshotResponse:
    """Save Workspace AI findings as draft intake for human review.

    Draft snapshots are intentionally not consumed by the business-story UI.
    A separate approval step must mark rows approved before facts can appear
    inside kita.
    """
    created_by = current_user.get("email") if isinstance(current_user, dict) else None
    return await create_workspace_ai_snapshot(
        pool,
        payload,
        created_by=created_by,
    )


@router.get("/workspace-ai-snapshots/review", response_model=list[WorkspaceAiSnapshotResponse])
async def review_workspace_ai_snapshots(
    status: Literal["draft", "approved", "rejected"] = "draft",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _current_user: dict = Depends(require_team_member),
) -> list[WorkspaceAiSnapshotResponse]:
    """Return Workspace AI snapshots awaiting team review."""
    return await fetch_workspace_ai_review_queue(
        pool,
        status=status,
        limit=limit,
    )


@router.post("/workspace-ai-snapshots/{snapshot_id}/approve", response_model=WorkspaceAiSnapshotResponse)
async def approve_workspace_ai_snapshot_draft(
    snapshot_id: str,
    pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(require_team_member),
) -> WorkspaceAiSnapshotResponse:
    """Approve a draft Workspace AI snapshot for Business Story use."""
    approved_by = current_user.get("email") if isinstance(current_user, dict) else None
    try:
        return await approve_workspace_ai_snapshot(
            pool,
            snapshot_id=snapshot_id,
            approved_by=approved_by,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Workspace AI snapshot not found or not in draft status.",
        ) from exc
