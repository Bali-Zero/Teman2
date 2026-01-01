"""
Unit tests for AutonomousScheduler
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import asyncio

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.autonomous_scheduler import AutonomousScheduler, ScheduledTask


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

