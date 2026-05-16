"""
Extra coverage tests for backend/services/rag/autonomous_executor.py

Focuses on lines NOT covered by the existing test_autonomous_executor.py:
- _load_plan with full DB row parsing
- _query_plans with DB pool and filters
- execute_plan with step failure and rollback
- _wait_for_approval with persistent DB check
- dequeue_next persistent mode with result
- _persist_approval with DB pool
- execute_plan end-to-end with mixed step types
- TASK_TEMPLATES completeness
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.autonomous_executor import (
    RETRY_CONFIG,
    TASK_PRIORITY,
    TASK_TEMPLATES,
    AutonomousExecutor,
    ExecutionStatus,
    StepSafety,
    _backoff_delay,
    _make_step,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=None)
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_cm)
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def persistent_executor(mock_db_pool):
    return AutonomousExecutor(db_pool=mock_db_pool)


# ============================================================================
# TESTS: TASK_TEMPLATES completeness
# ============================================================================


class TestTaskTemplates:
    def test_all_task_types_have_templates(self):
        for task_type in TASK_PRIORITY:
            assert task_type in TASK_TEMPLATES

    def test_all_templates_have_valid_fields(self):
        for _, steps in TASK_TEMPLATES.items():
            for step in steps:
                assert "action" in step
                assert "description" in step
                assert "safety_level" in step
                assert "rollback_action" in step

    def test_retry_config_covers_critical_actions(self):
        for _, steps in TASK_TEMPLATES.items():
            for step in steps:
                if step["safety_level"] in (StepSafety.CRITICAL, StepSafety.IRREVERSIBLE):
                    assert step["action"] in RETRY_CONFIG, \
                        f"Critical action {step['action']} missing from RETRY_CONFIG"


# ============================================================================
# TESTS: _load_plan with full row parsing
# ============================================================================


class TestLoadPlanPersistent:
    @pytest.mark.asyncio
    async def test_load_plan_full(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        now = datetime.now(UTC)

        plan_row = MagicMock()
        plan_data = {
            "plan_id": "plan_abc", "user_query": "NPWP registration",
            "user_email": "u@t.com", "task_type": "npwp_registration",
            "priority": 3, "current_step": 0,
            "overall_status": "pending",
            "created_at": now, "completed_at": None,
        }
        plan_row.__getitem__ = lambda s, k: plan_data[k]

        step_row = MagicMock()
        step_data = {
            "step_id": "step_0", "action": "verify_client_data",
            "description": "Verify", "safety_level": "safe",
            "status": "pending", "started_at": None, "completed_at": None,
            "last_error": None, "rollback_action": None,
            "retry_count": 0, "max_retries": 2,
        }
        step_row.__getitem__ = lambda s, k: step_data[k]

        approval_row = MagicMock()
        approval_data = {
            "step_id": "step_0", "approved": True,
            "approver_email": "admin@t.com", "decided_at": now,
        }
        approval_row.__getitem__ = lambda s, k: approval_data[k]

        conn.fetchrow = AsyncMock(return_value=plan_row)
        conn.fetch = AsyncMock(side_effect=[[step_row], [approval_row]])

        plan = await persistent_executor._load_plan("plan_abc")
        assert plan is not None
        assert plan["plan_id"] == "plan_abc"
        assert len(plan["steps"]) == 1
        assert len(plan["human_approvals"]) == 1

    @pytest.mark.asyncio
    async def test_load_plan_not_found(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)
        result = await persistent_executor._load_plan("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_plan_with_completed_at(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        now = datetime.now(UTC)

        plan_row = MagicMock()
        plan_data = {
            "plan_id": "plan_done", "user_query": "done",
            "user_email": "u@t.com", "task_type": "npwp_registration",
            "priority": 3, "current_step": 4,
            "overall_status": "completed",
            "created_at": now, "completed_at": now,
        }
        plan_row.__getitem__ = lambda s, k: plan_data[k]

        step_row = MagicMock()
        step_data = {
            "step_id": "step_0", "action": "verify",
            "description": "d", "safety_level": "safe",
            "status": "completed", "started_at": now, "completed_at": now,
            "last_error": None, "rollback_action": None,
            "retry_count": 0, "max_retries": 1,
        }
        step_row.__getitem__ = lambda s, k: step_data[k]

        conn.fetchrow = AsyncMock(return_value=plan_row)
        conn.fetch = AsyncMock(side_effect=[[step_row], []])

        plan = await persistent_executor._load_plan("plan_done")
        assert plan["completed_at"] is not None
        assert plan["steps"][0]["started_at"] is not None


# ============================================================================
# TESTS: _query_plans with filters
# ============================================================================


class TestQueryPlansPersistent:
    @pytest.mark.asyncio
    async def test_query_with_email_filter(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"plan_id": "plan_1"}[k]
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchrow = AsyncMock(return_value=None)

        plans = await persistent_executor._query_plans("u@t.com", None, 10)
        assert plans == []

    @pytest.mark.asyncio
    async def test_query_with_status_filter(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        plans = await persistent_executor._query_plans(None, ExecutionStatus.PENDING, 10)
        assert plans == []

    @pytest.mark.asyncio
    async def test_query_with_both_filters(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        plans = await persistent_executor._query_plans(
            "u@t.com", ExecutionStatus.COMPLETED, 5,
        )
        assert plans == []


# ============================================================================
# TESTS: dequeue_next persistent with result
# ============================================================================


class TestDequeuePersistent:
    @pytest.mark.asyncio
    async def test_dequeue_with_result(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"plan_id": "plan_abc"}[k]
        conn.fetchrow = AsyncMock(side_effect=[row, None])
        conn.fetch = AsyncMock(return_value=[])

        result = await persistent_executor.dequeue_next()
        # Will be None because _load_plan returns None (fetchrow returns None 2nd time)
        assert result is None


# ============================================================================
# TESTS: _wait_for_approval with DB
# ============================================================================


class TestWaitForApprovalPersistent:
    @pytest.mark.asyncio
    async def test_db_approval_found_true(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"approved": True}[k]
        conn.fetchrow = AsyncMock(side_effect=[row, None])  # approval check, then plan load

        persistent_executor.get_plan_status = AsyncMock(return_value={
            "plan_id": "p1", "human_approvals": [],
        })

        with patch("backend.services.rag.autonomous_executor.asyncio.sleep", new_callable=AsyncMock):
            result = await persistent_executor._wait_for_approval("p1", "step_0", timeout=5)
        assert result is True

    @pytest.mark.asyncio
    async def test_db_approval_found_false(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"approved": False}[k]
        conn.fetchrow = AsyncMock(return_value=row)

        with patch("backend.services.rag.autonomous_executor.asyncio.sleep", new_callable=AsyncMock):
            result = await persistent_executor._wait_for_approval("p1", "step_0", timeout=5)
        assert result is False


# ============================================================================
# TESTS: execute_plan with failure and rollback
# ============================================================================


class TestExecutePlanRollback:
    @pytest.mark.asyncio
    async def test_step_failure_triggers_rollback(self):
        executor = AutonomousExecutor()
        plan = await executor.create_plan("NPWP registration", "u@t.com")

        # Make all steps safe, always fail
        for step in plan["steps"]:
            step["safety_level"] = StepSafety.SAFE
            step["max_retries"] = 0  # No retries, fail immediately

        step_index = 0

        async def fail_on_second_step(step, email):
            nonlocal step_index
            step_index += 1
            if step_index >= 2:
                raise Exception("permanent failure")

        executor._execute_step = fail_on_second_step

        with patch("backend.services.rag.autonomous_executor.asyncio.sleep", new_callable=AsyncMock):
            result = await executor.execute_plan(plan["plan_id"])

        assert result["overall_status"] == ExecutionStatus.ROLLED_BACK


# ============================================================================
# TESTS: _persist_approval with DB
# ============================================================================


class TestPersistApproval:
    @pytest.mark.asyncio
    async def test_persist_approval_with_all_fields(self, persistent_executor, mock_db_pool):
        mock_db_pool._mock_conn.execute = AsyncMock()
        await persistent_executor._persist_approval(
            "plan_1", "step_0", True, "admin@t.com", "Approved because valid",
        )
        mock_db_pool._mock_conn.execute.assert_awaited_once()


# ============================================================================
# TESTS: list_plans persistent
# ============================================================================


class TestListPlansPersistent:
    @pytest.mark.asyncio
    async def test_list_plans_persistent(self, persistent_executor, mock_db_pool):
        conn = mock_db_pool._mock_conn
        conn.fetch = AsyncMock(return_value=[])

        plans = await persistent_executor.list_plans(user_email="u@t.com")
        assert plans == []


# ============================================================================
# TESTS: Backoff edge cases
# ============================================================================


class TestBackoffExtra:
    def test_zero_base_delay(self):
        delay = _backoff_delay(0, base_delay_s=0)
        assert delay == 0

    def test_large_attempt(self):
        delay = _backoff_delay(20, base_delay_s=5)
        assert delay <= 300  # capped


# ============================================================================
# TESTS: execute_step actions coverage
# ============================================================================


class TestExecuteStepActions:
    @pytest.mark.asyncio
    async def test_kitas_actions(self):
        executor = AutonomousExecutor()
        actions = [
            "check_kitas_eligibility", "prepare_kitas_documents",
            "submit_to_immigration", "schedule_biometrics", "track_kitas_status",
        ]
        for action in actions:
            step = _make_step({
                "action": action, "description": "test",
                "safety_level": StepSafety.SAFE, "rollback_action": "",
            }, 0)
            await executor._execute_step(step, "u@t.com")

    @pytest.mark.asyncio
    async def test_pt_pma_actions(self):
        executor = AutonomousExecutor()
        actions = [
            "verify_shareholders", "check_kbli_codes",
            "prepare_incorporation_docs", "submit_to_ahu",
            "register_oss", "obtain_nib",
        ]
        for action in actions:
            step = _make_step({
                "action": action, "description": "test",
                "safety_level": StepSafety.SAFE, "rollback_action": "",
            }, 0)
            await executor._execute_step(step, "u@t.com")
