"""
Integration Tests for AutonomousScheduler
Tests autonomous task scheduling and execution
"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAutonomousSchedulerIntegration:
    """Comprehensive integration tests for AutonomousScheduler"""

    @pytest_asyncio.fixture
    async def scheduler(self):
        """Create AutonomousScheduler instance"""
        from services.autonomous_scheduler import AutonomousScheduler

        return AutonomousScheduler()

    @pytest_asyncio.fixture
    async def mock_task_func(self):
        """Create mock task function"""

        async def task_func():
            return "task completed"

        return task_func

    def test_initialization(self, scheduler):
        """Test scheduler initialization"""
        assert scheduler is not None
        assert scheduler.tasks == {}
        assert scheduler._running is False

    def test_register_task(self, scheduler, mock_task_func):
        """Test registering a task"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=60)

        assert "test_task" in scheduler.tasks
        assert scheduler.tasks["test_task"].interval_seconds == 60
        assert scheduler.tasks["test_task"].enabled is True

    def test_register_task_disabled(self, scheduler, mock_task_func):
        """Test registering a disabled task"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=60, enabled=False)

        assert "test_task" in scheduler.tasks
        assert scheduler.tasks["test_task"].enabled is False

    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler, mock_task_func):
        """Test starting scheduler"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=1)

        await scheduler.start()

        assert scheduler._running is True

        # Clean up
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler, mock_task_func):
        """Test stopping scheduler"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=1)
        await scheduler.start()

        await scheduler.stop()

        assert scheduler._running is False

    def test_get_status(self, scheduler, mock_task_func):
        """Test getting scheduler status"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=60)

        status = scheduler.get_status()

        assert status is not None
        assert "running" in status
        assert "task_count" in status
        assert "tasks" in status
        assert "test_task" in status["tasks"]

    def test_enable_task(self, scheduler, mock_task_func):
        """Test enabling a task"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=60, enabled=False)

        result = scheduler.enable_task("test_task")

        assert result is True
        assert scheduler.tasks["test_task"].enabled is True

    def test_enable_task_not_found(self, scheduler):
        """Test enabling non-existent task"""
        result = scheduler.enable_task("nonexistent_task")

        assert result is False

    def test_disable_task(self, scheduler, mock_task_func):
        """Test disabling a task"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=60)

        result = scheduler.disable_task("test_task")

        assert result is True
        assert scheduler.tasks["test_task"].enabled is False

    def test_disable_task_not_found(self, scheduler):
        """Test disabling non-existent task"""
        result = scheduler.disable_task("nonexistent_task")

        assert result is False

    @pytest.mark.asyncio
    async def test_task_execution(self, scheduler):
        """Test task execution"""
        execution_count = 0

        async def counting_task():
            nonlocal execution_count
            execution_count += 1

        scheduler.register_task("counting_task", counting_task, interval_seconds=0.1)

        await scheduler.start()

        # Wait a bit for task to execute
        import asyncio

        await asyncio.sleep(0.3)

        await scheduler.stop()

        # Task should have executed at least once
        assert execution_count >= 1

    @pytest.mark.asyncio
    async def test_task_error_handling(self, scheduler):
        """Test task error handling"""
        error_count = 0

        async def failing_task():
            nonlocal error_count
            error_count += 1
            raise Exception("Task error")

        scheduler.register_task("failing_task", failing_task, interval_seconds=0.1)

        await scheduler.start()

        # Wait for task to fail
        import asyncio

        await asyncio.sleep(0.3)

        await scheduler.stop()

        # Task should have failed
        assert error_count >= 1
        assert scheduler.tasks["failing_task"].error_count >= 1

    @pytest.mark.asyncio
    async def test_task_timeout(self, scheduler):
        """Test task timeout handling"""

        async def slow_task():
            import asyncio

            await asyncio.sleep(2000)  # Longer than timeout

        scheduler.register_task("slow_task", slow_task, interval_seconds=0.1)

        await scheduler.start()

        # Wait for timeout
        import asyncio

        await asyncio.sleep(0.3)

        await scheduler.stop()

        # Task should have timed out
        assert scheduler.tasks["slow_task"].error_count >= 1

    def test_get_status_with_task_stats(self, scheduler, mock_task_func):
        """Test getting status with task statistics"""
        scheduler.register_task("test_task", mock_task_func, interval_seconds=60)

        status = scheduler.get_status()

        task_status = status["tasks"]["test_task"]
        assert "enabled" in task_status
        assert "interval_seconds" in task_status
        assert "run_count" in task_status
        assert "error_count" in task_status
        assert "last_error" in task_status
        assert "status" in task_status
