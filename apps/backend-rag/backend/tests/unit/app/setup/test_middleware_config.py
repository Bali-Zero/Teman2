"""
Unit tests for middleware_config.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.middleware_config import register_middleware


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    app.add_middleware = MagicMock()
    return app


class TestMiddlewareConfig:
    """Tests for middleware_config.py"""

    def test_register_middleware(self, mock_app):
        """Test registering all middleware"""
        with patch("app.setup.middleware_config.register_cors_middleware") as mock_cors:
            register_middleware(mock_app)
            
            mock_cors.assert_called_once_with(mock_app)
            # Verify middleware were added
            assert mock_app.add_middleware.called

