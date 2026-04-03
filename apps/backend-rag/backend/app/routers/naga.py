"""
Naga Research Engine — FastAPI Router

Endpoints for the Naga deep-research pipeline:
- POST /api/naga/research      — Start a research session
- GET  /api/naga/session/{id}  — Poll session status
- GET  /api/naga/claims/search — Search the Claims DB

V1: All endpoints return stub/placeholder responses.
Wiring to the real orchestrator is deferred to Task 19.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/naga", tags=["naga"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    """Body for POST /api/naga/research."""

    query: str
    tier: str = "auto"
    domain: str = "auto"
    mode: str = "auto"
    trusted_mode: bool = False
    channel: str = "api"


class ResearchResponse(BaseModel):
    """Unified response for research and session endpoints."""

    session_id: str
    status: str
    tier: str
    domain: str
    report: str = ""
    claims_count: int = 0
    sources_count: int = 0
    avg_confidence: float = 0.0
    duration_ms: int = 0
    action_items: list[dict] = Field(default_factory=list)


class ClaimSearchResponse(BaseModel):
    """Response for GET /api/naga/claims/search."""

    claims: list[dict] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest) -> ResearchResponse:
    """Start a Naga research session.

    V1 stub: returns a placeholder response with status ``not_implemented``.
    The real orchestrator will be wired in Task 19.
    """
    session_id = str(uuid.uuid4())
    logger.info(
        "naga research requested session_id=%s query=%s tier=%s domain=%s",
        session_id,
        request.query[:80],
        request.tier,
        request.domain,
    )
    return ResearchResponse(
        session_id=session_id,
        status="not_implemented",
        tier=request.tier,
        domain=request.domain,
    )


@router.get("/session/{session_id}", response_model=ResearchResponse)
async def get_session(session_id: str) -> ResearchResponse:
    """Retrieve the status of a research session.

    V1 stub: always returns 404 (no session store yet).
    """
    logger.info("naga session lookup session_id=%s", session_id)
    raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/claims/search", response_model=ClaimSearchResponse)
async def search_claims(
    q: str = Query(..., description="Search query for claims"),
    domain: str | None = Query(None, description="Filter by domain"),
    verification: str | None = Query(None, description="Filter by verification status"),
    limit: int = Query(20, ge=1, le=100, description="Max results (1-100)"),
) -> ClaimSearchResponse:
    """Search the Naga Claims DB.

    V1 stub: returns an empty list.
    """
    logger.info(
        "naga claims search q=%s domain=%s verification=%s limit=%d",
        q,
        domain,
        verification,
        limit,
    )
    return ClaimSearchResponse(claims=[], total=0)
