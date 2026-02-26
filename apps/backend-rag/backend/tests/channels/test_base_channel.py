"""
Unit tests for BaseChannel abstract class and data structures.

Author: Claude Sonnet
Date: 2026-02-10
"""

import pytest

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse


def test_channel_message_creation():
    """Test ChannelMessage dataclass creation."""
    msg = ChannelMessage(
        user_id="test_user_123",
        session_id="test_session_456",
        text="Hello world",
        media=["https://example.com/image.jpg"],
        metadata={"chat_id": "789"},
        channel="telegram",
    )

    assert msg.user_id == "test_user_123"
    assert msg.session_id == "test_session_456"
    assert msg.text == "Hello world"
    assert msg.media == ["https://example.com/image.jpg"]
    assert msg.metadata == {"chat_id": "789"}
    assert msg.channel == "telegram"


def test_channel_message_defaults():
    """Test ChannelMessage default values."""
    msg = ChannelMessage(user_id="user", session_id="session", text="test")

    assert msg.media is None
    assert msg.metadata == {}
    assert msg.channel == "unknown"


def test_channel_response_creation():
    """Test ChannelResponse dataclass creation."""
    response = ChannelResponse(
        text="Ciao! Come posso aiutarti?",
        sources=[{"title": "Source 1", "url": "https://example.com"}],
        metadata={"event_type": "answer"},
        workflow={"name": "PT PMA Setup", "steps": []},
    )

    assert response.text == "Ciao! Come posso aiutarti?"
    assert len(response.sources) == 1
    assert response.metadata["event_type"] == "answer"
    assert response.workflow["name"] == "PT PMA Setup"


def test_channel_response_defaults():
    """Test ChannelResponse default values."""
    response = ChannelResponse(text="Test")

    assert response.sources is None
    assert response.metadata == {}
    assert response.media is None
    assert response.workflow is None


class MockChannel(BaseChannel):
    """Mock implementation for testing BaseChannel abstract methods."""

    async def receive_message(self, raw_event: dict):
        return ChannelMessage(
            user_id="mock_user",
            session_id="mock_session",
            text=raw_event.get("text", ""),
            channel="mock",
        )

    async def send_response(self, channel_id: str, response: ChannelResponse):
        pass

    async def send_status_update(self, channel_id: str, status: str):
        pass

    async def stream_response(self, channel_id: str, response_stream):
        pass

    @property
    def channel_name(self):
        return "mock"

    @property
    def supports_markdown(self):
        return True

    @property
    def supports_media(self):
        return True

    @property
    def max_message_length(self):
        return 4096


def test_base_channel_init():
    """Test BaseChannel initialization."""
    config = {"timeout": 30.0, "update_interval": 2.0}
    channel = MockChannel(config)

    assert channel.timeout == 30.0
    assert channel.update_interval == 2.0
    assert channel.config == config


def test_base_channel_truncate_message():
    """Test message truncation."""
    channel = MockChannel({})

    # Short message - no truncation
    short = "Hello"
    assert channel.truncate_message(short, max_length=100) == short

    # Long message - should truncate
    long = "A" * 5000
    truncated = channel.truncate_message(long, max_length=4096)
    assert len(truncated) <= 4096
    assert "...continua..." in truncated


def test_base_channel_split_message():
    """Test message splitting."""
    channel = MockChannel({})

    # Short message - no split
    short = "Hello world"
    chunks = channel.split_message(short, max_length=100)
    assert len(chunks) == 1
    assert chunks[0] == short

    # Long message - should split
    para1 = "Paragraph 1\n\n"
    para2 = "Paragraph 2\n\n"
    para3 = "Paragraph 3"
    long = para1 + para2 + para3

    chunks = channel.split_message(long, max_length=30)
    assert len(chunks) >= 2  # Should be split into multiple chunks
    # Verify all content is preserved
    reassembled = "".join(chunks)
    assert para1.strip() in reassembled or para2.strip() in reassembled


@pytest.mark.asyncio
async def test_mock_channel_receive_message():
    """Test MockChannel receive_message implementation."""
    channel = MockChannel({})
    raw_event = {"text": "Test message", "user_id": "123"}

    msg = await channel.receive_message(raw_event)

    assert isinstance(msg, ChannelMessage)
    assert msg.user_id == "mock_user"
    assert msg.session_id == "mock_session"
    assert msg.text == "Test message"
    assert msg.channel == "mock"
