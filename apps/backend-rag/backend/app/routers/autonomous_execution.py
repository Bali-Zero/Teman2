"""
Autonomous Execution API Endpoints

POC endpoints for creating, executing, and managing autonomous task plans
with human-in-the-loop approval for critical steps.

Feature flag: ENABLE_AUTONOMOUS_EXECUTION (disabled by default)

Author: Windsurf
Created: 2026-02-09
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.cache import invalidate_cache
from backend.services.rag.autonomous_executor import (
    AutonomousExecutor,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/autonomous-execution",
    tags=["autonomous-execution"],
)

# Singleton executor instance (POC - in-memory state)
_executor: AutonomousExecutor | None = None


def get_executor() -> AutonomousExecutor:
    """Get or create the singleton AutonomousExecutor instance."""
    global _executor
    if _executor is None:
        _executor = AutonomousExecutor()
    return _executor


# ============================================================================
# Request/Response Models
# ============================================================================


class CreatePlanRequest(BaseModel):
    """Request body for creating an execution plan."""

    query: str = Field(..., description="Natural language task description", min_length=5)
    user_email: str = Field(..., description="Email of the requesting user")


class CreatePlanResponse(BaseModel):
    """Response for plan creation."""

    plan_id: str
    task_type: str
    steps_count: int
    plan: dict[str, Any]


class ApprovalRequest(BaseModel):
    """Request body for approving/rejecting a step."""

    approved: bool = Field(..., description="True to approve, False to reject")


class PlanStatusResponse(BaseModel):
    """Response for plan status queries."""

    plan: dict[str, Any]


class PlanListResponse(BaseModel):
    """Response for listing plans."""

    plans: list[dict[str, Any]]
    total: int


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/plans", response_model=CreatePlanResponse)
async def create_execution_plan(request: CreatePlanRequest) -> CreatePlanResponse:
    """
    Generate an execution plan from a natural language task description.

    Supported task types:
    - NPWP registration ("Create NPWP for ...")
    - KITAS application ("Apply for KITAS ...")
    - PT PMA incorporation ("Set up PT PMA ...")
    """
    executor = get_executor()

    try:
        plan = await executor.create_plan(request.query, request.user_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await invalidate_cache("zantara:autonomous_execution:*")
    return CreatePlanResponse(
        plan_id=plan["plan_id"],
        task_type=plan["task_type"],
        steps_count=len(plan["steps"]),
        plan=plan,
    )


@router.post("/plans/{plan_id}/execute", response_model=PlanStatusResponse)
async def execute_plan(plan_id: str) -> PlanStatusResponse:
    """
    Execute a plan step-by-step.

    Safe steps execute automatically. Critical steps pause and
    send a Telegram notification requesting human approval.
    """
    executor = get_executor()

    try:
        plan = await executor.execute_plan(plan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    await invalidate_cache("zantara:autonomous_execution:*")
    return PlanStatusResponse(plan=plan)


@router.get("/plans/{plan_id}", response_model=PlanStatusResponse)
async def get_plan_status(plan_id: str) -> PlanStatusResponse:
    """Get current execution status of a plan."""
    executor = get_executor()
    plan = executor.get_plan_status(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    return PlanStatusResponse(plan=plan)


@router.get("/plans", response_model=PlanListResponse)
async def list_plans(user_email: str | None = None) -> PlanListResponse:
    """List all execution plans, optionally filtered by user email."""
    executor = get_executor()
    plans = executor.list_plans(user_email=user_email)

    return PlanListResponse(plans=plans, total=len(plans))


@router.post("/plans/{plan_id}/steps/{step_id}/approve")
async def approve_step(
    plan_id: str,
    step_id: str,
    request: ApprovalRequest,
) -> dict[str, str]:
    """
    Approve or reject a critical step.

    Called from Telegram webhook callback or admin dashboard.
    """
    executor = get_executor()
    plan = executor.get_plan_status(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    # Verify step exists
    step_ids = [s["step_id"] for s in plan["steps"]]
    if step_id not in step_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Step {step_id} not found in plan {plan_id}",
        )

    executor.record_approval(plan_id, step_id, request.approved)
    action = "approved" if request.approved else "rejected"
    logger.info(f"Step {step_id} in plan {plan_id} {action}")

    await invalidate_cache("zantara:autonomous_execution:*")
    return {"status": action, "plan_id": plan_id, "step_id": step_id}
