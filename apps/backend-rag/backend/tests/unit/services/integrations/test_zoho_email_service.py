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
    service.get_connection_status = AsyncMock(
        return_value={
            "connected": True,
            "email": "test@example.com",
            "account_id": "test_account_id",
        }
    )
    return service


@pytest.fixture
def zoho_email_service(mock_db_pool, mock_oauth_service):
    """Create ZohoEmailService instance"""
    with (
        patch(
            "services.integrations.zoho_email_service.ZohoOAuthService",
            return_value=mock_oauth_service,
        ),
        patch("services.integrations.zoho_email_service.settings") as mock_settings,
    ):
        mock_settings.zoho_api_domain = "https://mail.zoho.com"
        service = ZohoEmailService(db_pool=mock_db_pool)
        service.oauth_service = mock_oauth_service
        return service


class TestZohoEmailServiceInit:
    """Tests for initialization"""

    def test_init(self, zoho_email_service):
        """Test initialization"""
        assert zoho_email_service.db_pool is not None
        assert zoho_email_service.oauth_service is not None


class TestInternalMethods:
    """Tests for internal helper methods"""

    @pytest.mark.asyncio
    async def test_get_headers(self, zoho_email_service, mock_oauth_service):
        """Test getting authenticated headers"""
        headers = await zoho_email_service._get_headers("user1")
        assert "Authorization" in headers
        assert headers["Authorization"] == "Zoho-oauthtoken test_token"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_account_id(self, zoho_email_service, mock_oauth_service):
        """Test getting account ID"""
        account_id = await zoho_email_service._get_account_id("user1")
        assert account_id == "test_account_id"

    @pytest.mark.asyncio
    async def test_request_success(self, zoho_email_service, mock_oauth_service):
        """Test making successful authenticated request"""
        with patch("httpx.AsyncClient") as mock_client_class:
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

    @pytest.mark.asyncio
    async def test_request_error(self, zoho_email_service, mock_oauth_service):
        """Test request error handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.content = b'{"data": {"errorCode": "INVALID_TOKEN"}}'
            mock_response.json.return_value = {"data": {"errorCode": "INVALID_TOKEN"}}
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="API error"):
                await zoho_email_service._request("user1", "GET", "/messages")


class TestFolderOperations:
    """Tests for folder operations"""

    @pytest.mark.asyncio
    async def test_list_folders(self, zoho_email_service):
        """Test listing folders"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {
                        "folderId": "1",
                        "folderName": "Inbox",
                        "folderType": "Inbox",
                        "unreadCount": 5,
                        "messageCount": 100,
                    },
                    {
                        "folderId": "2",
                        "folderName": "Sent",
                        "folderType": "Sent",
                        "unreadCount": 0,
                        "messageCount": 50,
                    },
                ]
            }

            folders = await zoho_email_service.list_folders("user1")

            assert len(folders) == 2
            assert folders[0]["folder_id"] == "1"
            assert folders[0]["folder_name"] == "Inbox"
            assert folders[0]["folder_type"] == "inbox"
            assert folders[0]["unread_count"] == 5

    def test_normalize_folder_type(self, zoho_email_service):
        """Test folder type normalization"""
        assert zoho_email_service._normalize_folder_type("Inbox") == "inbox"
        assert zoho_email_service._normalize_folder_type("Sent") == "sent"
        assert zoho_email_service._normalize_folder_type("Drafts") == "drafts"
        assert zoho_email_service._normalize_folder_type("Trash") == "trash"
        assert zoho_email_service._normalize_folder_type("Spam") == "spam"
        assert zoho_email_service._normalize_folder_type("Junk") == "spam"
        assert zoho_email_service._normalize_folder_type("CustomFolder") == "custom"


class TestEmailListOperations:
    """Tests for email listing operations"""

    @pytest.mark.asyncio
    async def test_list_emails(self, zoho_email_service):
        """Test listing emails"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {
                        "messageId": "msg1",
                        "folderId": "inbox",
                        "threadId": "thread1",
                        "subject": "Test Subject",
                        "fromAddress": "sender@example.com",
                        "sender": "Sender Name",
                        "toAddress": "receiver@example.com",
                        "ccAddress": "",
                        "summary": "Email snippet...",
                        "hasAttachment": False,
                        "isRead": False,
                        "isFlagged": True,
                        "receivedTime": "2026-01-05T10:00:00Z",
                    }
                ],
                "paging": {"totalCount": 1, "hasMoreData": False},
            }

            result = await zoho_email_service.list_emails("user1", "inbox", limit=50)

            assert len(result["emails"]) == 1
            assert result["total"] == 1
            assert result["has_more"] is False
            email = result["emails"][0]
            assert email["message_id"] == "msg1"
            assert email["subject"] == "Test Subject"
            assert email["from"]["address"] == "sender@example.com"
            assert email["is_flagged"] is True

    @pytest.mark.asyncio
    async def test_list_emails_with_search(self, zoho_email_service):
        """Test listing emails with search query"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": [], "paging": {"totalCount": 0}}

            await zoho_email_service.list_emails("user1", "inbox", search_key="test")

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["params"]["searchKey"] == "test"

    @pytest.mark.asyncio
    async def test_list_emails_unread_filter(self, zoho_email_service):
        """Test listing unread emails only"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": [], "paging": {"totalCount": 0}}

            await zoho_email_service.list_emails("user1", "inbox", is_unread=True)

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["params"]["status"] == "unread"

    def test_parse_recipients(self, zoho_email_service):
        """Test parsing recipient string"""
        result = zoho_email_service._parse_recipients("a@example.com, b@example.com")
        assert result == ["a@example.com", "b@example.com"]

        result = zoho_email_service._parse_recipients("")
        assert result == []

    def test_parse_recipients_to_objects(self, zoho_email_service):
        """Test parsing recipients to objects"""
        # Simple email
        result = zoho_email_service._parse_recipients_to_objects("test@example.com")
        assert result == [{"address": "test@example.com", "name": ""}]

        # Name <email> format
        result = zoho_email_service._parse_recipients_to_objects('"John Doe" <john@example.com>')
        assert result == [{"address": "john@example.com", "name": "John Doe"}]

        # Multiple recipients
        result = zoho_email_service._parse_recipients_to_objects("a@test.com, b@test.com")
        assert len(result) == 2

        # Empty string
        result = zoho_email_service._parse_recipients_to_objects("")
        assert result == []


class TestEmailReadOperations:
    """Tests for reading email content"""

    @pytest.mark.asyncio
    async def test_get_email(self, zoho_email_service):
        """Test getting full email content"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            # First call: list emails to find metadata
            # Second call: get content
            mock_request.side_effect = [
                {
                    "data": [
                        {
                            "messageId": "msg1",
                            "folderId": "inbox",
                            "threadId": "thread1",
                            "subject": "Test Subject",
                            "fromAddress": "sender@example.com",
                            "sender": "Sender",
                            "toAddress": "receiver@example.com",
                            "summary": "Snippet",
                            "hasAttachment": False,
                            "isFlagged": False,
                            "receivedTime": "2026-01-05T10:00:00Z",
                            "attachments": [],
                        }
                    ]
                },
                {"data": {"content": "<html><body>Email content</body></html>"}},
                {},  # mark_read response
            ]

            with patch.object(zoho_email_service, "mark_read", new_callable=AsyncMock):
                email = await zoho_email_service.get_email("user1", "msg1", "inbox")

            assert email["message_id"] == "msg1"
            assert email["subject"] == "Test Subject"
            assert email["html_content"] == "<html><body>Email content</body></html>"
            assert email["text_content"] == ""

    @pytest.mark.asyncio
    async def test_get_email_not_found(self, zoho_email_service):
        """Test getting email that doesn't exist"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": []}

            with pytest.raises(ValueError, match="not found"):
                await zoho_email_service.get_email("user1", "nonexistent", "inbox")

    @pytest.mark.asyncio
    async def test_get_email_no_folder_id(self, zoho_email_service):
        """Test getting email without folder_id"""
        with pytest.raises(ValueError, match="folder_id is required"):
            await zoho_email_service.get_email("user1", "msg1", None)

    def test_parse_attachments(self, zoho_email_service):
        """Test parsing attachments"""
        attachments = [
            {
                "attachmentId": "att1",
                "attachmentName": "file.pdf",
                "attachmentSize": 1024,
                "contentType": "application/pdf",
            }
        ]
        result = zoho_email_service._parse_attachments(attachments)
        assert len(result) == 1
        assert result[0]["attachment_id"] == "att1"
        assert result[0]["filename"] == "file.pdf"
        assert result[0]["size"] == 1024


class TestSearchOperations:
    """Tests for search operations"""

    @pytest.mark.asyncio
    async def test_search_emails(self, zoho_email_service):
        """Test searching emails"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": [
                    {
                        "messageId": "msg1",
                        "folderId": "inbox",
                        "subject": "Matching email",
                        "fromAddress": "sender@example.com",
                        "sender": "Sender",
                        "summary": "Contains search term",
                        "hasAttachment": False,
                        "isRead": True,
                        "receivedTime": "2026-01-05T10:00:00Z",
                    }
                ]
            }

            results = await zoho_email_service.search_emails("user1", "search term")

            assert len(results) == 1
            assert results[0]["id"] == "msg1"
            assert results[0]["subject"] == "Matching email"


class TestSendOperations:
    """Tests for sending email operations"""

    @pytest.mark.asyncio
    async def test_send_email(self, zoho_email_service):
        """Test sending new email"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "new_msg_1"}}

            result = await zoho_email_service.send_email(
                user_id="user1",
                to=["recipient@example.com"],
                subject="Test Subject",
                content="<p>Test content</p>",
                cc=["cc@example.com"],
                bcc=["bcc@example.com"],
            )

            assert result["success"] is True
            assert result["message_id"] == "new_msg_1"

    @pytest.mark.asyncio
    async def test_reply_email(self, zoho_email_service):
        """Test replying to email"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "reply_msg_1"}}

            result = await zoho_email_service.reply_email(
                user_id="user1",
                message_id="original_msg",
                content="<p>Reply content</p>",
                reply_all=False,
            )

            assert result["success"] is True
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "reply" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_reply_all_email(self, zoho_email_service):
        """Test reply all to email"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "reply_msg_1"}}

            await zoho_email_service.reply_email(
                user_id="user1",
                message_id="original_msg",
                content="<p>Reply content</p>",
                reply_all=True,
            )

            call_args = mock_request.call_args
            assert "replyall" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_forward_email(self, zoho_email_service):
        """Test forwarding email"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "fwd_msg_1"}}

            result = await zoho_email_service.forward_email(
                user_id="user1",
                message_id="original_msg",
                to=["forward@example.com"],
                content="<p>FYI</p>",
            )

            assert result["success"] is True
            call_args = mock_request.call_args
            assert "forward" in call_args[0][2]


class TestStatusOperations:
    """Tests for status operations"""

    @pytest.mark.asyncio
    async def test_mark_read(self, zoho_email_service):
        """Test marking emails as read"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await zoho_email_service.mark_read("user1", ["msg1", "msg2"], is_read=True)

            assert result is True
            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["mode"] == "markAsRead"

    @pytest.mark.asyncio
    async def test_mark_unread(self, zoho_email_service):
        """Test marking emails as unread"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            await zoho_email_service.mark_read("user1", ["msg1"], is_read=False)

            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["mode"] == "markAsUnread"

    @pytest.mark.asyncio
    async def test_toggle_flag(self, zoho_email_service):
        """Test flagging email"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await zoho_email_service.toggle_flag("user1", "msg1", is_flagged=True)

            assert result is True
            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["flagid"] == "1"

    @pytest.mark.asyncio
    async def test_unflag(self, zoho_email_service):
        """Test unflagging email"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            await zoho_email_service.toggle_flag("user1", "msg1", is_flagged=False)

            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["flagid"] == "0"

    @pytest.mark.asyncio
    async def test_move_to_folder(self, zoho_email_service):
        """Test moving emails to folder"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await zoho_email_service.move_to_folder("user1", ["msg1"], "archive")

            assert result is True
            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["destfolderId"] == "archive"

    @pytest.mark.asyncio
    async def test_delete_emails(self, zoho_email_service):
        """Test deleting emails (move to trash)"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await zoho_email_service.delete_emails("user1", ["msg1", "msg2"])

            assert result is True
            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["mode"] == "moveToTrash"


class TestAttachmentOperations:
    """Tests for attachment operations"""

    @pytest.mark.asyncio
    async def test_get_attachment(self, zoho_email_service, mock_oauth_service):
        """Test downloading attachment"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"file content bytes"
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            content = await zoho_email_service.get_attachment("user1", "msg1", "att1")

            assert content == b"file content bytes"

    @pytest.mark.asyncio
    async def test_get_attachment_error(self, zoho_email_service, mock_oauth_service):
        """Test attachment download error"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to download"):
                await zoho_email_service.get_attachment("user1", "msg1", "att1")

    @pytest.mark.asyncio
    async def test_upload_attachment(self, zoho_email_service, mock_oauth_service):
        """Test uploading attachment"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"attachmentId": "new_att_1"}}
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            att_id = await zoho_email_service.upload_attachment(
                "user1", "test.pdf", b"pdf content", "application/pdf"
            )

            assert att_id == "new_att_1"

    @pytest.mark.asyncio
    async def test_upload_attachment_error(self, zoho_email_service, mock_oauth_service):
        """Test attachment upload error"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 413
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to upload"):
                await zoho_email_service.upload_attachment(
                    "user1", "large.zip", b"content", "application/zip"
                )


class TestDraftOperations:
    """Tests for draft operations"""

    @pytest.mark.asyncio
    async def test_save_draft(self, zoho_email_service):
        """Test saving draft"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "draft_1"}}

            result = await zoho_email_service.save_draft(
                user_id="user1",
                to=["recipient@example.com"],
                subject="Draft Subject",
                content="<p>Draft content</p>",
            )

            assert result["success"] is True
            assert result["message_id"] == "draft_1"
            call_args = mock_request.call_args
            assert call_args[1]["json_data"]["mode"] == "draft"


class TestUnreadCount:
    """Tests for unread count operations"""

    @pytest.mark.asyncio
    async def test_get_unread_count(self, zoho_email_service):
        """Test getting total unread count"""
        with patch.object(zoho_email_service, "list_folders", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [
                {"folder_id": "1", "unread_count": 5},
                {"folder_id": "2", "unread_count": 3},
                {"folder_id": "3", "unread_count": 0},
            ]

            count = await zoho_email_service.get_unread_count("user1")

            assert count == 8

    @pytest.mark.asyncio
    async def test_get_unread_count_error(self, zoho_email_service):
        """Test unread count on error"""
        with patch.object(zoho_email_service, "list_folders", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = Exception("API error")

            count = await zoho_email_service.get_unread_count("user1")

            assert count == 0


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_list_emails_max_limit(self, zoho_email_service):
        """Test that limit is capped at 200"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": [], "paging": {"totalCount": 0}}

            await zoho_email_service.list_emails("user1", "inbox", limit=500)

            call_args = mock_request.call_args
            assert call_args[1]["params"]["limit"] == 200

    @pytest.mark.asyncio
    async def test_send_email_without_optional_fields(self, zoho_email_service):
        """Test sending email without CC/BCC/attachments"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "msg1"}}

            result = await zoho_email_service.send_email(
                user_id="user1",
                to=["recipient@example.com"],
                subject="Subject",
                content="Content",
            )

            assert result["success"] is True
            call_args = mock_request.call_args
            assert "ccAddress" not in call_args[1]["json_data"]
            assert "bccAddress" not in call_args[1]["json_data"]

    @pytest.mark.asyncio
    async def test_forward_email_without_content(self, zoho_email_service):
        """Test forwarding email without additional content"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": {"messageId": "fwd1"}}

            await zoho_email_service.forward_email(
                user_id="user1",
                message_id="msg1",
                to=["forward@example.com"],
            )

            call_args = mock_request.call_args
            assert "content" not in call_args[1]["json_data"]

    @pytest.mark.asyncio
    async def test_get_email_plain_text_content(self, zoho_email_service):
        """Test getting email with plain text content (no HTML)"""
        with patch.object(zoho_email_service, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                {
                    "data": [
                        {
                            "messageId": "msg1",
                            "folderId": "inbox",
                            "threadId": "thread1",
                            "subject": "Plain text email",
                            "fromAddress": "sender@example.com",
                            "sender": "Sender",
                            "toAddress": "receiver@example.com",
                            "summary": "Snippet",
                            "hasAttachment": False,
                            "isFlagged": False,
                            "receivedTime": "2026-01-05T10:00:00Z",
                            "attachments": [],
                        }
                    ]
                },
                {"data": {"content": "Plain text content without HTML tags"}},
                {},
            ]

            with patch.object(zoho_email_service, "mark_read", new_callable=AsyncMock):
                email = await zoho_email_service.get_email("user1", "msg1", "inbox")

            assert email["text_content"] == "Plain text content without HTML tags"
            assert email["html_content"] == ""
