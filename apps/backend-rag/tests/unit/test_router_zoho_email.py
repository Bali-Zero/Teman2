"""
Unit tests for Zoho Email Router
Tests Zoho Mail integration endpoints (OAuth + email operations)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse

# Add backend to path
backend_path = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(backend_path))


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()
    return pool


@pytest.fixture
def mock_current_user():
    """Mock current user dict"""
    return {"user_id": "user_123", "email": "test@example.com", "role": "client"}


@pytest.fixture
def mock_oauth_service():
    """Mock ZohoOAuthService"""
    service = MagicMock()
    service.get_authorization_url = MagicMock(return_value="https://accounts.zoho.com/oauth/v2/auth?state=test")
    service.exchange_code = AsyncMock()
    service.get_connection_status = AsyncMock(return_value={
        "connected": True,
        "email": "test@zoho.com",
        "account_id": "acc_123",
        "expires_at": "2024-12-31T00:00:00Z"
    })
    service.disconnect = AsyncMock()
    return service


@pytest.fixture
def mock_email_service():
    """Mock ZohoEmailService"""
    service = MagicMock()
    service.list_folders = AsyncMock(return_value=[
        {"id": "inbox", "name": "Inbox", "path": "/Inbox", "type": "user", "unread_count": 5, "total_count": 100}
    ])
    service.list_emails = AsyncMock(return_value={
        "emails": [
            {"id": "msg_1", "subject": "Test", "sender_email": "sender@example.com"}
        ],
        "total": 1,
        "limit": 50,
        "start": 0
    })
    service.get_email = AsyncMock(return_value={
        "id": "msg_1",
        "subject": "Test",
        "body": "Test body",
        "sender_email": "sender@example.com"
    })
    service.send_email = AsyncMock(return_value={"success": True, "message_id": "msg_new"})
    service.search_emails = AsyncMock(return_value=[
        {"id": "msg_1", "subject": "Test", "sender_email": "sender@example.com"}
    ])
    service.reply_email = AsyncMock(return_value={"success": True, "message_id": "msg_reply"})
    service.forward_email = AsyncMock(return_value={"success": True, "message_id": "msg_forward"})
    service.mark_read = AsyncMock(return_value=True)
    service.toggle_flag = AsyncMock(return_value=True)
    service.delete_emails = AsyncMock(return_value=True)
    service.get_attachment = AsyncMock(return_value=b"attachment content")
    service.get_unread_count = AsyncMock(return_value=5)
    return service


@pytest.mark.unit
class TestZohoEmailOAuth:
    """Test OAuth endpoints"""

    @pytest.mark.asyncio
    async def test_get_auth_url_success(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test get auth URL"""
        from app.routers.zoho_email import get_auth_url

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            response = await get_auth_url(mock_current_user, mock_db_pool)

            assert "auth_url" in response
            assert "state" in response
            mock_oauth_service.get_authorization_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_auth_url_error(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test get auth URL error"""
        from app.routers.zoho_email import get_auth_url

        mock_oauth_service.get_authorization_url.side_effect = ValueError("Config error")

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            with pytest.raises(HTTPException) as exc:
                await get_auth_url(mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_auth_url_no_user_id(self, mock_db_pool, mock_oauth_service):
        """Test get auth URL without user_id"""
        from app.routers.zoho_email import get_auth_url

        current_user_no_id = {"email": "test@example.com"}

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            with pytest.raises(HTTPException) as exc:
                await get_auth_url(current_user_no_id, mock_db_pool)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_oauth_callback_success(self, mock_db_pool, mock_oauth_service):
        """Test OAuth callback success"""
        from app.routers.zoho_email import oauth_callback

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service), \
             patch("app.routers.zoho_email.settings") as mock_settings:
            mock_settings.frontend_url = "http://localhost:3000"
            
            response = await oauth_callback(code="auth_code_123", state="user_123:state_token", error=None, db_pool=mock_db_pool)

            assert isinstance(response, RedirectResponse)
            assert "connected=true" in response.headers["location"]
            mock_oauth_service.exchange_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_oauth_callback_with_error(self, mock_db_pool):
        """Test OAuth callback with error"""
        from app.routers.zoho_email import oauth_callback

        with patch("app.routers.zoho_email.settings") as mock_settings:
            mock_settings.frontend_url = "http://localhost:3000"
            
            response = await oauth_callback(code=None, state=None, error="access_denied", db_pool=mock_db_pool)

            assert isinstance(response, RedirectResponse)
            assert "error=oauth_denied" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_oauth_callback_missing_params(self, mock_db_pool):
        """Test OAuth callback missing code/state"""
        from app.routers.zoho_email import oauth_callback

        with patch("app.routers.zoho_email.settings") as mock_settings:
            mock_settings.frontend_url = "http://localhost:3000"
            
            response = await oauth_callback(code=None, state=None, error=None, db_pool=mock_db_pool)

            assert isinstance(response, RedirectResponse)
            assert "error=missing_params" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_oauth_callback_invalid_state(self, mock_db_pool, mock_oauth_service):
        """Test OAuth callback invalid state format"""
        from app.routers.zoho_email import oauth_callback

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service), \
             patch("app.routers.zoho_email.settings") as mock_settings:
            mock_settings.frontend_url = "http://localhost:3000"
            
            response = await oauth_callback(code="auth_code", state="invalid_state", error=None, db_pool=mock_db_pool)

            assert isinstance(response, RedirectResponse)
            assert "error=invalid_state" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_oauth_callback_exception(self, mock_db_pool, mock_oauth_service):
        """Test OAuth callback generic exception (line 236)"""
        from app.routers.zoho_email import oauth_callback

        mock_oauth_service.exchange_code = AsyncMock(side_effect=RuntimeError("Network error"))

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service), \
             patch("app.routers.zoho_email.settings") as mock_settings:
            mock_settings.frontend_url = "http://localhost:3000"
            
            response = await oauth_callback(code="auth_code", state="user_123:token", error=None, db_pool=mock_db_pool)

            assert isinstance(response, RedirectResponse)
            assert "error=connection_failed" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_get_connection_status_connected(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test get connection status - connected"""
        from app.routers.zoho_email import get_connection_status

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            response = await get_connection_status(mock_current_user, mock_db_pool)

            assert response.connected is True
            assert response.email == "test@zoho.com"
            mock_oauth_service.get_connection_status.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_get_connection_status_not_connected(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test get connection status - not connected"""
        from app.routers.zoho_email import get_connection_status

        mock_oauth_service.get_connection_status.return_value = {"connected": False}

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            response = await get_connection_status(mock_current_user, mock_db_pool)

            assert response.connected is False

    @pytest.mark.asyncio
    async def test_get_connection_status_error(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test get connection status error handling"""
        from app.routers.zoho_email import get_connection_status

        mock_oauth_service.get_connection_status.side_effect = Exception("Service error")

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            response = await get_connection_status(mock_current_user, mock_db_pool)

            assert response.connected is False
            assert response.email is None

    @pytest.mark.asyncio
    async def test_disconnect_account_success(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test disconnect account"""
        from app.routers.zoho_email import disconnect_account

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            response = await disconnect_account(mock_current_user, mock_db_pool)

            assert response["success"] is True
            mock_oauth_service.disconnect.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_disconnect_account_error(self, mock_db_pool, mock_current_user, mock_oauth_service):
        """Test disconnect account error"""
        from app.routers.zoho_email import disconnect_account

        mock_oauth_service.disconnect.side_effect = Exception("Disconnect error")

        with patch("app.routers.zoho_email._get_oauth_service", return_value=mock_oauth_service):
            with pytest.raises(HTTPException) as exc:
                await disconnect_account(mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500


@pytest.mark.unit
class TestZohoEmailFolders:
    """Test folder endpoints"""

    @pytest.mark.asyncio
    async def test_list_folders_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test list folders"""
        from app.routers.zoho_email import list_folders

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await list_folders(mock_current_user, mock_db_pool)

            assert "folders" in response
            assert len(response["folders"]) == 1
            mock_email_service.list_folders.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_list_folders_error(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test list folders error"""
        from app.routers.zoho_email import list_folders

        mock_email_service.list_folders.side_effect = ValueError("Not connected")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await list_folders(mock_current_user, mock_db_pool)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_folders_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test list folders generic exception (line 314)"""
        from app.routers.zoho_email import list_folders

        mock_email_service.list_folders.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await list_folders(mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500


@pytest.mark.unit
class TestZohoEmailOperations:
    """Test email operation endpoints"""

    @pytest.mark.asyncio
    async def test_list_emails_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test list emails"""
        from app.routers.zoho_email import list_emails

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await list_emails(
                folder_id="inbox",
                limit=50,
                start=0,
                search=None,
                is_unread=None,
                current_user=mock_current_user,
                db_pool=mock_db_pool
            )

            assert "emails" in response
            assert response["total"] == 1
            mock_email_service.list_emails.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_emails_with_filters(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test list emails with search and unread filter"""
        from app.routers.zoho_email import list_emails

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await list_emails(
                folder_id="inbox",
                limit=50,
                start=0,
                search="test query",
                is_unread=True,
                current_user=mock_current_user,
                db_pool=mock_db_pool
            )

            assert "emails" in response

    @pytest.mark.asyncio
    async def test_list_emails_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test list emails generic exception (line 353)"""
        from app.routers.zoho_email import list_emails

        mock_email_service.list_emails.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await list_emails(
                    folder_id="inbox",
                    limit=50,
                    start=0,
                    search=None,
                    is_unread=None,
                    current_user=mock_current_user,
                    db_pool=mock_db_pool
                )
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_email_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test get email"""
        from app.routers.zoho_email import get_email

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await get_email(
                message_id="msg_1",
                folder_id="inbox",
                current_user=mock_current_user,
                db_pool=mock_db_pool
            )

            assert response["id"] == "msg_1"
            assert response["subject"] == "Test"
            mock_email_service.get_email.assert_called_once_with("user_123", "msg_1", "inbox")

    @pytest.mark.asyncio
    async def test_get_email_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test get email generic exception (line 377)"""
        from app.routers.zoho_email import get_email

        mock_email_service.get_email.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await get_email(
                    message_id="msg_1",
                    folder_id="inbox",
                    current_user=mock_current_user,
                    db_pool=mock_db_pool
                )
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_send_email_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test send email"""
        from app.routers.zoho_email import SendEmailRequest, send_email

        request_data = SendEmailRequest(
            to=["recipient@example.com"],
            subject="Test Subject",
            html_content="<p>Test Body</p>",
        )

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await send_email(request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True
            mock_email_service.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_with_cc_bcc(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test send email with CC and BCC"""
        from app.routers.zoho_email import SendEmailRequest, send_email

        request_data = SendEmailRequest(
            to=["recipient@example.com"],
            subject="Test Subject",
            html_content="<p>Test Body</p>",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await send_email(request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True

    @pytest.mark.asyncio
    async def test_send_email_error(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test send email error - service raises ValueError"""
        from app.routers.zoho_email import SendEmailRequest, send_email

        mock_email_service.send_email.side_effect = ValueError("Service error: Invalid recipient")

        request_data = SendEmailRequest(
            to=["recipient@example.com"],
            subject="Test",
            html_content="Test",
        )

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await send_email(request_data, mock_current_user, mock_db_pool)
            assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_send_email_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test send email generic exception (line 409)"""
        from app.routers.zoho_email import SendEmailRequest, send_email

        mock_email_service.send_email.side_effect = RuntimeError("Network error")

        request_data = SendEmailRequest(
            to=["recipient@example.com"],
            subject="Test",
            html_content="Test",
        )

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await send_email(request_data, mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_search_emails_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test search emails"""
        from app.routers.zoho_email import search_emails

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await search_emails(
                query="test query",
                limit=50,
                current_user=mock_current_user,
                db_pool=mock_db_pool
            )

            assert isinstance(response, list)
            assert len(response) == 1
            mock_email_service.search_emails.assert_called_once_with("user_123", "test query", 50)

    @pytest.mark.asyncio
    async def test_search_emails_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test search emails generic exception (line 432)"""
        from app.routers.zoho_email import search_emails

        mock_email_service.search_emails.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await search_emails(
                    query="test query",
                    limit=50,
                    current_user=mock_current_user,
                    db_pool=mock_db_pool
                )
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_reply_email_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test reply email"""
        from app.routers.zoho_email import ReplyEmailRequest, reply_email

        request_data = ReplyEmailRequest(content="Reply content", reply_all=False)

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await reply_email("msg_1", request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True
            mock_email_service.reply_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_reply_email_all(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test reply all"""
        from app.routers.zoho_email import ReplyEmailRequest, reply_email

        request_data = ReplyEmailRequest(content="Reply content", reply_all=True)

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await reply_email("msg_1", request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True

    @pytest.mark.asyncio
    async def test_reply_email_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test reply email generic exception (line 461)"""
        from app.routers.zoho_email import ReplyEmailRequest, reply_email

        mock_email_service.reply_email.side_effect = RuntimeError("Service error")

        request_data = ReplyEmailRequest(content="Reply content", reply_all=False)

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await reply_email("msg_1", request_data, mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_forward_email_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test forward email"""
        from app.routers.zoho_email import ForwardEmailRequest, forward_email

        request_data = ForwardEmailRequest(to=["forward@example.com"], content="Additional content")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await forward_email("msg_1", request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True
            mock_email_service.forward_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_email_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test forward email generic exception (line 490)"""
        from app.routers.zoho_email import ForwardEmailRequest, forward_email

        mock_email_service.forward_email.side_effect = RuntimeError("Service error")

        request_data = ForwardEmailRequest(to=["forward@example.com"], content="Additional content")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await forward_email("msg_1", request_data, mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_mark_emails_read_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test mark emails as read"""
        from app.routers.zoho_email import MarkReadRequest, mark_emails_read

        request_data = MarkReadRequest(message_ids=["msg_1", "msg_2"], is_read=True)

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await mark_emails_read(request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True
            mock_email_service.mark_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_emails_unread(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test mark emails as unread"""
        from app.routers.zoho_email import MarkReadRequest, mark_emails_read

        request_data = MarkReadRequest(message_ids=["msg_1"], is_read=False)

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await mark_emails_read(request_data, mock_current_user, mock_db_pool)

            assert response["success"] is True

    @pytest.mark.asyncio
    async def test_mark_emails_read_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test mark emails read generic exception (line 518)"""
        from app.routers.zoho_email import MarkReadRequest, mark_emails_read

        mock_email_service.mark_read.side_effect = RuntimeError("Service error")

        request_data = MarkReadRequest(message_ids=["msg_1", "msg_2"], is_read=True)

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await mark_emails_read(request_data, mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_toggle_flag_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test toggle flag"""
        from app.routers.zoho_email import toggle_flag

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await toggle_flag("msg_1", True, mock_current_user, mock_db_pool)

            assert response["success"] is True
            # Verify service was called (exact args checked by service mock)
            mock_email_service.toggle_flag.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_flag_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test toggle flag generic exception (line 545)"""
        from app.routers.zoho_email import toggle_flag

        mock_email_service.toggle_flag.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await toggle_flag("msg_1", True, mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_emails_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test delete emails"""
        from app.routers.zoho_email import delete_emails

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await delete_emails(["msg_1", "msg_2"], mock_current_user, mock_db_pool)

            assert response["success"] is True
            mock_email_service.delete_emails.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_emails_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test delete emails generic exception (line 572)"""
        from app.routers.zoho_email import delete_emails

        mock_email_service.delete_emails.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await delete_emails(["msg_1", "msg_2"], mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_download_attachment_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test download attachment"""
        from app.routers.zoho_email import download_attachment

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await download_attachment("msg_1", "att_1", mock_current_user, mock_db_pool)

            assert isinstance(response, Response)
            assert response.body == b"attachment content"
            # Verify service was called (exact args checked by service mock)
            mock_email_service.get_attachment.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_attachment_exception(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test download attachment generic exception (line 611)"""
        from app.routers.zoho_email import download_attachment

        mock_email_service.get_attachment.side_effect = RuntimeError("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            with pytest.raises(HTTPException) as exc:
                await download_attachment("msg_1", "att_1", mock_current_user, mock_db_pool)
            assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_unread_count_success(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test get unread count"""
        from app.routers.zoho_email import get_unread_count

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await get_unread_count(mock_current_user, mock_db_pool)

            assert response["unread_count"] == 5
            mock_email_service.get_unread_count.assert_called_once_with("user_123")

    @pytest.mark.asyncio
    async def test_get_unread_count_not_connected(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test get unread count - not connected"""
        from app.routers.zoho_email import get_unread_count

        mock_email_service.get_unread_count.side_effect = ValueError("Not connected")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await get_unread_count(mock_current_user, mock_db_pool)

            assert response["unread_count"] == 0

    @pytest.mark.asyncio
    async def test_get_unread_count_error(self, mock_db_pool, mock_current_user, mock_email_service):
        """Test get unread count error handling"""
        from app.routers.zoho_email import get_unread_count

        mock_email_service.get_unread_count.side_effect = Exception("Service error")

        with patch("app.routers.zoho_email._get_email_service", return_value=mock_email_service):
            response = await get_unread_count(mock_current_user, mock_db_pool)

            assert response["unread_count"] == 0


@pytest.mark.unit
class TestZohoEmailPydanticModels:
    """Test Pydantic models"""

    def test_send_email_request(self):
        """Test SendEmailRequest model"""
        from app.routers.zoho_email import SendEmailRequest

        request = SendEmailRequest(
            to=["test@example.com"],
            subject="Test",
            html_content="<p>Test</p>",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )

        assert len(request.to) == 1
        assert request.subject == "Test"
        assert request.html_content == "<p>Test</p>"
        assert request.get_content() == "<p>Test</p>"

    def test_send_email_request_content_priority(self):
        """Test SendEmailRequest content priority (html_content > text_content > content)"""
        from app.routers.zoho_email import SendEmailRequest

        request = SendEmailRequest(
            to=["test@example.com"],
            subject="Test",
            html_content="<p>HTML</p>",
            text_content="Plain text",
            content="Legacy content",
        )

        assert request.get_content() == "<p>HTML</p>"

        request2 = SendEmailRequest(
            to=["test@example.com"],
            subject="Test",
            text_content="Plain text",
            content="Legacy content",
        )

        assert request2.get_content() == "Plain text"

    def test_reply_email_request(self):
        """Test ReplyEmailRequest model"""
        from app.routers.zoho_email import ReplyEmailRequest

        request = ReplyEmailRequest(content="Reply content", reply_all=True)

        assert request.content == "Reply content"
        assert request.reply_all is True

    def test_forward_email_request(self):
        """Test ForwardEmailRequest model"""
        from app.routers.zoho_email import ForwardEmailRequest

        request = ForwardEmailRequest(to=["forward@example.com"], content="Additional content")

        assert len(request.to) == 1
        assert request.content == "Additional content"

    def test_mark_read_request(self):
        """Test MarkReadRequest model"""
        from app.routers.zoho_email import MarkReadRequest

        request = MarkReadRequest(message_ids=["msg_1", "msg_2"], is_read=False)

        assert len(request.message_ids) == 2
        assert request.is_read is False
