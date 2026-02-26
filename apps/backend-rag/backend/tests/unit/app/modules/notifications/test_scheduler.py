"""
Test NotificationScheduler.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.modules.notifications.scheduler import (
    NotificationScheduler,
    get_scheduler,
    init_scheduler,
    stop_scheduler,
)


class TestNotificationScheduler:
    """Test scheduler lifecycle and job execution."""

    @pytest.fixture
    def mock_db_pool(self) -> MagicMock:
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool

    @pytest.fixture
    def scheduler(self, mock_db_pool: MagicMock) -> NotificationScheduler:
        return NotificationScheduler(db_pool=mock_db_pool)

    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler: NotificationScheduler):
        """Scheduler starts and registers jobs."""
        await scheduler.start()

        assert scheduler.is_running is True
        assert scheduler.scheduler is not None
        assert len(scheduler.scheduler.get_jobs()) == 2

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_twice_is_noop(self, scheduler: NotificationScheduler):
        """Starting an already-running scheduler does nothing."""
        await scheduler.start()
        await scheduler.start()  # Second call should be ignored

        assert scheduler.is_running is True
        assert len(scheduler.scheduler.get_jobs()) == 2

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler: NotificationScheduler):
        """Scheduler stops cleanly."""
        await scheduler.start()
        await scheduler.stop()

        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_stop_not_started(self, scheduler: NotificationScheduler):
        """Stopping a not-started scheduler does nothing."""
        await scheduler.stop()  # Should not raise
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_daily_check_no_pool(self):
        """Daily check returns early when no db_pool."""
        scheduler = NotificationScheduler(db_pool=None)

        await scheduler._daily_check()  # Should not raise

    @pytest.mark.asyncio
    async def test_daily_check_no_clients(self, scheduler: NotificationScheduler, mock_db_pool: MagicMock):
        """Daily check handles no clients gracefully."""
        with patch(
            "backend.app.modules.notifications.scheduler.get_clients_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await scheduler._daily_check()  # Should not raise

    @pytest.mark.asyncio
    async def test_daily_check_lock_prevents_concurrent(self, scheduler: NotificationScheduler):
        """Concurrent daily check calls are blocked by lock."""
        # Acquire the lock manually
        scheduler._daily_check_lock = asyncio.Lock()
        await scheduler._daily_check_lock.acquire()

        # Now calling _daily_check should skip (lock is held)
        await scheduler._daily_check()  # Should return immediately

        scheduler._daily_check_lock.release()

    @pytest.mark.asyncio
    async def test_send_pending_no_pool(self):
        """Send pending returns early when no db_pool."""
        scheduler = NotificationScheduler(db_pool=None)

        await scheduler._send_pending_alerts()  # Should not raise

    @pytest.mark.asyncio
    async def test_send_pending_lock_prevents_concurrent(self, scheduler: NotificationScheduler):
        """Concurrent send pending calls are blocked by lock."""
        scheduler._send_lock = asyncio.Lock()
        await scheduler._send_lock.acquire()

        await scheduler._send_pending_alerts()  # Should return immediately

        scheduler._send_lock.release()

    @pytest.mark.asyncio
    async def test_daily_check_exception_handling(self, scheduler: NotificationScheduler):
        """Daily check handles exceptions without crashing."""
        with patch(
            "backend.app.modules.notifications.scheduler.get_clients_from_db",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB connection failed"),
        ):
            await scheduler._daily_check()  # Should not raise

    @pytest.mark.asyncio
    async def test_send_pending_exception_handling(
        self, scheduler: NotificationScheduler, mock_db_pool: MagicMock
    ):
        """Send pending handles exceptions without crashing."""
        with patch(
            "backend.app.modules.notifications.scheduler.NotificationService"
        ) as MockService:
            MockService.return_value.get_pending_alerts = AsyncMock(
                side_effect=RuntimeError("Service error")
            )
            await scheduler._send_pending_alerts()  # Should not raise


class TestGlobalSchedulerFunctions:
    """Test module-level scheduler management functions."""

    @pytest.mark.asyncio
    async def test_init_and_get_scheduler(self):
        """init_scheduler creates and returns a running scheduler."""
        with patch.object(NotificationScheduler, "start", new_callable=AsyncMock):
            sched = await init_scheduler(db_pool=None)

            assert sched is not None
            result = get_scheduler()
            assert result is sched

            await stop_scheduler()
            assert get_scheduler() is None

    @pytest.mark.asyncio
    async def test_init_scheduler_twice_returns_existing(self):
        """Double init returns the existing running instance."""
        mock_pool = MagicMock()

        with patch.object(NotificationScheduler, "start", new_callable=AsyncMock):
            sched1 = await init_scheduler(db_pool=mock_pool)
            sched1.is_running = True  # Simulate running

            sched2 = await init_scheduler(db_pool=mock_pool)

            assert sched2 is sched1  # Same instance

            await stop_scheduler()

    @pytest.mark.asyncio
    async def test_stop_scheduler_not_initialized(self):
        """Stopping when not initialized does nothing."""
        # Ensure clean state
        import backend.app.modules.notifications.scheduler as sched_mod
        sched_mod._scheduler = None

        await stop_scheduler()  # Should not raise
