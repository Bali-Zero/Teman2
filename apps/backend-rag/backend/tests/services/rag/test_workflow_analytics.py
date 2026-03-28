"""
Integration tests for Workflow Analytics (Phase 4).

Tests cover:
- WorkflowAnalyticsRepository: CRUD operations and aggregation queries
- Workflow Analytics Router: API endpoints (feedback, dashboard)
- Orchestrator tracking hook: fire-and-forget workflow logging
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ========== FIXTURES ==========


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool with proper async context manager."""
    conn = AsyncMock()

    # Create proper async context manager for pool.acquire()
    ctx_manager = AsyncMock()
    ctx_manager.__aenter__ = AsyncMock(return_value=conn)
    ctx_manager.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire.return_value = ctx_manager
    return pool, conn


@pytest.fixture
def repo(mock_db_pool):
    """WorkflowAnalyticsRepository with mocked pool."""
    from backend.db.repositories.workflow_analytics_repository import (
        WorkflowAnalyticsRepository,
    )

    pool, _ = mock_db_pool
    return WorkflowAnalyticsRepository(pool)


@pytest.fixture
def sample_workflow():
    """Sample workflow dict from KGLangGraphOrchestrator."""
    return {
        "type": "sequential_workflow",
        "name": "PT PMA Setup Workflow",
        "source": "kg_langgraph",
        "confidence": 0.85,
        "steps": [
            {"step": 1, "action": "Prepare business plan", "entity_id": "kbli:7310"},
            {"step": 2, "action": "Register NPWP", "entity_id": "tax:npwp"},
            {"step": 3, "action": "Apply for NIB", "entity_id": "oss:nib"},
        ],
    }


@pytest.fixture
def mock_founder_user():
    return {"email": "zero@balizero.com", "role": "Founder", "name": "Zero"}


@pytest.fixture
def mock_regular_user():
    return {"email": "user@example.com", "role": "user", "name": "User"}


# ========== REPOSITORY TESTS ==========


class TestWorkflowAnalyticsRepository:
    """Tests for WorkflowAnalyticsRepository."""

    @pytest.mark.asyncio
    async def test_log_workflow_success(self, mock_db_pool):
        """Test logging a workflow generation event."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"id": 42})
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.log_workflow(
            workflow_id="wf-abc123",
            query="How to set up PT PMA?",
            user_email="user@example.com",
            workflow_type="sequential_workflow",
            workflow_name="PT PMA Setup",
            steps_count=3,
            steps_json=[{"step": 1, "action": "Plan"}],
            source="kg_langgraph",
            confidence=0.85,
            execution_time_ms=350,
        )

        assert result == 42
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        assert "INSERT INTO workflow_analytics" in call_args[0][0]
        assert call_args[0][1] == "wf-abc123"  # workflow_id
        assert call_args[0][2] == "How to set up PT PMA?"  # query

    @pytest.mark.asyncio
    async def test_log_workflow_db_error(self, mock_db_pool):
        """Test graceful handling of DB errors during logging."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("Connection refused"))
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.log_workflow(
            workflow_id="wf-abc123",
            query="test query",
        )

        assert result is None  # Graceful failure

    @pytest.mark.asyncio
    async def test_log_workflow_none_steps(self, mock_db_pool):
        """Test logging with None steps_json."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"id": 1})
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.log_workflow(
            workflow_id="wf-minimal",
            query="simple query",
            steps_json=None,
        )

        assert result == 1
        call_args = conn.fetchrow.call_args
        # steps_json param should be None when no steps provided
        assert call_args[0][7] is None

    @pytest.mark.asyncio
    async def test_record_feedback_success(self, mock_db_pool):
        """Test recording user feedback on a workflow."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.execute = AsyncMock(return_value="UPDATE 1")
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.record_feedback(
            workflow_id="wf-abc123",
            followed=True,
            feedback_score=4.5,
            feedback_comment="Very helpful workflow!",
        )

        assert result is True
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_feedback_not_found(self, mock_db_pool):
        """Test feedback on non-existent workflow."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.execute = AsyncMock(return_value="UPDATE 0")
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.record_feedback(
            workflow_id="wf-nonexistent",
            followed=False,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_record_feedback_invalid_score(self, mock_db_pool):
        """Test that invalid scores are rejected."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.record_feedback(
            workflow_id="wf-abc123",
            followed=True,
            feedback_score=6.0,  # Out of range
        )

        assert result is False
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_feedback_negative_score(self, mock_db_pool):
        """Test that negative scores are rejected."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.record_feedback(
            workflow_id="wf-abc123",
            followed=True,
            feedback_score=-1.0,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_record_feedback_db_error(self, mock_db_pool):
        """Test graceful handling of DB errors during feedback."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.execute = AsyncMock(side_effect=Exception("DB timeout"))
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.record_feedback(
            workflow_id="wf-abc123",
            followed=True,
            feedback_score=3.0,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_follow_rate(self, mock_db_pool):
        """Test follow rate aggregation."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "total_workflows": 100,
                "followed_count": 75,
                "follow_rate_percent": 75.0,
                "avg_confidence": 0.82,
                "avg_feedback_score": 4.1,
            }
        )
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.get_follow_rate(days=7)

        assert result["total_workflows"] == 100
        assert result["followed_count"] == 75
        assert result["follow_rate_percent"] == 75.0
        assert result["avg_confidence"] == 0.82

    @pytest.mark.asyncio
    async def test_get_follow_rate_db_error(self, mock_db_pool):
        """Test follow rate returns defaults on error."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("Connection lost"))
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.get_follow_rate(days=7)

        assert result["total_workflows"] == 0
        assert result["follow_rate_percent"] is None

    @pytest.mark.asyncio
    async def test_get_top_workflows(self, mock_db_pool):
        """Test top workflows aggregation."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "workflow_name": "PT PMA Setup",
                    "workflow_type": "sequential_workflow",
                    "generation_count": 45,
                    "avg_confidence": 0.88,
                    "followed_count": 30,
                    "avg_score": 4.2,
                },
                {
                    "workflow_name": "KITAS Application",
                    "workflow_type": "sequential_workflow",
                    "generation_count": 32,
                    "avg_confidence": 0.91,
                    "followed_count": 28,
                    "avg_score": 4.5,
                },
            ]
        )
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.get_top_workflows(limit=10, days=7)

        assert len(result) == 2
        assert result[0]["workflow_name"] == "PT PMA Setup"
        assert result[0]["generation_count"] == 45

    @pytest.mark.asyncio
    async def test_get_workflow_volume(self, mock_db_pool):
        """Test workflow volume over time."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool
        now = datetime.now(tz=timezone.utc)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "bucket": now,
                    "workflow_count": 12,
                    "avg_confidence": 0.85,
                    "avg_latency_ms": 320,
                },
            ]
        )
        repo = WorkflowAnalyticsRepository(pool)

        result = await repo.get_workflow_volume(granularity="hour", days=1)

        assert len(result) == 1
        assert result[0]["workflow_count"] == 12
        assert result[0]["avg_latency_ms"] == 320

    @pytest.mark.asyncio
    async def test_get_dashboard_summary(self, mock_db_pool):
        """Test full dashboard summary aggregation."""
        from backend.db.repositories.workflow_analytics_repository import (
            WorkflowAnalyticsRepository,
        )

        pool, conn = mock_db_pool

        # Mock different calls with side effects
        follow_rate_data = {
            "total_workflows": 50,
            "followed_count": 35,
            "follow_rate_percent": 70.0,
            "avg_confidence": 0.83,
            "avg_feedback_score": 3.8,
        }
        conn.fetchrow = AsyncMock(return_value=follow_rate_data)
        conn.fetch = AsyncMock(return_value=[])

        repo = WorkflowAnalyticsRepository(pool)
        result = await repo.get_dashboard_summary(days=7)

        assert result["period_days"] == 7
        assert "follow_rate" in result
        assert "top_workflows" in result
        assert "workflow_volume_hourly" in result
        assert "workflow_volume_daily" in result
        assert "generated_at" in result


# ========== ROUTER ENDPOINT TESTS ==========


class TestWorkflowAnalyticsRouter:
    """Tests for workflow analytics API endpoints."""

    @pytest.mark.asyncio
    async def test_submit_feedback_success(self):
        """Test submitting workflow feedback."""
        from backend.app.routers.workflow_analytics import (
            WorkflowFeedbackRequest,
            submit_workflow_feedback,
        )

        mock_repo = AsyncMock()
        mock_repo.record_feedback = AsyncMock(return_value=True)
        mock_user = {"email": "user@example.com", "role": "user"}

        body = WorkflowFeedbackRequest(
            workflow_id="wf-abc123",
            followed=True,
            feedback_score=4.0,
            comment="Great workflow!",
        )

        result = await submit_workflow_feedback(
            body=body,
            repo=mock_repo,
            current_user=mock_user,
        )

        assert result["status"] == "ok"
        assert result["workflow_id"] == "wf-abc123"
        assert result["followed"] is True
        assert result["feedback_score"] == 4.0

    @pytest.mark.asyncio
    async def test_submit_feedback_not_found(self):
        """Test feedback for non-existent workflow returns 404."""
        from fastapi import HTTPException

        from backend.app.routers.workflow_analytics import (
            WorkflowFeedbackRequest,
            submit_workflow_feedback,
        )

        mock_repo = AsyncMock()
        mock_repo.record_feedback = AsyncMock(return_value=False)
        mock_user = {"email": "user@example.com", "role": "user"}

        body = WorkflowFeedbackRequest(
            workflow_id="wf-nonexistent",
            followed=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_workflow_feedback(
                body=body,
                repo=mock_repo,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_dashboard_founder_only(self):
        """Test that dashboard requires founder access."""
        from fastapi import HTTPException

        from backend.app.routers.workflow_analytics import _verify_founder_access

        regular_user = {"email": "user@example.com", "role": "user"}

        with pytest.raises(HTTPException) as exc_info:
            _verify_founder_access(current_user=regular_user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_dashboard_founder_access(self):
        """Test that founders can access dashboard."""
        from backend.app.routers.workflow_analytics import _verify_founder_access

        founder = {"email": "zero@balizero.com", "role": "Founder"}
        result = _verify_founder_access(current_user=founder)
        assert result == founder

    @pytest.mark.asyncio
    async def test_get_dashboard_admin_access(self):
        """Test that admins can access dashboard."""
        from backend.app.routers.workflow_analytics import _verify_founder_access

        admin = {"email": "admin@balizero.com", "role": "admin"}
        result = _verify_founder_access(current_user=admin)
        assert result == admin


# ========== ORCHESTRATOR TRACKING HOOK TESTS ==========


class TestOrchestratorTrackingHook:
    """Tests for the fire-and-forget workflow tracking in orchestrator_core."""

    def _make_pool_mock(self):
        """Create a properly mocked asyncpg pool."""
        mock_conn = AsyncMock()
        ctx_manager = AsyncMock()
        ctx_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx_manager.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = ctx_manager
        return mock_pool, mock_conn

    @pytest.mark.asyncio
    async def test_track_workflow_logs_to_repo(self, sample_workflow):
        """Test that _track_workflow calls the repository correctly."""
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

        mock_pool, mock_conn = self._make_pool_mock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})

        core = OrchestratorCore.__new__(OrchestratorCore)
        core.db_pool = mock_pool

        await core._track_workflow(
            query="How to set up PT PMA?",
            workflow=sample_workflow,
            execution_time_ms=350,
            user_email="user@example.com",
        )

        mock_conn.fetchrow.assert_called_once()
        call_sql = mock_conn.fetchrow.call_args[0][0]
        assert "INSERT INTO workflow_analytics" in call_sql

    @pytest.mark.asyncio
    async def test_track_workflow_no_db_pool(self, sample_workflow):
        """Test that tracking is skipped when no db_pool is available."""
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

        core = OrchestratorCore.__new__(OrchestratorCore)
        core.db_pool = None

        # Should return without error
        await core._track_workflow(
            query="test",
            workflow=sample_workflow,
        )

    @pytest.mark.asyncio
    async def test_track_workflow_generates_workflow_id(self, sample_workflow):
        """Test that a unique workflow_id is generated."""
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

        mock_pool, mock_conn = self._make_pool_mock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})

        core = OrchestratorCore.__new__(OrchestratorCore)
        core.db_pool = mock_pool

        await core._track_workflow(query="test", workflow=sample_workflow)

        call_args = mock_conn.fetchrow.call_args[0]
        workflow_id = call_args[1]  # Second positional arg = workflow_id
        assert workflow_id.startswith("wf-")
        assert len(workflow_id) == 15  # "wf-" + 12 hex chars

    @pytest.mark.asyncio
    async def test_track_workflow_db_error_suppressed(self, sample_workflow):
        """Test that DB errors in tracking don't propagate."""
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

        mock_pool, mock_conn = self._make_pool_mock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB connection lost"))

        core = OrchestratorCore.__new__(OrchestratorCore)
        core.db_pool = mock_pool

        # Should not raise
        await core._track_workflow(query="test", workflow=sample_workflow)

    @pytest.mark.asyncio
    async def test_track_workflow_captures_steps_count(self, sample_workflow):
        """Test that steps_count matches actual steps in workflow."""
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

        mock_pool, mock_conn = self._make_pool_mock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})

        core = OrchestratorCore.__new__(OrchestratorCore)
        core.db_pool = mock_pool

        await core._track_workflow(query="test", workflow=sample_workflow)

        call_args = mock_conn.fetchrow.call_args[0]
        steps_count = call_args[6]  # 7th positional arg = steps_count
        assert steps_count == 3  # sample_workflow has 3 steps


# ========== PYDANTIC MODEL VALIDATION TESTS ==========


class TestWorkflowFeedbackValidation:
    """Tests for WorkflowFeedbackRequest Pydantic validation."""

    def test_valid_feedback(self):
        """Test valid feedback request."""
        from backend.app.routers.workflow_analytics import WorkflowFeedbackRequest

        req = WorkflowFeedbackRequest(
            workflow_id="wf-abc123",
            followed=True,
            feedback_score=4.5,
            comment="Good",
        )
        assert req.workflow_id == "wf-abc123"
        assert req.followed is True
        assert req.feedback_score == 4.5

    def test_feedback_without_optional_fields(self):
        """Test feedback with only required fields."""
        from backend.app.routers.workflow_analytics import WorkflowFeedbackRequest

        req = WorkflowFeedbackRequest(
            workflow_id="wf-abc123",
            followed=False,
        )
        assert req.feedback_score is None
        assert req.comment is None

    def test_feedback_score_out_of_range(self):
        """Test that scores outside 0-5 are rejected."""
        from pydantic import ValidationError

        from backend.app.routers.workflow_analytics import WorkflowFeedbackRequest

        with pytest.raises(ValidationError):
            WorkflowFeedbackRequest(
                workflow_id="wf-abc123",
                followed=True,
                feedback_score=6.0,
            )

    def test_feedback_score_negative(self):
        """Test that negative scores are rejected."""
        from pydantic import ValidationError

        from backend.app.routers.workflow_analytics import WorkflowFeedbackRequest

        with pytest.raises(ValidationError):
            WorkflowFeedbackRequest(
                workflow_id="wf-abc123",
                followed=True,
                feedback_score=-1.0,
            )
