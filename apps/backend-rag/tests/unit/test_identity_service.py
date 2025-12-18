"""
Unit tests for Identity Service
100% coverage target with comprehensive mocking
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest
from jose import jwt

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.modules.identity.models import User
from app.modules.identity.service import IdentityService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    with patch("app.modules.identity.service.settings") as mock:
        mock.database_url = "postgresql://test:test@localhost/test"
        mock.jwt_secret_key = "test_secret_key_for_testing_12345"
        mock.jwt_algorithm = "HS256"
        yield mock


@pytest.fixture
def mock_settings_default_secret():
    """Mock settings with default secret key"""
    with patch("app.modules.identity.service.settings") as mock:
        mock.database_url = "postgresql://test:test@localhost/test"
        mock.jwt_secret_key = "zantara_default_secret_key_2025_change_in_production"
        mock.jwt_algorithm = "HS256"
        yield mock


@pytest.fixture
def mock_asyncpg_connection():
    """Mock asyncpg connection"""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.fetch = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def identity_service(mock_settings):
    """Create IdentityService instance"""
    return IdentityService()


@pytest.fixture
def sample_user():
    """Create a sample User object"""
    return User(
        id="test-user-id-123",
        name="Test User",
        email="test@example.com",
        pin_hash="$2b$12$hashed_pin_hash_here",
        role="CEO",
        department="management",
        language="en",
        personalized_response=True,
        is_active=True,
        last_login=datetime.now(timezone.utc),
        failed_attempts=0,
        locked_until=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_db_row():
    """Create a sample database row"""
    return {
        "id": "test-user-id-123",
        "name": "Test User",
        "email": "test@example.com",
        "pin_hash": "$2b$12$hashed_pin_hash_here",
        "role": "CEO",
        "department": "management",
        "language": "en",
        "personalized_response": True,
        "is_active": True,
        "last_login": datetime.now(timezone.utc),
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_with_custom_secret(mock_settings):
    """Test initialization with custom JWT secret"""
    service = IdentityService()
    assert service.jwt_secret == "test_secret_key_for_testing_12345"
    assert service.jwt_algorithm == "HS256"


def test_init_with_default_secret_warning(mock_settings_default_secret):
    """Test initialization with default secret triggers warning"""
    with patch("app.modules.identity.service.logger") as mock_logger:
        service = IdentityService()
        assert service.jwt_secret == "zantara_default_secret_key_2025_change_in_production"
        mock_logger.warning.assert_called_once()
        assert "default or empty JWT secret key" in mock_logger.warning.call_args[0][0]


def test_init_with_empty_secret_warning():
    """Test initialization with empty secret triggers warning"""
    with patch("app.modules.identity.service.settings") as mock_settings:
        mock_settings.jwt_secret_key = ""
        mock_settings.jwt_algorithm = "HS256"
        with patch("app.modules.identity.service.logger") as mock_logger:
            service = IdentityService()
            assert service.jwt_secret == ""
            mock_logger.warning.assert_called_once()


# ============================================================================
# Tests for get_password_hash
# ============================================================================


def test_get_password_hash_success(identity_service):
    """Test password hashing"""
    password = "test1234"
    hashed = identity_service.get_password_hash(password)

    assert hashed is not None
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")  # bcrypt hash format
    assert len(hashed) > 20  # bcrypt hashes are long


def test_get_password_hash_different_passwords(identity_service):
    """Test that different passwords produce different hashes"""
    password1 = "test1234"
    password2 = "test5678"

    hashed1 = identity_service.get_password_hash(password1)
    hashed2 = identity_service.get_password_hash(password2)

    assert hashed1 != hashed2


def test_get_password_hash_same_password_different_salt(identity_service):
    """Test that same password produces different hashes (due to salt)"""
    password = "test1234"

    hashed1 = identity_service.get_password_hash(password)
    hashed2 = identity_service.get_password_hash(password)

    # Different salts should produce different hashes
    assert hashed1 != hashed2
    # But both should verify correctly
    assert identity_service.verify_password(password, hashed1)
    assert identity_service.verify_password(password, hashed2)


# ============================================================================
# Tests for verify_password
# ============================================================================


def test_verify_password_success(identity_service):
    """Test successful password verification"""
    password = "test1234"
    hashed = identity_service.get_password_hash(password)

    result = identity_service.verify_password(password, hashed)
    assert result is True


def test_verify_password_failure_wrong_password(identity_service):
    """Test password verification with wrong password"""
    password = "test1234"
    wrong_password = "wrong1234"
    hashed = identity_service.get_password_hash(password)

    result = identity_service.verify_password(wrong_password, hashed)
    assert result is False


def test_verify_password_failure_invalid_hash(identity_service):
    """Test password verification with invalid hash format"""
    password = "test1234"
    invalid_hash = "not_a_valid_hash"

    result = identity_service.verify_password(password, invalid_hash)
    assert result is False


def test_verify_password_exception_handling(identity_service):
    """Test password verification exception handling"""
    password = "test1234"

    # Mock bcrypt.checkpw to raise an exception
    with patch("bcrypt.checkpw", side_effect=Exception("Bcrypt error")):
        with patch("app.modules.identity.service.logger") as mock_logger:
            result = identity_service.verify_password(password, "invalid_hash")
            assert result is False
            mock_logger.error.assert_called_once()
            assert "Bcrypt verification failed" in mock_logger.error.call_args[0][0]


def test_verify_password_encoding_error(identity_service):
    """Test password verification with encoding error"""
    # Use a password that might cause encoding issues
    password = "test1234"

    # Mock bcrypt.checkpw to raise an exception (simulating encoding or other errors)
    with patch("bcrypt.checkpw", side_effect=UnicodeEncodeError("utf-8", "", 0, 1, "error")):
        with patch("app.modules.identity.service.logger") as mock_logger:
            result = identity_service.verify_password(password, "some_hash")
            assert result is False
            mock_logger.error.assert_called_once()


# ============================================================================
# Tests for get_db_connection
# ============================================================================


@pytest.mark.asyncio
async def test_get_db_connection_success(mock_settings, identity_service, mock_asyncpg_connection):
    """Test successful database connection"""
    with patch("asyncpg.connect", return_value=mock_asyncpg_connection) as mock_connect:
        conn = await identity_service.get_db_connection()

        assert conn == mock_asyncpg_connection
        mock_connect.assert_called_once_with("postgresql://test:test@localhost/test")


@pytest.mark.asyncio
async def test_get_db_connection_no_database_url(identity_service):
    """Test database connection without DATABASE_URL"""
    with patch("app.modules.identity.service.settings") as mock_settings:
        mock_settings.database_url = None

        with pytest.raises(ValueError, match="DATABASE_URL not configured"):
            await identity_service.get_db_connection()


@pytest.mark.asyncio
async def test_get_db_connection_connection_error(identity_service):
    """Test database connection error"""
    with patch("asyncpg.connect", side_effect=Exception("Connection failed")):
        with pytest.raises(Exception, match="Connection failed"):
            await identity_service.get_db_connection()


# ============================================================================
# Tests for authenticate_user
# ============================================================================


@pytest.mark.asyncio
async def test_authenticate_user_success(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test successful user authentication"""
    # Setup mocks
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is not None
            assert isinstance(user, User)
            assert user.email == "test@example.com"
            assert user.name == "Test User"
            assert user.role == "CEO"
            assert user.failed_attempts == 0  # Reset after successful login
            assert user.locked_until is None  # Reset after successful login

            # Verify database operations
            assert mock_asyncpg_connection.fetchrow.call_count == 1
            assert mock_asyncpg_connection.execute.call_count == 1  # Reset failed attempts
            assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin_format_non_digit(mock_settings, identity_service):
    """Test authentication with invalid PIN format (non-digit)"""
    with patch("app.modules.identity.service.logger") as mock_logger:
        user = await identity_service.authenticate_user("test@example.com", "abcd")

        assert user is None
        mock_logger.warning.assert_called_once()
        assert "Invalid PIN format" in mock_logger.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin_format_too_short(mock_settings, identity_service):
    """Test authentication with invalid PIN format (too short)"""
    with patch("app.modules.identity.service.logger") as mock_logger:
        user = await identity_service.authenticate_user("test@example.com", "123")

        assert user is None
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin_format_too_long(mock_settings, identity_service):
    """Test authentication with invalid PIN format (too long)"""
    with patch("app.modules.identity.service.logger") as mock_logger:
        user = await identity_service.authenticate_user("test@example.com", "123456789")

        assert user is None
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_empty_pin(mock_settings, identity_service):
    """Test authentication with empty PIN"""
    with patch("app.modules.identity.service.logger") as mock_logger:
        user = await identity_service.authenticate_user("test@example.com", "")

        assert user is None
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_none_pin(mock_settings, identity_service):
    """Test authentication with None PIN"""
    with patch("app.modules.identity.service.logger") as mock_logger:
        user = await identity_service.authenticate_user("test@example.com", None)

        assert user is None
        mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_not_found(
    mock_settings, identity_service, mock_asyncpg_connection
):
    """Test authentication when user is not found"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=None)

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            user = await identity_service.authenticate_user("notfound@example.com", "1234")

            assert user is None
            mock_logger.warning.assert_called_once()
            assert "User not found or inactive" in mock_logger.warning.call_args[0][0]
            assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_account_locked(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication when account is locked"""
    # Set locked_until to future date
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    sample_db_row["locked_until"] = future_time
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is None
            mock_logger.warning.assert_called_once()
            assert "Account locked" in mock_logger.warning.call_args[0][0]
            assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_account_locked_expired(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication when account lock has expired"""
    # Set locked_until to past date
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    sample_db_row["locked_until"] = past_time
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")

            # Should succeed because lock has expired
            assert user is not None
            assert isinstance(user, User)


@pytest.mark.asyncio
async def test_authenticate_user_invalid_pin_hash(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication with invalid PIN hash"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return False
    with patch.object(identity_service, "verify_password", return_value=False):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            with patch("app.modules.identity.service.logger") as mock_logger:
                user = await identity_service.authenticate_user("test@example.com", "1234")

                assert user is None
                # Verify failed attempts were incremented
                assert mock_asyncpg_connection.execute.call_count == 1
                mock_logger.warning.assert_called()
                assert "Invalid PIN" in mock_logger.warning.call_args[0][0]
                assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_database_error(
    mock_settings, identity_service, mock_asyncpg_connection
):
    """Test authentication when database error occurs"""
    mock_asyncpg_connection.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is None
            mock_logger.error.assert_called_once()
            assert "Authentication error" in mock_logger.error.call_args[0][0]
            assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_connection_error(mock_settings, identity_service):
    """Test authentication when connection fails"""
    with patch("asyncpg.connect", side_effect=Exception("Connection failed")):
        with patch("app.modules.identity.service.logger") as mock_logger:
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is None
            mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_resets_failed_attempts_on_success(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that successful authentication resets failed attempts"""
    sample_db_row["failed_attempts"] = 5  # User had 5 failed attempts
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is not None
            assert user.failed_attempts == 0  # Reset to 0

            # Verify the reset query was executed
            execute_calls = mock_asyncpg_connection.execute.call_args_list
            reset_call = [call for call in execute_calls if "failed_attempts = 0" in str(call)]
            assert len(reset_call) > 0


@pytest.mark.asyncio
async def test_authenticate_user_updates_last_login(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that successful authentication updates last_login"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is not None
            # Verify the update query was executed
            execute_calls = mock_asyncpg_connection.execute.call_args_list
            update_call = [call for call in execute_calls if "last_login" in str(call)]
            assert len(update_call) > 0


@pytest.mark.asyncio
async def test_authenticate_user_with_none_language(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication with user that has language=None"""
    sample_db_row["language"] = None
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is not None
            assert user.language == "en"  # Default fallback


@pytest.mark.asyncio
async def test_authenticate_user_with_none_personalized_response(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication with user that has personalized_response=None"""
    sample_db_row["personalized_response"] = None
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is not None
            assert user.personalized_response is False  # Default fallback


@pytest.mark.asyncio
async def test_authenticate_user_case_insensitive_email(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that email matching is case-insensitive"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    # Mock password verification to return True
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            # Use uppercase email
            user = await identity_service.authenticate_user("TEST@EXAMPLE.COM", "1234")

            assert user is not None
            # Verify the query uses LOWER() for case-insensitive matching
            fetchrow_call = mock_asyncpg_connection.fetchrow.call_args
            assert "LOWER" in str(fetchrow_call)


# ============================================================================
# Tests for create_access_token
# ============================================================================


def test_create_access_token_success(identity_service, sample_user):
    """Test JWT token creation"""
    session_id = "session_12345"
    token = identity_service.create_access_token(sample_user, session_id)

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify token
    decoded = jwt.decode(
        token, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )
    assert decoded["userId"] == sample_user.id
    assert decoded["email"] == sample_user.email
    assert decoded["role"] == sample_user.role
    assert decoded["department"] == sample_user.department
    assert decoded["sessionId"] == session_id
    assert "exp" in decoded


def test_create_access_token_expiration(identity_service, sample_user):
    """Test that token has correct expiration (7 days)"""
    session_id = "session_12345"
    token = identity_service.create_access_token(sample_user, session_id)

    decoded = jwt.decode(
        token, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )
    exp_timestamp = decoded["exp"]
    exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

    # Check that expiration is approximately 7 days from now
    expected_exp = datetime.now(timezone.utc) + timedelta(days=7)
    time_diff = abs((exp_datetime - expected_exp).total_seconds())
    assert time_diff < 60  # Allow 1 minute tolerance


def test_create_access_token_payload_structure(identity_service, sample_user):
    """Test that token payload has correct structure"""
    session_id = "session_12345"
    token = identity_service.create_access_token(sample_user, session_id)

    decoded = jwt.decode(
        token, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )

    # Verify all required fields
    assert "userId" in decoded  # Node.js uses "userId" not "id"
    assert "email" in decoded
    assert "role" in decoded
    assert "department" in decoded
    assert "sessionId" in decoded
    assert "exp" in decoded


def test_create_access_token_different_users(identity_service, sample_user):
    """Test that different users get different tokens"""
    session_id = "session_12345"

    user1 = sample_user
    user2 = User(
        id="different-user-id",
        name="Different User",
        email="different@example.com",
        pin_hash="hash",
        role="Member",
        department="tech",
        language="en",
        personalized_response=False,
        is_active=True,
        last_login=None,
        failed_attempts=0,
        locked_until=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    token1 = identity_service.create_access_token(user1, session_id)
    token2 = identity_service.create_access_token(user2, session_id)

    assert token1 != token2


def test_create_access_token_different_sessions(identity_service, sample_user):
    """Test that different sessions get different tokens"""
    session_id1 = "session_12345"
    session_id2 = "session_67890"

    token1 = identity_service.create_access_token(sample_user, session_id1)
    token2 = identity_service.create_access_token(sample_user, session_id2)

    assert token1 != token2

    # Verify session IDs are different in tokens
    decoded1 = jwt.decode(
        token1, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )
    decoded2 = jwt.decode(
        token2, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )

    assert decoded1["sessionId"] == session_id1
    assert decoded2["sessionId"] == session_id2


# ============================================================================
# Tests for get_permissions_for_role
# ============================================================================


def test_get_permissions_for_role_ceo(identity_service):
    """Test permissions for CEO role"""
    permissions = identity_service.get_permissions_for_role("CEO")

    assert isinstance(permissions, list)
    assert "all" in permissions
    assert "admin" in permissions
    assert "finance" in permissions
    assert "hr" in permissions
    assert "tech" in permissions
    assert "marketing" in permissions


def test_get_permissions_for_role_board_member(identity_service):
    """Test permissions for Board Member role"""
    permissions = identity_service.get_permissions_for_role("Board Member")

    assert isinstance(permissions, list)
    assert "all" in permissions
    assert "finance" in permissions
    assert "hr" in permissions
    assert "tech" in permissions
    assert "marketing" in permissions


def test_get_permissions_for_role_ai_bridge(identity_service):
    """Test permissions for AI Bridge/Tech Lead role"""
    permissions = identity_service.get_permissions_for_role("AI Bridge/Tech Lead")

    assert isinstance(permissions, list)
    assert "all" in permissions
    assert "tech" in permissions
    assert "admin" in permissions
    assert "finance" in permissions


def test_get_permissions_for_role_executive_consultant(identity_service):
    """Test permissions for Executive Consultant role"""
    permissions = identity_service.get_permissions_for_role("Executive Consultant")

    assert isinstance(permissions, list)
    assert "setup" in permissions
    assert "finance" in permissions
    assert "clients" in permissions
    assert "reports" in permissions


def test_get_permissions_for_role_specialist_consultant(identity_service):
    """Test permissions for Specialist Consultant role"""
    permissions = identity_service.get_permissions_for_role("Specialist Consultant")

    assert isinstance(permissions, list)
    assert "setup" in permissions
    assert "clients" in permissions
    assert "reports" in permissions


def test_get_permissions_for_role_junior_consultant(identity_service):
    """Test permissions for Junior Consultant role"""
    permissions = identity_service.get_permissions_for_role("Junior Consultant")

    assert isinstance(permissions, list)
    assert "setup" in permissions
    assert "clients" in permissions
    assert "admin" not in permissions


def test_get_permissions_for_role_crew_lead(identity_service):
    """Test permissions for Crew Lead role"""
    permissions = identity_service.get_permissions_for_role("Crew Lead")

    assert isinstance(permissions, list)
    assert "setup" in permissions
    assert "clients" in permissions
    assert "team" in permissions


def test_get_permissions_for_role_tax_manager(identity_service):
    """Test permissions for Tax Manager role"""
    permissions = identity_service.get_permissions_for_role("Tax Manager")

    assert isinstance(permissions, list)
    assert "tax" in permissions
    assert "finance" in permissions
    assert "reports" in permissions
    assert "clients" in permissions


def test_get_permissions_for_role_tax_expert(identity_service):
    """Test permissions for Tax Expert role"""
    permissions = identity_service.get_permissions_for_role("Tax Expert")

    assert isinstance(permissions, list)
    assert "tax" in permissions
    assert "reports" in permissions
    assert "clients" in permissions


def test_get_permissions_for_role_tax_consultant(identity_service):
    """Test permissions for Tax Consultant role"""
    permissions = identity_service.get_permissions_for_role("Tax Consultant")

    assert isinstance(permissions, list)
    assert "tax" in permissions
    assert "clients" in permissions


def test_get_permissions_for_role_tax_care(identity_service):
    """Test permissions for Tax Care role"""
    permissions = identity_service.get_permissions_for_role("Tax Care")

    assert isinstance(permissions, list)
    assert "tax" in permissions
    assert "clients" in permissions


def test_get_permissions_for_role_marketing_specialist(identity_service):
    """Test permissions for Marketing Specialist role"""
    permissions = identity_service.get_permissions_for_role("Marketing Specialist")

    assert isinstance(permissions, list)
    assert "marketing" in permissions
    assert "clients" in permissions
    assert "reports" in permissions


def test_get_permissions_for_role_marketing_advisory(identity_service):
    """Test permissions for Marketing Advisory role"""
    permissions = identity_service.get_permissions_for_role("Marketing Advisory")

    assert isinstance(permissions, list)
    assert "marketing" in permissions
    assert "clients" in permissions


def test_get_permissions_for_role_reception(identity_service):
    """Test permissions for Reception role"""
    permissions = identity_service.get_permissions_for_role("Reception")

    assert isinstance(permissions, list)
    assert "clients" in permissions
    assert "appointments" in permissions


def test_get_permissions_for_role_external_advisory(identity_service):
    """Test permissions for External Advisory role"""
    permissions = identity_service.get_permissions_for_role("External Advisory")

    assert isinstance(permissions, list)
    assert "clients" in permissions
    assert "reports" in permissions


def test_get_permissions_for_role_unknown_role(identity_service):
    """Test permissions for unknown role (default fallback)"""
    permissions = identity_service.get_permissions_for_role("Unknown Role")

    assert isinstance(permissions, list)
    assert permissions == ["clients"]  # Default fallback


def test_get_permissions_for_role_empty_role(identity_service):
    """Test permissions for empty role (default fallback)"""
    permissions = identity_service.get_permissions_for_role("")

    assert isinstance(permissions, list)
    assert permissions == ["clients"]  # Default fallback


def test_get_permissions_for_role_none_role(identity_service):
    """Test permissions for None role (default fallback)"""
    permissions = identity_service.get_permissions_for_role(None)

    assert isinstance(permissions, list)
    assert permissions == ["clients"]  # Default fallback


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_authenticate_user_full_flow_with_real_bcrypt(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test full authentication flow with real bcrypt hashing"""
    # Create a real password hash
    real_pin = "1234"
    real_hash = bcrypt.hashpw(real_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    sample_db_row["pin_hash"] = real_hash

    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        user = await identity_service.authenticate_user("test@example.com", real_pin)

        assert user is not None
        assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_pin_hash_logging(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that PIN hash logging includes correct information"""
    sample_db_row["pin_hash"] = "$2b$12$testhash12345678901234567890"
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            with patch("app.modules.identity.service.logger") as mock_logger:
                await identity_service.authenticate_user("test@example.com", "1234")

                # Verify logging was called
                info_calls = [
                    call for call in mock_logger.info.call_args_list if "Verifying PIN" in str(call)
                ]
                assert len(info_calls) > 0


@pytest.mark.asyncio
async def test_authenticate_user_success_logging(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that successful authentication is logged"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            with patch("app.modules.identity.service.logger") as mock_logger:
                user = await identity_service.authenticate_user("test@example.com", "1234")

                assert user is not None
                # Verify success logging
                success_calls = [
                    call
                    for call in mock_logger.info.call_args_list
                    if "authenticated" in str(call).lower()
                ]
                assert len(success_calls) > 0


# ============================================================================
# Additional Edge Cases and Error Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_authenticate_user_execute_fails_on_failed_attempt_increment(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that authentication handles execute failure when incrementing failed attempts"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock(side_effect=Exception("Database write error"))

    # Mock password verification to return False (triggering failed attempt increment)
    with patch.object(identity_service, "verify_password", return_value=False):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            with patch("app.modules.identity.service.logger") as mock_logger:
                user = await identity_service.authenticate_user("test@example.com", "1234")

                assert user is None
                # Should still close connection even if execute fails
                assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_execute_fails_on_success_reset(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that authentication handles execute failure when resetting failed attempts"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    # Execute fails during reset (after successful PIN verification)
    mock_asyncpg_connection.execute = AsyncMock(side_effect=Exception("Database write error"))

    # Mock password verification to return True (triggering reset)
    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            with patch("app.modules.identity.service.logger") as mock_logger:
                user = await identity_service.authenticate_user("test@example.com", "1234")

                # When execute fails, exception is caught and None is returned
                assert user is None
                mock_logger.error.assert_called_once()
                assert "Authentication error" in mock_logger.error.call_args[0][0]
                assert mock_asyncpg_connection.close.called


@pytest.mark.asyncio
async def test_authenticate_user_pin_hash_none(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication when pin_hash is None in database"""
    sample_db_row["pin_hash"] = None
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            # verify_password should handle None gracefully
            result = identity_service.verify_password("1234", None)
            assert result is False

            user = await identity_service.authenticate_user("test@example.com", "1234")
            assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_pin_hash_empty_string(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication when pin_hash is empty string in database"""
    sample_db_row["pin_hash"] = ""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch.object(identity_service, "verify_password", return_value=False):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            user = await identity_service.authenticate_user("test@example.com", "1234")
            assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_locked_until_exact_current_time(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test authentication when locked_until is exactly current time (edge case)"""
    # Set locked_until to exactly now (should be considered locked)
    # Note: locked_until > now() means locked, so == now() is NOT locked
    # But we test the edge case where it's exactly equal
    current_time = datetime.now(timezone.utc)
    sample_db_row["locked_until"] = current_time
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            # Mock verify_password to avoid bcrypt issues with invalid hash
            with patch.object(identity_service, "verify_password", return_value=True):
                user = await identity_service.authenticate_user("test@example.com", "1234")
                # locked_until == now() means NOT locked (only > now() is locked)
                # So authentication should succeed
                assert user is not None


@pytest.mark.asyncio
async def test_authenticate_user_connection_close_fails(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test that authentication handles connection close failure"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()
    mock_asyncpg_connection.close = AsyncMock(side_effect=Exception("Close error"))

    with patch.object(identity_service, "verify_password", return_value=True):
        with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
            # When close fails in finally block, exception is propagated
            # This is expected behavior - close errors should be visible
            with pytest.raises(Exception, match="Close error"):
                await identity_service.authenticate_user("test@example.com", "1234")


def test_get_password_hash_empty_string(identity_service):
    """Test password hashing with empty string"""
    hashed = identity_service.get_password_hash("")
    assert hashed is not None
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")
    # Should be able to verify empty password
    assert identity_service.verify_password("", hashed)


def test_get_password_hash_unicode_characters(identity_service):
    """Test password hashing with unicode/special characters"""
    password = "test🔐1234àéîöü"
    hashed = identity_service.get_password_hash(password)
    assert hashed is not None
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")
    # Should be able to verify unicode password
    assert identity_service.verify_password(password, hashed)


def test_get_password_hash_very_long_password(identity_service):
    """Test password hashing with very long password"""
    password = "a" * 1000  # Very long password
    hashed = identity_service.get_password_hash(password)
    assert hashed is not None
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")
    # Should be able to verify long password
    assert identity_service.verify_password(password, hashed)


def test_verify_password_none_hash(identity_service):
    """Test password verification with None hash"""
    result = identity_service.verify_password("test1234", None)
    assert result is False


def test_verify_password_empty_hash(identity_service):
    """Test password verification with empty hash"""
    result = identity_service.verify_password("test1234", "")
    assert result is False


def test_verify_password_empty_password(identity_service):
    """Test password verification with empty password"""
    # Hash an empty password
    hashed = identity_service.get_password_hash("")
    # Verify it works
    assert identity_service.verify_password("", hashed)
    # Verify wrong empty password fails
    assert not identity_service.verify_password("wrong", hashed)


def test_verify_password_unicode_password(identity_service):
    """Test password verification with unicode password"""
    password = "test🔐1234àéîöü"
    hashed = identity_service.get_password_hash(password)
    assert identity_service.verify_password(password, hashed)
    assert not identity_service.verify_password("wrong", hashed)


def test_create_access_token_jwt_encode_failure(identity_service, sample_user):
    """Test that create_access_token handles JWT encode failure"""
    session_id = "session_12345"

    with patch("jose.jwt.encode", side_effect=Exception("JWT encoding error")):
        with pytest.raises(Exception, match="JWT encoding error"):
            identity_service.create_access_token(sample_user, session_id)


def test_create_access_token_with_none_session_id(identity_service, sample_user):
    """Test create_access_token with None session_id"""
    token = identity_service.create_access_token(sample_user, None)

    assert token is not None
    decoded = jwt.decode(
        token, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )
    assert decoded["sessionId"] is None


def test_create_access_token_with_empty_session_id(identity_service, sample_user):
    """Test create_access_token with empty session_id"""
    token = identity_service.create_access_token(sample_user, "")

    assert token is not None
    decoded = jwt.decode(
        token, identity_service.jwt_secret, algorithms=[identity_service.jwt_algorithm]
    )
    assert decoded["sessionId"] == ""


@pytest.mark.asyncio
async def test_authenticate_user_with_all_none_fields(
    mock_settings, identity_service, mock_asyncpg_connection
):
    """Test authentication with user that has all optional fields as None"""
    db_row = {
        "id": "test-user-id-123",
        "name": "Test User",
        "email": "test@example.com",
        "pin_hash": bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode("utf-8"),
        "role": None,
        "department": None,
        "language": None,
        "personalized_response": None,
        "is_active": True,
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        user = await identity_service.authenticate_user("test@example.com", "1234")

        assert user is not None
        assert user.role is None
        assert user.department is None
        assert user.language == "en"  # Default fallback
        assert user.personalized_response is False  # Default fallback


@pytest.mark.asyncio
async def test_authenticate_user_fetchrow_returns_none_after_connection(
    mock_settings, identity_service, mock_asyncpg_connection
):
    """Test authentication when fetchrow returns None after successful connection"""
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=None)

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            user = await identity_service.authenticate_user("test@example.com", "1234")

            assert user is None
            mock_logger.warning.assert_called()
            assert mock_asyncpg_connection.close.called


def test_get_permissions_for_role_case_sensitivity(identity_service):
    """Test that permissions are case-sensitive (role matching)"""
    # CEO should work
    permissions_ceo = identity_service.get_permissions_for_role("CEO")
    assert "all" in permissions_ceo

    # Lowercase should not match
    permissions_lower = identity_service.get_permissions_for_role("ceo")
    assert permissions_lower == ["clients"]  # Default fallback


def test_get_permissions_for_role_with_whitespace(identity_service):
    """Test permissions with role that has whitespace"""
    permissions = identity_service.get_permissions_for_role("  CEO  ")
    # Should not match due to whitespace
    assert permissions == ["clients"]  # Default fallback


@pytest.mark.asyncio
async def test_authenticate_user_pin_hash_logging_with_none(
    mock_settings, identity_service, mock_asyncpg_connection, sample_db_row
):
    """Test PIN hash logging when pin_hash is None (handles gracefully)"""
    sample_db_row["pin_hash"] = None
    mock_asyncpg_connection.fetchrow = AsyncMock(return_value=sample_db_row)
    mock_asyncpg_connection.execute = AsyncMock()

    with patch("asyncpg.connect", return_value=mock_asyncpg_connection):
        with patch("app.modules.identity.service.logger") as mock_logger:
            # When pin_hash is None, len() will fail, causing exception
            # This is caught by the exception handler
            with patch.object(identity_service, "verify_password", return_value=False):
                user = await identity_service.authenticate_user("test@example.com", "1234")

                # Should return None due to exception in logging or verification
                assert user is None
                # Exception should be logged
                assert mock_logger.error.called
