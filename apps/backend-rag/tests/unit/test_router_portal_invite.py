"""
Unit tests for Portal Invite Router
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.portal_invite import (
    CompleteRegistrationRequest,
    RegistrationResponse,
    SendInviteRequest,
    ValidateTokenResponse,
    build_invite_email_html,
    complete_registration,
    get_client_invitations,
    resend_invitation,
    send_invitation,
    validate_token,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn


@pytest.fixture
def mock_team_user():
    """Mock team user"""
    return {"id": 1, "email": "team@example.com", "role": "team"}


@pytest.fixture
def mock_client_user():
    """Mock client user"""
    return {"id": 2, "email": "client@example.com", "role": "client"}


@pytest.fixture
def mock_invite_service():
    """Mock InviteService"""
    service = MagicMock()
    service.create_invitation = AsyncMock(
        return_value={
            "invitation_id": 123,
            "token": "abc123",
            "invite_url": "/invite/validate/abc123",
            "client_name": "Test Client",
            "email": "client@example.com",
            "client_id": 1,
        }
    )
    service.get_client_invitations = AsyncMock(return_value=[{"id": 1, "token": "abc123"}])
    service.resend_invitation = AsyncMock(
        return_value={
            "invitation_id": 124,
            "token": "def456",
            "invite_url": "/invite/validate/def456",
            "client_name": "Test Client",
            "email": "client@example.com",
        }
    )
    service.validate_token = AsyncMock(
        return_value={
            "client_name": "Test Client",
            "email": "client@example.com",
            "invitation_id": 123,
            "client_id": 1,
        }
    )
    service.complete_registration = AsyncMock(
        return_value={"user_id": "uuid-123", "email": "client@example.com"}
    )
    return service


@pytest.fixture
def mock_email_service():
    """Mock ZohoEmailService"""
    service = MagicMock()
    service.send_email = AsyncMock(return_value={"success": True})
    return service


# ============================================================================
# Tests for build_invite_email_html
# ============================================================================


def test_build_invite_email_html():
    """Test building invite email HTML"""
    html = build_invite_email_html("John Doe", "https://example.com/invite/token123")

    assert "John Doe" in html
    assert "https://example.com/invite/token123" in html
    assert "Welcome to Bali Zero Portal" in html
    assert "Activate Your Portal" in html
    assert "font-family" in html


def test_build_invite_email_html_empty_name():
    """Test building invite email HTML with empty name"""
    html = build_invite_email_html("", "https://example.com/invite/token123")

    assert "https://example.com/invite/token123" in html
    assert "Hello" in html


# ============================================================================
# Tests for send_invitation
# ============================================================================


@pytest.mark.asyncio
async def test_send_invitation_success(mock_team_user, mock_invite_service, mock_email_service):
    """Test successful invitation sending"""
    request = SendInviteRequest(client_id=1, email="client@example.com")

    with patch("app.routers.portal_invite.settings") as mock_settings:
        mock_settings.frontend_url = "https://portal.example.com"

        result = await send_invitation(
            request, mock_team_user, mock_invite_service, mock_email_service
        )

        assert result["success"] is True
        assert "Invitation created" in result["message"]
        assert result["email_sent"] is True
        assert "full_invite_url" in result["data"]
        mock_invite_service.create_invitation.assert_called_once()
        mock_email_service.send_email.assert_called_once()


@pytest.mark.asyncio
async def test_send_invitation_client_user_forbidden(
    mock_client_user, mock_invite_service, mock_email_service
):
    """Test sending invitation as client user (forbidden)"""
    request = SendInviteRequest(client_id=1, email="client@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await send_invitation(request, mock_client_user, mock_invite_service, mock_email_service)

    assert exc_info.value.status_code == 403
    assert "cannot send invitations" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_send_invitation_email_failure(
    mock_team_user, mock_invite_service, mock_email_service
):
    """Test invitation sending when email fails"""
    request = SendInviteRequest(client_id=1, email="client@example.com")

    mock_email_service.send_email = AsyncMock(side_effect=Exception("Email service error"))

    with patch("app.routers.portal_invite.settings") as mock_settings:
        mock_settings.frontend_url = "https://portal.example.com"

        result = await send_invitation(
            request, mock_team_user, mock_invite_service, mock_email_service
        )

        assert result["success"] is True
        assert result["email_sent"] is False
        assert result["email_error"] is not None
        assert "not sent" in result["message"].lower()


@pytest.mark.asyncio
async def test_send_invitation_no_user_email(mock_invite_service, mock_email_service):
    """Test invitation sending when user has no email"""
    user_no_email = {"id": 1, "role": "team"}
    request = SendInviteRequest(client_id=1, email="client@example.com")

    with patch("app.routers.portal_invite.settings") as mock_settings:
        mock_settings.frontend_url = "https://portal.example.com"

        result = await send_invitation(
            request, user_no_email, mock_invite_service, mock_email_service
        )

        assert result["success"] is True
        # Email service should not be called if user has no email
        mock_email_service.send_email.assert_not_called()


@pytest.mark.asyncio
async def test_send_invitation_service_error(
    mock_team_user, mock_invite_service, mock_email_service
):
    """Test invitation sending when service raises error"""
    request = SendInviteRequest(client_id=1, email="client@example.com")

    mock_invite_service.create_invitation = AsyncMock(side_effect=ValueError("Invalid client"))

    with pytest.raises(HTTPException) as exc_info:
        await send_invitation(request, mock_team_user, mock_invite_service, mock_email_service)

    assert exc_info.value.status_code == 400
    assert "Invalid client" in exc_info.value.detail


@pytest.mark.asyncio
async def test_send_invitation_exception(mock_team_user, mock_invite_service, mock_email_service):
    """Test invitation sending when exception occurs"""
    request = SendInviteRequest(client_id=1, email="client@example.com")

    mock_invite_service.create_invitation = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await send_invitation(request, mock_team_user, mock_invite_service, mock_email_service)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_send_invitation_default_frontend_url(
    mock_team_user, mock_invite_service, mock_email_service
):
    """Test invitation sending with default frontend URL"""
    request = SendInviteRequest(client_id=1, email="client@example.com")

    with patch("app.routers.portal_invite.settings") as mock_settings:
        # Remove frontend_url attribute to test default
        if hasattr(mock_settings, "frontend_url"):
            delattr(mock_settings, "frontend_url")

        result = await send_invitation(
            request, mock_team_user, mock_invite_service, mock_email_service
        )

        assert result["success"] is True
        assert "full_invite_url" in result["data"]


# ============================================================================
# Tests for get_client_invitations
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_invitations_success(mock_team_user, mock_invite_service):
    """Test successful retrieval of client invitations"""
    result = await get_client_invitations(1, mock_team_user, mock_invite_service)

    assert result["success"] is True
    assert "data" in result
    assert len(result["data"]) == 1
    mock_invite_service.get_client_invitations.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_client_invitations_client_user_forbidden(mock_client_user, mock_invite_service):
    """Test getting invitations as client user (forbidden)"""
    with pytest.raises(HTTPException) as exc_info:
        await get_client_invitations(1, mock_client_user, mock_invite_service)

    assert exc_info.value.status_code == 403
    assert "cannot view" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_client_invitations_exception(mock_team_user, mock_invite_service):
    """Test getting invitations when exception occurs"""
    mock_invite_service.get_client_invitations = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client_invitations(1, mock_team_user, mock_invite_service)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


# ============================================================================
# Tests for resend_invitation
# ============================================================================


@pytest.mark.asyncio
async def test_resend_invitation_success(mock_team_user, mock_invite_service):
    """Test successful invitation resending"""
    result = await resend_invitation(1, mock_team_user, mock_invite_service)

    assert result["success"] is True
    assert "Invitation resent successfully" in result["message"]
    assert "data" in result
    # Verify it was called with client_id and created_by (as kwargs)
    call_args = mock_invite_service.resend_invitation.call_args
    assert call_args[1]["client_id"] == 1
    assert call_args[1]["created_by"] == "team@example.com"


@pytest.mark.asyncio
async def test_resend_invitation_client_user_forbidden(mock_client_user, mock_invite_service):
    """Test resending invitation as client user (forbidden)"""
    with pytest.raises(HTTPException) as exc_info:
        await resend_invitation(1, mock_client_user, mock_invite_service)

    assert exc_info.value.status_code == 403
    assert "cannot resend" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_resend_invitation_service_error(mock_team_user, mock_invite_service):
    """Test resending invitation when service raises error"""
    mock_invite_service.resend_invitation = AsyncMock(side_effect=ValueError("Invalid client"))

    with pytest.raises(HTTPException) as exc_info:
        await resend_invitation(1, mock_team_user, mock_invite_service)

    assert exc_info.value.status_code == 400
    assert "Invalid client" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resend_invitation_exception(mock_team_user, mock_invite_service):
    """Test resending invitation when exception occurs"""
    mock_invite_service.resend_invitation = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await resend_invitation(1, mock_team_user, mock_invite_service)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resend_invitation_no_user_email(mock_invite_service):
    """Test resending invitation when user has no email"""
    user_no_email = {"id": 1, "role": "team"}

    result = await resend_invitation(1, user_no_email, mock_invite_service)

    assert result["success"] is True
    # Verify it was called with client_id and created_by (as kwargs)
    call_args = mock_invite_service.resend_invitation.call_args
    assert call_args[1]["client_id"] == 1
    assert call_args[1]["created_by"] == "system"


# ============================================================================
# Tests for validate_token
# ============================================================================


@pytest.mark.asyncio
async def test_validate_token_success(mock_invite_service):
    """Test successful token validation"""
    result = await validate_token("abc123", mock_invite_service)

    assert result.valid is True
    assert result.client_name == "Test Client"
    assert result.email == "client@example.com"
    assert result.invitation_id == 123
    assert result.client_id == 1
    assert result.error is None
    mock_invite_service.validate_token.assert_called_once_with("abc123")


@pytest.mark.asyncio
async def test_validate_token_invalid(mock_invite_service):
    """Test token validation with invalid token"""
    mock_invite_service.validate_token = AsyncMock(return_value=None)

    result = await validate_token("invalid", mock_invite_service)

    assert result.valid is False
    assert result.error == "invalid_token"
    assert "invalid" in result.message.lower()
    assert result.client_name is None


@pytest.mark.asyncio
async def test_validate_token_expired(mock_invite_service):
    """Test token validation with expired token"""
    mock_invite_service.validate_token = AsyncMock(
        return_value={"error": "expired", "message": "This invitation has expired"}
    )

    result = await validate_token("expired123", mock_invite_service)

    assert result.valid is False
    assert result.error == "expired"
    assert "expired" in result.message.lower()
    assert result.client_name is None


@pytest.mark.asyncio
async def test_validate_token_exception(mock_invite_service):
    """Test token validation when exception occurs"""
    mock_invite_service.validate_token = AsyncMock(side_effect=Exception("Database error"))

    result = await validate_token("abc123", mock_invite_service)

    assert result.valid is False
    assert result.error == "server_error"
    assert "error" in result.message.lower()


# ============================================================================
# Tests for complete_registration
# ============================================================================


@pytest.mark.asyncio
async def test_complete_registration_success(mock_invite_service):
    """Test successful registration completion"""
    request = CompleteRegistrationRequest(token="abc123", pin="123456")

    result = await complete_registration(request, mock_invite_service)

    assert result.success is True
    assert "successful" in result.message.lower()
    assert result.user_id == "uuid-123"
    assert result.redirect_to == "/login"
    # Verify it was called with token and pin (as kwargs)
    call_args = mock_invite_service.complete_registration.call_args
    assert call_args[1]["token"] == "abc123"
    assert call_args[1]["pin"] == "123456"


@pytest.mark.asyncio
async def test_complete_registration_pin_validation():
    """Test PIN validation in CompleteRegistrationRequest"""
    # Test PIN too short
    with pytest.raises(ValidationError) as exc_info:
        CompleteRegistrationRequest(token="abc123", pin="123")
    assert "4-6 digits" in str(exc_info.value)

    # Test PIN too long
    with pytest.raises(ValidationError) as exc_info:
        CompleteRegistrationRequest(token="abc123", pin="1234567")
    assert "4-6 digits" in str(exc_info.value)

    # Test PIN with non-digits
    with pytest.raises(ValidationError) as exc_info:
        CompleteRegistrationRequest(token="abc123", pin="abc123")
    assert "digits" in str(exc_info.value).lower()

    # Test valid PIN (4 digits)
    request = CompleteRegistrationRequest(token="abc123", pin="1234")
    assert request.pin == "1234"

    # Test valid PIN (6 digits)
    request = CompleteRegistrationRequest(token="abc123", pin="123456")
    assert request.pin == "123456"

    # Test valid PIN (5 digits)
    request = CompleteRegistrationRequest(token="abc123", pin="12345")
    assert request.pin == "12345"


@pytest.mark.asyncio
async def test_complete_registration_service_error(mock_invite_service):
    """Test registration completion when service raises error"""
    mock_invite_service.complete_registration = AsyncMock(side_effect=ValueError("Invalid token"))

    request = CompleteRegistrationRequest(token="abc123", pin="123456")

    with pytest.raises(HTTPException) as exc_info:
        await complete_registration(request, mock_invite_service)

    assert exc_info.value.status_code == 400
    assert "Invalid token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_complete_registration_exception(mock_invite_service):
    """Test registration completion when exception occurs"""
    mock_invite_service.complete_registration = AsyncMock(side_effect=Exception("Database error"))

    request = CompleteRegistrationRequest(token="abc123", pin="123456")

    with pytest.raises(HTTPException) as exc_info:
        await complete_registration(request, mock_invite_service)

    assert exc_info.value.status_code == 500
    assert "failed" in exc_info.value.detail.lower()


# ============================================================================
# Tests for SendInviteRequest model
# ============================================================================


def test_send_invite_request_validation():
    """Test SendInviteRequest validation"""
    # Valid request
    request = SendInviteRequest(client_id=1, email="client@example.com")
    assert request.client_id == 1
    assert request.email == "client@example.com"

    # Test invalid email
    with pytest.raises(ValidationError):
        SendInviteRequest(client_id=1, email="invalid-email")


# ============================================================================
# Tests for ValidateTokenResponse model
# ============================================================================


def test_validate_token_response_defaults():
    """Test ValidateTokenResponse default values"""
    response = ValidateTokenResponse()
    assert response.valid is False
    assert response.error is None
    assert response.message is None
    assert response.client_name is None
    assert response.email is None
    assert response.invitation_id is None
    assert response.client_id is None


def test_validate_token_response_with_data():
    """Test ValidateTokenResponse with data"""
    response = ValidateTokenResponse(
        valid=True,
        client_name="Test Client",
        email="client@example.com",
        invitation_id=123,
        client_id=1,
    )
    assert response.valid is True
    assert response.client_name == "Test Client"
    assert response.email == "client@example.com"
    assert response.invitation_id == 123
    assert response.client_id == 1


# ============================================================================
# Tests for RegistrationResponse model
# ============================================================================


def test_registration_response_defaults():
    """Test RegistrationResponse default values"""
    response = RegistrationResponse(success=True, message="Success")
    assert response.success is True
    assert response.message == "Success"
    assert response.user_id is None
    assert response.redirect_to is None


def test_registration_response_with_data():
    """Test RegistrationResponse with data"""
    response = RegistrationResponse(
        success=True,
        message="Success",
        user_id="uuid-123",
        redirect_to="/login",
    )
    assert response.success is True
    assert response.user_id == "uuid-123"
    assert response.redirect_to == "/login"
