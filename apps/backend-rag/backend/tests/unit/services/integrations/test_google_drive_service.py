"""
Unit tests for GoogleDriveService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.integrations.google_drive_service import GoogleDriveService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=conn)
    return pool


@pytest.fixture
def google_drive_service(mock_db_pool):
    """Create GoogleDriveService instance"""
    with patch("backend.services.integrations.google_drive_service.settings") as mock_settings:
        mock_settings.google_drive_client_id = "test_client_id"
        mock_settings.google_drive_client_secret = "test_secret"
        mock_settings.google_drive_redirect_uri = "http://localhost/callback"
        mock_settings.google_drive_root_folder_id = "root_folder_id"
        return GoogleDriveService(db_pool=mock_db_pool)


class TestGoogleDriveService:
    """Tests for GoogleDriveService"""

    def test_init(self, google_drive_service):
        """Test initialization"""
        assert google_drive_service.db_pool is not None
        assert google_drive_service.client_id == "test_client_id"

    def test_is_configured_true(self, google_drive_service):
        """Test is_configured when credentials are set"""
        assert google_drive_service.is_configured() is True

    def test_is_configured_false(self, mock_db_pool):
        """Test is_configured when credentials are missing"""
        with patch("backend.services.integrations.google_drive_service.settings") as mock_settings:
            mock_settings.google_drive_client_id = None
            mock_settings.google_drive_client_secret = None
            mock_settings.google_drive_redirect_uri = None
            mock_settings.google_drive_root_folder_id = None
            service = GoogleDriveService(db_pool=mock_db_pool)
            assert service.is_configured() is False

    def test_get_authorization_url(self, google_drive_service):
        """Test getting authorization URL"""
        url = google_drive_service.get_authorization_url("test_state")
        assert "accounts.google.com" in url
        assert "test_state" in url
        assert "client_id=test_client_id" in url

    def test_get_authorization_url_not_configured(self, mock_db_pool):
        """Test getting authorization URL when not configured"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.google_drive_client_id = None
            service = GoogleDriveService(db_pool=mock_db_pool)
            with pytest.raises(ValueError):
                service.get_authorization_url("test_state")

    @pytest.mark.asyncio
    async def test_exchange_code(self, google_drive_service, mock_db_pool):
        """Test exchanging authorization code"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "expires_in": 3600,
            }
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            with patch.object(google_drive_service, "_store_tokens", new_callable=AsyncMock):
                result = await google_drive_service.exchange_code("test_code", "user1")
                assert "access_token" in result
