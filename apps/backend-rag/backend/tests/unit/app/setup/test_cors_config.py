"""
Unit tests for app/setup/cors_config.py
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


class TestCorsConfig:
    """Tests for CORS configuration"""

    def test_get_allowed_origins(self):
        """Test getting allowed origins"""
        with patch("app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = None
            mock_settings.dev_origins = None
            
            origins = get_allowed_origins()
            assert isinstance(origins, list)
            assert len(origins) > 0

    def test_get_allowed_origins_with_custom(self):
        """Test getting allowed origins with custom settings"""
        with patch("app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = "https://example.com,https://test.com"
            mock_settings.dev_origins = None
            
            origins = get_allowed_origins()
            assert "https://example.com" in origins
            assert "https://test.com" in origins

    def test_get_allowed_origins_with_dev_origins(self):
        """Test getting allowed origins with dev origins"""
        with patch("app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = None
            mock_settings.dev_origins = "http://localhost:3001"
            
            origins = get_allowed_origins()
            assert "http://localhost:3001" in origins

    def test_register_cors_middleware(self, mock_app):
        """Test registering CORS middleware"""
        with patch("app.setup.cors_config.get_allowed_origins") as mock_get_origins:
            mock_get_origins.return_value = ["https://example.com"]
            
            register_cors_middleware(mock_app)
            mock_app.add_middleware.assert_called_once()

