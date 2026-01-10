"""
Unit tests for shutdown lifecycle handlers
Target: >95% coverage
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.lifecycle.shutdown import register_shutdown_handlers


@pytest.fixture
def mock_app():
    """Mock FastAPI app with properly configured state"""
    app = MagicMock()
    # Create a simple namespace for state to avoid MagicMock auto-creation
    app.state = MagicMock()
    # Explicitly set all state attributes to None
    app.state.redis_listener_task = None
    app.state.health_monitor = None
    app.state.compliance_monitor = None
    app.state.autonomous_scheduler = None
    app.state.metrics_pusher_task = None
    app.state.daily_notifier = None
    app.state.ts_service = None
    app.state.db_health_check_task = None
    app.on_event = MagicMock()
    return app


def capture_shutdown_handler(mock_app):
    """Capture the shutdown handler function"""
    handler_func = None

    def capture_handler(event_type):
        def decorator(func):
            nonlocal handler_func
            handler_func = func
            return func

        return decorator

    mock_app.on_event = capture_handler
    register_shutdown_handlers(mock_app)
    return handler_func


class TestShutdownHandlers:
    """Tests for shutdown handlers"""

    def test_register_shutdown_handlers(self, mock_app):
        """Test registering shutdown handlers"""
        register_shutdown_handlers(mock_app)
        # Verify on_event was called
        assert mock_app.on_event.called

    @pytest.mark.asyncio
    async def test_shutdown_with_redis_task(self, mock_app):
        """Test shutdown with Redis listener task"""
        # Create a proper async task mock
        redis_task = MagicMock()
        redis_task.cancel = MagicMock()

        mock_app.state.redis_listener_task = redis_task

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            assert redis_task.cancel.called

    @pytest.mark.asyncio
    async def test_shutdown_with_health_monitor(self, mock_app):
        """Test shutdown with health monitor"""
        health_monitor = MagicMock()
        health_monitor.stop = AsyncMock()
        mock_app.state.health_monitor = health_monitor

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            health_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_compliance_monitor(self, mock_app):
        """Test shutdown with compliance monitor"""
        compliance_monitor = MagicMock()
        compliance_monitor.stop = AsyncMock()
        mock_app.state.compliance_monitor = compliance_monitor

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            compliance_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_autonomous_scheduler(self, mock_app):
        """Test shutdown with autonomous scheduler"""
        scheduler = MagicMock()
        scheduler.stop = AsyncMock()
        mock_app.state.autonomous_scheduler = scheduler

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            scheduler.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_metrics_pusher(self, mock_app):
        """Test shutdown with metrics pusher task"""

        # Create an awaitable task mock - must be awaitable after cancel()
        async def cancelled_task():
            raise asyncio.CancelledError()

        metrics_task = asyncio.create_task(asyncio.sleep(100))
        mock_app.state.metrics_pusher_task = metrics_task

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            assert metrics_task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_with_daily_notifier(self, mock_app):
        """Test shutdown with daily notifier"""
        daily_notifier = MagicMock()
        daily_notifier.stop = AsyncMock()
        mock_app.state.daily_notifier = daily_notifier

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            daily_notifier.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_ts_service(self, mock_app):
        """Test shutdown with team timesheet service"""
        ts_service = MagicMock()
        ts_service.stop_auto_logout_monitor = AsyncMock()
        mock_app.state.ts_service = ts_service

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            ts_service.stop_auto_logout_monitor.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_db_health_check(self, mock_app):
        """Test shutdown with database health check task"""
        # Create a real async task that can be cancelled
        db_task = asyncio.create_task(asyncio.sleep(100))

        mock_app.state.db_health_check_task = db_task

        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            await handler_func()
            assert db_task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_without_services(self, mock_app):
        """Test shutdown without any services"""
        handler_func = capture_shutdown_handler(mock_app)

        if handler_func:
            # Should not raise any errors
            await handler_func()
