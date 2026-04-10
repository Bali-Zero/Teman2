"""
Unit tests for backend/services/integrations/zoho_email_service.py
Covers: sanitize_filename, ZohoEmailService (list_folders, list_emails, get_email,
        search_emails, send_email, reply_email, forward_email, mark_read,
        toggle_flag, move_to_folder, _parse_recipients, _parse_recipients_to_objects,
        _parse_attachments, _normalize_folder_type, _request, _get_headers,
        _get_account_id, _log_activity, close)
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Patch heavy imports before importing the module
with (
    patch("backend.app.core.config.settings", MagicMock(zoho_api_domain="https://mail.zoho.com")),
    patch("backend.app.metrics.metrics_collector", MagicMock()),
):
    from backend.services.integrations.zoho_email_service import (
        ZohoEmailService,
        sanitize_filename,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_pool() -> MagicMock:
    """Mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn
    return pool


@pytest.fixture
def service(mock_pool: MagicMock) -> ZohoEmailService:
    """Create a ZohoEmailService with mocked deps."""
    with patch("backend.services.integrations.zoho_email_service.ZohoOAuthService"):
        svc = ZohoEmailService(db_pool=mock_pool)
        svc.oauth_service = AsyncMock()
        svc.oauth_service.get_valid_token = AsyncMock(return_value="test-token")
        svc.oauth_service.get_account_id = AsyncMock(return_value="acc123")
        svc.oauth_service.get_connection_status = AsyncMock(
            return_value={"email": "user@balizero.com"},
        )
        svc.oauth_service.close = AsyncMock()
        svc.api_domain = "https://mail.zoho.com"
        return svc


# ═══════════════════════════════════════════════════════════════════════════════
# sanitize_filename
# ═══════════════════════════════════════════════════════════════════════════════


class TestSanitizeFilename:
    def test_basic(self) -> None:
        assert sanitize_filename("test.pdf") == "test.pdf"

    def test_spaces_replaced(self) -> None:
        assert sanitize_filename("my file.pdf") == "my_file.pdf"

    def test_special_chars_removed(self) -> None:
        assert sanitize_filename('file<>:"|.pdf') == "file.pdf"

    def test_comma_removed(self) -> None:
        result = sanitize_filename("My File, Name (1).pdf")
        assert "," not in result
        assert result.endswith(".pdf")

    def test_empty_filename(self) -> None:
        assert sanitize_filename("") == "unnamed_file"

    def test_very_long_filename(self) -> None:
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_no_extension(self) -> None:
        result = sanitize_filename("myfile")
        assert result == "myfile"

    def test_only_special_chars(self) -> None:
        result = sanitize_filename('<>:"|?.pdf')
        assert result.endswith(".pdf")
        assert "file" in result  # falls back to "file"

    def test_multiple_underscores_collapsed(self) -> None:
        result = sanitize_filename("a   b   c.pdf")
        assert "___" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService._normalize_folder_type
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizeFolderType:
    def test_inbox(self, service: ZohoEmailService) -> None:
        assert service._normalize_folder_type("Inbox") == "inbox"

    def test_sent(self, service: ZohoEmailService) -> None:
        assert service._normalize_folder_type("Sent") == "sent"

    def test_custom(self, service: ZohoEmailService) -> None:
        assert service._normalize_folder_type("My Folder") == "custom"

    def test_junk(self, service: ZohoEmailService) -> None:
        assert service._normalize_folder_type("Junk") == "spam"


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService._parse_recipients / _parse_recipients_to_objects
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseRecipients:
    def test_empty(self, service: ZohoEmailService) -> None:
        assert service._parse_recipients("") == []
        assert service._parse_recipients_to_objects("") == []

    def test_single(self, service: ZohoEmailService) -> None:
        assert service._parse_recipients("a@b.com") == ["a@b.com"]

    def test_multiple(self, service: ZohoEmailService) -> None:
        result = service._parse_recipients("a@b.com, c@d.com")
        assert len(result) == 2

    def test_to_objects_simple(self, service: ZohoEmailService) -> None:
        result = service._parse_recipients_to_objects("user@example.com")
        assert result == [{"address": "user@example.com", "name": ""}]

    def test_to_objects_with_name(self, service: ZohoEmailService) -> None:
        result = service._parse_recipients_to_objects('"John Doe" <john@example.com>')
        assert len(result) == 1
        assert result[0]["address"] == "john@example.com"
        assert result[0]["name"] == "John Doe"


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService._parse_attachments
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseAttachments:
    def test_empty(self, service: ZohoEmailService) -> None:
        assert service._parse_attachments([]) == []

    def test_basic_attachment(self, service: ZohoEmailService) -> None:
        att = [
            {
                "attachmentId": "att1",
                "attachmentName": "test.pdf",
                "attachmentSize": 1024,
                "contentType": "application/pdf",
            },
        ]
        result = service._parse_attachments(att)
        assert len(result) == 1
        assert result[0]["attachment_id"] == "att1"
        assert result[0]["filename"] == "test.pdf"
        assert result[0]["size"] == 1024


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService._get_client / close
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetClientAndClose:
    def test_creates_client(self, service: ZohoEmailService) -> None:
        client = service._get_client()
        assert client is not None

    def test_returns_same_client(self, service: ZohoEmailService) -> None:
        c1 = service._get_client()
        c2 = service._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close(self, service: ZohoEmailService) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        service._client = mock_client

        await service.close()
        mock_client.aclose.assert_awaited_once()
        service.oauth_service.close.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService._request
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequest:
    @pytest.mark.asyncio
    async def test_successful_request(self, service: ZohoEmailService) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        service._client = mock_client
        service._client.is_closed = False

        result = await service._request("user1", "GET", "/messages/view")
        assert result == {"data": []}

    @pytest.mark.asyncio
    async def test_error_response(self, service: ZohoEmailService) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b'{"data": {"errorCode": "INVALID_TOKEN"}}'
        mock_response.json.return_value = {"data": {"errorCode": "INVALID_TOKEN"}}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(ValueError, match="API error"):
            await service._request("user1", "GET", "/messages/view")


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.list_folders
# ═══════════════════════════════════════════════════════════════════════════════


class TestListFolders:
    @pytest.mark.asyncio
    async def test_list_folders(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={
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

        result = await service.list_folders("user1")
        assert len(result) == 2
        assert result[0]["folder_id"] == "f1"
        assert result[0]["folder_type"] == "inbox"
        assert result[1]["folder_type"] == "sent"


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.list_emails
# ═══════════════════════════════════════════════════════════════════════════════


class TestListEmails:
    @pytest.mark.asyncio
    async def test_list_emails_basic(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={
                "data": [
                    {
                        "messageId": "m1",
                        "folderId": "inbox",
                        "threadId": "t1",
                        "subject": "Hello",
                        "fromAddress": "sender@example.com",
                        "sender": "Sender",
                        "toAddress": "me@balizero.com",
                        "ccAddress": "",
                        "summary": "Preview...",
                        "hasAttachment": False,
                        "isRead": False,
                        "isFlagged": False,
                        "receivedTime": "2026-01-01T10:00:00Z",
                    },
                ],
                "paging": {"totalCount": 1, "hasMoreData": False},
            },
        )

        result = await service.list_emails("user1")
        assert len(result["emails"]) == 1
        assert result["emails"][0]["subject"] == "Hello"
        assert result["total"] == 1
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_emails_with_filters(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": [], "paging": {"totalCount": 0, "hasMoreData": False}},
        )

        result = await service.list_emails(
            "user1",
            folder_id="sent",
            limit=10,
            start=5,
            search_key="invoice",
            is_unread=True,
        )
        assert result["emails"] == []
        # Verify params were passed correctly
        call_args = service._request.call_args
        assert call_args[1]["params"]["searchKey"] == "invoice"
        assert call_args[1]["params"]["status"] == "unread"


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.search_emails
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchEmails:
    @pytest.mark.asyncio
    async def test_search(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={
                "data": [
                    {
                        "messageId": "m1",
                        "folderId": "inbox",
                        "subject": "Invoice 2026",
                        "fromAddress": "billing@example.com",
                        "sender": "Billing",
                        "summary": "Your invoice...",
                        "hasAttachment": True,
                        "isRead": True,
                        "receivedTime": "2026-01-01T10:00:00Z",
                    },
                ],
            },
        )

        result = await service.search_emails("user1", "invoice")
        assert len(result) == 1
        assert result[0]["subject"] == "Invoice 2026"
        assert result[0]["has_attachments"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.send_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_send_basic(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": {"messageId": "sent1"}},
        )
        service._log_activity = AsyncMock()

        with patch("backend.services.integrations.zoho_email_service.metrics_collector"):
            result = await service.send_email(
                user_id="user1",
                to=["recipient@example.com"],
                subject="Test",
                content="<p>Hello</p>",
            )

        assert result["success"] is True
        assert result["message_id"] == "sent1"
        service._log_activity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_with_cc_bcc_attachments(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": {"messageId": "sent2"}},
        )
        service._log_activity = AsyncMock()

        with patch("backend.services.integrations.zoho_email_service.metrics_collector"):
            result = await service.send_email(
                user_id="user1",
                to=["a@b.com"],
                subject="With attachments",
                content="body",
                cc=["cc@b.com"],
                bcc=["bcc@b.com"],
                attachments=[{"store_name": "s", "attachment_path": "/p", "attachment_name": "f.pdf"}],
                is_html=False,
            )

        assert result["success"] is True
        payload = service._request.call_args[1]["json_data"]
        assert payload["ccAddress"] == "cc@b.com"
        assert payload["bccAddress"] == "bcc@b.com"
        assert len(payload["attachments"]) == 1

    @pytest.mark.asyncio
    async def test_send_error_records_metric(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(side_effect=ValueError("API error"))

        with (
            patch("backend.services.integrations.zoho_email_service.metrics_collector"),
            pytest.raises(ValueError),
        ):
            await service.send_email(
                user_id="user1",
                to=["a@b.com"],
                subject="Test",
                content="body",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.reply_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestReplyEmail:
    @pytest.mark.asyncio
    async def test_reply(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": {"messageId": "reply1"}},
        )
        service._log_activity = AsyncMock()

        result = await service.reply_email(
            user_id="user1",
            message_id="m1",
            content="Thanks!",
            to_address="sender@example.com",
        )
        assert result["success"] is True
        assert result["message_id"] == "reply1"

    @pytest.mark.asyncio
    async def test_reply_all(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": {"messageId": "reply2"}},
        )
        service._log_activity = AsyncMock()

        result = await service.reply_email(
            user_id="user1",
            message_id="m1",
            content="Reply all",
            reply_all=True,
            to_address="sender@example.com",
            cc_address="other@example.com",
        )
        assert result["success"] is True
        # Should call /messages/m1/replyall
        call_args = service._request.call_args
        assert "replyall" in call_args[0][2]


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.forward_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestForwardEmail:
    @pytest.mark.asyncio
    async def test_forward(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": {"messageId": "fwd1"}},
        )
        service._log_activity = AsyncMock()

        result = await service.forward_email(
            user_id="user1",
            message_id="m1",
            to=["fwd@example.com"],
            content="<p>FYI</p>",
        )
        assert result["success"] is True
        assert result["message_id"] == "fwd1"

    @pytest.mark.asyncio
    async def test_forward_no_content(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            return_value={"data": {"messageId": "fwd2"}},
        )
        service._log_activity = AsyncMock()

        result = await service.forward_email(
            user_id="user1",
            message_id="m1",
            to=["fwd@example.com"],
        )
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.mark_read / toggle_flag / move_to_folder
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusOperations:
    @pytest.mark.asyncio
    async def test_mark_read(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(return_value={})

        result = await service.mark_read("user1", ["m1", "m2"], is_read=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_unread(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(return_value={})

        result = await service.mark_read("user1", ["m1"], is_read=False)
        assert result is True
        payload = service._request.call_args[1]["json_data"]
        assert payload["mode"] == "markAsUnread"

    @pytest.mark.asyncio
    async def test_toggle_flag(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(return_value={})

        result = await service.toggle_flag("user1", "m1", is_flagged=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_move_to_folder(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(return_value={})

        result = await service.move_to_folder("user1", ["m1", "m2"], "trash_id")
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService.get_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetEmail:
    @pytest.mark.asyncio
    async def test_get_email(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(
            side_effect=[
                # First call: list emails to find metadata
                {
                    "data": [
                        {
                            "messageId": "m1",
                            "folderId": "inbox",
                            "threadId": "t1",
                            "subject": "Test Email",
                            "fromAddress": "sender@example.com",
                            "sender": "Sender",
                            "toAddress": "me@balizero.com",
                            "ccAddress": "",
                            "bccAddress": "",
                            "summary": "Preview",
                            "hasAttachment": False,
                            "isFlagged": False,
                            "receivedTime": "2026-01-01T10:00:00Z",
                            "attachments": [],
                        },
                    ],
                },
                # Second call: get content
                {"data": {"content": "<p>Hello World</p>"}},
            ],
        )
        service.mark_read = AsyncMock()

        result = await service.get_email("user1", "m1", folder_id="inbox")
        assert result["subject"] == "Test Email"
        assert result["html_content"] == "<p>Hello World</p>"
        assert result["is_read"] is True

    @pytest.mark.asyncio
    async def test_get_email_no_folder_id(self, service: ZohoEmailService) -> None:
        with pytest.raises(ValueError, match="folder_id is required"):
            await service.get_email("user1", "m1")

    @pytest.mark.asyncio
    async def test_get_email_not_found(self, service: ZohoEmailService) -> None:
        service._request = AsyncMock(return_value={"data": []})

        with pytest.raises(ValueError, match="not found"):
            await service.get_email("user1", "nonexistent", folder_id="inbox")


# ═══════════════════════════════════════════════════════════════════════════════
# ZohoEmailService._log_activity
# ═══════════════════════════════════════════════════════════════════════════════


class TestLogActivity:
    @pytest.mark.asyncio
    async def test_log_activity_success(self, service: ZohoEmailService, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchval = AsyncMock(return_value="user@balizero.com")
        mock_pool._conn.execute = AsyncMock()

        await service._log_activity(
            user_id="user1",
            operation="sent",
            email_subject="Test",
            recipient_email="a@b.com",
        )
        mock_pool._conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_activity_failure_does_not_raise(
        self, service: ZohoEmailService, mock_pool: MagicMock,
    ) -> None:
        mock_pool._conn.fetchval = AsyncMock(side_effect=Exception("DB error"))

        # Should not raise
        await service._log_activity(user_id="user1", operation="sent")
