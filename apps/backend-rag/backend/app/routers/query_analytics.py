"""
Query Analytics API Router
Exposes RAG query analytics endpoints for the dashboard.

Endpoints:
- GET  /api/analytics/query-insights          - Full dashboard summary
- GET  /api/analytics/query-insights/failed    - Top failed queries
- GET  /api/analytics/query-insights/collections - Collection hit rates
- GET  /api/analytics/query-insights/volume    - Query volume over time
- GET  /api/analytics/query-insights/satisfaction - User satisfaction score
- POST /api/analytics/query-insights/feedback  - Record user feedback
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.db.repositories.query_analytics_repository import QueryAnalyticsRepository

router = APIRouter(prefix="/api/analytics/query-insights", tags=["query-analytics"])


def _verify_founder_access(current_user=Depends(get_current_user)) -> Any:
    """Verify that the user has founder or admin level access."""
    if current_user.get("role") not in ["Founder", "admin"]:
        raise HTTPException(
            status_code=403, detail="Access denied. This dashboard is for founders/admins only."
        )
    return current_user


def _get_repo(db_pool=Depends(get_database_pool)) -> QueryAnalyticsRepository:
    """Dependency to get QueryAnalyticsRepository instance."""
    return QueryAnalyticsRepository(db_pool)


# ========== READ ENDPOINTS (Founder-only) ==========


@router.get("")
async def get_query_insights_dashboard(
    days: int = Query(7, ge=1, le=90, description="Lookback period in days"),
    repo: QueryAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """
    Full query analytics dashboard summary.
    Combines failed queries, collection hit rates, volume, and satisfaction.
    """
    try:
        return await repo.get_dashboard_summary(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load query insights: {str(e)}") from e


@router.get("/failed")
async def get_failed_queries(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=90),
    repo: QueryAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """Top N queries that returned 0 chunks."""
    try:
        return await repo.get_failed_queries(limit=limit, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get failed queries: {str(e)}") from e


@router.get("/collections")
async def get_collection_hit_rates(
    days: int = Query(7, ge=1, le=90),
    repo: QueryAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """Collection usage and hit rate stats."""
    try:
        return await repo.get_collection_hit_rates(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get collection hit rates: {str(e)}") from e


@router.get("/volume")
async def get_query_volume(
    granularity: str = Query("hour", regex="^(hour|day)$"),
    days: int = Query(7, ge=1, le=90),
    repo: QueryAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """Query volume over time (hourly or daily buckets)."""
    try:
        return await repo.get_query_volume(granularity=granularity, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get query volume: {str(e)}") from e


@router.get("/satisfaction")
async def get_satisfaction_score(
    days: int = Query(7, ge=1, le=90),
    repo: QueryAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """User satisfaction metrics from thumbs up/down feedback."""
    try:
        return await repo.get_satisfaction_score(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get satisfaction score: {str(e)}") from e


# ========== WRITE ENDPOINT (Any authenticated user) ==========


class FeedbackRequest(BaseModel):
    query_id: str
    feedback: str  # 'thumbs_up' or 'thumbs_down'
    comment: str | None = None


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    repo: QueryAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Record user feedback for a query.
    Any authenticated user can submit feedback on their own queries.
    """
    if body.feedback not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(status_code=400, detail="feedback must be 'thumbs_up' or 'thumbs_down'")

    success = await repo.record_feedback(
        query_id=body.query_id,
        feedback=body.feedback,
        comment=body.comment,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Query not found or feedback already recorded")

    return {"status": "ok", "query_id": body.query_id, "feedback": body.feedback}
