"""Tests for backend.services.integrations.telegram_bot_service"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
def service():
    with patch("backend.services.integrations.telegram_bot_service.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test_token_123"
        from backend.services.integrations.telegram_bot_service import TelegramBotService
        svc = TelegramBotService()
        svc._token = "test_token_123"
        return svc


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.is_closed = False
    return client


# ── Properties ──────────────────────────────────────────────────────────────


class TestTelegramBotProperties:
    def test_api_url(self, service):
        assert "test_token_123" in service.api_url
        assert service.api_url.startswith("https://api.telegram.org/bot")

    def test_token_property(self, service):
        assert service.token == "test_token_123"


# ── _get_client ─────────────────────────────────────────────────────────────


class TestGetClient:
    @pytest.mark.asyncio
    async def test_creates_client_when_none(self, service):
        service._client = None
        with patch("backend.services.integrations.telegram_bot_service.HttpTimeoutConstants") as mock_const:
            mock_const.TELEGRAM_TIMEOUT = 30.0
            client = await service._get_client()
            assert client is not None

    @pytest.mark.asyncio
    async def test_reuses_existing_client(self, service, mock_client):
        service._client = mock_client
        client = await service._get_client()
        assert client is mock_client


# ── close ───────────────────────────────────────────────────────────────────


class TestClose:
    @pytest.mark.asyncio
    async def test_close_when_client_exists(self, service, mock_client):
        service._client = mock_client
        await service.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, service):
        service._client = None
        await service.close()  # Should not raise


# ── send_message ────────────────────────────────────────────────────────────


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_success(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.send_message(chat_id=123, text="Hello")
        assert result["ok"] is True
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_with_reply(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        await service.send_message(chat_id=123, text="Reply", reply_to_message_id=42)
        call_kwargs = mock_client.post.call_args.kwargs["json"]
        assert call_kwargs["reply_to_message_id"] == 42

    @pytest.mark.asyncio
    async def test_send_message_no_parse_mode(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        await service.send_message(chat_id=123, text="Plain", parse_mode=None)
        call_kwargs = mock_client.post.call_args.kwargs["json"]
        assert "parse_mode" not in call_kwargs

    @pytest.mark.asyncio
    async def test_send_message_api_error(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request",
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        with pytest.raises(ValueError, match="Telegram API error"):
            await service.send_message(chat_id=123, text="Fail")

    @pytest.mark.asyncio
    async def test_send_message_no_token(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            with pytest.raises(ValueError, match="not configured"):
                await service.send_message(chat_id=123, text="Hello")

    @pytest.mark.asyncio
    async def test_send_message_http_error(self, service, mock_client):
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
        service._client = mock_client

        with pytest.raises(httpx.HTTPError):
            await service.send_message(chat_id=123, text="Fail")


# ── send_photo ──────────────────────────────────────────────────────────────


class TestSendPhoto:
    @pytest.mark.asyncio
    async def test_send_photo_success(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.send_photo(chat_id=123, photo=b"fake_image_data")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_send_photo_with_caption(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        await service.send_photo(
            chat_id=123, photo=b"img", caption="My photo",
            reply_markup={"inline_keyboard": []},
        )
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_photo_no_token(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            with pytest.raises(ValueError):
                await service.send_photo(chat_id=123, photo=b"img")

    @pytest.mark.asyncio
    async def test_send_photo_api_error(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error_code": 400, "description": "Bad"}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        with pytest.raises(ValueError, match="Telegram API error"):
            await service.send_photo(chat_id=123, photo=b"img")


# ── send_chat_action ────────────────────────────────────────────────────────


class TestSendChatAction:
    @pytest.mark.asyncio
    async def test_success(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.send_chat_action(chat_id=123)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_token_returns_false(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            result = await service.send_chat_action(chat_id=123)
            assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, service, mock_client):
        mock_client.post = AsyncMock(side_effect=Exception("fail"))
        service._client = mock_client
        result = await service.send_chat_action(chat_id=123)
        assert result is False


# ── set_webhook / delete_webhook / get_webhook_info ─────────────────────────


class TestWebhookMethods:
    @pytest.mark.asyncio
    async def test_set_webhook(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.set_webhook(
            url="https://example.com/webhook",
            secret_token="secret",
            allowed_updates=["message"],
        )
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_set_webhook_no_token(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            with pytest.raises(ValueError):
                await service.set_webhook(url="https://example.com/webhook")

    @pytest.mark.asyncio
    async def test_delete_webhook(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.delete_webhook()
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_get_webhook_info(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"url": ""}}
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.get_webhook_info()
        assert result["ok"] is True


# ── get_me ──────────────────────────────────────────────────────────────────


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_success(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"username": "testbot"}}
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.get_me()
        assert result["result"]["username"] == "testbot"

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            with pytest.raises(ValueError):
                await service.get_me()


# ── answer_callback_query ───────────────────────────────────────────────────


class TestAnswerCallbackQuery:
    @pytest.mark.asyncio
    async def test_answer_callback(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.answer_callback_query(
            callback_query_id="abc123", text="Done", show_alert=True,
        )
        assert result["ok"] is True


# ── get_file / download_file ────────────────────────────────────────────────


class TestFileMethods:
    @pytest.mark.asyncio
    async def test_get_file_success(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"file_path": "documents/file.pdf"},
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.get_file("file_id_123")
        assert result["file_path"] == "documents/file.pdf"

    @pytest.mark.asyncio
    async def test_get_file_error(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error_code": 404, "description": "Not found"}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        with pytest.raises(ValueError, match="getFile error"):
            await service.get_file("bad_id")

    @pytest.mark.asyncio
    async def test_download_file(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.content = b"file_content_bytes"
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        service._client = mock_client

        data = await service.download_file("documents/file.pdf")
        assert data == b"file_content_bytes"

    @pytest.mark.asyncio
    async def test_download_file_no_token(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            with pytest.raises(ValueError):
                await service.download_file("path")


# ── edit_message_text ───────────────────────────────────────────────────────


class TestEditMessageText:
    @pytest.mark.asyncio
    async def test_edit_message_success(self, service, mock_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        result = await service.edit_message_text(
            chat_id=123, message_id=456, text="Updated",
        )
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_edit_message_no_token(self, service):
        service._token = None
        with patch("backend.services.integrations.telegram_bot_service.settings") as ms:
            ms.telegram_bot_token = None
            with pytest.raises(ValueError):
                await service.edit_message_text(chat_id=123, message_id=456, text="x")
