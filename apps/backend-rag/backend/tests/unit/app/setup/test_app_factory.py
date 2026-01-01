"""
Unit tests for app_factory.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.app_factory import create_app


class TestAppFactory:
    """Tests for app_factory.py"""

    def test_create_app(self):
        """Test creating FastAPI app"""
        with patch("app.setup.app_factory.setup_observability") as mock_obs, \
             patch("app.setup.app_factory.register_middleware") as mock_middleware, \
             patch("app.setup.app_factory.include_routers") as mock_routers, \
             patch("app.setup.app_factory.register_startup_handlers") as mock_startup, \
             patch("app.setup.app_factory.register_shutdown_handlers") as mock_shutdown:
            
            app = create_app()
            
            assert app is not None
            mock_obs.assert_called_once()
            mock_middleware.assert_called_once()
            mock_routers.assert_called_once()
            mock_startup.assert_called_once()
            mock_shutdown.assert_called_once()

    def test_create_app_with_debug(self):
        """Test creating app with debug mode"""
        with patch("app.setup.app_factory.settings") as mock_settings, \
             patch("app.setup.app_factory.setup_observability"), \
             patch("app.setup.app_factory.register_middleware"), \
             patch("app.setup.app_factory.include_routers"), \
             patch("app.setup.app_factory.register_startup_handlers"), \
             patch("app.setup.app_factory.register_shutdown_handlers"):
            
            mock_settings.log_level = "DEBUG"
            mock_settings.PROJECT_NAME = "Test"
            mock_settings.API_V1_STR = "/api/v1"
            
            app = create_app()
            assert app is not None

