"""
Unit tests for Instagram Channel Adapter and Formatter.

Tests:
- Message parsing from Instagram webhooks
- Response formatting (plain text only)
- Send response via Meta Graph API
- Error handling for malformed payloads
- Config validation
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.channels.base import ChannelResponse
from backend.channels.instagram.adapter import InstagramChannelAdapter
from backend.channels.instagram.config import InstagramChannelConfig
from backend.channels.instagram.formatter import InstagramMessageFormatter

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def ig_config() -> dict:
    return {
        "access_token": "test_ig_access_token",
        "instagram_account_id": "17841400000000",
    }


@pytest.fixture
def adapter(ig_config: dict) -> InstagramChannelAdapter:
    return InstagramChannelAdapter(ig_config)


@pytest.fixture
def sample_webhook() -> dict:
    """A realistic Instagram DM webhook payload."""
    return {
        "object": "instagram",
        "entry": [
            {
                "id": "17841400000000",
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": "9876543210"},
                        "recipient": {"id": "17841400000000"},
                        "timestamp": 1700000000000,
                        "message": {
                            "mid": "m_abc123def456",
                            "text": "Ciao, quanto costa una PT PMA?",
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture
def empty_webhook() -> dict:
    """Webhook with no messaging data."""
    return {"object": "instagram", "entry": [{}]}


# ============================================================================
# CONFIG TESTS
# ============================================================================


class TestInstagramConfig:
    def test_valid_config(self) -> None:
        cfg = InstagramChannelConfig(
            access_token="tok_123",
            instagram_account_id="17841400000",
        )
        assert cfg.max_message_length == 1000
        assert cfg.supports_markdown is False
        assert cfg.supports_media is True

    def test_missing_access_token_raises(self) -> None:
        with pytest.raises(ValueError, match="access_token required"):
            InstagramChannelConfig(access_token="", instagram_account_id="123")

    def test_missing_account_id_raises(self) -> None:
        with pytest.raises(ValueError, match="instagram_account_id required"):
            InstagramChannelConfig(access_token="tok", instagram_account_id="")


# ============================================================================
# FORMATTER TESTS
# ============================================================================


class TestInstagramFormatter:
    def test_format_text_only(self, simple_response: ChannelResponse) -> None:
        result = InstagramMessageFormatter.format_response(simple_response)
        assert result == "Hello, how can I help you?"

    def test_format_with_sources(self, response_with_sources: ChannelResponse) -> None:
        result = InstagramMessageFormatter.format_response(response_with_sources)
        assert "Here is the answer." in result
        assert "Fonti:" in result
        assert "1. Visa Guide" in result
        assert "https://example.com/visa" in result
        # Only first 3 sources shown
        assert "3. Local Doc" in result

    def test_format_sources_limited_to_three(self) -> None:
        response = ChannelResponse(
            text="Answer",
            sources=[
                {"title": f"Source {i}", "url": f"https://example.com/{i}"}
                for i in range(10)
            ],
            metadata={},
        )
        result = InstagramMessageFormatter.format_response(response)
        assert "Source 0" in result
        assert "Source 2" in result
        # Source 3 (4th) should NOT appear (limit is 3)
        assert "Source 3" not in result

    def test_format_empty_response(self) -> None:
        result = InstagramMessageFormatter.format_response(
            ChannelResponse(text="", metadata={})
        )
        assert result == ""

    def test_format_error(self) -> None:
        result = InstagramMessageFormatter.format_error("something broke")
        assert result == "❌ Errore: something broke"

    def test_format_source_without_url(self) -> None:
        response = ChannelResponse(
            text="Answer",
            sources=[{"title": "No URL Doc"}],
            metadata={},
        )
        result = InstagramMessageFormatter.format_response(response)
        assert "1. No URL Doc" in result


# ============================================================================
# ADAPTER TESTS
# ============================================================================


class TestInstagramAdapter:
    def test_adapter_properties(self, adapter: InstagramChannelAdapter) -> None:
        assert adapter.channel_name == "instagram"
        assert adapter.supports_markdown is False
        assert adapter.supports_media is True
        assert adapter.max_message_length == 1000

    async def test_receive_message_valid(
        self, adapter: InstagramChannelAdapter, sample_webhook: dict,
    ) -> None:
        msg = await adapter.receive_message(sample_webhook)
        assert msg.user_id == "instagram_9876543210"
        assert msg.session_id == "ig_session_9876543210"
        assert msg.text == "Ciao, quanto costa una PT PMA?"
        assert msg.channel == "instagram"
        assert msg.metadata["sender_id"] == "9876543210"
        assert msg.metadata["mid"] == "m_abc123def456"

    async def test_receive_message_empty_entry(
        self, adapter: InstagramChannelAdapter, empty_webhook: dict,
    ) -> None:
        msg = await adapter.receive_message(empty_webhook)
        assert msg.user_id == "instagram_unknown"
        assert msg.text == ""

    async def test_receive_message_malformed_raises(
        self, adapter: InstagramChannelAdapter,
    ) -> None:
        # entry is not a list -> IndexError
        with pytest.raises(Exception):
            await adapter.receive_message({"entry": "bad"})

    async def test_send_response(
        self, adapter: InstagramChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        await adapter.send_response("9876543210", simple_response)

        # Should call post twice: once for message, once for mark_seen
        assert adapter.client.post.call_count == 2
        first_call = adapter.client.post.call_args_list[0]
        assert "messages" in first_call.args[0]
        assert first_call.kwargs["json"]["recipient"]["id"] == "9876543210"

    async def test_send_response_truncates_long_message(
        self, adapter: InstagramChannelAdapter, long_response: ChannelResponse,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=MagicMock())

        await adapter.send_response("123", long_response)

        first_call = adapter.client.post.call_args_list[0]
        sent_text = first_call.kwargs["json"]["message"]["text"]
        assert len(sent_text) <= adapter.max_message_length

    async def test_send_response_api_error(
        self, adapter: InstagramChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(side_effect=Exception("API down"))

        # Adapter re-raises exceptions for DLQ routing via send_response_safe()
        with pytest.raises(Exception, match="API down"):
            await adapter.send_response("123", simple_response)

    async def test_send_status_update_noop(
        self, adapter: InstagramChannelAdapter,
    ) -> None:
        # Instagram doesn't support typing indicators, should be no-op
        await adapter.send_status_update("123", "typing")

    async def test_stream_response_accumulates(
        self, adapter: InstagramChannelAdapter,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=MagicMock())

        async def mock_stream():
            yield ChannelResponse(text="Hello ", metadata={})
            yield ChannelResponse(text="world!", metadata={})

        await adapter.stream_response("123", mock_stream())

        # Should have sent 1 message (accumulated) + 1 mark_seen
        first_call = adapter.client.post.call_args_list[0]
        sent_text = first_call.kwargs["json"]["message"]["text"]
        assert "Hello world!" in sent_text
