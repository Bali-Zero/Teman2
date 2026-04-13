"""
Tests for IdentityService - authentication and user management.
Covers: password hashing, verification, JWT creation, permissions, DB auth flow.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    """Mock settings for identity service."""
    s = MagicMock()
    s.jwt_secret_key = "test-secret-key-at-least-32-characters-long-for-safety"
    s.jwt_algorithm = "HS256"
    s.database_url = "postgresql://test:test@localhost:5432/testdb"
    return s


@pytest.fixture
def identity_service(mock_settings):
    """Create IdentityService with mocked settings."""
    with patch("backend.app.modules.identity.service.settings", mock_settings):
        from backend.app.modules.identity.service import IdentityService
        return IdentityService()


@pytest.fixture
def sample_user():
    """Create a sample User object for testing."""
    from backend.app.modules.identity.models import User
    return User(
        id="test-uuid-1234",
        name="Test User",
        email="test@balizero.com",
        pin_hash="$2b$12$hashedpinvalue",
        role="CEO",
        department="Management",
        language="en",
        personalized_response=False,
        is_active=True,
        last_login=None,
        failed_attempts=0,
        locked_until=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# --- Test init ---

def test_init_warns_on_default_secret():
    """IdentityService should warn when JWT secret is empty."""
    mock_s = MagicMock()
    mock_s.jwt_secret_key = ""
    mock_s.jwt_algorithm = "HS256"
    with patch("backend.app.modules.identity.service.settings", mock_s), \
         patch("backend.app.modules.identity.service.logger") as mock_logger:
        from backend.app.modules.identity.service import IdentityService
        svc = IdentityService()
        mock_logger.warning.assert_called_once()
        assert "JWT" in mock_logger.warning.call_args[0][0]


# --- Test password hashing ---

def test_password_hash_and_verify(identity_service):
    """Hashing a password and verifying it should succeed."""
    pin = "1234"
    hashed = identity_service.get_password_hash(pin)
    assert hashed != pin
    assert hashed.startswith("$2b$")
    assert identity_service.verify_password(pin, hashed) is True


def test_verify_password_invalid_hash(identity_service):
    """Verifying against an invalid hash should return False."""
    result = identity_service.verify_password("1234", "not-a-valid-hash")
    assert result is False


# --- Test get_db_connection ---

@pytest.mark.asyncio
async def test_get_db_connection_requires_url():
    """get_db_connection should raise ValueError when DATABASE_URL is empty."""
    mock_s = MagicMock()
    mock_s.jwt_secret_key = "test-secret-key-at-least-32-characters-long-for-safety"
    mock_s.jwt_algorithm = "HS256"
    mock_s.database_url = ""
    with patch("backend.app.modules.identity.service.settings", mock_s):
        from backend.app.modules.identity.service import IdentityService
        svc = IdentityService()
        with pytest.raises(ValueError, match="DATABASE_URL not configured"):
            await svc.get_db_connection()


# --- Test authenticate_user ---

@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin(identity_service):
    """authenticate_user should return None for invalid PIN format."""
    result = await identity_service.authenticate_user("test@balizero.com", "abc")
    assert result is None

    result2 = await identity_service.authenticate_user("test@balizero.com", "12")
    assert result2 is None

    result3 = await identity_service.authenticate_user("test@balizero.com", "")
    assert result3 is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(identity_service):
    """authenticate_user should return None when user is not found in DB."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.close = AsyncMock()

    with patch.object(identity_service, "get_db_connection", return_value=mock_conn):
        result = await identity_service.authenticate_user("unknown@balizero.com", "1234")
    assert result is None
    mock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_user_locked(identity_service):
    """authenticate_user should return None when account is locked."""
    from datetime import timedelta
    locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_row = {
        "id": "uuid-1",
        "name": "Locked User",
        "email": "locked@balizero.com",
        "pin_hash": "$2b$12$hash",
        "role": "member",
        "department": None,
        "language": "en",
        "personalized_response": False,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 5,
        "locked_until": locked_until,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)
    mock_conn.close = AsyncMock()

    with patch.object(identity_service, "get_db_connection", return_value=mock_conn):
        result = await identity_service.authenticate_user("locked@balizero.com", "1234")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin_increments(identity_service):
    """authenticate_user should increment failed_attempts on wrong PIN."""
    mock_row = {
        "id": "uuid-1",
        "name": "Test User",
        "email": "test@balizero.com",
        "pin_hash": identity_service.get_password_hash("9999"),
        "role": "member",
        "department": None,
        "language": "en",
        "personalized_response": False,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch.object(identity_service, "get_db_connection", return_value=mock_conn):
        result = await identity_service.authenticate_user("test@balizero.com", "1234")
    assert result is None
    # Should have called execute to increment failed_attempts
    mock_conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_user_success(identity_service):
    """authenticate_user should return User on correct PIN."""
    correct_pin = "5678"
    mock_row = {
        "id": "uuid-1",
        "name": "Success User",
        "email": "success@balizero.com",
        "pin_hash": identity_service.get_password_hash(correct_pin),
        "role": "CEO",
        "department": "Management",
        "language": "en",
        "personalized_response": True,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch.object(identity_service, "get_db_connection", return_value=mock_conn):
        result = await identity_service.authenticate_user("success@balizero.com", correct_pin)
    assert result is not None
    assert result.email == "success@balizero.com"
    assert result.role == "CEO"
    assert result.failed_attempts == 0


@pytest.mark.asyncio
async def test_authenticate_user_exception(identity_service):
    """authenticate_user should return None on unexpected exceptions."""
    with patch.object(
        identity_service,
        "get_db_connection",
        side_effect=Exception("DB connection failed"),
    ):
        result = await identity_service.authenticate_user("test@balizero.com", "1234")
    assert result is None


# --- Test create_access_token ---

def test_create_access_token(identity_service, sample_user):
    """create_access_token should return a valid JWT string."""
    from jose import jwt as jose_jwt
    token = identity_service.create_access_token(sample_user, "session-abc")
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify payload
    payload = jose_jwt.decode(
        token,
        "test-secret-key-at-least-32-characters-long-for-safety",
        algorithms=["HS256"],
    )
    assert payload["sub"] == sample_user.id
    assert payload["email"] == sample_user.email
    assert payload["role"] == sample_user.role
    assert payload["sessionId"] == "session-abc"
    assert "exp" in payload


# --- Test get_permissions_for_role ---

def test_permissions_for_role(identity_service):
    """get_permissions_for_role should return correct permissions per role."""
    ceo_perms = identity_service.get_permissions_for_role("CEO")
    assert "all" in ceo_perms
    assert "admin" in ceo_perms

    junior_perms = identity_service.get_permissions_for_role("Junior Consultant")
    assert "setup" in junior_perms
    assert "clients" in junior_perms
    assert "admin" not in junior_perms

    # Unknown role gets default
    unknown_perms = identity_service.get_permissions_for_role("UnknownRole")
    assert unknown_perms == ["clients"]
