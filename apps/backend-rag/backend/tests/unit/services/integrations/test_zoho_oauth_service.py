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

from backend.services.integrations.zoho_oauth_service import ZohoOAuthService


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
    with patch("backend.services.integrations.zoho_oauth_service.settings") as mock_settings:
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
        with patch("backend.services.integrations.zoho_oauth_service.settings") as mock_settings:
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
        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock token exchange response
            token_response = MagicMock()
            token_response.status_code = 200
            token_response.json.return_value = {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "expires_in": 3600,
            }
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=token_response)
            mock_client_class.return_value = mock_client
            with patch.object(
                zoho_oauth_service, "_get_account_info", new_callable=AsyncMock
            ) as mock_get_account:
                mock_get_account.return_value = {
                    "account_id": "test_account_id",
                    "email": "test@example.com",
                }
                with patch.object(zoho_oauth_service, "_store_tokens", new_callable=AsyncMock):
                    result = await zoho_oauth_service.exchange_code("test_code", "user1")
                    assert "access_token" in result

    @pytest.mark.asyncio
    async def test_exchange_code_error_response(self, zoho_oauth_service):
        """Test exchange_code with error response from Zoho"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.content = b'{"error": "invalid_code"}'
            mock_response.json.return_value = {"error": "invalid_code"}
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Token exchange failed"):
                await zoho_oauth_service.exchange_code("bad_code", "user1")

    @pytest.mark.asyncio
    async def test_exchange_code_not_configured(self, mock_db_pool):
        """Test exchange_code when OAuth not configured"""
        with patch("backend.services.integrations.zoho_oauth_service.settings") as mock_settings:
            mock_settings.zoho_client_id = None
            mock_settings.zoho_client_secret = None
            mock_settings.zoho_redirect_uri = None
            mock_settings.zoho_accounts_url = None
            mock_settings.zoho_api_domain = None
            service = ZohoOAuthService(db_pool=mock_db_pool)

            with pytest.raises(ValueError, match="Zoho OAuth not configured"):
                await service.exchange_code("code", "user1")


class TestGetValidToken:
    """Tests for get_valid_token method"""

    @pytest.mark.asyncio
    async def test_get_valid_token_fresh(self, zoho_oauth_service, mock_db_pool):
        """Test getting a fresh (non-expired) token"""
        from datetime import datetime, timedelta, timezone

        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_row = {
            "access_token": "valid_token",
            "refresh_token": "refresh_token",
            "token_expires_at": future_expiry,
            "account_id": "acc123",
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        token = await zoho_oauth_service.get_valid_token("user1")
        assert token == "valid_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_no_account(self, zoho_oauth_service, mock_db_pool):
        """Test get_valid_token when no account connected"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        with pytest.raises(ValueError, match="No Zoho account connected"):
            await zoho_oauth_service.get_valid_token("user1")

    @pytest.mark.asyncio
    async def test_get_valid_token_needs_refresh(self, zoho_oauth_service, mock_db_pool):
        """Test getting token that needs refresh"""
        from datetime import datetime, timedelta, timezone

        # Token expiring in 2 minutes (within 5-min buffer)
        expiring_soon = datetime.now(timezone.utc) + timedelta(minutes=2)
        mock_row = {
            "access_token": "old_token",
            "refresh_token": "refresh_token",
            "token_expires_at": expiring_soon,
            "account_id": "acc123",
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        with patch.object(
            zoho_oauth_service, "_refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            mock_refresh.return_value = "new_token"
            token = await zoho_oauth_service.get_valid_token("user1")
            assert token == "new_token"
            mock_refresh.assert_called_once()


class TestRefreshToken:
    """Tests for _refresh_token method"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, zoho_oauth_service, mock_db_pool):
        """Test successful token refresh"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_access_token",
                "expires_in": 3600,
            }
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            conn = AsyncMock()
            conn.execute = AsyncMock()
            conn.__aenter__ = AsyncMock(return_value=conn)
            conn.__aexit__ = AsyncMock(return_value=None)
            mock_db_pool.acquire = MagicMock(return_value=conn)

            token = await zoho_oauth_service._refresh_token("user1", "acc123", "refresh_token")
            assert token == "new_access_token"

    @pytest.mark.asyncio
    async def test_refresh_token_no_refresh_token(self, zoho_oauth_service):
        """Test refresh when no refresh token available"""
        with pytest.raises(ValueError, match="No refresh token available"):
            await zoho_oauth_service._refresh_token("user1", "acc123", "")

    @pytest.mark.asyncio
    async def test_refresh_token_api_error(self, zoho_oauth_service):
        """Test refresh when API returns error"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.content = b'{"error": "invalid_grant"}'
            mock_response.json.return_value = {"error": "invalid_grant"}
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to refresh token"):
                await zoho_oauth_service._refresh_token("user1", "acc123", "refresh")


class TestGetAccountId:
    """Tests for get_account_id method"""

    @pytest.mark.asyncio
    async def test_get_account_id_success(self, zoho_oauth_service, mock_db_pool):
        """Test getting account ID successfully"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"account_id": "acc123"})
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        account_id = await zoho_oauth_service.get_account_id("user1")
        assert account_id == "acc123"

    @pytest.mark.asyncio
    async def test_get_account_id_not_found(self, zoho_oauth_service, mock_db_pool):
        """Test get_account_id when no account connected"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        with pytest.raises(ValueError, match="No Zoho account connected"):
            await zoho_oauth_service.get_account_id("user1")


class TestGetConnectionStatus:
    """Tests for get_connection_status method"""

    @pytest.mark.asyncio
    async def test_get_connection_status_connected(self, zoho_oauth_service, mock_db_pool):
        """Test getting status when connected"""
        from datetime import datetime, timezone

        mock_row = {
            "account_id": "acc123",
            "email_address": "test@example.com",
            "token_expires_at": datetime.now(timezone.utc),
            "api_domain": "https://mail.zoho.com",
        }

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        status = await zoho_oauth_service.get_connection_status("user1")
        assert status["connected"] is True
        assert status["email"] == "test@example.com"
        assert status["account_id"] == "acc123"

    @pytest.mark.asyncio
    async def test_get_connection_status_not_connected(self, zoho_oauth_service, mock_db_pool):
        """Test getting status when not connected"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        status = await zoho_oauth_service.get_connection_status("user1")
        assert status["connected"] is False
        assert status["email"] is None


class TestDisconnect:
    """Tests for disconnect method"""

    @pytest.mark.asyncio
    async def test_disconnect_success(self, zoho_oauth_service, mock_db_pool):
        """Test successful disconnection"""
        mock_row = {"refresh_token": "refresh_token"}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await zoho_oauth_service.disconnect("user1")
            assert result is True
            # Verify delete was called for tokens and cache
            assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_no_refresh_token(self, zoho_oauth_service, mock_db_pool):
        """Test disconnection without refresh token"""
        mock_row = {"refresh_token": None}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        result = await zoho_oauth_service.disconnect("user1")
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_revoke_fails(self, zoho_oauth_service, mock_db_pool):
        """Test disconnection when revoke request fails (should still succeed)"""
        mock_row = {"refresh_token": "refresh_token"}

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.execute = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client_class.return_value = mock_client

            # Should still succeed even if revoke fails
            result = await zoho_oauth_service.disconnect("user1")
            assert result is True


class TestGetAccountInfo:
    """Tests for _get_account_info method"""

    @pytest.mark.asyncio
    async def test_get_account_info_success(self, zoho_oauth_service):
        """Test getting account info successfully"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {
                        "accountId": "acc123",
                        "email": [{"isPrimary": True, "mailId": "test@example.com"}],
                    }
                ]
            }
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            info = await zoho_oauth_service._get_account_info("test_token")
            assert info["account_id"] == "acc123"
            assert info["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_account_info_no_accounts(self, zoho_oauth_service):
        """Test _get_account_info when no accounts found"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": []}
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="No Zoho Mail accounts found"):
                await zoho_oauth_service._get_account_info("test_token")

    @pytest.mark.asyncio
    async def test_get_account_info_api_error(self, zoho_oauth_service):
        """Test _get_account_info when API returns error"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to get account information"):
                await zoho_oauth_service._get_account_info("test_token")

    @pytest.mark.asyncio
    async def test_get_account_info_email_string(self, zoho_oauth_service):
        """Test _get_account_info when email is already a string"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {
                        "accountId": "acc123",
                        "email": "direct@example.com",  # String instead of list
                    }
                ]
            }
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            info = await zoho_oauth_service._get_account_info("test_token")
            assert info["email"] == "direct@example.com"


class TestStoreTokens:
    """Tests for _store_tokens method"""

    @pytest.mark.asyncio
    async def test_store_tokens_success(self, zoho_oauth_service, mock_db_pool):
        """Test storing tokens successfully"""
        conn = AsyncMock()
        conn.execute = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=conn)

        await zoho_oauth_service._store_tokens(
            user_id="user1",
            account_id="acc123",
            email_address="test@example.com",
            access_token="access_token",
            refresh_token="refresh_token",
            expires_in=3600,
        )

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "INSERT INTO zoho_email_tokens" in call_args[0][0]
