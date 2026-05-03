"""
Naga Research Engine — FastAPI Router

Endpoints for the Naga deep-research pipeline:
- POST /api/naga/research      — Start a research session (LIVE — calls real orchestrator)
- GET  /api/naga/session/{id}  — Poll session status (stub — no session store yet)
- GET  /api/naga/claims/search — Search the Claims DB (stub — wired in v1.1)
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
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
async def start_research(request: ResearchRequest, req: Request) -> ResearchResponse:
    """Start a Naga research session using the real orchestrator."""
    session_id = str(uuid.uuid4())
    logger.info(
        "naga research session=%s query=%s tier=%s domain=%s",
        session_id[:8],
        request.query[:80],
        request.tier,
        request.domain,
    )

    try:
        from backend.services.naga.deps import build_deps
        from backend.services.naga.orchestrator import NagaOrchestrator

        # Get db_pool from app state (set during lifespan)
        db_pool = getattr(req.app.state, "db_pool", None)
        deps = build_deps(mode="server", db_pool=db_pool)
        orch = NagaOrchestrator(deps=deps)

        result = await orch.research(
            query=request.query,
            tier=request.tier,
            domain=request.domain,
            mode=request.mode,
            channel=request.channel,
            trusted_mode=request.trusted_mode,
        )

        return ResearchResponse(
            session_id=result.get("session_id", session_id),
            status=result.get("status", "completed"),
            tier=result.get("tier", request.tier),
            domain=result.get("domain", request.domain),
            report=result.get("report_markdown", ""),
            claims_count=result.get("claims_extracted", 0),
            sources_count=len(result.get("search_results", [])),
            avg_confidence=result.get("avg_confidence", 0.0),
            duration_ms=result.get("duration_ms", 0),
            action_items=result.get("action_items", []),
        )

    except Exception as e:
        logger.error("naga research failed: %s", e, exc_info=True)
        return ResearchResponse(
            session_id=session_id,
            status="failed",
            tier=request.tier,
            domain=request.domain,
            report=f"Research failed: {e}",
        )


@router.get("/session/{session_id}", response_model=ResearchResponse)
async def get_session(session_id: str) -> ResearchResponse:
    """Retrieve the status of a research session.

    V1: always returns 404 (no session store yet — wired in v1.1 with PostgreSQL).
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

    V1: returns empty list (wired to PostgreSQL in v1.1).
    """
    logger.info(
        "naga claims search q=%s domain=%s verification=%s limit=%d",
        q,
        domain,
        verification,
        limit,
    )
    return ClaimSearchResponse(claims=[], total=0)
