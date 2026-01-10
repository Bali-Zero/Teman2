"""
Tests for AutonomousScheduler
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_root = Path(__file__).parents[4] / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.fixture(autouse=True)
def mock_asyncio_sleep(monkeypatch):
    """Mock asyncio.sleep globally for all tests in this module"""
    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(asyncio, "sleep", mock)
    return mock


@pytest.fixture
def scheduler_module(monkeypatch):
    """Force fresh import of autonomous_scheduler module"""
    if "backend.services.misc.autonomous_scheduler" in sys.modules:
        del sys.modules["backend.services.misc.autonomous_scheduler"]
    import backend.services.misc.autonomous_scheduler as mod
    return mod


@pytest.fixture
def scheduler(scheduler_module):
    """Create AutonomousScheduler instance"""
    return scheduler_module.AutonomousScheduler()


@pytest.mark.asyncio
async def test_run_task_loop_success(scheduler, monkeypatch, scheduler_module):
    """Test successful task execution in loop"""
    task_executed = False

    async def task_func():
        nonlocal task_executed
        task_executed = True

    task = scheduler_module.ScheduledTask(
        name="test_task",
        interval_seconds=1,
        task_func=task_func,
        enabled=True
    )
    
    scheduler._shutdown_event.clear()
    
    async def wait_side_effect(coro, timeout=None):
        if timeout == 1800:
            await coro
            return None
        scheduler._shutdown_event.set()
        return True
        
    mock_wait = AsyncMock(side_effect=wait_side_effect)
    monkeypatch.setattr(scheduler_module.asyncio, "wait_for", mock_wait)
    
    await scheduler._run_task_loop(task)
    
    assert task_executed is True
    assert task.run_count == 1


@pytest.mark.asyncio
async def test_run_task_loop_timeout(scheduler, monkeypatch, scheduler_module):
    """Test _run_task_loop with timeout error"""
    async def slow_task_func():
        await asyncio.sleep(10)

    task = scheduler_module.ScheduledTask(
        name="test_task",
        interval_seconds=1,
        task_func=slow_task_func,
        enabled=True
    )
    
    scheduler._shutdown_event.clear()
    
    async def wait_side_effect(coro, timeout=None):
        if timeout == 1800:
            raise asyncio.TimeoutError()
        scheduler._shutdown_event.set()
        return True
        
    mock_wait = AsyncMock(side_effect=wait_side_effect)
    monkeypatch.setattr(scheduler_module.asyncio, "wait_for", mock_wait)
    
    await scheduler._run_task_loop(task)
    
    assert task.error_count == 1


@pytest.mark.asyncio
async def test_run_task_loop_exception(scheduler, monkeypatch, scheduler_module):
    """Test _run_task_loop with generic exception"""
    async def failing_task_func():
        raise RuntimeError("Boom")

    task = scheduler_module.ScheduledTask(
        name="test_task",
        interval_seconds=1,
        task_func=failing_task_func,
        enabled=True
    )
    
    scheduler._shutdown_event.clear()
    
    async def wait_side_effect(coro, timeout=None):
        if timeout == 1800:
            return await coro
        scheduler._shutdown_event.set()
        return True
        
    mock_wait = AsyncMock(side_effect=wait_side_effect)
    monkeypatch.setattr(scheduler_module.asyncio, "wait_for", mock_wait)
    
    await scheduler._run_task_loop(task)
    
    assert task.error_count == 1
    assert "Boom" in task.last_error


@pytest.mark.asyncio
async def test_create_and_start_scheduler_success(monkeypatch, scheduler_module):
    """Test create_and_start_scheduler factory"""
    db_pool = MagicMock()
    ai_client = MagicMock()
    search_service = MagicMock()
    
    app = MagicMock()
    app.state = MagicMock()
    
    sched = MagicMock()
    sched.start = AsyncMock()
    monkeypatch.setattr(scheduler_module, "get_autonomous_scheduler", lambda: sched)
    
    result = await scheduler_module.create_and_start_scheduler(db_pool, ai_client, search_service)
    
    assert sched.start.called
    assert result is sched