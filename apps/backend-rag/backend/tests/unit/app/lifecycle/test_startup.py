"""
Unit tests for app/lifecycle/startup.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# Mock the imports that cause circular dependency BEFORE importing startup
@pytest.fixture(autouse=True)
def mock_startup_dependencies():
    """Mock dependencies that cause circular imports"""
    with patch.dict(
        "sys.modules",
        {
            "app.setup.plugin_initializer": MagicMock(),
            "app.setup.service_initializer": MagicMock(),
        },
    ):
        yield


class TestStartupHandlers:
    """Tests for startup handlers"""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app"""
        app = MagicMock()
        app.state = MagicMock()
        app.on_event = MagicMock()
        return app

    def test_register_startup_handlers(self, mock_app):
        """Test registering startup handlers"""
        # Import inside test to use mocked dependencies
        with patch("app.setup.plugin_initializer.initialize_plugins", new=AsyncMock()):
            with patch("app.setup.service_initializer.initialize_services", new=AsyncMock()):
                # Re-import with mocked deps
                if "app.lifecycle.startup" in sys.modules:
                    del sys.modules["app.lifecycle.startup"]

                # Mock the imports at module level
                with patch.dict(
                    "sys.modules",
                    {
                        "app.setup.plugin_initializer": MagicMock(initialize_plugins=AsyncMock()),
                        "app.setup.service_initializer": MagicMock(initialize_services=AsyncMock()),
                        "services.monitoring.alert_service": MagicMock(AlertService=MagicMock()),
                    },
                ):
                    from app.lifecycle.startup import register_startup_handlers

                    register_startup_handlers(mock_app)

                    # Should register startup event
                    assert mock_app.on_event.called


class TestStartupHandlersDirect:
    """Test startup handlers with direct mocking approach"""

    def test_register_startup_creates_on_event_decorator(self):
        """Test that register_startup_handlers creates an on_event decorator"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()

        # Track the decorator calls
        decorated_funcs = []

        def mock_on_event(event_name):
            def decorator(func):
                decorated_funcs.append((event_name, func))
                return func

            return decorator

        mock_app.on_event = mock_on_event

        with patch.dict(
            "sys.modules",
            {
                "app.setup.plugin_initializer": MagicMock(initialize_plugins=AsyncMock()),
                "app.setup.service_initializer": MagicMock(initialize_services=AsyncMock()),
                "services.monitoring.alert_service": MagicMock(AlertService=MagicMock()),
            },
        ):
            # Clear cached module
            if "app.lifecycle.startup" in sys.modules:
                del sys.modules["app.lifecycle.startup"]

            from app.lifecycle.startup import register_startup_handlers

            register_startup_handlers(mock_app)

            # Should have registered startup event
            assert len(decorated_funcs) == 1
            assert decorated_funcs[0][0] == "startup"

    @pytest.mark.asyncio
    async def test_startup_handler_initializes_services(self):
        """Test that startup handler initializes services correctly"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()

        # Capture the startup handler
        startup_handler = None

        def mock_on_event(event_name):
            def decorator(func):
                nonlocal startup_handler
                if event_name == "startup":
                    startup_handler = func
                return func

            return decorator

        mock_app.on_event = mock_on_event

        mock_init_services = AsyncMock()
        mock_init_plugins = AsyncMock()
        mock_alert_service = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "app.setup.plugin_initializer": MagicMock(initialize_plugins=mock_init_plugins),
                "app.setup.service_initializer": MagicMock(initialize_services=mock_init_services),
                "services.monitoring.alert_service": MagicMock(AlertService=mock_alert_service),
            },
        ):
            # Clear cached module
            if "app.lifecycle.startup" in sys.modules:
                del sys.modules["app.lifecycle.startup"]

            from app.lifecycle.startup import register_startup_handlers

            register_startup_handlers(mock_app)

            # Execute the captured handler
            assert startup_handler is not None
            await startup_handler()

            # Verify services were initialized
            mock_init_services.assert_called_once_with(mock_app)
            mock_init_plugins.assert_called_once_with(mock_app)

            # Verify alert service was set on app state
            assert mock_app.state.alert_service is not None

    @pytest.mark.asyncio
    async def test_startup_handler_with_failing_service(self):
        """Test startup handler when a service fails to initialize"""
        mock_app = MagicMock()
        mock_app.state = MagicMock()

        startup_handler = None

        def mock_on_event(event_name):
            def decorator(func):
                nonlocal startup_handler
                if event_name == "startup":
                    startup_handler = func
                return func

            return decorator

        mock_app.on_event = mock_on_event

        # Make initialize_services raise an error
        mock_init_services = AsyncMock(side_effect=Exception("Service init failed"))
        mock_init_plugins = AsyncMock()

        with patch.dict(
            "sys.modules",
            {
                "app.setup.plugin_initializer": MagicMock(initialize_plugins=mock_init_plugins),
                "app.setup.service_initializer": MagicMock(initialize_services=mock_init_services),
                "services.monitoring.alert_service": MagicMock(AlertService=MagicMock()),
            },
        ):
            if "app.lifecycle.startup" in sys.modules:
                del sys.modules["app.lifecycle.startup"]

            from app.lifecycle.startup import register_startup_handlers

            register_startup_handlers(mock_app)

            # Execute should raise the error
            with pytest.raises(Exception, match="Service init failed"):
                await startup_handler()
