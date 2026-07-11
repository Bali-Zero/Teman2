"""
Unit tests for backend/app/routers/autonomous_execution.py

Regression coverage for a prod 500 on GET /api/v1/autonomous-execution/plans:
AutonomousExecutor.get_plan_status / list_plans / record_approval are all
`async def`, but the router previously called them without `await`, so the
handler operated on a coroutine object instead of the awaited result
(TypeError on `len()`, always-truthy `if not plan`, or a fire-and-forget
approval that never actually persists). The global exception handler turned
that into an opaque "Internal server error" response.

These tests call the router handler functions directly (no TestClient),
with `get_executor()` patched to return an AsyncMock whose async methods
would surface as un-awaited coroutines if the router regressed.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.routers.autonomous_execution import (
    ApprovalRequest,
    approve_step,
    get_plan_status,
    list_plans,
)


def _sample_plan(plan_id: str = "plan_abc123") -> dict:
    return {
        "plan_id": plan_id,
        "user_query": "Create NPWP for John Doe",
        "user_email": "john@example.com",
        "task_type": "npwp_registration",
        "priority": 3,
        "steps": [
            {
                "step_id": "step_0",
                "action": "verify_client_data",
                "description": "Verify client data in CRM",
                "safety_level": "safe",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "error": None,
                "rollback_action": None,
                "retry_count": 0,
                "max_retries": 1,
            },
        ],
        "current_step": 0,
        "overall_status": "pending",
        "created_at": "2026-07-08T00:00:00+00:00",
        "completed_at": None,
        "human_approvals": [],
    }


@pytest.mark.asyncio
class TestListPlans:
    async def test_list_plans_awaits_executor_and_returns_real_list(self) -> None:
        """
        Regression for the live 500: executor.list_plans() is async — the
        router must await it before calling len() on the result. Calling
        len() on an un-awaited coroutine raises TypeError, which is exactly
        what the global exception handler swallowed into "Internal server
        error" in prod.
        """
        mock_executor = AsyncMock()
        mock_executor.list_plans.return_value = [_sample_plan("plan_1"), _sample_plan("plan_2")]

        with patch(
            "backend.app.routers.autonomous_execution.get_executor",
            return_value=mock_executor,
        ):
            response = await list_plans(user_email="john@example.com")

        mock_executor.list_plans.assert_awaited_once_with(user_email="john@example.com")
        assert response.total == 2
        assert len(response.plans) == 2

    async def test_list_plans_empty(self) -> None:
        mock_executor = AsyncMock()
        mock_executor.list_plans.return_value = []

        with patch(
            "backend.app.routers.autonomous_execution.get_executor",
            return_value=mock_executor,
        ):
            response = await list_plans(user_email=None)

        assert response.total == 0
        assert response.plans == []


@pytest.mark.asyncio
class TestGetPlanStatus:
    async def test_get_plan_status_awaits_executor(self) -> None:
        mock_executor = AsyncMock()
        mock_executor.get_plan_status.return_value = _sample_plan("plan_xyz")

        with patch(
            "backend.app.routers.autonomous_execution.get_executor",
            return_value=mock_executor,
        ):
            response = await get_plan_status("plan_xyz")

        mock_executor.get_plan_status.assert_awaited_once_with("plan_xyz")
        assert response.plan["plan_id"] == "plan_xyz"

    async def test_get_plan_status_missing_raises_404(self) -> None:
        from fastapi import HTTPException

        mock_executor = AsyncMock()
        mock_executor.get_plan_status.return_value = None

        with patch(
            "backend.app.routers.autonomous_execution.get_executor",
            return_value=mock_executor,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_plan_status("plan_missing")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestApproveStep:
    async def test_approve_step_awaits_record_approval(self) -> None:
        plan = _sample_plan("plan_appr")
        mock_executor = AsyncMock()
        mock_executor.get_plan_status.return_value = plan

        with (
            patch(
                "backend.app.routers.autonomous_execution.get_executor",
                return_value=mock_executor,
            ),
            patch(
                "backend.app.routers.autonomous_execution.invalidate_cache",
                new=AsyncMock(),
            ),
        ):
            result = await approve_step(
                "plan_appr",
                "step_0",
                ApprovalRequest(approved=True),
            )

        # Regression: record_approval must actually be awaited, not fired
        # and forgotten as a dangling coroutine.
        mock_executor.record_approval.assert_awaited_once_with("plan_appr", "step_0", True)
        assert result == {"status": "approved", "plan_id": "plan_appr", "step_id": "step_0"}
