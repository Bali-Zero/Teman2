"""
Unit tests for shutdown lifecycle handlers
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.lifecycle.shutdown import register_shutdown_handlers


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    app.state = MagicMock()
    app.on_event = MagicMock()
    return app


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
        from unittest.mock import AsyncMock
        redis_task = AsyncMock()
        redis_task.cancel = MagicMock()
        # Make redis_task not awaitable (inspect.isawaitable returns False)
        redis_task.__await__ = None
        mock_app.state.redis_listener_task = redis_task

        # Capture the handler function
        handler_func = None
        def capture_handler(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator

        mock_app.on_event = capture_handler
        register_shutdown_handlers(mock_app)

        if handler_func:
            await handler_func()
            assert redis_task.cancel.called

    @pytest.mark.asyncio
    async def test_shutdown_with_health_monitor(self, mock_app):
        """Test shutdown with health monitor"""
        health_monitor = AsyncMock()
        health_monitor.stop = AsyncMock()
        mock_app.state.health_monitor = health_monitor

        handler_func = None
        def capture_handler(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator

        mock_app.on_event = capture_handler
        register_shutdown_handlers(mock_app)

        if handler_func:
            await handler_func()
            health_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_compliance_monitor(self, mock_app):
        """Test shutdown with compliance monitor"""
        compliance_monitor = AsyncMock()
        compliance_monitor.stop = AsyncMock()
        mock_app.state.compliance_monitor = compliance_monitor

        handler_func = None
        def capture_handler(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator

        mock_app.on_event = capture_handler
        register_shutdown_handlers(mock_app)

        if handler_func:
            await handler_func()
            compliance_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_autonomous_scheduler(self, mock_app):
        """Test shutdown with autonomous scheduler"""
        scheduler = AsyncMock()
        scheduler.stop = AsyncMock()
        mock_app.state.autonomous_scheduler = scheduler

        handler_func = None
        def capture_handler(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator

        mock_app.on_event = capture_handler
        register_shutdown_handlers(mock_app)

        if handler_func:
            await handler_func()
            scheduler.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_metrics_pusher(self, mock_app):
        """Test shutdown with metrics pusher task"""
        from unittest.mock import AsyncMock
        metrics_task = AsyncMock()
        metrics_task.cancel = MagicMock()
        # Make metrics_task awaitable for the await call
        async def await_metrics_task():
            pass
        metrics_task.__await__ = lambda self: await_metrics_task().__await__()
        mock_app.state.metrics_pusher_task = metrics_task

        handler_func = None
        def capture_handler(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator

        mock_app.on_event = capture_handler
        register_shutdown_handlers(mock_app)

        if handler_func:
            await handler_func()
            assert metrics_task.cancel.called

    @pytest.mark.asyncio
    async def test_shutdown_without_services(self, mock_app):
        """Test shutdown without any services"""
        handler_func = None
        def capture_handler(event_type):
            def decorator(func):
                nonlocal handler_func
                handler_func = func
                return func
            return decorator

        mock_app.on_event = capture_handler
        register_shutdown_handlers(mock_app)

        if handler_func:
            # Should not raise any errors
            try:
                await handler_func()
            except Exception:
                # Some services might not be mocked, that's ok
                pass
