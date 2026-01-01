"""
Unit tests for ZohoOAuthService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.integrations.zoho_oauth_service import ZohoOAuthService


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
def zoho_oauth_service(mock_db_pool):
    """Create ZohoOAuthService instance"""
    with patch('services.integrations.zoho_oauth_service.settings') as mock_settings:
        mock_settings.zoho_client_id = "test_client_id"
        mock_settings.zoho_client_secret = "test_secret"
        mock_settings.zoho_redirect_uri = "http://localhost/callback"
        mock_settings.zoho_accounts_url = "https://accounts.zoho.com"
        mock_settings.zoho_api_domain = "https://mail.zoho.com"
        return ZohoOAuthService(db_pool=mock_db_pool)


class TestZohoOAuthService:
    """Tests for ZohoOAuthService"""

    def test_init(self, zoho_oauth_service):
        """Test initialization"""
        assert zoho_oauth_service.db_pool is not None
        assert zoho_oauth_service.client_id == "test_client_id"

    def test_get_authorization_url(self, zoho_oauth_service):
        """Test getting authorization URL"""
        url = zoho_oauth_service.get_authorization_url("test_state")
        assert "accounts.zoho.com" in url
        assert "test_state" in url
        assert "client_id=test_client_id" in url

    def test_get_authorization_url_not_configured(self, mock_db_pool):
        """Test getting authorization URL when not configured"""
        with patch('services.integrations.zoho_oauth_service.settings') as mock_settings:
            mock_settings.zoho_client_id = None
            mock_settings.zoho_client_secret = None
            mock_settings.zoho_redirect_uri = None
            mock_settings.zoho_accounts_url = None
            mock_settings.zoho_api_domain = None
            service = ZohoOAuthService(db_pool=mock_db_pool)
            with pytest.raises(ValueError):
                service.get_authorization_url("test_state")

    @pytest.mark.asyncio
    async def test_exchange_code(self, zoho_oauth_service, mock_db_pool):
        """Test exchanging authorization code"""
        with patch('httpx.AsyncClient') as mock_client_class:
            # Mock token exchange response
            token_response = MagicMock()
            token_response.status_code = 200
            token_response.json.return_value = {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "expires_in": 3600
            }
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=token_response)
            mock_client_class.return_value = mock_client
            with patch.object(zoho_oauth_service, '_get_account_info', new_callable=AsyncMock) as mock_get_account:
                mock_get_account.return_value = {"account_id": "test_account_id", "email": "test@example.com"}
                with patch.object(zoho_oauth_service, '_store_tokens', new_callable=AsyncMock):
                    result = await zoho_oauth_service.exchange_code("test_code", "user1")
                    assert "access_token" in result

