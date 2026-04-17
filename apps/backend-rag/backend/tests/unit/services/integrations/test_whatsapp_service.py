"""
Unit tests for backend/services/integrations/whatsapp_service.py

Covers:
  - WhatsAppService properties (token, phone_number_id, api_url)
  - send_message (success, errors, phone format, reply, char limit)
  - send_typing_action
  - mark_message_read
  - format_message
  - chunk_message
  - _get_client / close
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.whatsapp_api_token = "test-token"
    s.whatsapp_phone_number_id = "123456789"
    return s


@pytest.fixture
def service(mock_settings):
    # CI test-ordering issue: if an earlier test cleared os.environ and forced
    # a config reload, the module's top-level `from backend.app.core.config
    # import settings` binding can be missing by the time this fixture runs.
    # Import (and if already imported, reload) the module so the top-level
    # `from backend.app.core.config import settings` runs again, then patch
    # on the resolved attribute. Proper long-term fix is to make
    # WhatsAppService read settings lazily (tracked as follow-up).
    import importlib
    import sys

    modname = "backend.services.integrations.whatsapp_service"
    if modname in sys.modules:
        whatsapp_module = importlib.reload(sys.modules[modname])
    else:
        whatsapp_module = importlib.import_module(modname)
    with patch.object(whatsapp_module, "settings", mock_settings):
        svc = whatsapp_module.WhatsAppService()
    svc._token = "test-token"
    svc._phone_number_id = "123456789"
    return svc


# ============================================================
# Properties
# ============================================================


class TestProperties:
    def test_api_url(self, service):
        assert service.api_url == "https://graph.facebook.com/v22.0/123456789"

    def test_token(self, service):
        assert service.token == "test-token"

    def test_phone_number_id(self, service):
        assert service.phone_number_id == "123456789"


# ============================================================
# _get_client / close
# ============================================================


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_get_client_creates_new(self, service):
        service._client = None
        client = await service._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        await service.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing(self, service):
        service._client = None
        c1 = await service._get_client()
        c2 = await service._get_client()
        assert c1 is c2
        await service.close()

    @pytest.mark.asyncio
    async def test_close_when_none(self, service):
        service._client = None
        await service.close()  # Should not raise


# ============================================================
# send_message
# ============================================================


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_success(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"id": "wamid.test123"}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service.send_message("6281234567890", "Hello!")
        assert result["messages"][0]["id"] == "wamid.test123"

    @pytest.mark.asyncio
    async def test_strips_plus_prefix(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.1"}]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        await service.send_message("+6281234567890", "Hello")
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["to"] == "6281234567890"

    @pytest.mark.asyncio
    async def test_with_reply_context(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.2"}]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        await service.send_message("6281234567890", "Reply text", reply_to_message_id="wamid.original")
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["context"]["message_id"] == "wamid.original"

    @pytest.mark.asyncio
    async def test_truncates_to_4096_chars(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid.3"}]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        long_text = "A" * 5000
        await service.send_message("6281234567890", long_text)
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(payload["text"]["body"]) == 4096

    @pytest.mark.asyncio
    async def test_no_token_raises(self, service):
        service._token = None
        with patch("backend.services.integrations.whatsapp_service.settings") as ms:
            ms.whatsapp_api_token = None
            with pytest.raises(ValueError, match="token"):
                await service.send_message("6281234567890", "Hello")

    @pytest.mark.asyncio
    async def test_no_phone_id_raises(self, service):
        service._phone_number_id = None
        with patch("backend.services.integrations.whatsapp_service.settings") as ms:
            ms.whatsapp_phone_number_id = None
            ms.whatsapp_api_token = "token"
            with pytest.raises(ValueError, match="phone number"):
                await service.send_message("6281234567890", "Hello")

    @pytest.mark.asyncio
    async def test_api_error_raises(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"code": 190, "message": "Invalid access token"}
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(ValueError, match="Invalid access token"):
            await service.send_message("6281234567890", "Hello")

    @pytest.mark.asyncio
    async def test_http_error_raises(self, service):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(httpx.HTTPError):
            await service.send_message("6281234567890", "Hello")


# ============================================================
# send_typing_action
# ============================================================


class TestSendTypingAction:
    @pytest.mark.asyncio
    async def test_returns_true(self, service):
        result = await service.send_typing_action("6281234567890")
        assert result is True


# ============================================================
# mark_message_read
# ============================================================


class TestMarkMessageRead:
    @pytest.mark.asyncio
    async def test_success(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service.mark_message_read("wamid.test123")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_token(self, service):
        service._token = None
        service._phone_number_id = None
        result = await service.mark_message_read("wamid.test123")
        assert result is False

    @pytest.mark.asyncio
    async def test_api_failure(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        service._client = mock_client

        result = await service.mark_message_read("wamid.fail")
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, service):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.is_closed = False
        service._client = mock_client

        result = await service.mark_message_read("wamid.error")
        assert result is False


# ============================================================
# format_message
# ============================================================


class TestFormatMessage:
    def test_passthrough(self, service):
        text = "*bold* _italic_ ~strike~"
        assert service.format_message(text) == text


# ============================================================
# chunk_message
# ============================================================


class TestChunkMessage:
    def test_short_message_single_chunk(self, service):
        chunks = service.chunk_message("Hello world")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_exact_limit(self, service):
        text = "A" * 4000
        chunks = service.chunk_message(text, max_length=4000)
        assert len(chunks) == 1

    def test_splits_by_paragraph(self, service):
        para1 = "A" * 2000
        para2 = "B" * 2000
        para3 = "C" * 2000
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = service.chunk_message(text, max_length=3000)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 3000

    def test_splits_long_paragraph_by_lines(self, service):
        # A single paragraph that's too long, with newlines inside
        lines = ["X" * 100 + "\n" for _ in range(50)]
        text = "".join(lines)  # ~5050 chars, no double newlines
        chunks = service.chunk_message(text, max_length=2000)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 2000

    def test_empty_message(self, service):
        chunks = service.chunk_message("")
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_preserves_content(self, service):
        text = "First paragraph\n\nSecond paragraph\n\nThird paragraph"
        chunks = service.chunk_message(text, max_length=100)
        combined = " ".join(chunks)
        assert "First paragraph" in combined
        assert "Second paragraph" in combined
        assert "Third paragraph" in combined
