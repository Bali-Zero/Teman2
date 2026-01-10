"""
Unit tests for InviteService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.portal.invite_service import InviteService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()
    mock_client = MagicMock()
    mock_client.__getitem__ = lambda self, key: {
        "id": 1,
        "full_name": "Test Client",
        "email": "test@example.com",
    }.get(key)
    conn.fetchrow = AsyncMock(return_value=mock_client)
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=conn)
    return pool


@pytest.fixture
def invite_service(mock_db_pool):
    """Create InviteService instance"""
    return InviteService(pool=mock_db_pool)


class TestInviteService:
    """Tests for InviteService"""

    def test_init(self, invite_service):
        """Test initialization"""
        assert invite_service.pool is not None

    @pytest.mark.asyncio
    async def test_create_invitation(self, invite_service, mock_db_pool):
        """Test creating invitation"""
        from datetime import datetime, timezone

        mock_conn = AsyncMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {
            "id": 1,
            "full_name": "Test Client",
            "email": "test@example.com",
        }.get(key)
        mock_invitation = MagicMock()
        expires_at = datetime.now(timezone.utc)
        mock_invitation.__getitem__ = lambda self, key: {
            "id": 1,
            "token": "test_token",
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }.get(key)
        mock_conn.fetchrow = AsyncMock(side_effect=[mock_client, None, mock_invitation])
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await invite_service.create_invitation(1, "test@example.com", "team@example.com")
        assert "token" in result
        assert result["client_id"] == 1

    @pytest.mark.asyncio
    async def test_create_invitation_client_not_found(self, invite_service, mock_db_pool):
        """Test creating invitation for non-existent client"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        with pytest.raises(ValueError):
            await invite_service.create_invitation(999, "test@example.com", "team@example.com")

    @pytest.mark.asyncio
    async def test_validate_token(self, invite_service, mock_db_pool):
        """Test validating token"""
        from datetime import datetime, timedelta, timezone

        mock_conn = AsyncMock()
        mock_invitation = MagicMock()
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_invitation.__getitem__ = lambda self, key: {
            "id": 1,
            "client_id": 1,
            "email": "test@example.com",
            "expires_at": expires_at,
            "used_at": None,
            "client_name": "Test Client",
        }.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_invitation)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await invite_service.validate_token("test_token")
        assert result is not None
        assert result["client_id"] == 1
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_token_invalid(self, invite_service, mock_db_pool):
        """Test validating invalid token"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await invite_service.validate_token("invalid_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_already_used(self, invite_service, mock_db_pool):
        """Test validating already used token"""
        from datetime import datetime, timedelta, timezone

        mock_conn = AsyncMock()
        mock_invitation = MagicMock()
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_invitation.__getitem__ = lambda self, key: {
            "id": 1,
            "client_id": 1,
            "email": "test@example.com",
            "expires_at": expires_at,
            "used_at": datetime.now(timezone.utc),
            "client_name": "Test Client",
        }.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_invitation)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await invite_service.validate_token("used_token")
        assert result is not None
        assert result["error"] == "already_used"

    @pytest.mark.asyncio
    async def test_validate_token_expired(self, invite_service, mock_db_pool):
        """Test validating expired token"""
        from datetime import datetime, timedelta, timezone

        mock_conn = AsyncMock()
        mock_invitation = MagicMock()
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        mock_invitation.__getitem__ = lambda self, key: {
            "id": 1,
            "client_id": 1,
            "email": "test@example.com",
            "expires_at": expires_at,
            "used_at": None,
            "client_name": "Test Client",
        }.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_invitation)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await invite_service.validate_token("expired_token")
        assert result is not None
        assert result["error"] == "expired"

    @pytest.mark.asyncio
    async def test_complete_registration_invalid_pin_short(self, invite_service):
        """Test completing registration with invalid PIN (too short)"""
        with pytest.raises(ValueError, match="PIN must be 4-6 digits"):
            await invite_service.complete_registration("token", "123")  # Too short

    @pytest.mark.asyncio
    async def test_complete_registration_invalid_pin_long(self, invite_service):
        """Test completing registration with invalid PIN (too long)"""
        with pytest.raises(ValueError, match="PIN must be 4-6 digits"):
            await invite_service.complete_registration("token", "1234567")  # Too long

    @pytest.mark.asyncio
    async def test_complete_registration_invalid_pin_not_digits(self, invite_service):
        """Test completing registration with invalid PIN (not digits)"""
        with pytest.raises(ValueError, match="PIN must be 4-6 digits"):
            await invite_service.complete_registration("token", "abcd")

    @pytest.mark.asyncio
    async def test_get_client_invitations(self, invite_service, mock_db_pool):
        """Test getting client invitations"""
        from datetime import datetime, timezone

        mock_conn = AsyncMock()
        mock_invitation = MagicMock()
        mock_invitation.__getitem__ = lambda self, key: {
            "id": 1,
            "email": "test@example.com",
            "expires_at": datetime.now(timezone.utc),
            "used_at": None,
            "created_by": "team@example.com",
            "created_at": datetime.now(timezone.utc),
        }.get(key)
        mock_conn.fetch = AsyncMock(return_value=[mock_invitation])
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)

        result = await invite_service.get_client_invitations(1)
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_resend_invitation(self, invite_service, mock_db_pool):
        """Test resending invitation"""
        from datetime import datetime, timezone

        mock_conn = AsyncMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda self, key: {
            "id": 1,
            "email": "test@example.com",
        }.get(key)
        mock_invitation = MagicMock()
        expires_at = datetime.now(timezone.utc)
        mock_invitation.__getitem__ = lambda self, key: {
            "id": 2,
            "token": "new_token",
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }.get(key)
        mock_conn.fetchrow = AsyncMock(side_effect=[mock_client, None, mock_invitation])
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)

        result = await invite_service.resend_invitation(1, "team@example.com")
        assert "token" in result
        assert result["client_id"] == 1

    @pytest.mark.asyncio
    async def test_resend_invitation_client_not_found(self, invite_service, mock_db_pool):
        """Test resending invitation for non-existent client"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)

        with pytest.raises(ValueError, match="Client not found"):
            await invite_service.resend_invitation(999, "team@example.com")
