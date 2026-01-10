"""
Unit tests for middleware configuration
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.setup.middleware_config import register_middleware


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    app.add_middleware = MagicMock()
    return app


class TestMiddlewareConfig:
    """Tests for middleware configuration"""

    def test_register_middleware(self, mock_app):
        """Test registering middleware"""
        with patch("backend.app.setup.middleware_config.register_cors_middleware") as mock_cors:
            register_middleware(mock_app)

            # Verify CORS middleware was registered
            mock_cors.assert_called_once_with(mock_app)

            # Verify other middleware were added
            assert mock_app.add_middleware.call_count >= 4
