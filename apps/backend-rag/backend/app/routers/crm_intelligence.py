"""Team-only CRM intelligence endpoints."""

import asyncio
import json
import logging
from typing import Annotated, Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_database_pool, require_team_member
from backend.services.crm.evidence_dossier import build_evidence_dossiers
from backend.services.crm.tax_company_pilot import TaxCompanyPilotMap
from backend.services.crm.workspace_ai_snapshots import (
    WorkspaceAiAutoApproveResult,
    WorkspaceAiSnapshotCreate,
    WorkspaceAiSnapshotResponse,
    approve_workspace_ai_snapshot,
    auto_approve_workspace_ai_snapshots,
    create_workspace_ai_snapshot,
    fetch_workspace_ai_review_queue,
)

router = APIRouter(prefix="/api/crm/intelligence", tags=["crm-intelligence"])
logger = logging.getLogger(__name__)

_NLM_CLI_PATH = "/Users/nuzantara/.local/bin/nlm"
_NLM_NOTEBOOK_ID = "5c2c3d90-eed2-4755-86b1-269e637e51e1"
_NLM_TIMEOUT_SECONDS = 30


class WorkspaceAiAutoApproveRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(default=25, ge=1, le=100)


class NlmQueryRequest(BaseModel):
    """Request body for querying NotebookLM about a specific client."""

    question: str = Field(..., min_length=1, max_length=2000)


class NlmCitation(BaseModel):
    """A single citation returned by NotebookLM."""

    source_id: str
    cited_text: str


class NlmQueryResponse(BaseModel):
    """Response from a NotebookLM client query."""

    answer: str
    citations: list[NlmCitation]


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


@router.post(
    "/workspace-ai-snapshots/auto-approve",
    response_model=WorkspaceAiAutoApproveResult,
)
async def auto_approve_workspace_ai_snapshot_drafts(
    payload: WorkspaceAiAutoApproveRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _current_user: dict = Depends(require_team_member),
) -> WorkspaceAiAutoApproveResult:
    """Dry-run or apply policy auto-approval for reviewed Workspace AI stories."""
    return await auto_approve_workspace_ai_snapshots(
        pool,
        limit=payload.limit,
        dry_run=payload.dry_run,
    )


@router.post(
    "/workspace-ai-snapshots/{snapshot_id}/approve", response_model=WorkspaceAiSnapshotResponse
)
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


@router.post("/{client_id}/query", response_model=NlmQueryResponse)
async def query_notebooklm_for_client(
    client_id: int,
    body: NlmQueryRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
    _current_user: dict = Depends(require_team_member),
) -> NlmQueryResponse:
    """Query NotebookLM with CRM context for a specific client.

    Builds an Italian-language prompt that references the client by name and ID,
    then shells out to the NLM CLI to query the CRM notebook.
    """
    # 1. Fetch client name from database
    row: asyncpg.Record | None = await pool.fetchrow(
        "SELECT full_name FROM clients WHERE id = $1",
        client_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found.")

    client_name: str = row["full_name"]

    # 2. Build prompt with CRM context
    prompt_text = (
        f"Con riferimento specifico al cliente '{client_name}' (ID {client_id}) "
        f"e a qualsiasi informazione associata o documenti ad esso collegati "
        f"nel database CRM, rispondi in italiano in modo professionale e preciso "
        f"alla seguente domanda: {body.question}"
    )

    # 3. Run NLM CLI as async subprocess
    try:
        process = await asyncio.create_subprocess_exec(
            _NLM_CLI_PATH,
            "query",
            "notebook",
            _NLM_NOTEBOOK_ID,
            prompt_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=_NLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("NLM CLI timed out after %ds for client %s", _NLM_TIMEOUT_SECONDS, client_id)
        raise HTTPException(
            status_code=503,
            detail="NotebookLM query timed out.",
        )
    except OSError as exc:
        logger.error("Failed to execute NLM CLI: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="NotebookLM service unavailable.",
        ) from exc

    if process.returncode != 0:
        logger.error(
            "NLM CLI exited with code %d for client %s: %s",
            process.returncode,
            client_id,
            stderr.decode(errors="replace").strip(),
        )
        raise HTTPException(
            status_code=503,
            detail="NotebookLM query failed.",
        )

    # 4. Parse JSON stdout
    try:
        result: dict[str, Any] = json.loads(stdout.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to parse NLM CLI output for client %s: %s", client_id, exc)
        raise HTTPException(
            status_code=503,
            detail="Invalid response from NotebookLM.",
        ) from exc

    # 5. Build and return typed response
    citations = [
        NlmCitation(
            source_id=cite.get("source_id", ""),
            cited_text=cite.get("cited_text", ""),
        )
        for cite in result.get("citations", [])
    ]

    return NlmQueryResponse(
        answer=result.get("answer", ""),
        citations=citations,
    )
