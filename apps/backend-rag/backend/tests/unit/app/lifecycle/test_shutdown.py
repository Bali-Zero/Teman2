"""
Unit tests for app/lifecycle/shutdown.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.lifecycle.shutdown import register_shutdown_handlers


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    app.on_event = MagicMock()
    app.state = MagicMock()
    return app


class TestShutdownHandlers:
    """Tests for shutdown handlers"""

    def test_register_shutdown_handlers(self, mock_app):
        """Test registering shutdown handlers"""
        register_shutdown_handlers(mock_app)
        mock_app.on_event.assert_called_once_with("shutdown")

