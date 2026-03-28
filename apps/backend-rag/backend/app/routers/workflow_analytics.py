"""
Workflow Analytics API Router
Exposes LangGraph workflow tracking and feedback endpoints.

Endpoints:
- GET  /api/v1/analytics/workflow-dashboard       - Full workflow analytics dashboard
- GET  /api/v1/analytics/workflow-dashboard/top    - Top generated workflows
- GET  /api/v1/analytics/workflow-dashboard/volume - Workflow volume over time
- POST /api/v1/analytics/workflow-feedback         - Record user feedback on a workflow
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.db.repositories.workflow_analytics_repository import WorkflowAnalyticsRepository

router = APIRouter(prefix="/api/v1/analytics", tags=["workflow-analytics"])


def _verify_founder_access(current_user=Depends(get_current_user)) -> Any:
    """Verify that the user has founder or admin level access."""
    if current_user.get("role") not in ["Founder", "admin"]:
        raise HTTPException(
            status_code=403, detail="Access denied. This dashboard is for founders/admins only."
        )
    return current_user


def _get_repo(db_pool=Depends(get_database_pool)) -> WorkflowAnalyticsRepository:
    """Dependency to get WorkflowAnalyticsRepository instance."""
    return WorkflowAnalyticsRepository(db_pool)


# ========== READ ENDPOINTS (Founder-only) ==========


@router.get("/workflow-dashboard")
async def get_workflow_dashboard(
    days: int = Query(7, ge=1, le=90, description="Lookback period in days"),
    repo: WorkflowAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """
    Full workflow analytics dashboard summary.
    Combines follow rate, top workflows, and volume data.
    """
    try:
        return await repo.get_dashboard_summary(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load workflow dashboard: {str(e)}") from e


@router.get("/workflow-dashboard/top")
async def get_top_workflows(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=90),
    repo: WorkflowAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """Top N most generated workflow types."""
    try:
        return await repo.get_top_workflows(limit=limit, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get top workflows: {str(e)}") from e


@router.get("/workflow-dashboard/volume")
async def get_workflow_volume(
    granularity: str = Query("hour", pattern="^(hour|day)$"),
    days: int = Query(7, ge=1, le=90),
    repo: WorkflowAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(_verify_founder_access),
) -> Any:
    """Workflow generation volume over time (hourly or daily buckets)."""
    try:
        return await repo.get_workflow_volume(granularity=granularity, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow volume: {str(e)}") from e


# ========== WRITE ENDPOINT (Any authenticated user) ==========


class WorkflowFeedbackRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow identifier (e.g. wf-abc123)")
    followed: bool = Field(..., description="Whether the user followed the workflow")
    feedback_score: float | None = Field(None, ge=0.0, le=5.0, description="Score from 0.0 to 5.0")
    comment: str | None = Field(None, max_length=1000, description="Optional feedback text")


@router.post("/workflow-feedback")
async def submit_workflow_feedback(
    body: WorkflowFeedbackRequest,
    repo: WorkflowAnalyticsRepository = Depends(_get_repo),
    current_user=Depends(get_current_user),
) -> dict[str, Any]:
    """
    Record user feedback for a generated workflow.
    Any authenticated user can submit feedback.
    """
    success = await repo.record_feedback(
        workflow_id=body.workflow_id,
        followed=body.followed,
        feedback_score=body.feedback_score,
        feedback_comment=body.comment,
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found or feedback could not be recorded",
        )

    return {
        "status": "ok",
        "workflow_id": body.workflow_id,
        "followed": body.followed,
        "feedback_score": body.feedback_score,
    }
