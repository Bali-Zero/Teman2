"""
Comprehensive unit tests for app/setup/cors_config.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.setup.cors_config import get_allowed_origins, register_cors_middleware


class TestGetAllowedOrigins:
    """Tests for get_allowed_origins"""

    def test_get_allowed_origins_defaults(self):
        """Test getting default origins"""
        with patch("backend.app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = None
            mock_settings.dev_origins = None

            origins = get_allowed_origins()

            assert len(origins) > 0
            assert "https://zantara.balizero.com" in origins
            assert "http://localhost:3000" in origins

    def test_get_allowed_origins_from_settings(self):
        """Test getting origins from settings"""
        with patch("backend.app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = "https://example.com,https://test.com"
            mock_settings.dev_origins = None

            origins = get_allowed_origins()

            assert "https://example.com" in origins
            assert "https://test.com" in origins
            assert "https://zantara.balizero.com" in origins  # Defaults still included

    def test_get_allowed_origins_with_dev_origins(self):
        """Test getting origins including dev origins"""
        with patch("backend.app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = None
            mock_settings.dev_origins = "http://localhost:8080,http://localhost:8081"

            origins = get_allowed_origins()

            assert "http://localhost:8080" in origins
            assert "http://localhost:8081" in origins

    def test_get_allowed_origins_strips_whitespace(self):
        """Test that whitespace is stripped from origins"""
        with patch("backend.app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = " https://example.com , https://test.com "
            mock_settings.dev_origins = None

            origins = get_allowed_origins()

            assert "https://example.com" in origins
            assert "https://test.com" in origins
            # No whitespace in origins
            assert not any(" " in origin for origin in origins)

    def test_get_allowed_origins_filters_empty(self):
        """Test that empty origins are filtered out"""
        with patch("backend.app.setup.cors_config.settings") as mock_settings:
            mock_settings.zantara_allowed_origins = "https://example.com,,https://test.com"
            mock_settings.dev_origins = None

            origins = get_allowed_origins()

            assert "https://example.com" in origins
            assert "https://test.com" in origins
            assert "" not in origins


class TestRegisterCorsMiddleware:
    """Tests for register_cors_middleware"""

    def test_register_cors_middleware(self):
        """Test registering CORS middleware"""
        mock_app = MagicMock()

        register_cors_middleware(mock_app)

        mock_app.add_middleware.assert_called_once()

    def test_register_cors_middleware_config(self):
        """Test CORS middleware configuration"""
        mock_app = MagicMock()

        with patch("backend.app.setup.cors_config.get_allowed_origins") as mock_get_origins:
            mock_get_origins.return_value = ["https://example.com"]

            register_cors_middleware(mock_app)

            call_args = mock_app.add_middleware.call_args
            assert call_args is not None

            # Verify middleware class
            middleware_class = call_args[0][0]
            assert middleware_class.__name__ == "CORSMiddleware"

            # Verify kwargs
            kwargs = call_args[1]
            assert "allow_origins" in kwargs
            assert kwargs["allow_credentials"] is True
            assert kwargs["allow_methods"] == ["*"]
            assert kwargs["allow_headers"] == ["*"]
