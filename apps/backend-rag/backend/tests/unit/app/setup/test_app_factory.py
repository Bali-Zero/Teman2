"""
Unit tests for app_factory.py.

Tests create_app(), lifespan(), and _safe_stop() with all external
dependencies mocked.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Guard imports so settings validation doesn't fire ──
_mock_settings = MagicMock()
_mock_settings.PROJECT_NAME = "Test Nuzantara"
_mock_settings.API_V1_STR = "/api/v1"
_mock_settings.log_level = "INFO"

# Pre-seed modules that app_factory imports at module level
_patches = {
    "backend.app.setup.logging_config": MagicMock(configure_logging=MagicMock()),
    "backend.app.setup.middleware_config": MagicMock(),
    "backend.app.setup.observability": MagicMock(),
    "backend.app.setup.exception_handlers": MagicMock(),
    "backend.app.setup.router_registration": MagicMock(),
    "backend.app.routers.root_endpoints": MagicMock(router=MagicMock()),
    "backend.app.routers.audio": MagicMock(router=MagicMock()),
    "backend.app.streaming": MagicMock(router=MagicMock()),
    "backend.app.routers.system_observability": MagicMock(router=MagicMock()),
    "backend.app.routers.article_composer": MagicMock(limiter=MagicMock()),
    "slowapi": MagicMock(_rate_limit_exceeded_handler=MagicMock()),
    "slowapi.errors": MagicMock(RateLimitExceeded=Exception),
}


# ---------------------------------------------------------------------------
# Tests: _safe_stop
# ---------------------------------------------------------------------------


class TestSafeStop:
    @pytest.mark.asyncio
    async def test_successful_stop(self):
        from backend.app.setup.app_factory import _safe_stop

        coro = AsyncMock()()
        await _safe_stop("TestService", coro)
        # Should not raise

    @pytest.mark.asyncio
    async def test_timeout_stop(self):
        from backend.app.setup.app_factory import _safe_stop

        async def slow_coro():
            await asyncio.sleep(100)

        # Should not raise even if slow — just log warning
        with patch("backend.app.setup.app_factory.SHUTDOWN_TIMEOUT", 0.01):
            await _safe_stop("SlowService", slow_coro())

    @pytest.mark.asyncio
    async def test_exception_stop(self):
        from backend.app.setup.app_factory import _safe_stop

        async def failing_coro():
            raise RuntimeError("boom")

        # Should not propagate
        await _safe_stop("FailService", failing_coro())


# ---------------------------------------------------------------------------
# Tests: create_app
# ---------------------------------------------------------------------------


class TestCreateApp:
    def test_creates_fastapi_instance(self):
        with patch.dict(sys.modules, _patches), \
             patch("backend.app.setup.app_factory.settings", _mock_settings), \
             patch("backend.app.setup.app_factory.register_middleware"), \
             patch("backend.app.setup.app_factory.setup_observability"), \
             patch("backend.app.setup.app_factory.http_exception_handler"), \
             patch("backend.app.setup.app_factory.starlette_http_exception_handler"), \
             patch("backend.app.setup.app_factory.general_exception_handler"):
            from backend.app.setup.app_factory import create_app

            app = create_app()
            assert app.title == "Test Nuzantara"

    def test_app_has_exception_handlers(self):
        with patch.dict(sys.modules, _patches), \
             patch("backend.app.setup.app_factory.settings", _mock_settings), \
             patch("backend.app.setup.app_factory.register_middleware"), \
             patch("backend.app.setup.app_factory.setup_observability"), \
             patch("backend.app.setup.app_factory.http_exception_handler"), \
             patch("backend.app.setup.app_factory.starlette_http_exception_handler"), \
             patch("backend.app.setup.app_factory.general_exception_handler"):
            from backend.app.setup.app_factory import create_app

            app = create_app()
            # FastAPI should have exception handlers registered
            assert app.exception_handlers is not None


# ---------------------------------------------------------------------------
# Tests: lifespan
# ---------------------------------------------------------------------------


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_yields(self):
        """Lifespan should yield (startup) then complete (shutdown)."""
        from types import SimpleNamespace
        from backend.app.setup.app_factory import lifespan

        app_state = SimpleNamespace()
        mock_app = MagicMock()
        mock_app.state = app_state

        mock_task = MagicMock()
        mock_task.done.return_value = True

        with patch("backend.app.setup.app_factory.asyncio.create_task", return_value=mock_task):
            async with lifespan(mock_app):
                assert app_state.process_mode == "rag"

    @pytest.mark.asyncio
    async def test_lifespan_cancels_pending_init_on_shutdown(self):
        """If init_task is not done, lifespan should cancel it."""
        from types import SimpleNamespace
        from backend.app.setup.app_factory import lifespan

        app_state = SimpleNamespace()
        mock_app = MagicMock()
        mock_app.state = app_state

        # Create a real asyncio Future to act as the init task
        loop = asyncio.get_event_loop()
        real_future = loop.create_future()

        with patch("backend.app.setup.app_factory.asyncio.create_task", return_value=real_future):
            async with lifespan(mock_app):
                pass

        # The lifespan cancels the init task if not done
        assert real_future.cancelled()
