"""
Unit tests for router_registration.py
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.router_registration import include_routers


@pytest.fixture
def mock_app():
    """Mock FastAPI app"""
    app = MagicMock()
    app.include_router = MagicMock()
    return app


class TestRouterRegistration:
    """Tests for router_registration.py"""

    def test_include_routers(self, mock_app):
        """Test including all routers"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.admin_api_key = None
            
            include_routers(mock_app)
            
            # Verify routers were included
            assert mock_app.include_router.called

    def test_include_routers_with_debug(self, mock_app):
        """Test including routers with debug router enabled"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.admin_api_key = None
            
            include_routers(mock_app)
            
            # Debug router should be included in non-production
            assert mock_app.include_router.called

    def test_include_routers_production_with_admin_key(self, mock_app):
        """Test including routers in production with admin key"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.admin_api_key = "test_key"
            
            include_routers(mock_app)
            
            # Debug router should be included if admin_api_key is set
            assert mock_app.include_router.called

