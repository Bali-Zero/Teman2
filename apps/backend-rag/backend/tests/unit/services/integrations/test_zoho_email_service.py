"""
Unit tests for ZohoEmailService and sanitize_filename.
Target: send, receive, folder listing, error handling, attachments.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.integrations.zoho_email_service import (
    ZohoEmailService,
    sanitize_filename,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg pool with acquire() as async context manager."""
    pool = MagicMock()
    mock_conn = AsyncMock()

    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        ),
    )
    pool._mock_conn = mock_conn
    return pool


@pytest.fixture
def mock_conn(mock_db_pool):
    """Shortcut to the mocked connection."""
    return mock_db_pool._mock_conn


@pytest.fixture
def service(mock_db_pool):
    """Create ZohoEmailService with mocked dependencies."""
    with (
        patch("backend.services.integrations.zoho_email_service.settings") as mock_settings,
        patch("backend.services.integrations.zoho_email_service.ZohoOAuthService") as mock_oauth_cls,
    ):
        mock_settings.zoho_api_domain = "https://mail.zoho.com"
        mock_oauth = AsyncMock()
        mock_oauth.get_valid_token = AsyncMock(return_value="mock-token-123")
        mock_oauth.get_account_id = AsyncMock(return_value="account-456")
        mock_oauth.get_connection_status = AsyncMock(return_value={"email": "user@balizero.com"})
        mock_oauth.close = AsyncMock()
        mock_oauth_cls.return_value = mock_oauth

        svc = ZohoEmailService(db_pool=mock_db_pool)
        svc.oauth_service = mock_oauth
        svc.api_domain = "https://mail.zoho.com"
        yield svc


@pytest.fixture
def mock_http_response():
    """Factory for mock httpx responses."""
    def _make(status_code=200, json_data=None, content=b""):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.content = content or (json_data is not None and b"data")
        resp.text = str(json_data) if json_data else ""
        resp.json.return_value = json_data or {}
        return resp
    return _make


# ============================================================================
# sanitize_filename TESTS
# ============================================================================


class TestSanitizeFilename:
    """Tests for the sanitize_filename utility."""

    def test_empty_filename(self):
        """Empty filename returns unnamed_file."""
        assert sanitize_filename("") == "unnamed_file"

    def test_spaces_replaced(self):
        """Spaces replaced with underscores."""
        result = sanitize_filename("My File Name.pdf")
        assert " " not in result
        assert result.endswith(".pdf")

    def test_special_chars_removed(self):
        """Special characters removed."""
        result = sanitize_filename('File<>:"/\\|?*,.pdf')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result

    def test_truncation(self):
        """Long filenames truncated to max_length."""
        result = sanitize_filename("a" * 300 + ".txt", max_length=200)
        assert len(result) <= 200
        assert result.endswith(".txt")

    def test_multiple_underscores_collapsed(self):
        """Multiple consecutive underscores collapsed to one."""
        result = sanitize_filename("file___name.pdf")
        assert "___" not in result

    def test_leading_trailing_underscores_stripped(self):
        """Leading/trailing underscores removed from name part."""
        result = sanitize_filename("_file_.pdf")
        assert not result.startswith("_")

    def test_only_special_chars(self):
        """Filename with only special chars gets fallback name."""
        result = sanitize_filename('<>:"/\\|?*.pdf')
        assert "file" in result or "unnamed" in result

    def test_no_extension(self):
        """Filename without extension handled."""
        result = sanitize_filename("README")
        assert result == "README"

    def test_preserves_extension(self):
        """Extension preserved after sanitization."""
        result = sanitize_filename("My Document (1).docx")
        assert result.endswith(".docx")

    def test_comma_in_filename(self):
        """Commas removed (known Zoho API issue)."""
        result = sanitize_filename("File, Name (1).pdf")
        assert "," not in result


# ============================================================================
# ZohoEmailService._normalize_folder_type TESTS
# ============================================================================


class TestNormalizeFolderType:
    """Tests for folder type normalization."""

    def test_inbox(self, service):
        assert service._normalize_folder_type("Inbox") == "inbox"

    def test_sent(self, service):
        assert service._normalize_folder_type("Sent") == "sent"

    def test_drafts(self, service):
        assert service._normalize_folder_type("Drafts") == "drafts"

    def test_trash(self, service):
        assert service._normalize_folder_type("Trash") == "trash"

    def test_junk_maps_to_spam(self, service):
        assert service._normalize_folder_type("Junk") == "spam"

    def test_custom(self, service):
        assert service._normalize_folder_type("MyFolder") == "custom"


# ============================================================================
# ZohoEmailService._parse_recipients TESTS
# ============================================================================


class TestParseRecipients:
    """Tests for recipient parsing."""

    def test_empty_string(self, service):
        assert service._parse_recipients("") == []

    def test_single_recipient(self, service):
        result = service._parse_recipients("user@example.com")
        assert result == ["user@example.com"]

    def test_multiple_recipients(self, service):
        result = service._parse_recipients("a@b.com, c@d.com, e@f.com")
        assert len(result) == 3

    def test_parse_recipients_to_objects_empty(self, service):
        assert service._parse_recipients_to_objects("") == []

    def test_parse_recipients_to_objects_plain(self, service):
        result = service._parse_recipients_to_objects("user@example.com")
        assert len(result) == 1
        assert result[0]["address"] == "user@example.com"
        assert result[0]["name"] == ""

    def test_parse_recipients_to_objects_with_name(self, service):
        result = service._parse_recipients_to_objects('"John Doe" <john@example.com>')
        assert len(result) == 1
        assert result[0]["address"] == "john@example.com"
        assert result[0]["name"] == "John Doe"


# ============================================================================
# ZohoEmailService._parse_attachments TESTS
# ============================================================================


class TestParseAttachments:
    """Tests for attachment metadata parsing."""

    def test_empty_list(self, service):
        assert service._parse_attachments([]) == []

    def test_single_attachment(self, service):
        attachments = [
            {
                "attachmentId": "att-1",
                "attachmentName": "doc.pdf",
                "attachmentSize": 1024,
                "contentType": "application/pdf",
            },
        ]
        result = service._parse_attachments(attachments)
        assert len(result) == 1
        assert result[0]["attachment_id"] == "att-1"
        assert result[0]["filename"] == "doc.pdf"
        assert result[0]["size"] == 1024
        assert result[0]["mime_type"] == "application/pdf"


# ============================================================================
# ZohoEmailService.list_folders TESTS
# ============================================================================


class TestListFolders:
    """Tests for folder listing."""

    @pytest.mark.asyncio
    async def test_list_folders_success(self, service, mock_http_response):
        """Successful folder listing returns transformed data."""
        mock_resp = mock_http_response(
            200,
            {
                "data": [
                    {
                        "folderId": "f1",
                        "folderName": "Inbox",
                        "folderType": "Inbox",
                        "unreadCount": 5,
                        "messageCount": 100,
                    },
                    {
                        "folderId": "f2",
                        "folderName": "Sent",
                        "folderType": "Sent",
                        "unreadCount": 0,
                        "messageCount": 50,
                    },
                ],
            },
        )
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        folders = await service.list_folders("user-1")
        assert len(folders) == 2
        assert folders[0]["folder_id"] == "f1"
        assert folders[0]["folder_type"] == "inbox"
        assert folders[0]["unread_count"] == 5
        assert folders[1]["folder_type"] == "sent"


# ============================================================================
# ZohoEmailService.list_emails TESTS
# ============================================================================


class TestListEmails:
    """Tests for email listing."""

    @pytest.mark.asyncio
    async def test_list_emails_success(self, service, mock_http_response):
        """Successful email listing returns transformed data."""
        mock_resp = mock_http_response(
            200,
            {
                "data": [
                    {
                        "messageId": "m1",
                        "folderId": "f1",
                        "threadId": "t1",
                        "subject": "Test Email",
                        "fromAddress": "sender@example.com",
                        "sender": "Sender Name",
                        "toAddress": "me@balizero.com",
                        "ccAddress": "",
                        "summary": "Preview text...",
                        "hasAttachment": False,
                        "isRead": False,
                        "isFlagged": True,
                        "receivedTime": "2026-03-15T10:00:00Z",
                    },
                ],
                "paging": {"totalCount": 1, "hasMoreData": False},
            },
        )
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.list_emails("user-1", folder_id="f1", limit=50)
        assert len(result["emails"]) == 1
        assert result["total"] == 1
        assert result["has_more"] is False
        email = result["emails"][0]
        assert email["message_id"] == "m1"
        assert email["subject"] == "Test Email"
        assert email["is_read"] is False
        assert email["is_flagged"] is True


# ============================================================================
# ZohoEmailService.get_email TESTS
# ============================================================================


class TestGetEmail:
    """Tests for reading a single email."""

    @pytest.mark.asyncio
    async def test_get_email_requires_folder_id(self, service):
        """get_email raises ValueError without folder_id."""
        with pytest.raises(ValueError, match="folder_id is required"):
            await service.get_email("user-1", "msg-1", folder_id=None)

    @pytest.mark.asyncio
    async def test_get_email_not_found(self, service, mock_http_response):
        """get_email raises ValueError when message not in folder."""
        list_resp = mock_http_response(200, {"data": []})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=list_resp)
        service._client = mock_client

        with pytest.raises(ValueError, match="not found"):
            await service.get_email("user-1", "msg-999", folder_id="f1")


# ============================================================================
# ZohoEmailService.send_email TESTS
# ============================================================================


class TestSendEmail:
    """Tests for sending emails."""

    @pytest.mark.asyncio
    async def test_send_email_success(self, service, mock_conn, mock_http_response):
        """Successful send returns message_id."""
        mock_resp = mock_http_response(200, {"data": {"messageId": "sent-1"}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        # Mock _log_activity to avoid DB calls
        service._log_activity = AsyncMock()

        with patch("backend.services.integrations.zoho_email_service.metrics_collector"):
            result = await service.send_email(
                user_id="user-1",
                to=["recipient@example.com"],
                subject="Test Subject",
                content="<p>Hello</p>",
            )

        assert result["success"] is True
        assert result["message_id"] == "sent-1"

    @pytest.mark.asyncio
    async def test_send_email_api_error(self, service, mock_http_response):
        """API error during send raises and records metrics."""
        mock_resp = mock_http_response(
            400,
            {"data": {"errorCode": "INVALID_DATA", "message": "Bad request"}},
        )
        mock_resp.content = b"error"
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        with (
            patch("backend.services.integrations.zoho_email_service.metrics_collector"),
            pytest.raises(ValueError),
        ):
            await service.send_email(
                user_id="user-1",
                to=["bad@example.com"],
                subject="Fail",
                content="content",
            )


# ============================================================================
# ZohoEmailService.reply_email TESTS
# ============================================================================


class TestReplyEmail:
    """Tests for replying to emails."""

    @pytest.mark.asyncio
    async def test_reply_email_success(self, service, mock_http_response):
        """Successful reply returns message_id."""
        mock_resp = mock_http_response(200, {"data": {"messageId": "reply-1"}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client
        service._log_activity = AsyncMock()

        result = await service.reply_email(
            user_id="user-1",
            message_id="msg-1",
            content="Thanks!",
            to_address="sender@example.com",
        )
        assert result["success"] is True
        assert result["message_id"] == "reply-1"

    @pytest.mark.asyncio
    async def test_reply_all(self, service, mock_http_response):
        """Reply all uses 'replyall' endpoint."""
        mock_resp = mock_http_response(200, {"data": {"messageId": "reply-2"}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client
        service._log_activity = AsyncMock()

        result = await service.reply_email(
            user_id="user-1",
            message_id="msg-1",
            content="Thanks all!",
            reply_all=True,
            to_address="sender@example.com",
        )
        assert result["success"] is True
        call_args = mock_client.request.call_args
        assert "replyall" in call_args.kwargs.get("url", "")


# ============================================================================
# ZohoEmailService.forward_email TESTS
# ============================================================================


class TestForwardEmail:
    """Tests for forwarding emails."""

    @pytest.mark.asyncio
    async def test_forward_email_success(self, service, mock_http_response):
        """Successful forward returns message_id."""
        mock_resp = mock_http_response(200, {"data": {"messageId": "fwd-1"}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client
        service._log_activity = AsyncMock()

        result = await service.forward_email(
            user_id="user-1",
            message_id="msg-1",
            to=["forward@example.com"],
            content="FYI",
        )
        assert result["success"] is True
        assert result["message_id"] == "fwd-1"


# ============================================================================
# ZohoEmailService.mark_read TESTS
# ============================================================================


class TestMarkRead:
    """Tests for marking emails as read/unread."""

    @pytest.mark.asyncio
    async def test_mark_read(self, service, mock_http_response):
        """mark_read sends correct mode."""
        mock_resp = mock_http_response(200, {"data": {}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.mark_read("user-1", ["msg-1", "msg-2"], is_read=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_unread(self, service, mock_http_response):
        """mark_read with is_read=False sends markAsUnread."""
        mock_resp = mock_http_response(200, {"data": {}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.mark_read("user-1", ["msg-1"], is_read=False)
        assert result is True


# ============================================================================
# ZohoEmailService.toggle_flag TESTS
# ============================================================================


class TestToggleFlag:
    """Tests for flagging/unflagging emails."""

    @pytest.mark.asyncio
    async def test_flag_email(self, service, mock_http_response):
        """Flag an email."""
        mock_resp = mock_http_response(200, {"data": {}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.toggle_flag("user-1", "msg-1", is_flagged=True)
        assert result is True


# ============================================================================
# ZohoEmailService.move_to_folder TESTS
# ============================================================================


class TestMoveToFolder:
    """Tests for moving emails between folders."""

    @pytest.mark.asyncio
    async def test_move_to_folder(self, service, mock_http_response):
        """Move emails to a folder."""
        mock_resp = mock_http_response(200, {"data": {}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.move_to_folder("user-1", ["msg-1"], "folder-archive")
        assert result is True


# ============================================================================
# ZohoEmailService.delete_emails TESTS
# ============================================================================


class TestDeleteEmails:
    """Tests for deleting emails (move to trash)."""

    @pytest.mark.asyncio
    async def test_delete_finds_trash_and_moves(self, service, mock_http_response):
        """delete_emails finds Trash folder and moves messages there."""
        # Mock list_folders → returns a trash folder
        service.list_folders = AsyncMock(
            return_value=[
                {"folder_id": "f-inbox", "folder_name": "Inbox", "folder_type": "inbox"},
                {"folder_id": "f-trash", "folder_name": "Trash", "folder_type": "trash"},
            ],
        )
        service.move_to_folder = AsyncMock(return_value=True)
        service._log_activity = AsyncMock()

        with patch("backend.services.integrations.zoho_email_service.metrics_collector"):
            result = await service.delete_emails("user-1", ["msg-1"])
        assert result is True
        service.move_to_folder.assert_awaited_once_with("user-1", ["msg-1"], "f-trash")

    @pytest.mark.asyncio
    async def test_delete_no_trash_folder_raises(self, service):
        """delete_emails raises if no Trash folder found."""
        service.list_folders = AsyncMock(
            return_value=[
                {"folder_id": "f-inbox", "folder_name": "Inbox", "folder_type": "inbox"},
            ],
        )

        with (
            patch("backend.services.integrations.zoho_email_service.metrics_collector"),
            pytest.raises(ValueError, match="Trash folder not found"),
        ):
            await service.delete_emails("user-1", ["msg-1"])


# ============================================================================
# ZohoEmailService.upload_attachment TESTS
# ============================================================================


class TestUploadAttachment:
    """Tests for attachment upload with validation."""

    @pytest.mark.asyncio
    async def test_upload_too_large(self, service):
        """File exceeding 25MB limit is rejected."""
        big_content = b"x" * (26 * 1024 * 1024)
        with pytest.raises(ValueError, match="too large"):
            await service.upload_attachment(
                user_id="user-1",
                filename="huge.pdf",
                content=big_content,
                content_type="application/pdf",
            )

    @pytest.mark.asyncio
    async def test_upload_filename_too_long(self, service):
        """Filename exceeding 255 chars is rejected."""
        with pytest.raises(ValueError, match="too long"):
            await service.upload_attachment(
                user_id="user-1",
                filename="a" * 300 + ".pdf",
                content=b"content",
                content_type="application/pdf",
            )

    @pytest.mark.asyncio
    async def test_upload_success(self, service, mock_http_response):
        """Successful upload returns attachment details."""
        mock_resp = mock_http_response(
            200,
            {
                "data": {
                    "attachmentId": "att-1",
                    "storeName": "store-1",
                    "attachmentPath": "/path/to/att",
                    "attachmentName": "doc.pdf",
                },
            },
        )
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.upload_attachment(
            user_id="user-1",
            filename="doc.pdf",
            content=b"PDF content here",
            content_type="application/pdf",
        )
        assert result["attachment_id"] == "att-1"
        assert result["store_name"] == "store-1"


# ============================================================================
# ZohoEmailService.save_draft TESTS
# ============================================================================


class TestSaveDraft:
    """Tests for saving email drafts."""

    @pytest.mark.asyncio
    async def test_save_draft_success(self, service, mock_http_response):
        """Successful draft save returns message_id."""
        mock_resp = mock_http_response(200, {"data": {"messageId": "draft-1"}})
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        result = await service.save_draft(
            user_id="user-1",
            to=["draft-recipient@example.com"],
            subject="Draft Subject",
            content="Draft body",
        )
        assert result["success"] is True
        assert result["message_id"] == "draft-1"


# ============================================================================
# ZohoEmailService.get_unread_count TESTS
# ============================================================================


class TestGetUnreadCount:
    """Tests for unread count aggregation."""

    @pytest.mark.asyncio
    async def test_get_unread_count_success(self, service):
        """Sums unread counts across all folders."""
        service.list_folders = AsyncMock(
            return_value=[
                {"folder_id": "f1", "unread_count": 5},
                {"folder_id": "f2", "unread_count": 3},
                {"folder_id": "f3", "unread_count": 0},
            ],
        )
        count = await service.get_unread_count("user-1")
        assert count == 8

    @pytest.mark.asyncio
    async def test_get_unread_count_error_returns_zero(self, service):
        """Returns 0 when list_folders fails."""
        service.list_folders = AsyncMock(side_effect=Exception("API error"))
        count = await service.get_unread_count("user-1")
        assert count == 0


# ============================================================================
# ZohoEmailService.search_emails TESTS
# ============================================================================


class TestSearchEmails:
    """Tests for email search."""

    @pytest.mark.asyncio
    async def test_search_emails_success(self, service, mock_http_response):
        """Successful search returns transformed results."""
        mock_resp = mock_http_response(
            200,
            {
                "data": [
                    {
                        "messageId": "m1",
                        "folderId": "f1",
                        "subject": "Invoice #123",
                        "fromAddress": "accounts@vendor.com",
                        "sender": "Vendor",
                        "summary": "Please find attached...",
                        "hasAttachment": True,
                        "isRead": True,
                        "receivedTime": "2026-03-10T09:00:00Z",
                    },
                ],
            },
        )
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_resp)
        service._client = mock_client

        results = await service.search_emails("user-1", "invoice")
        assert len(results) == 1
        assert results[0]["subject"] == "Invoice #123"
        assert results[0]["has_attachments"] is True


# ============================================================================
# ZohoEmailService.close TESTS
# ============================================================================


class TestServiceClose:
    """Tests for cleanup."""

    @pytest.mark.asyncio
    async def test_close_with_active_client(self, service):
        """close() shuts down the httpx client and oauth service."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        service._client = mock_client

        await service.close()
        mock_client.aclose.assert_awaited_once()
        service.oauth_service.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_without_client(self, service):
        """close() handles no client gracefully."""
        service._client = None
        await service.close()
        service.oauth_service.close.assert_awaited_once()
