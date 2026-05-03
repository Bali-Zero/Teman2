"""
Unit tests for backend/services/misc/autonomous_scheduler.py
Covers: _get_client, close_scheduler_client, _get_redis, _acquire_task_lock,
        ScheduledTask, AutonomousScheduler, get_autonomous_scheduler,
        create_and_start_scheduler
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.misc.autonomous_scheduler import (
    AutonomousScheduler,
    ScheduledTask,
    _acquire_task_lock,
    _get_client,
    close_scheduler_client,
    get_autonomous_scheduler,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_module_globals() -> None:
    """Reset module-level globals between tests."""
    import backend.services.misc.autonomous_scheduler as mod

    mod._client = None
    mod._scheduler = None


@pytest.fixture
def scheduler() -> AutonomousScheduler:
    """Fresh scheduler instance."""
    return AutonomousScheduler()


@pytest.fixture
def mock_db_pool() -> MagicMock:
    """Mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn  # stash for assertions
    return pool


# ═══════════════════════════════════════════════════════════════════════════════
# _get_client / close_scheduler_client
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetClient:
    def test_creates_client_on_first_call(self) -> None:
        client = _get_client()
        assert client is not None
        assert not client.is_closed

    def test_returns_same_client(self) -> None:
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2

    def test_recreates_if_closed(self) -> None:
        c1 = _get_client()
        import backend.services.misc.autonomous_scheduler as mod

        # Simulate closure by patching is_closed
        mod._client = MagicMock(is_closed=True)
        c2 = _get_client()
        assert c2 is not mod._client or not c2.is_closed

    def test_custom_timeout(self) -> None:
        client = _get_client(timeout=60.0)
        assert client is not None


class TestCloseSchedulerClient:
    @pytest.mark.asyncio
    async def test_close_when_client_exists(self) -> None:
        import backend.services.misc.autonomous_scheduler as mod

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mod._client = mock_client

        await close_scheduler_client()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self) -> None:
        # Should not raise
        await close_scheduler_client()

    @pytest.mark.asyncio
    async def test_close_when_already_closed(self) -> None:
        import backend.services.misc.autonomous_scheduler as mod

        mock_client = AsyncMock()
        mock_client.is_closed = True
        mod._client = mock_client

        await close_scheduler_client()
        mock_client.aclose.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# _acquire_task_lock
# ═══════════════════════════════════════════════════════════════════════════════


class TestAcquireTaskLock:
    @pytest.mark.asyncio
    @patch("backend.services.misc.autonomous_scheduler._get_redis", new_callable=AsyncMock)
    async def test_no_redis_returns_true(self, mock_get_redis: AsyncMock) -> None:
        mock_get_redis.return_value = None
        result = await _acquire_task_lock("test_task", 300)
        assert result is True

    @pytest.mark.asyncio
    @patch("backend.services.misc.autonomous_scheduler._get_redis", new_callable=AsyncMock)
    async def test_lock_acquired(self, mock_get_redis: AsyncMock) -> None:
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        result = await _acquire_task_lock("test_task", 300)
        assert result is True
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("backend.services.misc.autonomous_scheduler._get_redis", new_callable=AsyncMock)
    async def test_lock_not_acquired(self, mock_get_redis: AsyncMock) -> None:
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=None)
        mock_get_redis.return_value = mock_redis

        result = await _acquire_task_lock("test_task", 300)
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.services.misc.autonomous_scheduler._get_redis", new_callable=AsyncMock)
    async def test_redis_error_returns_true(self, mock_get_redis: AsyncMock) -> None:
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_get_redis.return_value = mock_redis

        result = await _acquire_task_lock("test_task", 300)
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# ScheduledTask
# ═══════════════════════════════════════════════════════════════════════════════


class TestScheduledTask:
    def test_defaults(self) -> None:
        async def dummy() -> None:
            pass

        task = ScheduledTask(name="test", interval_seconds=60, task_func=dummy)
        assert task.enabled is True
        assert task.last_run is None
        assert task.run_count == 0
        assert task.error_count == 0
        assert task.last_error is None
        assert task._task is None

    def test_custom_values(self) -> None:
        async def dummy() -> None:
            pass

        task = ScheduledTask(
            name="custom",
            interval_seconds=120,
            task_func=dummy,
            enabled=False,
        )
        assert task.enabled is False
        assert task.interval_seconds == 120


# ═══════════════════════════════════════════════════════════════════════════════
# AutonomousScheduler
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutonomousScheduler:
    def test_init(self, scheduler: AutonomousScheduler) -> None:
        assert scheduler.tasks == {}
        assert scheduler._running is False

    def test_register_task(self, scheduler: AutonomousScheduler) -> None:
        async def dummy() -> None:
            pass

        scheduler.register_task("t1", dummy, 60)
        assert "t1" in scheduler.tasks
        assert scheduler.tasks["t1"].interval_seconds == 60
        assert scheduler.tasks["t1"].enabled is True

    def test_register_disabled_task(self, scheduler: AutonomousScheduler) -> None:
        async def dummy() -> None:
            pass

        scheduler.register_task("t2", dummy, 300, enabled=False)
        assert scheduler.tasks["t2"].enabled is False

    def test_enable_task(self, scheduler: AutonomousScheduler) -> None:
        async def dummy() -> None:
            pass

        scheduler.register_task("t", dummy, 60, enabled=False)
        result = scheduler.enable_task("t")
        assert result is True
        assert scheduler.tasks["t"].enabled is True

    def test_enable_nonexistent_task(self, scheduler: AutonomousScheduler) -> None:
        result = scheduler.enable_task("nonexistent")
        assert result is False

    def test_disable_task(self, scheduler: AutonomousScheduler) -> None:
        async def dummy() -> None:
            pass

        scheduler.register_task("t", dummy, 60, enabled=True)
        result = scheduler.disable_task("t")
        assert result is True
        assert scheduler.tasks["t"].enabled is False

    def test_disable_nonexistent_task(self, scheduler: AutonomousScheduler) -> None:
        result = scheduler.disable_task("nonexistent")
        assert result is False

    def test_get_status_empty(self, scheduler: AutonomousScheduler) -> None:
        status = scheduler.get_status()
        assert status["running"] is False
        assert status["task_count"] == 0
        assert status["tasks"] == {}

    def test_get_status_with_tasks(self, scheduler: AutonomousScheduler) -> None:
        async def dummy() -> None:
            pass

        scheduler.register_task("t1", dummy, 60)
        scheduler.register_task("t2", dummy, 120, enabled=False)
        status = scheduler.get_status()
        assert status["task_count"] == 2
        assert "t1" in status["tasks"]
        assert status["tasks"]["t1"]["enabled"] is True
        assert status["tasks"]["t2"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_start(self, scheduler: AutonomousScheduler) -> None:
        called = False

        async def quick_task() -> None:
            nonlocal called
            called = True

        scheduler.register_task("quick", quick_task, 9999)

        with patch(
            "backend.services.misc.autonomous_scheduler._acquire_task_lock",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await scheduler.start()
            assert scheduler._running is True

            # Give the task loop time to start but don't wait for it to run
            await asyncio.sleep(0.05)
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, scheduler: AutonomousScheduler) -> None:
        scheduler._running = True
        await scheduler.start()  # Should return early

    @pytest.mark.asyncio
    async def test_stop_not_running(self, scheduler: AutonomousScheduler) -> None:
        await scheduler.stop()  # Should return early without error

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self, scheduler: AutonomousScheduler) -> None:
        async def slow_task() -> None:
            await asyncio.sleep(9999)

        scheduler.register_task("slow", slow_task, 9999)

        with patch(
            "backend.services.misc.autonomous_scheduler._acquire_task_lock",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await scheduler.start()
            assert scheduler._running is True
            await asyncio.sleep(0.05)
            await scheduler.stop()
            assert scheduler._running is False


# ═══════════════════════════════════════════════════════════════════════════════
# get_autonomous_scheduler (singleton)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAutonomousScheduler:
    def test_creates_singleton(self) -> None:
        s1 = get_autonomous_scheduler()
        s2 = get_autonomous_scheduler()
        assert s1 is s2

    def test_is_instance(self) -> None:
        s = get_autonomous_scheduler()
        assert isinstance(s, AutonomousScheduler)


# ═══════════════════════════════════════════════════════════════════════════════
# create_and_start_scheduler
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateAndStartScheduler:
    @pytest.mark.asyncio
    async def test_minimal_start(self, mock_db_pool: MagicMock) -> None:
        """Start scheduler with all optional features disabled."""
        from backend.services.misc.autonomous_scheduler import create_and_start_scheduler

        mock_db_pool._conn.fetchval = AsyncMock(return_value=5)  # golden routes seeded

        with (
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler.os.getenv",
                side_effect=lambda k, d="": {
                    "FLY_MACHINE_ID": "test",
                    "ENVIRONMENT": "production",
                    "ENABLE_KG_INCREMENTAL": "false",
                    "MCP_SERVER_URL": "http://localhost:8000",
                }.get(k, d),
            ),
            patch(
                "backend.services.crm.birthday_notifier_service.run_birthday_notifier_task",
                new_callable=AsyncMock,
                create=True,
            ),
        ):
            scheduler = await create_and_start_scheduler(
                db_pool=mock_db_pool,
                ai_client=MagicMock(),
                search_service=MagicMock(),
                auto_ingestion_enabled=False,
                self_healing_enabled=False,
                conversation_trainer_enabled=False,
                conversation_cleanup_enabled=False,
            )
            assert isinstance(scheduler, AutonomousScheduler)
            assert scheduler._running is True
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_no_db_pool(self) -> None:
        """Scheduler still starts even without db_pool (fewer tasks registered)."""
        from backend.services.misc.autonomous_scheduler import create_and_start_scheduler

        with (
            patch(
                "backend.services.misc.autonomous_scheduler._acquire_task_lock",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "backend.services.misc.autonomous_scheduler.os.getenv",
                side_effect=lambda k, d="": {
                    "ENVIRONMENT": "production",
                    "ENABLE_KG_INCREMENTAL": "false",
                }.get(k, d),
            ),
            patch(
                "backend.services.crm.birthday_notifier_service.run_birthday_notifier_task",
                new_callable=AsyncMock,
                create=True,
            ),
        ):
            scheduler = await create_and_start_scheduler(
                db_pool=None,
                ai_client=MagicMock(),
                search_service=MagicMock(),
                self_healing_enabled=False,
            )
            assert scheduler._running is True
            await scheduler.stop()
