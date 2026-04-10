"""
Unit tests for backend/services/rag/autonomous_executor.py

Covers: AutonomousExecutor init, classify_task, generate_steps, create_plan,
        get_plan_status, list_plans, execute_plan, approval flow, rollback,
        dequeue_next, _make_step, _backoff_delay, persistent & in-memory modes.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.autonomous_executor import (
    AutonomousExecutor,
    ExecutionPlan,
    ExecutionStatus,
    ExecutionStep,
    StepSafety,
    TASK_PRIORITY,
    TASK_TEMPLATES,
    _backoff_delay,
    _make_step,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def executor():
    """In-memory executor (no DB)."""
    return AutonomousExecutor()


@pytest.fixture
def executor_with_crm():
    """Executor with CRM service."""
    crm = MagicMock()
    crm.search_clients = AsyncMock(return_value=[{"email": "user@test.com"}])
    return AutonomousExecutor(crm_service=crm)


@pytest.fixture
def executor_with_telegram():
    """Executor with Telegram service."""
    telegram = MagicMock()
    telegram.send_message = AsyncMock()
    return AutonomousExecutor(telegram_service=telegram)


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg Pool for persistent executor."""
    pool = MagicMock()
    conn = AsyncMock()

    # Transaction context manager
    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=None)
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_cm)

    # Connection context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def persistent_executor(mock_db_pool):
    """Persistent executor with DB pool."""
    return AutonomousExecutor(db_pool=mock_db_pool)


# ============================================================================
# TESTS: _make_step
# ============================================================================


class TestMakeStep:
    def test_make_step_basic(self):
        template = {
            "action": "verify_client_data",
            "description": "Verify client data",
            "safety_level": StepSafety.SAFE,
            "rollback_action": "",
        }
        step = _make_step(template, 0)
        assert step["step_id"] == "step_0"
        assert step["action"] == "verify_client_data"
        assert step["status"] == ExecutionStatus.PENDING
        assert step["rollback_action"] is None  # Empty string becomes None
        assert step["retry_count"] == 0

    def test_make_step_with_rollback(self):
        template = {
            "action": "submit_to_djp",
            "description": "Submit to DJP",
            "safety_level": StepSafety.CRITICAL,
            "rollback_action": "cancel_djp_submission",
        }
        step = _make_step(template, 3)
        assert step["step_id"] == "step_3"
        assert step["rollback_action"] == "cancel_djp_submission"
        assert step["max_retries"] == 3  # From RETRY_CONFIG

    def test_make_step_custom_retry(self):
        template = {
            "action": "submit_to_ahu",
            "description": "Submit to AHU",
            "safety_level": StepSafety.IRREVERSIBLE,
            "rollback_action": "request_ahu_cancellation",
        }
        step = _make_step(template, 0)
        assert step["max_retries"] == 2  # From RETRY_CONFIG for submit_to_ahu


# ============================================================================
# TESTS: _backoff_delay
# ============================================================================


class TestBackoffDelay:
    def test_first_attempt(self):
        delay = _backoff_delay(0, base_delay_s=2)
        # 2 * (2^0) + jitter = 2 + (0..0.6)
        assert 2 <= delay <= 2.6

    def test_second_attempt(self):
        delay = _backoff_delay(1, base_delay_s=2)
        # 2 * (2^1) + jitter = 4 + (0..1.2)
        assert 4 <= delay <= 5.2

    def test_cap_at_300(self):
        delay = _backoff_delay(10, base_delay_s=2)
        assert delay <= 300


# ============================================================================
# TESTS: AutonomousExecutor Properties
# ============================================================================


class TestExecutorProperties:
    def test_persistent_with_pool(self, persistent_executor):
        assert persistent_executor._persistent is True

    def test_persistent_without_pool(self, executor):
        assert executor._persistent is False

    def test_plans_property(self, executor):
        assert executor.plans == {}

    def test_approvals_property(self, executor):
        assert executor._approvals == {}


# ============================================================================
# TESTS: classify_task
# ============================================================================


class TestClassifyTask:
    def test_npwp(self, executor):
        assert executor.classify_task("I need NPWP registration") == "npwp_registration"

    def test_kitas(self, executor):
        assert executor.classify_task("Apply for KITAS") == "kitas_application"
        assert executor.classify_task("I need a work permit") == "kitas_application"
        assert executor.classify_task("Stay permit renewal") == "kitas_application"

    def test_pt_pma(self, executor):
        assert executor.classify_task("Setup PT PMA company") == "pt_pma_incorporation"
        assert executor.classify_task("I want to incorporate") == "pt_pma_incorporation"
        assert executor.classify_task("company setup process") == "pt_pma_incorporation"

    def test_general(self, executor):
        assert executor.classify_task("How do I pay taxes?") == "general_task"

    def test_case_insensitive(self, executor):
        assert executor.classify_task("NPWP REGISTRATION") == "npwp_registration"


# ============================================================================
# TESTS: generate_steps
# ============================================================================


class TestGenerateSteps:
    def test_npwp_steps(self, executor):
        steps = executor.generate_steps("npwp_registration")
        assert len(steps) == 5
        assert steps[0]["action"] == "verify_client_data"

    def test_kitas_steps(self, executor):
        steps = executor.generate_steps("kitas_application")
        assert len(steps) == 6

    def test_pt_pma_steps(self, executor):
        steps = executor.generate_steps("pt_pma_incorporation")
        assert len(steps) == 6

    def test_unknown_task_empty(self, executor):
        steps = executor.generate_steps("unknown_task")
        assert len(steps) == 0


# ============================================================================
# TESTS: create_plan — in-memory
# ============================================================================


class TestCreatePlanInMemory:
    @pytest.mark.asyncio
    async def test_create_plan_npwp(self, executor):
        plan = await executor.create_plan(
            query="Register NPWP for me",
            user_email="user@test.com",
        )

        assert plan["plan_id"].startswith("plan_")
        assert plan["task_type"] == "npwp_registration"
        assert plan["priority"] == TASK_PRIORITY["npwp_registration"]
        assert len(plan["steps"]) == 5
        assert plan["overall_status"] == ExecutionStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_plan_custom_priority(self, executor):
        plan = await executor.create_plan(
            query="NPWP registration",
            user_email="user@test.com",
            priority=99,
        )
        assert plan["priority"] == 99

    @pytest.mark.asyncio
    async def test_create_plan_unknown_task_raises(self, executor):
        with pytest.raises(ValueError, match="Unknown task type"):
            await executor.create_plan(
                query="What is the weather?",
                user_email="user@test.com",
            )

    @pytest.mark.asyncio
    async def test_create_plan_stored_in_memory(self, executor):
        plan = await executor.create_plan(
            query="NPWP registration",
            user_email="user@test.com",
        )
        assert plan["plan_id"] in executor.plans


# ============================================================================
# TESTS: create_plan — persistent
# ============================================================================


class TestCreatePlanPersistent:
    @pytest.mark.asyncio
    async def test_create_plan_calls_persist(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.execute = AsyncMock()

        plan = await persistent_executor.create_plan(
            query="Register NPWP",
            user_email="user@test.com",
        )

        assert plan["plan_id"].startswith("plan_")
        # Verify DB calls were made
        assert mock_db_pool._mock_conn.execute.call_count > 0


# ============================================================================
# TESTS: get_plan_status
# ============================================================================


class TestGetPlanStatus:
    @pytest.mark.asyncio
    async def test_get_plan_in_memory(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        result = await executor.get_plan_status(plan["plan_id"])
        assert result is not None
        assert result["plan_id"] == plan["plan_id"]

    @pytest.mark.asyncio
    async def test_get_plan_not_found(self, executor):
        result = await executor.get_plan_status("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_plan_persistent(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await persistent_executor.get_plan_status("plan_abc")
        assert result is None


# ============================================================================
# TESTS: list_plans
# ============================================================================


class TestListPlans:
    @pytest.mark.asyncio
    async def test_list_all_in_memory(self, executor):
        await executor.create_plan("NPWP registration", "user@test.com")
        await executor.create_plan("Apply for KITAS", "user2@test.com")

        plans = await executor.list_plans()
        assert len(plans) == 2

    @pytest.mark.asyncio
    async def test_list_by_email(self, executor):
        await executor.create_plan("NPWP registration", "user@test.com")
        await executor.create_plan("Apply for KITAS", "other@test.com")

        plans = await executor.list_plans(user_email="user@test.com")
        assert len(plans) == 1
        assert plans[0]["user_email"] == "user@test.com"

    @pytest.mark.asyncio
    async def test_list_by_status(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        plans = await executor.list_plans(status=ExecutionStatus.PENDING)
        assert len(plans) == 1

    @pytest.mark.asyncio
    async def test_list_with_limit(self, executor):
        for i in range(5):
            await executor.create_plan("NPWP registration", f"user{i}@test.com")

        plans = await executor.list_plans(limit=3)
        assert len(plans) == 3


# ============================================================================
# TESTS: execute_plan — in-memory
# ============================================================================


class TestExecutePlan:
    @pytest.mark.asyncio
    async def test_execute_all_safe_steps(self, executor):
        """Execute plan with only safe steps (no approval needed)."""
        plan = await executor.create_plan("NPWP registration", "user@test.com")

        # Mark all steps as safe
        for step in plan["steps"]:
            step["safety_level"] = StepSafety.SAFE

        result = await executor.execute_plan(plan["plan_id"])
        assert result["overall_status"] == ExecutionStatus.COMPLETED
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_execute_plan_not_found(self, executor):
        with pytest.raises(KeyError, match="not found"):
            await executor.execute_plan("nonexistent")

    @pytest.mark.asyncio
    async def test_execute_with_approval_rejected(self, executor_with_telegram):
        """Critical step requires approval — rejected."""
        plan = await executor_with_telegram.create_plan(
            "NPWP registration", "user@test.com",
        )

        # Pre-reject the critical step
        for step in plan["steps"]:
            if step["safety_level"] in (StepSafety.CRITICAL, StepSafety.IRREVERSIBLE):
                approval_key = f"{plan['plan_id']}_{step['step_id']}"
                executor_with_telegram._memory_approvals[approval_key] = False
                break

        result = await executor_with_telegram.execute_plan(plan["plan_id"])
        assert result["overall_status"] == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_with_approval_approved(self, executor_with_telegram):
        """Critical step requires approval — approved."""
        plan = await executor_with_telegram.create_plan(
            "NPWP registration", "user@test.com",
        )

        # Pre-approve ALL critical steps
        for step in plan["steps"]:
            if step["safety_level"] in (StepSafety.CRITICAL, StepSafety.IRREVERSIBLE):
                approval_key = f"{plan['plan_id']}_{step['step_id']}"
                executor_with_telegram._memory_approvals[approval_key] = True

        result = await executor_with_telegram.execute_plan(plan["plan_id"])
        assert result["overall_status"] == ExecutionStatus.COMPLETED


# ============================================================================
# TESTS: _execute_step
# ============================================================================


class TestExecuteStep:
    @pytest.mark.asyncio
    async def test_verify_client_data_with_crm(self, executor_with_crm):
        step = _make_step(
            {"action": "verify_client_data", "description": "verify", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        await executor_with_crm._execute_step(step, "user@test.com")
        executor_with_crm.crm_service.search_clients.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_verify_client_data_not_found(self, executor_with_crm):
        executor_with_crm.crm_service.search_clients = AsyncMock(return_value=[])
        step = _make_step(
            {"action": "verify_client_data", "description": "verify", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        with pytest.raises(ValueError, match="not found in CRM"):
            await executor_with_crm._execute_step(step, "user@test.com")

    @pytest.mark.asyncio
    async def test_verify_client_data_no_crm(self, executor):
        step = _make_step(
            {"action": "verify_client_data", "description": "verify", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        # Should not raise — just logs
        await executor._execute_step(step, "user@test.com")

    @pytest.mark.asyncio
    async def test_eligibility_check(self, executor):
        step = _make_step(
            {"action": "check_npwp_eligibility", "description": "check", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        await executor._execute_step(step, "user@test.com")

    @pytest.mark.asyncio
    async def test_prepare_documents(self, executor):
        step = _make_step(
            {"action": "prepare_npwp_documents", "description": "prepare", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        await executor._execute_step(step, "user@test.com")

    @pytest.mark.asyncio
    async def test_submit_critical(self, executor):
        step = _make_step(
            {"action": "submit_to_djp", "description": "submit", "safety_level": StepSafety.CRITICAL, "rollback_action": "cancel"},
            0,
        )
        await executor._execute_step(step, "user@test.com")

    @pytest.mark.asyncio
    async def test_track_status(self, executor):
        step = _make_step(
            {"action": "track_npwp_status", "description": "track", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        await executor._execute_step(step, "user@test.com")

    @pytest.mark.asyncio
    async def test_unknown_action(self, executor):
        step = _make_step(
            {"action": "unknown_action", "description": "unknown", "safety_level": StepSafety.SAFE, "rollback_action": ""},
            0,
        )
        # Should just log warning, not raise
        await executor._execute_step(step, "user@test.com")


# ============================================================================
# TESTS: _execute_step_with_retry
# ============================================================================


class TestExecuteStepWithRetry:
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, executor):
        """Step fails then succeeds on retry."""
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        step = plan["steps"][0]

        call_count = 0
        original_execute = executor._execute_step

        async def flaky_execute(s, email):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient error")
            return await original_execute(s, email)

        executor._execute_step = flaky_execute

        with patch("backend.services.rag.autonomous_executor.asyncio.sleep", new_callable=AsyncMock):
            success = await executor._execute_step_with_retry(plan, step)

        assert success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, executor):
        """Step fails on all retries."""
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        step = plan["steps"][0]

        executor._execute_step = AsyncMock(side_effect=Exception("permanent error"))

        with patch("backend.services.rag.autonomous_executor.asyncio.sleep", new_callable=AsyncMock):
            success = await executor._execute_step_with_retry(plan, step)

        assert success is False
        assert step["status"] == ExecutionStatus.FAILED


# ============================================================================
# TESTS: Approval flow
# ============================================================================


class TestApprovalFlow:
    @pytest.mark.asyncio
    async def test_record_approval(self, executor):
        await executor.record_approval("plan_1", "step_0", True)
        assert executor._approvals["plan_1_step_0"] is True

    @pytest.mark.asyncio
    async def test_record_rejection(self, executor):
        await executor.record_approval("plan_1", "step_0", False)
        assert executor._approvals["plan_1_step_0"] is False

    @pytest.mark.asyncio
    async def test_record_approval_persistent(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.execute = AsyncMock()
        await persistent_executor.record_approval(
            "plan_1", "step_0", True,
            approver_email="admin@test.com",
            reason="Looks good",
        )
        mock_db_pool._mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_request_approval_with_telegram(self, executor_with_telegram):
        plan = await executor_with_telegram.create_plan("NPWP registration", "user@test.com")
        step = plan["steps"][0]

        await executor_with_telegram._request_approval(plan, step)
        executor_with_telegram.telegram_service.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_request_approval_telegram_fails(self, executor_with_telegram):
        executor_with_telegram.telegram_service.send_message = AsyncMock(
            side_effect=Exception("Telegram error"),
        )
        plan = await executor_with_telegram.create_plan("NPWP registration", "user@test.com")
        step = plan["steps"][0]

        # Should not raise
        await executor_with_telegram._request_approval(plan, step)

    @pytest.mark.asyncio
    async def test_request_approval_no_telegram(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        step = plan["steps"][0]

        # Should not raise
        await executor._request_approval(plan, step)

    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self, executor):
        """Approval times out."""
        with patch(
            "backend.services.rag.autonomous_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._wait_for_approval("plan_1", "step_0", timeout=0)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_approval_approved(self, executor):
        """Approval found immediately."""
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        executor._memory_approvals[f"{plan['plan_id']}_step_0"] = True

        with patch(
            "backend.services.rag.autonomous_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._wait_for_approval(plan["plan_id"], "step_0")
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_approval_rejected(self, executor):
        """Approval found but rejected."""
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        executor._memory_approvals[f"{plan['plan_id']}_step_0"] = False

        with patch(
            "backend.services.rag.autonomous_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await executor._wait_for_approval(plan["plan_id"], "step_0")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_approval_db(self, persistent_executor, mock_db_pool):
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"approved": True}[k]
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=row)

        result = await persistent_executor._check_approval_db("plan_1", "step_0")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_approval_db_not_found(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await persistent_executor._check_approval_db("plan_1", "step_0")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_approval_db_in_memory_mode(self, executor):
        result = await executor._check_approval_db("plan_1", "step_0")
        assert result is None


# ============================================================================
# TESTS: Rollback
# ============================================================================


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_completed_steps(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")

        # Mark first two steps as completed with rollback
        plan["steps"][0]["status"] = ExecutionStatus.COMPLETED
        plan["steps"][0]["rollback_action"] = "undo_step_0"
        plan["steps"][1]["status"] = ExecutionStatus.COMPLETED
        plan["steps"][1]["rollback_action"] = "undo_step_1"

        await executor._rollback_plan(plan, until_step=1)

        assert plan["steps"][0]["status"] == ExecutionStatus.ROLLED_BACK
        assert plan["steps"][1]["status"] == ExecutionStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_rollback_skips_non_completed(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")

        plan["steps"][0]["status"] = ExecutionStatus.COMPLETED
        plan["steps"][0]["rollback_action"] = "undo_step_0"
        plan["steps"][1]["status"] = ExecutionStatus.PENDING

        await executor._rollback_plan(plan, until_step=1)

        assert plan["steps"][0]["status"] == ExecutionStatus.ROLLED_BACK
        assert plan["steps"][1]["status"] == ExecutionStatus.PENDING

    @pytest.mark.asyncio
    async def test_rollback_skips_no_rollback_action(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")

        plan["steps"][0]["status"] = ExecutionStatus.COMPLETED
        plan["steps"][0]["rollback_action"] = None  # No rollback

        await executor._rollback_plan(plan, until_step=0)

        # Should not be rolled back since no rollback action
        assert plan["steps"][0]["status"] == ExecutionStatus.COMPLETED


# ============================================================================
# TESTS: dequeue_next
# ============================================================================


class TestDequeueNext:
    @pytest.mark.asyncio
    async def test_dequeue_empty(self, executor):
        result = await executor.dequeue_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_highest_priority(self, executor):
        await executor.create_plan("NPWP registration", "user@test.com")
        await executor.create_plan("Setup PT PMA company", "user@test.com")

        result = await executor.dequeue_next()
        # PT PMA has higher priority (10 vs 3)
        assert result["task_type"] == "pt_pma_incorporation"

    @pytest.mark.asyncio
    async def test_dequeue_no_pending(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        plan["overall_status"] = ExecutionStatus.COMPLETED

        result = await executor.dequeue_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_persistent(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await persistent_executor.dequeue_next()
        assert result is None


# ============================================================================
# TESTS: Persistence layer (no-op in memory mode)
# ============================================================================


class TestPersistenceNoOp:
    @pytest.mark.asyncio
    async def test_persist_plan_no_pool(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        # Should be no-op
        await executor._persist_plan(plan)

    @pytest.mark.asyncio
    async def test_persist_step_update_no_pool(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        await executor._persist_step_update(plan, plan["steps"][0])

    @pytest.mark.asyncio
    async def test_persist_plan_completion_no_pool(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        await executor._persist_plan_completion(plan)

    @pytest.mark.asyncio
    async def test_persist_approval_no_pool(self, executor):
        await executor._persist_approval("plan_1", "step_0", True, None, None)

    @pytest.mark.asyncio
    async def test_query_plans_no_pool(self, executor):
        result = await executor._query_plans(None, None, 50)
        assert result == []

    @pytest.mark.asyncio
    async def test_load_plan_no_pool(self, executor):
        result = await executor._load_plan("plan_1")
        assert result is None


# ============================================================================
# TESTS: Persistence layer (with DB pool)
# ============================================================================


class TestPersistenceWithDB:
    @pytest.mark.asyncio
    async def test_persist_step_update(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.execute = AsyncMock()

        plan = ExecutionPlan(
            plan_id="plan_test", user_query="test", user_email="u@t.com",
            task_type="npwp_registration", priority=3,
            steps=[_make_step(TASK_TEMPLATES["npwp_registration"][0], 0)],
            current_step=0, overall_status=ExecutionStatus.IN_PROGRESS,
            created_at=datetime.now(UTC).isoformat(),
            completed_at=None, human_approvals=[],
        )

        await persistent_executor._persist_step_update(plan, plan["steps"][0])
        mock_db_pool._mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_persist_plan_completion(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.execute = AsyncMock()

        plan = ExecutionPlan(
            plan_id="plan_test", user_query="test", user_email="u@t.com",
            task_type="npwp_registration", priority=3, steps=[],
            current_step=0, overall_status=ExecutionStatus.COMPLETED,
            created_at=datetime.now(UTC).isoformat(),
            completed_at=datetime.now(UTC).isoformat(), human_approvals=[],
        )

        await persistent_executor._persist_plan_completion(plan)
        mock_db_pool._mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_plan_status_persistent(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.execute = AsyncMock()

        plan = ExecutionPlan(
            plan_id="plan_test", user_query="test", user_email="u@t.com",
            task_type="npwp_registration", priority=3, steps=[],
            current_step=0, overall_status=ExecutionStatus.PENDING,
            created_at=datetime.now(UTC).isoformat(),
            completed_at=None, human_approvals=[],
        )

        await persistent_executor._update_plan_status(plan, ExecutionStatus.IN_PROGRESS)
        assert plan["overall_status"] == ExecutionStatus.IN_PROGRESS
        mock_db_pool._mock_conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_plan_status_in_memory(self, executor):
        plan = await executor.create_plan("NPWP registration", "user@test.com")
        await executor._update_plan_status(plan, ExecutionStatus.IN_PROGRESS)
        assert plan["overall_status"] == ExecutionStatus.IN_PROGRESS


# ============================================================================
# TESTS: Enums
# ============================================================================


class TestEnums:
    def test_execution_status_values(self):
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.COMPLETED == "completed"
        assert ExecutionStatus.FAILED == "failed"

    def test_step_safety_values(self):
        assert StepSafety.SAFE == "safe"
        assert StepSafety.CRITICAL == "critical"
        assert StepSafety.IRREVERSIBLE == "irreversible"
