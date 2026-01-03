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

from app.lifecycle.startup import register_startup_handlers


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
        register_startup_handlers(mock_app)

        # Should register startup event
        mock_app.on_event.assert_called_once_with("startup")

    @pytest.mark.asyncio
    async def test_startup_handler_execution(self, mock_app):
        """Test startup handler execution"""
        register_startup_handlers(mock_app)

        # Get the registered handler
        call_args = mock_app.on_event.call_args
        assert call_args is not None

        # The handler should be the second argument (first is "startup")
        handler = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]['handler']

        # Mock dependencies
        with patch("app.lifecycle.startup.AlertService") as mock_alert, \
             patch("app.lifecycle.startup.initialize_services") as mock_init_services, \
             patch("app.lifecycle.startup.initialize_plugins") as mock_init_plugins:

            mock_alert_instance = MagicMock()
            mock_alert.return_value = mock_alert_instance
            mock_init_services.return_value = AsyncMock()
            mock_init_plugins.return_value = AsyncMock()

            # Execute handler
            await handler()

            # Verify AlertService was initialized
            assert mock_app.state.alert_service == mock_alert_instance
            # Verify services and plugins were initialized
            mock_init_services.assert_called_once_with(mock_app)
            mock_init_plugins.assert_called_once_with(mock_app)




