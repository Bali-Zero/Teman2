"""
Unit tests for WhatsApp Channel Adapter and Formatter.

Tests:
- Message parsing from WhatsApp Business API webhooks
- Response formatting (limited Markdown)
- Send response via Meta Cloud API
- Stream response (accumulate then send)
- Error handling
- Config validation
"""

import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.channels.base import ChannelResponse
from backend.channels.whatsapp.adapter import WhatsAppChannelAdapter
from backend.channels.whatsapp.config import WhatsAppChannelConfig
from backend.channels.whatsapp.formatter import WhatsAppMessageFormatter

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def wa_config() -> dict:
    return {
        "access_token": "wa_test_token_123",
        "phone_number_id": "123456789",
        "business_account_id": "987654321",
    }


@pytest.fixture
def adapter(wa_config: dict) -> WhatsAppChannelAdapter:
    return WhatsAppChannelAdapter(wa_config)


@pytest.fixture
def sample_webhook() -> dict:
    """Realistic WhatsApp Business API webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "987654321",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "628123456789",
                                "phone_number_id": "123456789",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "John Doe"},
                                    "wa_id": "6281234567890",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "6281234567890",
                                    "id": "wamid.HBgLNjI4MTIzNDU2",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Berapa biaya KITAS?"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def webhook_no_messages() -> dict:
    """Webhook with status update but no messages."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "987654321",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": "wamid.xxx", "status": "delivered"}
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


# ============================================================================
# CONFIG TESTS
# ============================================================================


class TestWhatsAppConfig:
    def test_valid_config(self) -> None:
        cfg = WhatsAppChannelConfig(
            access_token="tok",
            phone_number_id="123",
        )
        assert cfg.max_message_length == 1600
        assert cfg.supports_markdown is True
        assert cfg.supports_media is True
        assert cfg.api_version == "v18.0"
        assert cfg.api_base_url == "https://graph.facebook.com"

    def test_missing_access_token_raises(self) -> None:
        with pytest.raises(ValueError, match="access_token is required"):
            WhatsAppChannelConfig(access_token="", phone_number_id="123")

    def test_missing_phone_number_id_raises(self) -> None:
        with pytest.raises(ValueError, match="phone_number_id is required"):
            WhatsAppChannelConfig(access_token="tok", phone_number_id="")

    def test_message_length_too_large_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed 4096"):
            WhatsAppChannelConfig(
                access_token="tok",
                phone_number_id="123",
                max_message_length=5000,
            )

    def test_optional_business_account_id(self) -> None:
        cfg = WhatsAppChannelConfig(access_token="tok", phone_number_id="123")
        assert cfg.business_account_id is None

    def test_custom_api_version(self) -> None:
        cfg = WhatsAppChannelConfig(
            access_token="tok",
            phone_number_id="123",
            api_version="v20.0",
        )
        assert cfg.api_version == "v20.0"


# ============================================================================
# FORMATTER TESTS
# ============================================================================


class TestWhatsAppFormatter:
    def test_format_text_only(self, simple_response: ChannelResponse) -> None:
        result = WhatsAppMessageFormatter.format_response(simple_response)
        assert result == "Hello, how can I help you?"

    def test_format_with_sources(self, response_with_sources: ChannelResponse) -> None:
        result = WhatsAppMessageFormatter.format_response(response_with_sources)
        assert "Here is the answer." in result
        assert "*📚 Fonti:*" in result
        assert "1. Visa Guide" in result
        assert "https://example.com/visa" in result
        # WhatsApp puts URL on separate line (no Markdown links)
        assert "[Visa Guide]" not in result

    def test_format_sources_max_five(self) -> None:
        response = ChannelResponse(
            text="A",
            sources=[
                {"title": f"S{i}", "url": f"https://x.com/{i}"} for i in range(10)
            ],
            metadata={},
        )
        result = WhatsAppMessageFormatter.format_response(response)
        assert "S0" in result
        assert "S4" in result
        assert "S5" not in result

    def test_format_source_without_url(self) -> None:
        response = ChannelResponse(
            text="A",
            sources=[{"title": "Offline Doc"}],
            metadata={},
        )
        result = WhatsAppMessageFormatter.format_response(response)
        assert "1. Offline Doc" in result

    def test_format_with_workflow(self, response_with_workflow: ChannelResponse) -> None:
        result = WhatsAppMessageFormatter.format_response(response_with_workflow)
        assert "*📋 Piano:*" in result
        assert "*PT PMA Setup:*" in result
        assert "1. Prepare documents" in result
        assert "3. Register at OSS" in result

    def test_format_workflow_no_steps(self) -> None:
        result = WhatsAppMessageFormatter._format_workflow(
            {"name": "Empty", "steps": []},
        )
        assert result == "*Empty*"

    def test_format_workflow_dict_steps(self) -> None:
        workflow = {
            "name": "Plan",
            "steps": [{"description": "A"}, {"action": "B"}],
        }
        result = WhatsAppMessageFormatter._format_workflow(workflow)
        assert "1. A" in result
        assert "2. B" in result

    def test_format_workflow_string_steps(self) -> None:
        workflow = {"name": "Plan", "steps": ["Do X", "Do Y"]}
        result = WhatsAppMessageFormatter._format_workflow(workflow)
        assert "1. Do X" in result

    def test_format_workflow_max_ten_steps(self) -> None:
        workflow = {"name": "Big", "steps": [f"S{i}" for i in range(15)]}
        result = WhatsAppMessageFormatter._format_workflow(workflow)
        assert "10. S9" in result
        assert "S10" not in result

    def test_format_thinking(self) -> None:
        result = WhatsAppMessageFormatter.format_thinking("Thinking hard...")
        assert result == "_💭 Thinking hard..._"

    def test_format_error(self) -> None:
        result = WhatsAppMessageFormatter.format_error("API timeout")
        assert result == "❌ *Errore:* API timeout"

    def test_format_empty_text(self) -> None:
        result = WhatsAppMessageFormatter.format_response(
            ChannelResponse(text="", metadata={})
        )
        assert result == ""


# ============================================================================
# ADAPTER TESTS
# ============================================================================


class TestWhatsAppAdapter:
    def test_adapter_properties(self, adapter: WhatsAppChannelAdapter) -> None:
        assert adapter.channel_name == "whatsapp"
        assert adapter.supports_markdown is True
        assert adapter.supports_media is True
        assert adapter.max_message_length == 1600

    async def test_receive_message_text(
        self, adapter: WhatsAppChannelAdapter, sample_webhook: dict,
    ) -> None:
        msg = await adapter.receive_message(sample_webhook)
        assert msg.user_id == "whatsapp_6281234567890"
        assert msg.session_id == "wa_session_6281234567890"
        assert msg.text == "Berapa biaya KITAS?"
        assert msg.channel == "whatsapp"
        assert msg.metadata["phone"] == "6281234567890"
        assert msg.metadata["sender_name"] == "John Doe"
        assert msg.metadata["message_id"] == "wamid.HBgLNjI4MTIzNDU2"
        assert msg.metadata["message_type"] == "text"

    async def test_receive_message_no_messages(
        self, adapter: WhatsAppChannelAdapter, webhook_no_messages: dict,
    ) -> None:
        msg = await adapter.receive_message(webhook_no_messages)
        assert msg.user_id == "unknown"
        assert msg.text == ""
        assert msg.channel == "whatsapp"

    async def test_receive_message_no_contacts(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        webhook = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "123",
                                        "id": "wamid.x",
                                        "type": "text",
                                        "text": {"body": "Hi"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        msg = await adapter.receive_message(webhook)
        assert msg.metadata["sender_name"] is None
        assert msg.text == "Hi"

    async def test_receive_message_malformed_raises(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        with pytest.raises(Exception):
            await adapter.receive_message({"entry": "bad"})

    async def test_send_response_success(
        self, adapter: WhatsAppChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        await adapter.send_response("6281234567890", simple_response)

        adapter.client.post.assert_called_once()
        call_args = adapter.client.post.call_args
        url = call_args.args[0]
        assert "123456789/messages" in url
        assert "graph.facebook.com" in url

        payload = call_args.kwargs["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "6281234567890"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Hello, how can I help you?"

        headers = call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer wa_test_token_123"

    async def test_send_response_truncates(
        self, adapter: WhatsAppChannelAdapter, long_response: ChannelResponse,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        await adapter.send_response("123", long_response)

        sent_text = adapter.client.post.call_args.kwargs["json"]["text"]["body"]
        assert len(sent_text) <= 1600

    async def test_send_response_api_error(
        self, adapter: WhatsAppChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(),
            ),
        )

        # Should not raise, just log
        await adapter.send_response("123", simple_response)

    async def test_send_status_update_noop(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        # WhatsApp doesn't support typing indicators
        await adapter.send_status_update("123", "typing")

    async def test_stream_response_accumulates_and_sends(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        async def mock_stream():
            yield ChannelResponse(text="Hello ", metadata={})
            yield ChannelResponse(text="beautiful ", metadata={})
            yield ChannelResponse(text="world!", metadata={})

        await adapter.stream_response("6281234567890", mock_stream())

        # Should send 1 accumulated message
        adapter.client.post.assert_called_once()
        sent_text = adapter.client.post.call_args.kwargs["json"]["text"]["body"]
        assert "Hello beautiful world!" in sent_text

    async def test_stream_response_with_sources(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        async def mock_stream():
            yield ChannelResponse(text="Answer here.", metadata={})
            yield ChannelResponse(
                text="",
                sources=[{"title": "Doc A", "url": "https://a.com"}],
                metadata={},
            )

        await adapter.stream_response("123", mock_stream())

        sent_text = adapter.client.post.call_args.kwargs["json"]["text"]["body"]
        assert "Answer here." in sent_text
        assert "Doc A" in sent_text

    async def test_stream_response_with_workflow(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        async def mock_stream():
            yield ChannelResponse(
                text="Plan:",
                workflow={"name": "Setup", "steps": ["Step 1"]},
                metadata={},
            )

        await adapter.stream_response("123", mock_stream())

        sent_text = adapter.client.post.call_args.kwargs["json"]["text"]["body"]
        assert "Plan:" in sent_text
        assert "Setup" in sent_text

    async def test_stream_response_empty_stream(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock()

        async def empty_stream():
            return
            yield  # noqa: unreachable

        await adapter.stream_response("123", empty_stream())
        # No message should be sent for empty stream
        adapter.client.post.assert_not_called()

    async def test_stream_response_error_sends_error_message(
        self, adapter: WhatsAppChannelAdapter,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        async def failing_stream():
            yield ChannelResponse(text="Start...", metadata={})
            raise RuntimeError("Processing failed")

        await adapter.stream_response("123", failing_stream())

        # Should have sent error message
        assert adapter.client.post.call_count >= 1
        last_call = adapter.client.post.call_args
        sent_text = last_call.kwargs["json"]["text"]["body"]
        assert "Errore" in sent_text or "errore" in sent_text


# ============================================================================
# BASE CHANNEL HELPER TESTS
# ============================================================================


class TestBaseChannelHelpers:
    """Test truncate_message and split_message from BaseChannel."""

    def test_truncate_short_message(self, adapter: WhatsAppChannelAdapter) -> None:
        result = adapter.truncate_message("Hello!")
        assert result == "Hello!"

    def test_truncate_long_message(self, adapter: WhatsAppChannelAdapter) -> None:
        long_text = "A" * 2000
        result = adapter.truncate_message(long_text)
        assert len(result) <= adapter.max_message_length
        assert result.endswith("_...continua..._")

    def test_truncate_custom_limit(self, adapter: WhatsAppChannelAdapter) -> None:
        result = adapter.truncate_message("A" * 200, max_length=100)
        assert len(result) <= 100

    def test_split_short_message(self, adapter: WhatsAppChannelAdapter) -> None:
        result = adapter.split_message("Short message")
        assert len(result) == 1
        assert result[0] == "Short message"

    def test_split_long_message(self, adapter: WhatsAppChannelAdapter) -> None:
        paragraphs = ["Paragraph " + str(i) + "." + " X" * 400 for i in range(10)]
        long_text = "\n\n".join(paragraphs)
        result = adapter.split_message(long_text)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= adapter.max_message_length
