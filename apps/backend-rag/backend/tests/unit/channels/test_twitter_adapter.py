"""
Unit tests for Twitter/X Channel Adapter and Formatter.

Tests:
- Message parsing from X webhook (Account Activity API)
- OAuth 1.0a header generation
- Response formatting (plain text)
- Send response via X API v2
- Error handling
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
from backend.channels.twitter.adapter import TwitterChannelAdapter
from backend.channels.twitter.config import TwitterChannelConfig
from backend.channels.twitter.formatter import TwitterMessageFormatter


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def tw_config() -> dict:
    return {
        "consumer_key": "ck_test",
        "consumer_secret": "cs_test",
        "access_token": "at_test",
        "access_token_secret": "ats_test",
        "bearer_token": "bt_test",
    }


@pytest.fixture
def adapter(tw_config: dict) -> TwitterChannelAdapter:
    return TwitterChannelAdapter(tw_config)


@pytest.fixture
def sample_dm_webhook() -> dict:
    """Realistic X Account Activity API DM webhook."""
    return {
        "direct_message_events": [
            {
                "type": "message_create",
                "id": "1234567890",
                "created_timestamp": "1700000000000",
                "message_create": {
                    "sender_id": "111222333",
                    "target": {"recipient_id": "444555666"},
                    "message_data": {
                        "text": "What visa do I need for Bali?",
                        "entities": {},
                    },
                },
            }
        ],
        "for_user_id": "444555666",
    }


@pytest.fixture
def empty_dm_webhook() -> dict:
    """Webhook with no DM events."""
    return {"direct_message_events": []}


# ============================================================================
# CONFIG TESTS
# ============================================================================


class TestTwitterConfig:
    def test_valid_config(self) -> None:
        cfg = TwitterChannelConfig(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )
        assert cfg.max_message_length == 10000
        assert cfg.supports_markdown is False
        assert cfg.supports_media is True

    def test_missing_consumer_key_raises(self) -> None:
        with pytest.raises(ValueError, match="consumer_key and consumer_secret required"):
            TwitterChannelConfig(
                consumer_key="",
                consumer_secret="cs",
                access_token="at",
                access_token_secret="ats",
            )

    def test_missing_consumer_secret_raises(self) -> None:
        with pytest.raises(ValueError, match="consumer_key and consumer_secret required"):
            TwitterChannelConfig(
                consumer_key="ck",
                consumer_secret="",
                access_token="at",
                access_token_secret="ats",
            )

    def test_missing_access_token_raises(self) -> None:
        with pytest.raises(ValueError, match="access_token and access_token_secret required"):
            TwitterChannelConfig(
                consumer_key="ck",
                consumer_secret="cs",
                access_token="",
                access_token_secret="ats",
            )

    def test_missing_access_token_secret_raises(self) -> None:
        with pytest.raises(ValueError, match="access_token and access_token_secret required"):
            TwitterChannelConfig(
                consumer_key="ck",
                consumer_secret="cs",
                access_token="at",
                access_token_secret="",
            )

    def test_optional_fields_default(self) -> None:
        cfg = TwitterChannelConfig(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )
        assert cfg.bearer_token == ""
        assert cfg.client_id == ""
        assert cfg.client_secret == ""


# ============================================================================
# FORMATTER TESTS
# ============================================================================


class TestTwitterFormatter:
    def test_format_text_only(self, simple_response: ChannelResponse) -> None:
        result = TwitterMessageFormatter.format_response(simple_response)
        assert result == "Hello, how can I help you?"

    def test_format_with_sources(self, response_with_sources: ChannelResponse) -> None:
        result = TwitterMessageFormatter.format_response(response_with_sources)
        assert "Here is the answer." in result
        assert "Sources:" in result
        assert "1. Visa Guide https://example.com/visa" in result
        assert "2. Tax Info https://example.com/tax" in result

    def test_format_sources_max_three(self) -> None:
        response = ChannelResponse(
            text="Answer",
            sources=[
                {"title": f"S{i}", "url": f"https://x.com/{i}"} for i in range(10)
            ],
            metadata={},
        )
        result = TwitterMessageFormatter.format_response(response)
        assert "S0" in result
        assert "S2" in result
        assert "S3" not in result

    def test_format_source_no_url(self) -> None:
        response = ChannelResponse(
            text="Answer",
            sources=[{"title": "Offline Source"}],
            metadata={},
        )
        result = TwitterMessageFormatter.format_response(response)
        assert "1. Offline Source " in result

    def test_format_error(self) -> None:
        result = TwitterMessageFormatter.format_error("oops")
        assert result == "❌ Error: oops"

    def test_format_empty_text(self) -> None:
        result = TwitterMessageFormatter.format_response(
            ChannelResponse(text="", metadata={})
        )
        assert result == ""


# ============================================================================
# ADAPTER TESTS
# ============================================================================


class TestTwitterAdapter:
    def test_adapter_properties(self, adapter: TwitterChannelAdapter) -> None:
        assert adapter.channel_name == "twitter"
        assert adapter.supports_markdown is False
        assert adapter.supports_media is True
        assert adapter.max_message_length == 10000

    async def test_receive_message_valid(
        self, adapter: TwitterChannelAdapter, sample_dm_webhook: dict,
    ) -> None:
        msg = await adapter.receive_message(sample_dm_webhook)
        assert msg.user_id == "twitter_111222333"
        assert msg.session_id == "tw_session_111222333"
        assert msg.text == "What visa do I need for Bali?"
        assert msg.channel == "twitter"
        assert msg.metadata["sender_id"] == "111222333"

    async def test_receive_message_no_events(
        self, adapter: TwitterChannelAdapter, empty_dm_webhook: dict,
    ) -> None:
        msg = await adapter.receive_message(empty_dm_webhook)
        assert msg.user_id == "unknown"
        assert msg.text == ""

    async def test_receive_message_malformed_raises(
        self, adapter: TwitterChannelAdapter,
    ) -> None:
        with pytest.raises(Exception):
            await adapter.receive_message({"direct_message_events": "bad"})

    def test_oauth1_header_structure(self, adapter: TwitterChannelAdapter) -> None:
        header = adapter._oauth1_header("POST", "https://api.x.com/2/dm_conversations/with/123/messages")
        assert header.startswith("OAuth ")
        assert "oauth_consumer_key" in header
        assert "oauth_signature" in header
        assert "oauth_nonce" in header
        assert "oauth_timestamp" in header
        assert "oauth_version" in header

    def test_oauth1_header_different_nonce(self, adapter: TwitterChannelAdapter) -> None:
        """Two calls should produce different nonces."""
        h1 = adapter._oauth1_header("POST", "https://api.x.com/2/test")
        h2 = adapter._oauth1_header("POST", "https://api.x.com/2/test")
        # Nonces should differ (UUIDs)
        assert h1 != h2

    async def test_send_response_success(
        self, adapter: TwitterChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        await adapter.send_response("111222333", simple_response)

        adapter.client.post.assert_called_once()
        call_args = adapter.client.post.call_args
        assert "dm_conversations/with/111222333/messages" in call_args.args[0]
        assert call_args.kwargs["json"]["text"] == "Hello, how can I help you?"

    async def test_send_response_api_error_status(
        self, adapter: TwitterChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        # Should not raise
        await adapter.send_response("123", simple_response)

    async def test_send_response_network_error(
        self, adapter: TwitterChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(side_effect=Exception("Network error"))

        # Should not raise
        await adapter.send_response("123", simple_response)

    async def test_send_response_truncates(
        self, adapter: TwitterChannelAdapter, long_response: ChannelResponse,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        await adapter.send_response("123", long_response)

        sent_text = adapter.client.post.call_args.kwargs["json"]["text"]
        assert len(sent_text) <= adapter.max_message_length

    async def test_send_status_update_noop(
        self, adapter: TwitterChannelAdapter,
    ) -> None:
        await adapter.send_status_update("123", "typing")

    async def test_stream_response_accumulates(
        self, adapter: TwitterChannelAdapter,
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_resp)

        async def mock_stream():
            yield ChannelResponse(text="Part A ", metadata={})
            yield ChannelResponse(text="Part B", metadata={})

        await adapter.stream_response("123", mock_stream())

        sent_text = adapter.client.post.call_args.kwargs["json"]["text"]
        assert "Part A Part B" in sent_text

    async def test_stream_response_empty_stream(
        self, adapter: TwitterChannelAdapter,
    ) -> None:
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock()

        async def empty_stream():
            return
            yield  # noqa: unreachable - makes it an async generator

        await adapter.stream_response("123", empty_stream())
        adapter.client.post.assert_not_called()
