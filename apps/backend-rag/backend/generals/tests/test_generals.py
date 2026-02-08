"""
Comprehensive test suite for The Generals Multi-Agent System

Tests with mocked PostgreSQL (no real DB required):
- CodingGeneral: polling, execution, memory write, error handling
- IntelligenceGeneral: polling, research, Gemini integration, memory ops
- TaskCoordinator: task CRUD, memory management, activity, statistics
- Integration: cross-component workflows
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.generals.coding_general import CodingGeneral
from backend.generals.intelligence_general import IntelligenceGeneral
from backend.generals.task_coordinator import TaskCoordinator

# =============================================================================
# Mock Helpers
# =============================================================================


def create_mock_pool() -> tuple[MagicMock, AsyncMock]:
    """
    Create a mock asyncpg pool + connection with async context manager support.

    Returns:
        (mock_pool, mock_conn) - pool.acquire() yields mock_conn
    """
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_pool = MagicMock()
    mock_acm = AsyncMock()
    mock_acm.__aenter__.return_value = mock_conn
    mock_acm.__aexit__.return_value = False
    mock_pool.acquire.return_value = mock_acm
    mock_pool.close = AsyncMock()

    return mock_pool, mock_conn


def make_task_record(
    task_id: int = 1,
    task_type: str = "code",
    title: str = "Test Task",
    description: str = "Test Description",
    payload: dict | None = None,
    priority: int = 5,
    status: str = "pending",
) -> dict:
    """Create a task record dict (simulates asyncpg.Record)."""
    return {
        "id": task_id,
        "task_type": task_type,
        "assigned_to": None,
        "status": status,
        "priority": priority,
        "title": title,
        "description": description,
        "payload": payload or {},
        "result": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "assigned_at": None,
        "started_at": None,
        "completed_at": None,
        "updated_at": datetime.now(timezone.utc),
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Provide mocked database pool and connection."""
    pool, conn = create_mock_pool()
    return pool, conn


@pytest.fixture
def coding_general(mock_db):
    """CodingGeneral with mocked DB pool."""
    pool, _conn = mock_db
    with patch("backend.generals.coding_general.settings") as mock_settings:
        mock_settings.database_url = "postgresql://test/test"
        general = CodingGeneral(database_url="postgresql://test/test")
        general.pool = pool
        yield general


@pytest.fixture
def intelligence_general(mock_db):
    """IntelligenceGeneral with mocked DB pool and Gemini client."""
    pool, _conn = mock_db
    with (
        patch("backend.generals.intelligence_general.settings") as mock_settings,
        patch("backend.generals.intelligence_general.GENAI_AVAILABLE", True),
        patch("backend.generals.intelligence_general.get_genai_client") as mock_get_client,
    ):
        mock_settings.database_url = "postgresql://test/test"

        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client.generate_content = AsyncMock(
            return_value={
                "text": "Test analysis with key insights and important findings.",
                "model": "gemini-2.0-flash-001",
                "usage": {"input_tokens": 100, "output_tokens": 200},
            }
        )
        mock_get_client.return_value = mock_client

        general = IntelligenceGeneral(database_url="postgresql://test/test")
        general.pool = pool
        general.genai_client = mock_client
        yield general


@pytest.fixture
def task_coordinator(mock_db):
    """TaskCoordinator with mocked DB pool."""
    pool, _conn = mock_db
    with patch("backend.generals.task_coordinator.settings") as mock_settings:
        mock_settings.database_url = "postgresql://test/test"
        coordinator = TaskCoordinator(database_url="postgresql://test/test")
        coordinator.pool = pool
        yield coordinator


# =============================================================================
# CodingGeneral Tests
# =============================================================================


class TestCodingGeneral:
    """Tests for CodingGeneral: polling, execution, memory, error handling."""

    def test_init(self, coding_general: CodingGeneral):
        """Test initialization sets correct attributes."""
        assert coding_general.general_name == "coding_general"
        assert coding_general.pool is not None
        assert coding_general.running is False
        assert coding_general.poll_interval == 5

    def test_init_no_database_url(self):
        """Test initialization fails without database URL."""
        with patch("backend.generals.coding_general.settings") as mock_settings:
            mock_settings.database_url = None
            with pytest.raises(ValueError, match="DATABASE_URL not configured"):
                CodingGeneral(database_url=None)

    @pytest.mark.asyncio
    async def test_poll_task_empty(self, coding_general: CodingGeneral, mock_db):
        """Test polling returns None when no tasks are available."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = None

        task = await coding_general.poll_task()
        assert task is None

    @pytest.mark.asyncio
    async def test_poll_task_found(self, coding_general: CodingGeneral, mock_db):
        """Test polling finds and assigns a task."""
        _pool, mock_conn = mock_db
        task_record = make_task_record(
            task_id=42,
            task_type="code",
            title="Run linter",
            payload={"command": "ruff check ."},
        )
        mock_conn.fetchrow.return_value = task_record

        task = await coding_general.poll_task()

        assert task is not None
        assert task["id"] == 42
        assert task["title"] == "Run linter"
        # Verify assignment UPDATE was called
        mock_conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_execute_task_command(self, coding_general: CodingGeneral):
        """Test executing a shell command task."""
        task = {
            "id": 1,
            "task_type": "code",
            "title": "Echo Test",
            "description": "Echo hello",
            "payload": {"command": "echo hello"},
            "priority": 5,
        }

        result = await coding_general.execute_task(task)

        assert result["status"] == "completed"
        assert "hello" in result["output"].lower()
        assert result["execution_time_seconds"] > 0
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_execute_task_code(self, coding_general: CodingGeneral):
        """Test executing inline Python code task."""
        task = {
            "id": 2,
            "task_type": "code",
            "title": "Code Test",
            "description": "Print hello",
            "payload": {"code": 'logger.info("hello from code")'},
            "priority": 5,
        }

        result = await coding_general.execute_task(task)

        assert result["status"] == "completed"
        assert "hello from code" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_task_invalid_payload(self, coding_general: CodingGeneral):
        """Test execution fails gracefully with empty payload."""
        task = {
            "id": 3,
            "task_type": "code",
            "title": "Invalid Task",
            "description": "No payload",
            "payload": {},
            "priority": 5,
        }

        result = await coding_general.execute_task(task)

        assert result["status"] == "failed"
        assert result["error"] is not None
        assert "command" in result["error"].lower() or "script" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_task_failed_command(self, coding_general: CodingGeneral):
        """Test execution handles command failure."""
        task = {
            "id": 4,
            "task_type": "code",
            "title": "Failing Command",
            "description": "This should fail",
            "payload": {"command": "false"},
            "priority": 5,
        }

        result = await coding_general.execute_task(task)

        assert result["status"] == "failed"
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_execute_task_quoted_args(self, coding_general: CodingGeneral):
        """Test command with quoted arguments works (shlex fix)."""
        task = {
            "id": 5,
            "task_type": "code",
            "title": "Quoted Args",
            "description": "Test quoted arguments",
            "payload": {"command": "echo 'hello world with spaces'"},
            "priority": 5,
        }

        result = await coding_general.execute_task(task)

        assert result["status"] == "completed"
        assert "hello world with spaces" in result["output"]

    @pytest.mark.asyncio
    async def test_memory_write_on_completion(self, coding_general: CodingGeneral, mock_db):
        """Test that successful tasks write to generals_memory."""
        _pool, mock_conn = mock_db

        task = {
            "id": 10,
            "task_type": "code",
            "title": "Memory Write Test",
            "description": "Should write to memory",
            "payload": {"command": "echo done"},
            "priority": 5,
        }

        result = await coding_general.execute_task(task)
        assert result["status"] == "completed"

        # Verify _write_memory was called (INSERT INTO generals_memory)
        execute_calls = mock_conn.execute.call_args_list
        memory_insert_found = any("generals_memory" in str(c) for c in execute_calls)
        assert memory_insert_found, (
            "Expected INSERT INTO generals_memory after successful completion"
        )

    @pytest.mark.asyncio
    async def test_log_activity(self, coding_general: CodingGeneral, mock_db):
        """Test activity logging writes to generals_activity."""
        _pool, mock_conn = mock_db

        await coding_general._log_activity(
            "task_polled",
            "Test activity message",
            task_id=1,
            metadata={"test": True},
        )

        # Verify INSERT INTO generals_activity
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "generals_activity" in call_args[0][0]
        assert call_args[0][1] == "coding_general"

    @pytest.mark.asyncio
    async def test_write_memory(self, coding_general: CodingGeneral, mock_db):
        """Test _write_memory inserts into generals_memory."""
        _pool, mock_conn = mock_db

        await coding_general._write_memory(
            "test_key",
            {"data": "test_value"},
        )

        # First call is the memory INSERT, second is the activity log
        assert mock_conn.execute.call_count >= 1
        first_call = mock_conn.execute.call_args_list[0]
        assert "generals_memory" in first_call[0][0]

    @pytest.mark.asyncio
    async def test_read_memory_found(self, coding_general: CodingGeneral, mock_db):
        """Test _read_memory returns value when found."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = {
            "value": {"data": "found_value"},
            "expires_at": None,
        }

        value = await coding_general._read_memory("test_key")

        assert value is not None
        assert value["data"] == "found_value"

    @pytest.mark.asyncio
    async def test_read_memory_not_found(self, coding_general: CodingGeneral, mock_db):
        """Test _read_memory returns None when key doesn't exist."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = None

        value = await coding_general._read_memory("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_read_memory_expired(self, coding_general: CodingGeneral, mock_db):
        """Test _read_memory returns None and deletes expired entries."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = {
            "value": {"data": "expired"},
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=60),
        }

        value = await coding_general._read_memory("expired_key")

        assert value is None
        # Verify DELETE was called
        delete_found = any("DELETE" in str(c) for c in mock_conn.execute.call_args_list)
        assert delete_found

    @pytest.mark.asyncio
    async def test_stop(self, coding_general: CodingGeneral):
        """Test stop sets running flag to False."""
        coding_general.running = True
        coding_general.stop()
        assert coding_general.running is False

    @pytest.mark.asyncio
    async def test_close(self, coding_general: CodingGeneral, mock_db):
        """Test close shuts down the pool."""
        pool, _conn = mock_db
        await coding_general.close()
        pool.close.assert_called_once()


# =============================================================================
# IntelligenceGeneral Tests
# =============================================================================


class TestIntelligenceGeneral:
    """Tests for IntelligenceGeneral: polling, research, Gemini, memory."""

    def test_init(self, intelligence_general: IntelligenceGeneral):
        """Test initialization with Gemini client."""
        assert intelligence_general.general_name == "intelligence_general"
        assert intelligence_general.pool is not None
        assert intelligence_general.genai_client is not None
        assert intelligence_general.running is False

    @pytest.mark.asyncio
    async def test_poll_task_empty(self, intelligence_general: IntelligenceGeneral, mock_db):
        """Test polling returns None when no research tasks."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = None

        task = await intelligence_general.poll_task()
        assert task is None

    @pytest.mark.asyncio
    async def test_poll_task_found(self, intelligence_general: IntelligenceGeneral, mock_db):
        """Test polling finds and assigns a research task."""
        _pool, mock_conn = mock_db
        task_record = make_task_record(
            task_id=99,
            task_type="research",
            title="Market Analysis",
            payload={"query": "Bali market trends 2026"},
        )
        mock_conn.fetchrow.return_value = task_record

        task = await intelligence_general.poll_task()

        assert task is not None
        assert task["id"] == 99
        assert task["task_type"] == "research"

    @pytest.mark.asyncio
    async def test_execute_research(self, intelligence_general: IntelligenceGeneral, mock_db):
        """Test executing a research task calls Gemini and returns analysis."""
        _pool, mock_conn = mock_db

        task = {
            "id": 1,
            "task_type": "research",
            "title": "AI Research",
            "description": "Research AI trends",
            "payload": {"query": "What is AI?"},
            "priority": 5,
        }

        result = await intelligence_general.execute_task(task)

        assert result["status"] == "completed"
        assert result["analysis"] != ""
        assert result["model_used"] is not None
        assert result["token_usage"] is not None
        assert result["execution_time_seconds"] > 0
        # Verify Gemini was called
        intelligence_general.genai_client.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_research_no_gemini(
        self, intelligence_general: IntelligenceGeneral, mock_db
    ):
        """Test research fails gracefully without Gemini client."""
        _pool, _conn = mock_db
        intelligence_general.genai_client = None

        task = {
            "id": 2,
            "task_type": "research",
            "title": "No Gemini",
            "description": "Should fail",
            "payload": {"query": "test"},
            "priority": 5,
        }

        result = await intelligence_general.execute_task(task)

        assert result["status"] == "failed"
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_with_memory_context(
        self, intelligence_general: IntelligenceGeneral, mock_db
    ):
        """Test research task reads from shared memory for context."""
        _pool, mock_conn = mock_db

        # Mock memory read to return previous research
        mock_conn.fetchrow.return_value = {
            "value": {"context": "Previous findings about AI"},
            "expires_at": None,
        }

        task = {
            "id": 3,
            "task_type": "research",
            "title": "Context Research",
            "description": "Use memory",
            "payload": {
                "query": "Follow-up on AI",
                "memory_keys": ["previous_research"],
            },
            "priority": 5,
        }

        result = await intelligence_general.execute_task(task)

        assert result["status"] == "completed"
        # Verify Gemini prompt included memory context
        call_args = intelligence_general.genai_client.generate_content.call_args
        contents = call_args[1]["contents"]
        assert "Shared Memory Context" in contents or "previous_research" in contents

    @pytest.mark.asyncio
    async def test_execute_saves_to_memory(
        self, intelligence_general: IntelligenceGeneral, mock_db
    ):
        """Test research task saves result to memory when requested."""
        _pool, mock_conn = mock_db

        task = {
            "id": 4,
            "task_type": "research",
            "title": "Save Result",
            "description": "Save to memory",
            "payload": {
                "query": "test",
                "save_to_memory": True,
                "memory_key": "research_result",
            },
            "priority": 5,
        }

        result = await intelligence_general.execute_task(task)

        assert result["status"] == "completed"
        # Verify memory INSERT was called
        memory_calls = [c for c in mock_conn.execute.call_args_list if "generals_memory" in str(c)]
        assert len(memory_calls) > 0

    @pytest.mark.asyncio
    async def test_memory_write(self, intelligence_general: IntelligenceGeneral, mock_db):
        """Test _write_memory upserts into generals_memory."""
        _pool, mock_conn = mock_db

        await intelligence_general._write_memory(
            "test_key",
            {"data": "value"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        first_call = mock_conn.execute.call_args_list[0]
        assert "generals_memory" in first_call[0][0]

    @pytest.mark.asyncio
    async def test_memory_read_found(self, intelligence_general: IntelligenceGeneral, mock_db):
        """Test _read_memory returns value."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = {
            "value": {"data": "found"},
            "expires_at": None,
        }

        value = await intelligence_general._read_memory("key")
        assert value is not None
        assert value["data"] == "found"

    @pytest.mark.asyncio
    async def test_memory_read_expired(self, intelligence_general: IntelligenceGeneral, mock_db):
        """Test _read_memory deletes and returns None for expired keys."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = {
            "value": {"data": "old"},
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        }

        value = await intelligence_general._read_memory("expired")
        assert value is None

    @pytest.mark.asyncio
    async def test_stop(self, intelligence_general: IntelligenceGeneral):
        """Test stop sets running flag to False."""
        intelligence_general.running = True
        intelligence_general.stop()
        assert intelligence_general.running is False


# =============================================================================
# TaskCoordinator Tests
# =============================================================================


class TestTaskCoordinator:
    """Tests for TaskCoordinator: CRUD, memory, activity, stats."""

    def test_init(self, task_coordinator: TaskCoordinator):
        """Test initialization."""
        assert task_coordinator.pool is not None

    @pytest.mark.asyncio
    async def test_submit_code_task(self, task_coordinator: TaskCoordinator, mock_db):
        """Test submitting a code task."""
        _pool, mock_conn = mock_db
        mock_conn.fetchval.return_value = 42

        task_id = await task_coordinator.submit_task(
            task_type="code",
            title="Test Code Task",
            description="Run echo",
            payload={"command": "echo test"},
            priority=7,
        )

        assert task_id == 42
        mock_conn.fetchval.assert_called_once()
        call_query = mock_conn.fetchval.call_args[0][0]
        assert "INSERT INTO generals_tasks" in call_query

    @pytest.mark.asyncio
    async def test_submit_research_task(self, task_coordinator: TaskCoordinator, mock_db):
        """Test submitting a research task."""
        _pool, mock_conn = mock_db
        mock_conn.fetchval.return_value = 43

        task_id = await task_coordinator.submit_task(
            task_type="research",
            title="Research Task",
            payload={"query": "What is Python?"},
            priority=8,
        )

        assert task_id == 43

    @pytest.mark.asyncio
    async def test_submit_invalid_type(self, task_coordinator: TaskCoordinator):
        """Test submitting task with invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid task_type"):
            await task_coordinator.submit_task(
                task_type="invalid",
                title="Bad Task",
            )

    @pytest.mark.asyncio
    async def test_submit_invalid_priority(self, task_coordinator: TaskCoordinator):
        """Test submitting task with out-of-range priority raises ValueError."""
        with pytest.raises(ValueError, match="Invalid priority"):
            await task_coordinator.submit_task(
                task_type="code",
                title="Bad Priority",
                priority=15,
            )

    @pytest.mark.asyncio
    async def test_get_task(self, task_coordinator: TaskCoordinator, mock_db):
        """Test getting task by ID."""
        _pool, mock_conn = mock_db
        task_record = make_task_record(task_id=1, title="Found Task")
        mock_conn.fetchrow.return_value = task_record

        task = await task_coordinator.get_task(1)

        assert task is not None
        assert task["id"] == 1
        assert task["title"] == "Found Task"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, task_coordinator: TaskCoordinator, mock_db):
        """Test getting nonexistent task returns None."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = None

        task = await task_coordinator.get_task(999)
        assert task is None

    @pytest.mark.asyncio
    async def test_get_tasks_filtered(self, task_coordinator: TaskCoordinator, mock_db):
        """Test listing tasks with filters."""
        _pool, mock_conn = mock_db
        mock_conn.fetch.return_value = [
            make_task_record(task_id=1, task_type="code", title="Code 1"),
            make_task_record(task_id=2, task_type="code", title="Code 2"),
        ]

        tasks = await task_coordinator.get_tasks(task_type="code")

        assert len(tasks) == 2
        assert all(t["task_type"] == "code" for t in tasks)
        # Verify query included filter
        call_query = mock_conn.fetch.call_args[0][0]
        assert "task_type" in call_query

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_coordinator: TaskCoordinator, mock_db):
        """Test cancelling a pending task."""
        _pool, mock_conn = mock_db
        mock_conn.execute.return_value = "UPDATE 1"

        cancelled = await task_coordinator.cancel_task(1)
        assert cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, task_coordinator: TaskCoordinator, mock_db):
        """Test cancelling nonexistent task returns False."""
        _pool, mock_conn = mock_db
        mock_conn.execute.return_value = "UPDATE 0"

        cancelled = await task_coordinator.cancel_task(999)
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_get_task_result_completed(self, task_coordinator: TaskCoordinator, mock_db):
        """Test getting result of a completed task."""
        _pool, mock_conn = mock_db
        task_record = make_task_record(task_id=1, status="completed")
        task_record["result"] = {"output": "success"}
        task_record["completed_at"] = datetime.now(timezone.utc)
        mock_conn.fetchrow.return_value = task_record

        result = await task_coordinator.get_task_result(1)

        assert result is not None
        assert result["task_id"] == 1
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_task_result_pending(self, task_coordinator: TaskCoordinator, mock_db):
        """Test getting result of pending task returns None."""
        _pool, mock_conn = mock_db
        task_record = make_task_record(task_id=1, status="pending")
        mock_conn.fetchrow.return_value = task_record

        result = await task_coordinator.get_task_result(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_set(self, task_coordinator: TaskCoordinator, mock_db):
        """Test writing to shared memory."""
        _pool, mock_conn = mock_db

        success = await task_coordinator.set_memory(
            "test_key",
            {"data": "test_value"},
        )

        assert success is True
        call_query = mock_conn.execute.call_args[0][0]
        assert "generals_memory" in call_query

    @pytest.mark.asyncio
    async def test_memory_get(self, task_coordinator: TaskCoordinator, mock_db):
        """Test reading from shared memory."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = {
            "value": {"data": "found"},
            "expires_at": None,
            "general_name": "task_coordinator",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        memory = await task_coordinator.get_memory("test_key")

        assert memory is not None
        assert memory["key"] == "test_key"
        assert memory["value"]["data"] == "found"

    @pytest.mark.asyncio
    async def test_memory_get_not_found(self, task_coordinator: TaskCoordinator, mock_db):
        """Test reading nonexistent memory key returns None."""
        _pool, mock_conn = mock_db
        mock_conn.fetchrow.return_value = None

        memory = await task_coordinator.get_memory("nonexistent")
        assert memory is None

    @pytest.mark.asyncio
    async def test_memory_delete(self, task_coordinator: TaskCoordinator, mock_db):
        """Test deleting a memory key."""
        _pool, mock_conn = mock_db
        mock_conn.execute.return_value = "DELETE 1"

        deleted = await task_coordinator.delete_memory("test_key")
        assert deleted is True

    @pytest.mark.asyncio
    async def test_memory_delete_not_found(self, task_coordinator: TaskCoordinator, mock_db):
        """Test deleting nonexistent memory key returns False."""
        _pool, mock_conn = mock_db
        mock_conn.execute.return_value = "DELETE 0"

        deleted = await task_coordinator.delete_memory("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_activity(self, task_coordinator: TaskCoordinator, mock_db):
        """Test getting activity log entries."""
        _pool, mock_conn = mock_db
        mock_conn.fetch.return_value = [
            {
                "id": 1,
                "general_name": "coding_general",
                "task_id": 10,
                "activity_type": "task_started",
                "message": "Started task",
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
            }
        ]

        activities = await task_coordinator.get_activity(
            general_name="coding_general",
            limit=10,
        )

        assert len(activities) == 1
        assert activities[0]["general_name"] == "coding_general"

    @pytest.mark.asyncio
    async def test_get_stats(self, task_coordinator: TaskCoordinator, mock_db):
        """Test getting system statistics."""
        _pool, mock_conn = mock_db

        # Mock three sequential fetchrow calls (tasks, memory, activity)
        mock_conn.fetchrow.side_effect = [
            {
                "total_tasks": 10,
                "pending_tasks": 3,
                "in_progress_tasks": 1,
                "completed_tasks": 5,
                "failed_tasks": 1,
                "code_tasks": 6,
                "research_tasks": 4,
            },
            {
                "total_memories": 5,
                "expired_memories": 1,
            },
            {
                "total_activities": 50,
                "recent_activities": 8,
            },
        ]

        stats = await task_coordinator.get_stats()

        assert "tasks" in stats
        assert "memory" in stats
        assert "activity" in stats
        assert stats["tasks"]["total_tasks"] == 10
        assert stats["memory"]["total_memories"] == 5
        assert stats["activity"]["total_activities"] == 50


# =============================================================================
# Integration Tests (mocked)
# =============================================================================


class TestIntegration:
    """Cross-component workflow tests with mocked DB."""

    @pytest.mark.asyncio
    async def test_full_code_workflow(
        self, task_coordinator: TaskCoordinator, coding_general: CodingGeneral, mock_db
    ):
        """Test: submit code task -> poll -> execute -> verify result."""
        _pool, mock_conn = mock_db

        # 1. Submit task (coordinator)
        mock_conn.fetchval.return_value = 100
        task_id = await task_coordinator.submit_task(
            task_type="code",
            title="Integration Echo",
            payload={"command": "echo integration"},
            priority=5,
        )
        assert task_id == 100

        # 2. Poll task (coding general)
        mock_conn.fetchrow.return_value = make_task_record(
            task_id=100,
            task_type="code",
            title="Integration Echo",
            payload={"command": "echo integration"},
        )
        task = await coding_general.poll_task()
        assert task is not None
        assert task["id"] == 100

        # 3. Execute task
        result = await coding_general.execute_task(task)
        assert result["status"] == "completed"
        assert "integration" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_full_research_workflow(
        self,
        task_coordinator: TaskCoordinator,
        intelligence_general: IntelligenceGeneral,
        mock_db,
    ):
        """Test: submit research task -> poll -> execute -> verify analysis."""
        _pool, mock_conn = mock_db

        # 1. Submit task
        mock_conn.fetchval.return_value = 200
        task_id = await task_coordinator.submit_task(
            task_type="research",
            title="Integration Research",
            payload={"query": "What is integration testing?"},
            priority=5,
        )
        assert task_id == 200

        # 2. Poll task
        mock_conn.fetchrow.return_value = make_task_record(
            task_id=200,
            task_type="research",
            title="Integration Research",
            payload={"query": "What is integration testing?"},
        )
        task = await intelligence_general.poll_task()
        assert task is not None

        # 3. Execute
        result = await intelligence_general.execute_task(task)
        assert result["status"] == "completed"
        assert result["analysis"] != ""
        assert result["model_used"] is not None

    @pytest.mark.asyncio
    async def test_memory_sharing_flow(
        self,
        task_coordinator: TaskCoordinator,
        intelligence_general: IntelligenceGeneral,
        coding_general: CodingGeneral,
        mock_db,
    ):
        """Test: one general writes memory, coordinator reads it."""
        _pool, mock_conn = mock_db

        # Intelligence general writes memory
        await intelligence_general._write_memory(
            "shared_findings",
            {"findings": "Important data from research"},
        )

        # Verify INSERT was called with correct key
        memory_calls = [
            c
            for c in mock_conn.execute.call_args_list
            if "generals_memory" in str(c) and "shared_findings" in str(c)
        ]
        assert len(memory_calls) > 0

        # Coordinator reads memory (mock the fetchrow return)
        mock_conn.fetchrow.return_value = {
            "value": {"findings": "Important data from research"},
            "expires_at": None,
            "general_name": "intelligence_general",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        memory = await task_coordinator.get_memory("shared_findings")
        assert memory is not None
        assert memory["value"]["findings"] == "Important data from research"


# =============================================================================
# FastAPI Router Tests
# =============================================================================


class TestFastAPIRouter:
    """Tests for the FastAPI router endpoints."""

    @pytest.mark.asyncio
    async def test_submit_task_endpoint(self, mock_db):
        """Test POST /api/generals/tasks endpoint."""
        from backend.generals.task_coordinator import (
            TaskSubmitRequest,
        )
        from backend.generals.task_coordinator import (
            submit_task as endpoint_submit_task,
        )

        pool, mock_conn = mock_db
        mock_conn.fetchval.return_value = 1

        with patch("backend.generals.task_coordinator.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test/test"
            coordinator = TaskCoordinator(database_url="postgresql://test/test")
            coordinator.pool = pool

            request = TaskSubmitRequest(
                task_type="code",
                title="Router Test",
                description="Test via router",
                payload={"command": "echo test"},
                priority=5,
            )

            result = await endpoint_submit_task(request, coordinator)
            assert result["task_id"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_endpoint(self, mock_db):
        """Test GET /api/generals/stats endpoint."""
        from backend.generals.task_coordinator import get_stats as endpoint_get_stats

        pool, mock_conn = mock_db

        mock_conn.fetchrow.side_effect = [
            {
                "total_tasks": 5,
                "pending_tasks": 2,
                "in_progress_tasks": 0,
                "completed_tasks": 3,
                "failed_tasks": 0,
                "code_tasks": 3,
                "research_tasks": 2,
            },
            {"total_memories": 1, "expired_memories": 0},
            {"total_activities": 10, "recent_activities": 3},
        ]

        with patch("backend.generals.task_coordinator.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test/test"
            coordinator = TaskCoordinator(database_url="postgresql://test/test")
            coordinator.pool = pool

            stats = await endpoint_get_stats(coordinator)
            assert stats.tasks["total_tasks"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
