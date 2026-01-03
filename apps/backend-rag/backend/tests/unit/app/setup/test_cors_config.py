"""
Unit tests for CORS configuration
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.cors_config import get_allowed_origins, register_cors_middleware


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    app.add_middleware = MagicMock()
    return app


class TestCORSConfig:
    """Tests for CORS configuration"""

    def test_get_allowed_origins_with_settings(self):
        """Test getting allowed origins from settings"""
        with patch("app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = "https://example.com,https://test.com"
            mock_settings.dev_origins = None

            origins = get_allowed_origins()

            assert "https://example.com" in origins
            assert "https://test.com" in origins
            assert "https://zantara.balizero.com" in origins  # Default

    def test_get_allowed_origins_with_dev_origins(self):
        """Test getting allowed origins with dev origins"""
        with patch("app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = None
            mock_settings.dev_origins = "http://localhost:3001"

            origins = get_allowed_origins()

            assert "http://localhost:3001" in origins

    def test_get_allowed_origins_defaults(self):
        """Test getting default allowed origins"""
        with patch("app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = None
            if hasattr(mock_settings, "dev_origins"):
                delattr(mock_settings, "dev_origins")

            origins = get_allowed_origins()

            assert "https://zantara.balizero.com" in origins
            assert "http://localhost:3000" in origins

    def test_register_cors_middleware(self, mock_app):
        """Test registering CORS middleware"""
        with patch("app.setup.cors_config.get_allowed_origins") as mock_get_origins:
            mock_get_origins.return_value = ["https://example.com"]

            register_cors_middleware(mock_app)

            mock_app.add_middleware.assert_called_once()
            call_args = mock_app.add_middleware.call_args
            assert call_args[1]["allow_origins"] == ["https://example.com"]
            assert call_args[1]["allow_credentials"] is True
