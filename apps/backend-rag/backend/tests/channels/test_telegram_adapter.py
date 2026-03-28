"""
Unit tests for TelegramChannelAdapter.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.channels.base import ChannelMessage, ChannelResponse
from backend.channels.telegram.adapter import TelegramChannelAdapter
from backend.channels.telegram.config import TelegramChannelConfig


@pytest.fixture
def telegram_config():
    """Create Telegram configuration for testing."""
    return {
        "bot_token": "test_bot_token_123",
        "max_message_length": 4096,
        "update_interval": 1.5,
        "parse_mode": "Markdown",
    }


@pytest.fixture
def telegram_adapter(telegram_config):
    """Create TelegramChannelAdapter instance."""
    return TelegramChannelAdapter(telegram_config)


def test_telegram_adapter_init(telegram_config):
    """Test TelegramChannelAdapter initialization."""
    adapter = TelegramChannelAdapter(telegram_config)

    assert adapter.channel_name == "telegram"
    assert adapter.supports_markdown is True
    assert adapter.supports_media is True
    assert adapter.max_message_length == 4096
    assert adapter.telegram_config.bot_token == "test_bot_token_123"
    assert adapter.telegram_config.update_interval == 1.5


@pytest.mark.asyncio
async def test_receive_message_text_only(telegram_adapter):
    """Test parsing Telegram update with text message."""
    update = {
        "update_id": 12345,
        "message": {
            "message_id": 789,
            "from": {
                "id": 123456789,
                "first_name": "John",
                "username": "john_doe",
            },
            "chat": {
                "id": 123456789,
                "type": "private",
            },
            "date": 1234567890,
            "text": "Hello bot!",
        },
    }

    message = await telegram_adapter.receive_message(update)

    assert isinstance(message, ChannelMessage)
    assert message.user_id == "telegram_123456789"
    assert message.session_id == "tg_session_123456789"
    assert message.text == "Hello bot!"
    assert message.channel == "telegram"
    assert message.metadata["chat_id"] == "123456789"
    assert message.metadata["username"] == "john_doe"
    assert message.metadata["first_name"] == "John"


@pytest.mark.asyncio
async def test_receive_message_with_photo(telegram_adapter):
    """Test parsing Telegram update with photo attachment."""
    update = {
        "update_id": 12345,
        "message": {
            "message_id": 789,
            "from": {"id": 123456789, "first_name": "John"},
            "chat": {"id": 123456789, "type": "private"},
            "date": 1234567890,
            "text": "Check this photo",
            "photo": [
                {"file_id": "small_photo_id", "width": 90, "height": 90},
                {"file_id": "large_photo_id", "width": 1280, "height": 720},
            ],
        },
    }

    message = await telegram_adapter.receive_message(update)

    assert message.media is not None
    assert len(message.media) == 1
    assert message.media[0] == "telegram://photo/large_photo_id"


@pytest.mark.asyncio
async def test_receive_message_no_message_field(telegram_adapter):
    """Test parsing Telegram update without message field."""
    update = {
        "update_id": 12345,
        # No message field (could be callback_query, etc.)
    }

    message = await telegram_adapter.receive_message(update)

    assert message.user_id == "unknown"
    assert message.session_id == "unknown"
    assert message.text == ""


@pytest.mark.asyncio
async def test_send_response(telegram_adapter):
    """Test sending a complete response via Telegram."""
    with patch.object(
        telegram_adapter.bot_service, "send_message", new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = {
            "ok": True,
            "result": {"message_id": 999, "chat": {"id": 123456789}},
        }

        response = ChannelResponse(
            text="Test response",
            sources=[{"title": "Source 1", "url": "https://example.com"}],
            metadata={},
        )

        await telegram_adapter.send_response("123456789", response)

        # Verify send_message was called
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args.kwargs["chat_id"] == "123456789"
        assert "Test response" in call_args.kwargs["text"]
        assert call_args.kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_send_status_update(telegram_adapter):
    """Test sending typing indicator."""
    with patch.object(
        telegram_adapter.bot_service, "send_chat_action", new_callable=AsyncMock,
    ) as mock_action:
        mock_action.return_value = True

        await telegram_adapter.send_status_update("123456789", "processing")

        mock_action.assert_called_once()
        call_args = mock_action.call_args
        assert call_args.kwargs["chat_id"] == "123456789"
        assert call_args.kwargs["action"] == "typing"


@pytest.mark.asyncio
async def test_stream_response(telegram_adapter):
    """Test streaming response with progressive updates."""
    with (
        patch.object(
            telegram_adapter.bot_service, "send_message", new_callable=AsyncMock,
        ) as mock_send,
        patch.object(
            telegram_adapter.bot_service, "edit_message_text", new_callable=AsyncMock,
        ) as mock_edit,
    ):
        # Mock initial message creation
        mock_send.return_value = {
            "ok": True,
            "result": {"message_id": 999, "chat": {"id": 123456789}},
        }

        # Mock message edits
        mock_edit.return_value = {"ok": True}

        # Create mock response stream
        async def mock_stream():
            # Yield tokens
            yield ChannelResponse(text="Hello ", metadata={"event_type": "token"})
            yield ChannelResponse(text="world!", metadata={"event_type": "token"})
            # Yield final answer
            yield ChannelResponse(text=" Complete.", metadata={"event_type": "answer"})

        # Stream response
        await telegram_adapter.stream_response("123456789", mock_stream())

        # Verify initial message was sent
        mock_send.assert_called_once()

        # Verify edits were made (at least once for final message)
        assert mock_edit.call_count >= 1


@pytest.mark.asyncio
async def test_truncate_long_message(telegram_adapter):
    """Test message truncation for long messages."""
    long_text = "A" * 5000  # Exceeds 4096 limit

    response = ChannelResponse(text=long_text, metadata={})

    with patch.object(
        telegram_adapter.bot_service, "send_message", new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = {"ok": True, "result": {"message_id": 999}}

        await telegram_adapter.send_response("123456789", response)

        # Verify message was truncated
        call_args = mock_send.call_args
        sent_text = call_args.kwargs["text"]
        assert len(sent_text) <= 4096
        assert "...continua..." in sent_text


def test_telegram_config_validation():
    """Test TelegramChannelConfig validation."""
    # Valid config
    config = TelegramChannelConfig(bot_token="test_token")
    assert config.bot_token == "test_token"

    # Invalid: empty bot_token
    with pytest.raises(ValueError, match="bot_token is required"):
        TelegramChannelConfig(bot_token="")

    # Invalid: max_message_length > 4096
    with pytest.raises(ValueError, match="cannot exceed 4096"):
        TelegramChannelConfig(bot_token="test", max_message_length=5000)

    # Invalid: update_interval < 1.0
    with pytest.raises(ValueError, match="must be >= 1.0 seconds"):
        TelegramChannelConfig(bot_token="test", update_interval=0.5)
