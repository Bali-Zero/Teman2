"""
Guardian V4 API Router

Provides REST endpoints for Core Guardian decision audit trail and risk scores.
All endpoints require admin access.

Endpoints:
- GET /api/guardian/decisions - Recent decisions with filters
- GET /api/guardian/risk-score - Latest risk score + 7-day trend
- GET /api/guardian/risk-score/history - Full risk score history
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guardian", tags=["guardian", "monitoring"])


# ============================================================================
# Pydantic Models
# ============================================================================


class DecisionRecord(BaseModel):
    id: int
    run_id: str
    timestamp: str
    component: str
    check_type: str
    finding: str
    severity: str
    action_taken: str
    rationale: str | None = None
    rollback_plan: str | None = None
    risk_score: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionsResponse(BaseModel):
    total: int
    hours: int
    decisions: list[DecisionRecord]


class RiskScoreSnapshot(BaseModel):
    timestamp: str
    overall_score: int
    rbac_score: int
    api_contract_score: int
    cache_score: int
    dead_code_score: int
    red_team_survival: float | None = None
    seo_health: float | None = None
    ragas_quality: float | None = None


class RiskScoreResponse(BaseModel):
    current: RiskScoreSnapshot | None
    trend: list[dict[str, Any]]


class RiskScoreHistoryResponse(BaseModel):
    days: int
    scores: list[RiskScoreSnapshot]


# ============================================================================
# Helpers
# ============================================================================


def _require_admin(current_user: dict) -> None:
    email = (current_user.get("email") or "").lower()
    if email not in settings.admin_emails_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


async def _get_pool(request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database pool not available",
        )
    return pool


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/decisions", response_model=DecisionsResponse)
async def get_decisions(
    request: Request,
    last: int = Query(default=24, ge=1, le=720, description="Hours to look back"),
    component: str | None = Query(default=None, description="Filter by component"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
) -> DecisionsResponse:
    """Get recent guardian decisions with optional filters."""
    _require_admin(current_user)
    pool = await _get_pool(request)

    query = """
        SELECT id, run_id, timestamp::text, component, check_type, finding,
               severity, action_taken, rationale, rollback_plan,
               risk_score, metadata
        FROM guardian_decisions
        WHERE timestamp > NOW() - ($1 || ' hours')::interval
    """
    params: list[Any] = [str(last)]
    idx = 2

    if component:
        query += f" AND component = ${idx}"
        params.append(component)
        idx += 1
    if severity:
        query += f" AND severity = ${idx}"
        params.append(severity)
        idx += 1

    query += f" ORDER BY timestamp DESC LIMIT ${idx}"
    params.append(limit)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
    except Exception as e:
        logger.error(f"Failed to query guardian decisions: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

    decisions = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get("metadata"), str):
            r["metadata"] = json.loads(r["metadata"])
        decisions.append(DecisionRecord(**r))

    return DecisionsResponse(total=len(decisions), hours=last, decisions=decisions)


@router.get("/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> RiskScoreResponse:
    """Get latest risk score and 7-day trend."""
    _require_admin(current_user)
    pool = await _get_pool(request)

    try:
        async with pool.acquire() as conn:
            # Latest score
            latest = await conn.fetchrow(
                "SELECT * FROM guardian_risk_scores ORDER BY timestamp DESC LIMIT 1"
            )

            # 7-day trend (daily averages)
            trend_rows = await conn.fetch("""
                SELECT
                    DATE(timestamp)::text as date,
                    ROUND(AVG(overall_score))::int as avg_overall,
                    ROUND(AVG(rbac_score))::int as avg_rbac,
                    ROUND(AVG(api_contract_score))::int as avg_api_contract,
                    ROUND(AVG(cache_score))::int as avg_cache,
                    ROUND(AVG(dead_code_score))::int as avg_dead_code,
                    COUNT(*)::int as samples
                FROM guardian_risk_scores
                WHERE timestamp > NOW() - '7 days'::interval
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """)
    except Exception as e:
        logger.error(f"Failed to query risk scores: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

    current = None
    if latest:
        current = RiskScoreSnapshot(
            timestamp=str(latest["timestamp"]),
            overall_score=latest["overall_score"],
            rbac_score=latest["rbac_score"],
            api_contract_score=latest["api_contract_score"],
            cache_score=latest["cache_score"],
            dead_code_score=latest["dead_code_score"],
            red_team_survival=latest["red_team_survival"],
            seo_health=latest["seo_health"],
            ragas_quality=latest["ragas_quality"],
        )

    return RiskScoreResponse(
        current=current,
        trend=[dict(row) for row in trend_rows],
    )


@router.get("/risk-score/history", response_model=RiskScoreHistoryResponse)
async def get_risk_score_history(
    request: Request,
    days: int = Query(default=30, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
) -> RiskScoreHistoryResponse:
    """Get full risk score history."""
    _require_admin(current_user)
    pool = await _get_pool(request)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT timestamp::text, overall_score, rbac_score,
                       api_contract_score, cache_score, dead_code_score,
                       red_team_survival, seo_health, ragas_quality
                FROM guardian_risk_scores
                WHERE timestamp > NOW() - ($1 || ' days')::interval
                ORDER BY timestamp DESC
                """,
                str(days),
            )
    except Exception as e:
        logger.error(f"Failed to query risk score history: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")

    scores = [RiskScoreSnapshot(**dict(row)) for row in rows]
    return RiskScoreHistoryResponse(days=days, scores=scores)
