"""
Unit tests for CRM Portal Integration Router
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.crm_portal_integration import (
    SendInviteRequest,
    TeamMessageRequest,
    get_client_messages,
    get_portal_preview,
    get_portal_status,
    get_recent_portal_activity,
    get_unread_messages_count,
    mark_client_message_read,
    require_team_auth,
    send_message_to_client,
    send_portal_invite,
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
    """Mock team user (not client)"""
    return {"id": 1, "email": "team@example.com", "role": "team"}


@pytest.fixture
def mock_client_user():
    """Mock client user"""
    return {"id": 2, "email": "client@example.com", "role": "client"}


@pytest.fixture
def mock_invite_service():
    """Mock InviteService"""
    service = MagicMock()
    service.create_invitation = AsyncMock(return_value={"invite_id": 123, "token": "abc123"})
    return service


@pytest.fixture
def mock_portal_service():
    """Mock PortalService"""
    service = MagicMock()
    service.get_dashboard = AsyncMock(return_value={"summary": "dashboard data"})
    service.get_visa_status = AsyncMock(return_value={"status": "active"})
    service.get_companies = AsyncMock(return_value=[{"id": 1, "name": "Company 1"}])
    service.get_tax_overview = AsyncMock(return_value={"total": 1000})
    service.get_messages = AsyncMock(return_value={"messages": [], "total": 0})
    return service


# ============================================================================
# Tests for require_team_auth
# ============================================================================


def test_require_team_auth_team_user(mock_team_user):
    """Test require_team_auth allows team users"""
    result = require_team_auth(mock_team_user)
    assert result == mock_team_user


def test_require_team_auth_client_user(mock_client_user):
    """Test require_team_auth rejects client users"""
    with pytest.raises(HTTPException) as exc_info:
        require_team_auth(mock_client_user)

    assert exc_info.value.status_code == 403
    assert "team members" in exc_info.value.detail.lower()


# ============================================================================
# Tests for get_portal_status
# ============================================================================


@pytest.mark.asyncio
async def test_get_portal_status_with_portal_user(mock_db_pool, mock_team_user):
    """Test portal status when client has portal access"""
    pool, conn = mock_db_pool

    portal_user = {
        "id": 10,
        "email": "client@example.com",
        "last_login": datetime.now(),
    }

    conn.fetchrow = AsyncMock(side_effect=[portal_user, None])

    result = await get_portal_status(1, mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["has_portal_access"] is True
    assert result["data"]["portal_user_id"] == 10
    assert result["data"]["portal_email"] == "client@example.com"
    assert result["data"]["pending_invite"] is False


@pytest.mark.asyncio
async def test_get_portal_status_with_pending_invite(mock_db_pool, mock_team_user):
    """Test portal status when client has pending invite"""
    pool, conn = mock_db_pool

    pending_invite = {"expires_at": datetime.now()}

    conn.fetchrow = AsyncMock(side_effect=[None, pending_invite])

    result = await get_portal_status(1, mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["has_portal_access"] is False
    assert result["data"]["pending_invite"] is True
    assert result["data"]["invite_expires_at"] is not None


@pytest.mark.asyncio
async def test_get_portal_status_no_access(mock_db_pool, mock_team_user):
    """Test portal status when client has no access and no invite"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value=None)

    result = await get_portal_status(1, mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["has_portal_access"] is False
    assert result["data"]["pending_invite"] is False
    assert result["data"]["portal_user_id"] is None


@pytest.mark.asyncio
async def test_get_portal_status_with_no_last_login(mock_db_pool, mock_team_user):
    """Test portal status when portal user has no last_login"""
    pool, conn = mock_db_pool

    portal_user = {"id": 10, "email": "client@example.com", "last_login": None}

    conn.fetchrow = AsyncMock(side_effect=[portal_user, None])

    result = await get_portal_status(1, mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["has_portal_access"] is True
    assert result["data"]["last_login"] is None


# ============================================================================
# Tests for send_portal_invite
# ============================================================================


@pytest.mark.asyncio
async def test_send_portal_invite_with_email(mock_db_pool, mock_team_user, mock_invite_service):
    """Test sending portal invite with email provided"""
    pool, conn = mock_db_pool

    request = SendInviteRequest(email="client@example.com")

    result = await send_portal_invite(1, request, mock_team_user, mock_invite_service, pool)

    assert result["success"] is True
    assert "Invitation sent" in result["message"]
    mock_invite_service.create_invitation.assert_called_once()
    call_args = mock_invite_service.create_invitation.call_args
    assert call_args[1]["client_id"] == 1
    assert call_args[1]["email"] == "client@example.com"


@pytest.mark.asyncio
async def test_send_portal_invite_without_email(mock_db_pool, mock_team_user, mock_invite_service):
    """Test sending portal invite without email (uses client email)"""
    pool, conn = mock_db_pool

    client = {"email": "client@example.com"}
    conn.fetchrow = AsyncMock(return_value=client)

    request = SendInviteRequest(email=None)

    result = await send_portal_invite(1, request, mock_team_user, mock_invite_service, pool)

    assert result["success"] is True
    mock_invite_service.create_invitation.assert_called_once()
    call_args = mock_invite_service.create_invitation.call_args
    assert call_args[1]["email"] == "client@example.com"


@pytest.mark.asyncio
async def test_send_portal_invite_without_request(
    mock_db_pool, mock_team_user, mock_invite_service
):
    """Test sending portal invite without request object"""
    pool, conn = mock_db_pool

    client = {"email": "client@example.com"}
    conn.fetchrow = AsyncMock(return_value=client)

    result = await send_portal_invite(1, None, mock_team_user, mock_invite_service, pool)

    assert result["success"] is True
    mock_invite_service.create_invitation.assert_called_once()


@pytest.mark.asyncio
async def test_send_portal_invite_client_no_email(
    mock_db_pool, mock_team_user, mock_invite_service
):
    """Test sending portal invite when client has no email"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(return_value=None)

    request = SendInviteRequest(email=None)

    with pytest.raises(HTTPException) as exc_info:
        await send_portal_invite(1, request, mock_team_user, mock_invite_service, pool)

    assert exc_info.value.status_code == 400
    assert "email" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_send_portal_invite_service_error(mock_db_pool, mock_team_user, mock_invite_service):
    """Test sending portal invite when service raises error"""
    pool, conn = mock_db_pool

    mock_invite_service.create_invitation = AsyncMock(side_effect=ValueError("Invalid email"))

    request = SendInviteRequest(email="client@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await send_portal_invite(1, request, mock_team_user, mock_invite_service, pool)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_send_portal_invite_exception(mock_db_pool, mock_team_user, mock_invite_service):
    """Test sending portal invite when exception occurs"""
    pool, conn = mock_db_pool

    mock_invite_service.create_invitation = AsyncMock(side_effect=Exception("Database error"))

    request = SendInviteRequest(email="client@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await send_portal_invite(1, request, mock_team_user, mock_invite_service, pool)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


# ============================================================================
# Tests for get_portal_preview
# ============================================================================


@pytest.mark.asyncio
async def test_get_portal_preview_success(mock_team_user, mock_portal_service):
    """Test successful portal preview"""
    result = await get_portal_preview(1, mock_team_user, mock_portal_service)

    assert result["success"] is True
    assert "dashboard" in result["data"]
    assert "visa" in result["data"]
    assert "companies" in result["data"]
    assert "taxes" in result["data"]
    mock_portal_service.get_dashboard.assert_called_once_with(1)
    mock_portal_service.get_visa_status.assert_called_once_with(1)
    mock_portal_service.get_companies.assert_called_once_with(1)
    mock_portal_service.get_tax_overview.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_portal_preview_service_error(mock_team_user, mock_portal_service):
    """Test portal preview when service raises error"""
    mock_portal_service.get_dashboard = AsyncMock(side_effect=Exception("Service error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_portal_preview(1, mock_team_user, mock_portal_service)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


# ============================================================================
# Tests for get_unread_messages_count
# ============================================================================


@pytest.mark.asyncio
async def test_get_unread_messages_count_success(mock_db_pool, mock_team_user):
    """Test successful unread messages count"""
    pool, conn = mock_db_pool

    conn.fetchval = AsyncMock(return_value=5)
    conn.fetch = AsyncMock(
        return_value=[
            {"client_id": 1, "client_name": "Client 1", "unread_count": 3},
            {"client_id": 2, "client_name": "Client 2", "unread_count": 2},
        ]
    )

    result = await get_unread_messages_count(mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["total_unread"] == 5
    assert len(result["data"]["by_client"]) == 2
    assert result["data"]["by_client"][0]["client_id"] == 1
    assert result["data"]["by_client"][0]["unread_count"] == 3


@pytest.mark.asyncio
async def test_get_unread_messages_count_empty(mock_db_pool, mock_team_user):
    """Test unread messages count when no unread messages"""
    pool, conn = mock_db_pool

    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])

    result = await get_unread_messages_count(mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["total_unread"] == 0
    assert len(result["data"]["by_client"]) == 0


@pytest.mark.asyncio
async def test_get_unread_messages_count_none_total(mock_db_pool, mock_team_user):
    """Test unread messages count when total is None"""
    pool, conn = mock_db_pool

    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    result = await get_unread_messages_count(mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["total_unread"] == 0


# ============================================================================
# Tests for get_client_messages
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_messages_success(mock_team_user, mock_portal_service):
    """Test successful client messages retrieval"""
    mock_portal_service.get_messages = AsyncMock(
        return_value={"messages": [{"id": 1, "content": "Hello"}], "total": 1}
    )

    result = await get_client_messages(
        1, limit=50, offset=0, current_user=mock_team_user, portal_service=mock_portal_service
    )

    assert result["success"] is True
    assert "data" in result
    mock_portal_service.get_messages.assert_called_once_with(1, limit=50, offset=0)


@pytest.mark.asyncio
async def test_get_client_messages_with_custom_limit(mock_team_user, mock_portal_service):
    """Test client messages with custom limit"""
    mock_portal_service.get_messages = AsyncMock(return_value={"messages": [], "total": 0})

    result = await get_client_messages(
        1, limit=25, offset=10, current_user=mock_team_user, portal_service=mock_portal_service
    )

    assert result["success"] is True
    mock_portal_service.get_messages.assert_called_once_with(1, limit=25, offset=10)


@pytest.mark.asyncio
async def test_get_client_messages_service_error(mock_team_user, mock_portal_service):
    """Test client messages when service raises error"""
    mock_portal_service.get_messages = AsyncMock(side_effect=Exception("Service error"))

    with pytest.raises(HTTPException) as exc_info:
        await get_client_messages(
            1, limit=50, offset=0, current_user=mock_team_user, portal_service=mock_portal_service
        )

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


# ============================================================================
# Tests for send_message_to_client
# ============================================================================


@pytest.mark.asyncio
async def test_send_message_to_client_success(mock_db_pool, mock_team_user):
    """Test successful message sending to client"""
    pool, conn = mock_db_pool

    message = {
        "id": 123,
        "subject": "Test Subject",
        "content": "Test Content",
        "sent_by": "team@example.com",
        "created_at": datetime.now(),
    }

    conn.fetchrow = AsyncMock(return_value=message)

    request = TeamMessageRequest(content="Test Content", subject="Test Subject", practice_id=1)

    result = await send_message_to_client(1, request, mock_team_user, pool)

    assert result["success"] is True
    assert result["message"] == "Message sent"
    assert result["data"]["id"] == 123
    assert result["data"]["subject"] == "Test Subject"
    assert result["data"]["content"] == "Test Content"
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_to_client_without_subject(mock_db_pool, mock_team_user):
    """Test sending message without subject"""
    pool, conn = mock_db_pool

    message = {
        "id": 123,
        "subject": None,
        "content": "Test Content",
        "sent_by": "team@example.com",
        "created_at": datetime.now(),
    }

    conn.fetchrow = AsyncMock(return_value=message)

    request = TeamMessageRequest(content="Test Content", subject=None, practice_id=None)

    result = await send_message_to_client(1, request, mock_team_user, pool)

    assert result["success"] is True
    assert result["data"]["id"] == 123


@pytest.mark.asyncio
async def test_send_message_to_client_exception(mock_db_pool, mock_team_user):
    """Test sending message when exception occurs"""
    pool, conn = mock_db_pool

    conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

    request = TeamMessageRequest(content="Test Content")

    with pytest.raises(HTTPException) as exc_info:
        await send_message_to_client(1, request, mock_team_user, pool)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_send_message_to_client_with_default_sent_by(mock_db_pool):
    """Test sending message with default sent_by when user has no email"""
    pool, conn = mock_db_pool

    user_no_email = {"id": 1, "role": "team"}

    message = {
        "id": 123,
        "subject": "Test",
        "content": "Test Content",
        "sent_by": "team",
        "created_at": datetime.now(),
    }

    conn.fetchrow = AsyncMock(return_value=message)

    request = TeamMessageRequest(content="Test Content", subject="Test")

    result = await send_message_to_client(1, request, user_no_email, pool)

    assert result["success"] is True
    assert result["data"]["sent_by"] == "team"


# ============================================================================
# Tests for mark_client_message_read
# ============================================================================


@pytest.mark.asyncio
async def test_mark_client_message_read_success(mock_db_pool, mock_team_user):
    """Test successful marking message as read"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(return_value="UPDATE 1")

    result = await mark_client_message_read(1, 123, mock_team_user, pool)

    assert result["success"] is True
    assert result["message"] == "Message marked as read"
    conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_client_message_read_exception(mock_db_pool, mock_team_user):
    """Test marking message as read when exception occurs"""
    pool, conn = mock_db_pool

    conn.execute = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(HTTPException) as exc_info:
        await mark_client_message_read(1, 123, mock_team_user, pool)

    assert exc_info.value.status_code == 500
    assert "Failed" in exc_info.value.detail


# ============================================================================
# Tests for get_recent_portal_activity
# ============================================================================


@pytest.mark.asyncio
async def test_get_recent_portal_activity_success(mock_db_pool, mock_team_user):
    """Test successful recent portal activity retrieval"""
    pool, conn = mock_db_pool

    activities = [
        {
            "id": 1,
            "activity_type": "message",
            "client_id": 1,
            "client_name": "Client 1",
            "subject": "Test Subject",
            "preview": "Test preview",
            "created_at": datetime.now(),
        }
    ]

    conn.fetch = AsyncMock(return_value=activities)

    result = await get_recent_portal_activity(limit=10, current_user=mock_team_user, db_pool=pool)

    assert result["success"] is True
    assert len(result["data"]["activities"]) == 1
    assert result["data"]["activities"][0]["id"] == 1
    assert result["data"]["activities"][0]["type"] == "message"
    assert result["data"]["activities"][0]["client_id"] == 1
    conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_recent_portal_activity_empty(mock_db_pool, mock_team_user):
    """Test recent portal activity when empty"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_recent_portal_activity(limit=10, current_user=mock_team_user, db_pool=pool)

    assert result["success"] is True
    assert len(result["data"]["activities"]) == 0


@pytest.mark.asyncio
async def test_get_recent_portal_activity_with_custom_limit(mock_db_pool, mock_team_user):
    """Test recent portal activity with custom limit"""
    pool, conn = mock_db_pool

    conn.fetch = AsyncMock(return_value=[])

    result = await get_recent_portal_activity(limit=25, current_user=mock_team_user, db_pool=pool)

    assert result["success"] is True
    # Verify fetch was called with limit parameter
    call_args = conn.fetch.call_args[0]
    assert len(call_args) == 2  # query and limit
    assert call_args[1] == 25  # limit parameter
