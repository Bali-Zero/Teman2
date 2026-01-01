"""
Unit tests for ZohoEmailService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.integrations.zoho_email_service import ZohoEmailService


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
def mock_oauth_service():
    """Mock OAuth service"""
    service = AsyncMock()
    service.get_valid_token = AsyncMock(return_value="test_token")
    service.get_account_id = AsyncMock(return_value="test_account_id")
    return service


@pytest.fixture
def zoho_email_service(mock_db_pool, mock_oauth_service):
    """Create ZohoEmailService instance"""
    with patch('services.integrations.zoho_email_service.ZohoOAuthService', return_value=mock_oauth_service):
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.zoho_api_domain = "https://mail.zoho.com"
            return ZohoEmailService(db_pool=mock_db_pool)


class TestZohoEmailService:
    """Tests for ZohoEmailService"""

    def test_init(self, zoho_email_service):
        """Test initialization"""
        assert zoho_email_service.db_pool is not None
        assert zoho_email_service.oauth_service is not None

    @pytest.mark.asyncio
    async def test_get_headers(self, zoho_email_service, mock_oauth_service):
        """Test getting authenticated headers"""
        headers = await zoho_email_service._get_headers("user1")
        assert "Authorization" in headers
        assert headers["Authorization"] == "Zoho-oauthtoken test_token"

    @pytest.mark.asyncio
    async def test_get_account_id(self, zoho_email_service, mock_oauth_service):
        """Test getting account ID"""
        account_id = await zoho_email_service._get_account_id("user1")
        assert account_id == "test_account_id"

    @pytest.mark.asyncio
    async def test_request(self, zoho_email_service, mock_oauth_service):
        """Test making authenticated request"""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            result = await zoho_email_service._request("user1", "GET", "/messages")
            assert result == {"data": "test"}

