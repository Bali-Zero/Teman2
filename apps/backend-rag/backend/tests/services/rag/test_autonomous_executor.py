"""
Test suite for Autonomous Task Executor (Phase 7 POC)

Tests plan generation, step execution, approval flow, rollback,
and edge cases for the human-in-the-loop autonomous executor.

Author: Windsurf (QA Engineer)
Created: 2026-02-09
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.rag.autonomous_executor import (
    TASK_TEMPLATES,
    AutonomousExecutor,
    ExecutionStatus,
    StepSafety,
)


@pytest.fixture
def executor():
    """Create an AutonomousExecutor with no external dependencies."""
    return AutonomousExecutor()


@pytest.fixture
def executor_with_crm():
    """Create an AutonomousExecutor with a mock CRM service."""
    crm = AsyncMock()
    crm.search_clients = AsyncMock(return_value=[{"email": "test@example.com"}])
    return AutonomousExecutor(crm_service=crm)


@pytest.fixture
def executor_with_telegram():
    """Create an AutonomousExecutor with a mock Telegram service."""
    telegram = AsyncMock()
    telegram.send_message = AsyncMock()
    return AutonomousExecutor(telegram_service=telegram)


# ============================================================================
# Plan Generation Tests
# ============================================================================


class TestPlanGeneration:
    """Test execution plan creation from user queries."""

    @pytest.mark.asyncio
    async def test_generate_npwp_plan(self, executor):
        """NPWP query generates a 5-step plan with correct structure."""
        plan = await executor.create_plan("Create NPWP for test@example.com", "test@example.com")

        assert plan["plan_id"].startswith("plan_")
        assert plan["task_type"] == "npwp_registration"
        assert plan["user_email"] == "test@example.com"
        assert plan["overall_status"] == ExecutionStatus.PENDING
        assert len(plan["steps"]) == 5
        assert plan["steps"][0]["action"] == "verify_client_data"
        assert plan["steps"][3]["action"] == "submit_to_djp"
        assert plan["completed_at"] is None

    @pytest.mark.asyncio
    async def test_generate_kitas_plan(self, executor):
        """KITAS query generates a 6-step plan."""
        plan = await executor.create_plan(
            "Apply for KITAS work permit for client@bali.com", "client@bali.com",
        )

        assert plan["task_type"] == "kitas_application"
        assert len(plan["steps"]) == 6
        assert plan["steps"][3]["action"] == "submit_to_immigration"
        assert plan["steps"][4]["action"] == "schedule_biometrics"

    @pytest.mark.asyncio
    async def test_generate_pt_pma_plan(self, executor):
        """PT PMA query generates a 6-step plan."""
        plan = await executor.create_plan(
            "Set up PT PMA for investor@company.com", "investor@company.com",
        )

        assert plan["task_type"] == "pt_pma_incorporation"
        assert len(plan["steps"]) == 6
        assert plan["steps"][3]["safety_level"] == StepSafety.IRREVERSIBLE

    @pytest.mark.asyncio
    async def test_unknown_task_raises_error(self, executor):
        """Unknown task type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown task type"):
            await executor.create_plan("Order pizza for the team", "hungry@example.com")

    @pytest.mark.asyncio
    async def test_plan_stored_in_memory(self, executor):
        """Created plan is stored and retrievable."""
        plan = await executor.create_plan("Create NPWP for test@example.com", "test@example.com")

        retrieved = await executor.get_plan_status(plan["plan_id"])
        assert retrieved is not None
        assert retrieved["plan_id"] == plan["plan_id"]

    @pytest.mark.asyncio
    async def test_plan_has_unique_id(self, executor):
        """Each plan gets a unique ID."""
        plan1 = await executor.create_plan("Create NPWP for a@b.com", "a@b.com")
        plan2 = await executor.create_plan("Create NPWP for c@d.com", "c@d.com")

        assert plan1["plan_id"] != plan2["plan_id"]


# ============================================================================
# Task Classification Tests
# ============================================================================


class TestTaskClassification:
    """Test query-to-task-type classification."""

    def test_classify_npwp(self, executor):
        assert executor.classify_task("Create NPWP for client") == "npwp_registration"

    def test_classify_kitas(self, executor):
        assert executor.classify_task("Apply for KITAS") == "kitas_application"

    def test_classify_work_permit(self, executor):
        assert executor.classify_task("Get a work permit") == "kitas_application"

    def test_classify_pt_pma(self, executor):
        assert executor.classify_task("Set up PT PMA company") == "pt_pma_incorporation"

    def test_classify_incorporate(self, executor):
        assert executor.classify_task("Incorporate a new company") == "pt_pma_incorporation"

    def test_classify_unknown(self, executor):
        assert executor.classify_task("What is the weather?") == "general_task"


# ============================================================================
# Step Safety Tests
# ============================================================================


class TestStepSafety:
    """Test safety level assignments on generated steps."""

    @pytest.mark.asyncio
    async def test_npwp_safe_steps(self, executor):
        """First 3 NPWP steps are SAFE."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        for i in range(3):
            assert plan["steps"][i]["safety_level"] == StepSafety.SAFE

    @pytest.mark.asyncio
    async def test_npwp_critical_step(self, executor):
        """NPWP submit_to_djp step is CRITICAL."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        assert plan["steps"][3]["safety_level"] == StepSafety.CRITICAL
        assert plan["steps"][3]["rollback_action"] == "cancel_djp_submission"

    @pytest.mark.asyncio
    async def test_pt_pma_irreversible_step(self, executor):
        """PT PMA submit_to_ahu step is IRREVERSIBLE."""
        plan = await executor.create_plan("Set up PT PMA for t@t.com", "t@t.com")

        ahu_step = next(s for s in plan["steps"] if s["action"] == "submit_to_ahu")
        assert ahu_step["safety_level"] == StepSafety.IRREVERSIBLE


# ============================================================================
# Execution Tests
# ============================================================================


class TestStepExecution:
    """Test step-by-step plan execution."""

    @pytest.mark.asyncio
    async def test_execute_safe_steps_auto(self, executor):
        """Safe steps execute without requiring approval."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        # Pre-approve the critical step so execution completes
        executor._approvals[f"{plan['plan_id']}_step_3"] = True

        result = await executor.execute_plan(plan["plan_id"])

        assert result["overall_status"] == ExecutionStatus.COMPLETED
        assert result["completed_at"] is not None
        # All steps should be completed
        for step in result["steps"]:
            assert step["status"] == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_pause_at_critical_step(self, executor):
        """Execution pauses at critical step when not pre-approved, then times out."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        # Don't pre-approve - use a very short timeout so test doesn't hang
        with patch.object(executor, "_wait_for_approval", return_value=False):
            result = await executor.execute_plan(plan["plan_id"])

        # Should fail because approval was not granted
        assert result["overall_status"] == ExecutionStatus.FAILED
        assert result["steps"][3]["error"] == "Human rejected this step"

    @pytest.mark.asyncio
    async def test_execute_plan_not_found(self, executor):
        """Executing a non-existent plan raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            await executor.execute_plan("plan_nonexistent")


# ============================================================================
# Approval Flow Tests
# ============================================================================


class TestApprovalFlow:
    """Test human-in-the-loop approval mechanism."""

    @pytest.mark.asyncio
    async def test_record_approval_true(self, executor):
        """Recording approval sets the approval flag."""
        await executor.record_approval("plan_1", "step_3", True)
        assert executor._approvals["plan_1_step_3"] is True

    @pytest.mark.asyncio
    async def test_record_approval_false(self, executor):
        """Recording rejection sets the approval flag to False."""
        await executor.record_approval("plan_1", "step_3", False)
        assert executor._approvals["plan_1_step_3"] is False

    @pytest.mark.asyncio
    async def test_approval_recorded_in_plan(self, executor):
        """Approved steps are tracked in plan's human_approvals list."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")
        executor._approvals[f"{plan['plan_id']}_step_3"] = True

        result = await executor.execute_plan(plan["plan_id"])

        assert len(result["human_approvals"]) == 1
        assert result["human_approvals"][0]["step_id"] == "step_3"
        assert result["human_approvals"][0]["approved"] is True

    @pytest.mark.asyncio
    async def test_telegram_notification_sent(self, executor_with_telegram):
        """Telegram notification is sent when approval is requested."""
        executor = executor_with_telegram
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        # Pre-approve so execution completes
        executor._approvals[f"{plan['plan_id']}_step_3"] = True

        await executor.execute_plan(plan["plan_id"])

        # Telegram send_message should have been called for the critical step
        executor.telegram_service.send_message.assert_called_once()
        call_kwargs = executor.telegram_service.send_message.call_args
        assert "Approval Required" in str(call_kwargs)


# ============================================================================
# Rollback Tests
# ============================================================================


class TestRollback:
    """Test rollback mechanism on step failure."""

    @pytest.mark.asyncio
    async def test_rollback_on_step_failure(self, executor):
        """Failed step triggers rollback of completed steps."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        # Make step 2 (prepare_npwp_documents) fail
        original_execute = executor._execute_step

        async def failing_execute(step, user_email):
            if step["action"] == "prepare_npwp_documents":
                raise RuntimeError("Document preparation failed")
            return await original_execute(step, user_email)

        with patch.object(executor, "_execute_step", side_effect=failing_execute):
            result = await executor.execute_plan(plan["plan_id"])

        assert result["overall_status"] == ExecutionStatus.ROLLED_BACK
        assert result["steps"][2]["status"] == ExecutionStatus.FAILED
        assert result["steps"][2]["error"] == "Document preparation failed"

    @pytest.mark.asyncio
    async def test_rollback_skips_steps_without_rollback_action(self, executor):
        """Rollback only affects steps that have a rollback_action defined."""
        plan = await executor.create_plan("Create NPWP for t@t.com", "t@t.com")

        # First 3 steps have no rollback_action, so rollback is a no-op
        # Manually complete first 2 steps then fail step 2
        plan["steps"][0]["status"] = ExecutionStatus.COMPLETED
        plan["steps"][1]["status"] = ExecutionStatus.COMPLETED

        await executor._rollback_plan(plan, until_step=1)

        # Steps without rollback_action stay COMPLETED (not rolled back)
        assert plan["steps"][0]["status"] == ExecutionStatus.COMPLETED
        assert plan["steps"][1]["status"] == ExecutionStatus.COMPLETED


# ============================================================================
# Plan Listing Tests
# ============================================================================


class TestPlanListing:
    """Test plan listing and filtering."""

    @pytest.mark.asyncio
    async def test_list_all_plans(self, executor):
        """List all plans returns all created plans."""
        await executor.create_plan("Create NPWP for a@b.com", "a@b.com")
        await executor.create_plan("Apply for KITAS for c@d.com", "c@d.com")

        plans = await executor.list_plans()
        assert len(plans) == 2

    @pytest.mark.asyncio
    async def test_list_plans_filtered_by_email(self, executor):
        """List plans filtered by user email."""
        await executor.create_plan("Create NPWP for a@b.com", "a@b.com")
        await executor.create_plan("Apply for KITAS for c@d.com", "c@d.com")

        plans = await executor.list_plans(user_email="a@b.com")
        assert len(plans) == 1
        assert plans[0]["user_email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_plan(self, executor):
        """Getting a non-existent plan returns None."""
        assert await executor.get_plan_status("plan_nonexistent") is None


# ============================================================================
# Template Coverage Tests
# ============================================================================


class TestTaskTemplates:
    """Test that all task templates are well-formed."""

    def test_all_templates_have_steps(self):
        """Every template has at least one step."""
        for task_type, steps in TASK_TEMPLATES.items():
            assert len(steps) > 0, f"Template {task_type} has no steps"

    def test_all_steps_have_required_fields(self):
        """Every step template has action, description, safety_level."""
        required_fields = {"action", "description", "safety_level", "rollback_action"}
        for task_type, steps in TASK_TEMPLATES.items():
            for i, step in enumerate(steps):
                for field in required_fields:
                    assert field in step, f"Template {task_type} step {i} missing '{field}'"

    def test_critical_steps_have_rollback(self):
        """Critical and irreversible steps must have a rollback_action."""
        for task_type, steps in TASK_TEMPLATES.items():
            for i, step in enumerate(steps):
                if step["safety_level"] in (StepSafety.CRITICAL, StepSafety.IRREVERSIBLE):
                    assert step["rollback_action"], (
                        f"Template {task_type} step {i} ({step['action']}) is "
                        f"{step['safety_level']} but has no rollback_action"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
