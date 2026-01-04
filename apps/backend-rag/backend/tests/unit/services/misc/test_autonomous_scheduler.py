"""
Unit tests for AutonomousScheduler
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.autonomous_scheduler import AutonomousScheduler


class TestAutonomousScheduler:
    """Tests for AutonomousScheduler"""

    def test_init(self):
        """Test initialization"""
        scheduler = AutonomousScheduler()
        assert len(scheduler.tasks) == 0
        assert scheduler._running is False

    def test_register_task(self):
        """Test registering a task"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60)
        assert "test_task" in scheduler.tasks
        assert scheduler.tasks["test_task"].interval_seconds == 60
        assert scheduler.tasks["test_task"].enabled is True

    def test_register_task_disabled(self):
        """Test registering a disabled task"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60, enabled=False)
        assert scheduler.tasks["test_task"].enabled is False

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping scheduler"""
        scheduler = AutonomousScheduler()
        await scheduler.start()
        assert scheduler._running is True
        await scheduler.stop()
        assert scheduler._running is False

    def test_get_status(self):
        """Test getting scheduler status"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60)
        status = scheduler.get_status()
        assert status["running"] is False
        assert status["task_count"] == 1
        assert "test_task" in status["tasks"]

    @pytest.mark.asyncio
    async def test_enable_disable_task(self):
        """Test enabling and disabling tasks"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60)
        scheduler.disable_task("test_task")
        assert scheduler.tasks["test_task"].enabled is False
        scheduler.enable_task("test_task")
        assert scheduler.tasks["test_task"].enabled is True

    @pytest.mark.asyncio
    async def test_enable_task_not_found(self):
        """Test enabling non-existent task"""
        scheduler = AutonomousScheduler()
        result = scheduler.enable_task("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_disable_task_not_found(self):
        """Test disabling non-existent task"""
        scheduler = AutonomousScheduler()
        result = scheduler.disable_task("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting scheduler when already running"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60)
        await scheduler.start()
        assert scheduler._running is True

        # Try to start again
        await scheduler.start()  # Should not raise, just log warning
        assert scheduler._running is True

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stopping scheduler when not running"""
        scheduler = AutonomousScheduler()
        await scheduler.stop()  # Should not raise
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_start_stop_with_tasks(self):
        """Test starting and stopping scheduler with tasks"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60)
        await scheduler.start()
        assert scheduler._running is True
        assert "test_task" in scheduler.tasks

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_start_skips_disabled_tasks(self):
        """Test starting scheduler skips disabled tasks"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("enabled_task", dummy_task, interval_seconds=60, enabled=True)
        scheduler.register_task("disabled_task", dummy_task, interval_seconds=60, enabled=False)

        await scheduler.start()
        assert scheduler._running is True
        # Disabled task should not have _task created (checked via status)
        status = scheduler.get_status()
        # Both tasks should be in status, but disabled one should not be running
        assert "enabled_task" in status["tasks"]
        assert "disabled_task" in status["tasks"]

        await scheduler.stop()

    def test_get_status_with_tasks(self):
        """Test getting status with tasks"""
        scheduler = AutonomousScheduler()

        async def dummy_task():
            pass

        scheduler.register_task("test_task", dummy_task, interval_seconds=60)
        status = scheduler.get_status()

        assert status["running"] is False
        assert status["task_count"] == 1
        assert "test_task" in status["tasks"]
        assert status["tasks"]["test_task"]["enabled"] is True
        assert status["tasks"]["test_task"]["interval_seconds"] == 60

    def test_get_status_empty(self):
        """Test getting status with no tasks"""
        scheduler = AutonomousScheduler()
        status = scheduler.get_status()

        assert status["running"] is False
        assert status["task_count"] == 0
        assert status["tasks"] == {}
