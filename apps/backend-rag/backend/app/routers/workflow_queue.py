"""
Workflow Queue API — enqueue/status endpoints for MCP chain dispatch.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.dependencies import get_current_user
from backend.services.workflow.executor import get_registered_chains

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class EnqueueRequest(BaseModel):
    chain_id: str
    payload: dict[str, Any] = {}
    thread_id: str | None = None


class EnqueueResponse(BaseModel):
    job_id: str
    thread_id: str
    chain_id: str
    status: str = "pending"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    chain_id: str
    thread_id: str | None
    retry_count: int
    error_msg: str | None


@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue_workflow_job(
    request: Request,
    body: EnqueueRequest,
    _user: dict = Depends(get_current_user),
) -> EnqueueResponse:
    """
    Enqueue a workflow chain for async execution.
    Returns job_id and thread_id for status polling and LangGraph resume.
    """
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database pool not ready")

    registered = get_registered_chains()
    if body.chain_id not in registered:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown chain_id '{body.chain_id}'. Available: {registered}",
        )

    from backend.services.workflow.queue import enqueue_workflow

    thread_id = body.thread_id or f"{body.chain_id}:{uuid.uuid4()}"
    job_id = await enqueue_workflow(
        db_pool=db_pool,
        chain_id=body.chain_id,
        payload=body.payload,
        thread_id=thread_id,
    )

    return EnqueueResponse(
        job_id=job_id,
        thread_id=thread_id,
        chain_id=body.chain_id,
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    request: Request,
    _user: dict = Depends(get_current_user),
) -> JobStatusResponse:
    """Poll job status by job_id."""
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database pool not ready")

    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    row = await db_pool.fetchrow(
        "SELECT id, status, chain_id, thread_id, retry_count, error_msg "
        "FROM workflow_jobs WHERE id = $1",
        job_uuid,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=str(row["id"]),
        status=row["status"],
        chain_id=row["chain_id"],
        thread_id=row["thread_id"],
        retry_count=row["retry_count"],
        error_msg=row["error_msg"],
    )


@router.get("/chains")
async def list_chains(_user: dict = Depends(get_current_user)) -> dict[str, list[str]]:
    """List all registered workflow chain IDs."""
    return {"chains": get_registered_chains()}
