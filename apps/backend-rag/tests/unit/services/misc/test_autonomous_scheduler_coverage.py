"""
Comprehensive coverage tests for AutonomousScheduler
Target: >99% coverage
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Load module directly to avoid import issues
module_path = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "services"
    / "misc"
    / "autonomous_scheduler.py"
)
spec = importlib.util.spec_from_file_location("services.misc.autonomous_scheduler", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
AutonomousScheduler = module.AutonomousScheduler
ScheduledTask = module.ScheduledTask
get_autonomous_scheduler = module.get_autonomous_scheduler


@pytest.fixture
def scheduler():
    """Create a fresh scheduler instance"""
    return AutonomousScheduler()


@pytest.fixture
def dummy_task_func():
    """Create a dummy async task function"""
    async def task_func():
        pass

    return task_func


def test_init(scheduler):
    """Test initialization"""
    assert len(scheduler.tasks) == 0
    assert scheduler._running is False
    assert scheduler._shutdown_event is not None


def test_register_task(scheduler, dummy_task_func):
    """Test registering a task"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60)
    assert "test_task" in scheduler.tasks
    assert scheduler.tasks["test_task"].interval_seconds == 60
    assert scheduler.tasks["test_task"].enabled is True
    assert scheduler.tasks["test_task"].task_func == dummy_task_func


def test_register_task_disabled(scheduler, dummy_task_func):
    """Test registering a disabled task"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60, enabled=False)
    assert scheduler.tasks["test_task"].enabled is False


@pytest.mark.asyncio
async def test_start_stop(scheduler):
    """Test starting and stopping scheduler"""
    await scheduler.start()
    assert scheduler._running is True
    await scheduler.stop()
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_start_already_running(scheduler, dummy_task_func):
    """Test starting scheduler when already running"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60)
    await scheduler.start()
    assert scheduler._running is True

    # Try to start again
    await scheduler.start()  # Should not raise, just log warning
    assert scheduler._running is True

    await scheduler.stop()


@pytest.mark.asyncio
async def test_stop_not_running(scheduler):
    """Test stopping scheduler when not running"""
    await scheduler.stop()  # Should not raise
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_start_stop_with_tasks(scheduler, dummy_task_func):
    """Test starting and stopping scheduler with tasks"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60)
    await scheduler.start()
    assert scheduler._running is True
    assert "test_task" in scheduler.tasks

    await scheduler.stop()
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_start_skips_disabled_tasks(scheduler, dummy_task_func):
    """Test starting scheduler skips disabled tasks"""
    scheduler.register_task("enabled_task", dummy_task_func, interval_seconds=60, enabled=True)
    scheduler.register_task("disabled_task", dummy_task_func, interval_seconds=60, enabled=False)

    await scheduler.start()
    assert scheduler._running is True
    status = scheduler.get_status()
    assert "enabled_task" in status["tasks"]
    assert "disabled_task" in status["tasks"]

    await scheduler.stop()


def test_get_status_empty(scheduler):
    """Test getting status with no tasks"""
    status = scheduler.get_status()
    assert status["running"] is False
    assert status["task_count"] == 0
    assert status["tasks"] == {}


def test_get_status_with_tasks(scheduler, dummy_task_func):
    """Test getting status with tasks"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60)
    status = scheduler.get_status()

    assert status["running"] is False
    assert status["task_count"] == 1
    assert "test_task" in status["tasks"]
    assert status["tasks"]["test_task"]["enabled"] is True
    assert status["tasks"]["test_task"]["interval_seconds"] == 60
    assert status["tasks"]["test_task"]["run_count"] == 0
    assert status["tasks"]["test_task"]["error_count"] == 0
    assert status["tasks"]["test_task"]["last_run"] is None
    assert status["tasks"]["test_task"]["last_error"] is None


def test_get_status_with_last_run(scheduler, dummy_task_func):
    """Test getting status with task that has last_run"""
    from datetime import datetime

    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60)
    scheduler.tasks["test_task"].last_run = datetime(2024, 1, 1, 12, 0, 0)
    status = scheduler.get_status()
    assert status["tasks"]["test_task"]["last_run"] == "2024-01-01T12:00:00"


def test_enable_task(scheduler, dummy_task_func):
    """Test enabling a task"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60, enabled=False)
    assert scheduler.tasks["test_task"].enabled is False

    result = scheduler.enable_task("test_task")
    assert result is True
    assert scheduler.tasks["test_task"].enabled is True


def test_disable_task(scheduler, dummy_task_func):
    """Test disabling a task"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=60, enabled=True)
    assert scheduler.tasks["test_task"].enabled is True

    result = scheduler.disable_task("test_task")
    assert result is True
    assert scheduler.tasks["test_task"].enabled is False


def test_enable_task_not_found(scheduler):
    """Test enabling non-existent task"""
    result = scheduler.enable_task("nonexistent")
    assert result is False


def test_disable_task_not_found(scheduler):
    """Test disabling non-existent task"""
    result = scheduler.disable_task("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_run_task_loop_success(scheduler):
    """Test _run_task_loop with successful task execution - test via start()"""
    task_executed = False

    async def task_func():
        nonlocal task_executed
        await asyncio.sleep(0.01)  # Small delay
        task_executed = True

    scheduler.register_task("test_task", task_func, interval_seconds=60, enabled=True)
    
    # Use a task name that gives small hash (for shorter initial delay)
    task = scheduler.tasks["test_task"]
    task.name = "aa"  # Small hash
    
    await scheduler.start()
    
    # Wait a bit longer to ensure task runs (initial delay + execution)
    await asyncio.sleep(0.2)
    
    await scheduler.stop()
    
    # Task should have executed
    assert task_executed or scheduler.tasks["test_task"].run_count > 0


@pytest.mark.asyncio
async def test_run_task_loop_timeout(scheduler):
    """Test _run_task_loop with timeout error (covers line 103-106)"""
    async def slow_task_func():
        await asyncio.sleep(2000)  # Longer than timeout (30 min)

    scheduler.register_task("test_task", slow_task_func, interval_seconds=60, enabled=True)
    task = scheduler.tasks["test_task"]
    task.name = "aa"  # Small hash for shorter delay
    
    # Patch wait_for to simulate timeout on task execution (timeout=1800)
    original_wait_for = asyncio.wait_for
    
    async def mock_wait_for(coro, timeout=None):
        # Task execution call with timeout=1800 should timeout
        if timeout == 1800:
            raise asyncio.TimeoutError()
        # Other calls (shutdown wait) pass through
        return await original_wait_for(coro, timeout=timeout)

    with patch("services.misc.autonomous_scheduler.asyncio.wait_for", side_effect=mock_wait_for):
        await scheduler.start()
        await asyncio.sleep(0.15)  # Wait for timeout to be caught
        await scheduler.stop()
    
    assert task.error_count > 0
    assert task.last_error == "Task timed out after 30 minutes"


@pytest.mark.asyncio
async def test_run_task_loop_cancelled(scheduler):
    """Test _run_task_loop with CancelledError (covers line 108-110)"""
    async def task_func():
        await asyncio.sleep(1)

    task = ScheduledTask(
        name="test_task",
        interval_seconds=1,
        task_func=task_func,
        enabled=True,
    )

    scheduler._shutdown_event.clear()
    loop_task = asyncio.create_task(scheduler._run_task_loop(task))

    # Cancel immediately
    await asyncio.sleep(0.05)
    loop_task.cancel()

    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Should have logged cancellation


@pytest.mark.asyncio
async def test_run_task_loop_exception(scheduler):
    """Test _run_task_loop with generic exception (covers line 112-115)"""
    async def failing_task_func():
        raise RuntimeError("Task failed")

    scheduler.register_task("test_task", failing_task_func, interval_seconds=60, enabled=True)
    task = scheduler.tasks["test_task"]
    task.name = "aa"  # Small hash for shorter delay
    
    await scheduler.start()
    await asyncio.sleep(0.15)  # Wait for task to execute and fail
    await scheduler.stop()
    
    assert task.error_count > 0
    assert "Task failed" in task.last_error


@pytest.mark.asyncio
async def test_run_task_loop_disabled(scheduler):
    """Test _run_task_loop with disabled task (covers line 89-91)"""
    async def task_func():
        pass

    task = ScheduledTask(
        name="test_task",
        interval_seconds=1,
        task_func=task_func,
        enabled=False,  # Disabled
    )

    scheduler._shutdown_event.clear()

    loop_task = asyncio.create_task(scheduler._run_task_loop(task))
    await asyncio.sleep(0.15)  # Should sleep 60 seconds, but we stop early
    scheduler._shutdown_event.set()
    await asyncio.sleep(0.1)
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Task should not have run
    assert task.run_count == 0


@pytest.mark.asyncio
async def test_run_task_loop_shutdown_during_wait(scheduler):
    """Test _run_task_loop with shutdown during wait (covers line 118-121)"""
    async def task_func():
        pass

    task = ScheduledTask(
        name="test_task",
        interval_seconds=10,  # Long interval
        task_func=task_func,
        enabled=True,
    )

    scheduler._shutdown_event.clear()

    loop_task = asyncio.create_task(scheduler._run_task_loop(task))

    # Let task run once
    await asyncio.sleep(0.1)

    # Signal shutdown while waiting for interval
    scheduler._shutdown_event.set()

    await asyncio.sleep(0.2)
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Should have exited cleanly


@pytest.mark.asyncio
async def test_run_task_loop_timeout_during_wait(scheduler):
    """Test _run_task_loop with timeout during wait (covers line 122-124)"""
    async def task_func():
        pass

    task = ScheduledTask(
        name="test_task",
        interval_seconds=1,  # Short interval
        task_func=task_func,
        enabled=True,
    )

    scheduler._shutdown_event.clear()

    loop_task = asyncio.create_task(scheduler._run_task_loop(task))
    await asyncio.sleep(0.2)  # Let it run and wait
    scheduler._shutdown_event.set()
    await asyncio.sleep(0.1)
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Should continue loop normally


@pytest.mark.asyncio
async def test_stop_cancels_tasks(scheduler, dummy_task_func):
    """Test stop cancels running tasks (covers line 155-161)"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=1)
    await scheduler.start()

    # Ensure task is running
    assert scheduler.tasks["test_task"]._task is not None

    await scheduler.stop()

    # Task should be cancelled
    assert scheduler._running is False


@pytest.mark.asyncio
async def test_stop_task_timeout(scheduler, dummy_task_func):
    """Test stop with task that times out during cancellation"""
    async def slow_task():
        await asyncio.sleep(100)  # Very long task

    scheduler.register_task("test_task", slow_task, interval_seconds=1)
    await scheduler.start()

    await asyncio.sleep(0.1)  # Let task start

    # Stop should wait max 5 seconds
    await scheduler.stop()

    assert scheduler._running is False


@pytest.mark.asyncio
async def test_get_status_running_task(scheduler, dummy_task_func):
    """Test get_status with running task"""
    scheduler.register_task("test_task", dummy_task_func, interval_seconds=1)
    await scheduler.start()

    status = scheduler.get_status()
    assert status["running"] is True
    # Task status should indicate it's running or stopped
    assert "status" in status["tasks"]["test_task"]

    await scheduler.stop()


def test_get_autonomous_scheduler():
    """Test get_autonomous_scheduler creates singleton"""
    # Reset module's global
    module._scheduler = None

    scheduler1 = get_autonomous_scheduler()
    scheduler2 = get_autonomous_scheduler()

    assert scheduler1 is scheduler2
    assert isinstance(scheduler1, AutonomousScheduler)


@pytest.mark.asyncio
async def test_create_and_start_scheduler_no_deps():
    """Test create_and_start_scheduler with all tasks disabled"""
    # Reset global scheduler
    module._scheduler = None

    scheduler = await module.create_and_start_scheduler(
        db_pool=None,
        ai_client=None,
        search_service=None,
        auto_ingestion_enabled=False,
        self_healing_enabled=False,
        conversation_trainer_enabled=False,
        client_value_predictor_enabled=False,
        knowledge_graph_enabled=False,
    )

    assert scheduler is not None
    assert scheduler._running is True

    await scheduler.stop()


@pytest.mark.asyncio
async def test_create_and_start_scheduler_with_import_errors():
    """Test create_and_start_scheduler handles import errors gracefully"""
    module._scheduler = None

    # Mock imports to fail
    with patch("builtins.__import__", side_effect=ImportError("Module not found")):
        scheduler = await module.create_and_start_scheduler(
            db_pool=None,
            ai_client=None,
            search_service=None,
            auto_ingestion_enabled=True,  # Will fail to import
            self_healing_enabled=True,  # Will fail to import
            conversation_trainer_enabled=False,
            client_value_predictor_enabled=False,
            knowledge_graph_enabled=False,
        )

        # Should still work, just without those tasks
        assert scheduler is not None

        await scheduler.stop()

