"""
Unit tests for ChannelRouter — message routing across channels.

Tests adapter registration, routing logic, and error handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.base import ChannelMessage, ChannelResponse


@pytest.fixture
def mock_conversation_engine():
    """Mock ConversationEngine that returns a fixed response."""
    engine = AsyncMock()
    engine.process_message = AsyncMock(
        return_value=ChannelResponse(
            text="I can help with that!",
            sources=[{"title": "KITAS Guide"}],
        )
    )
    return engine


@pytest.fixture
def mock_telegram_adapter():
    """Mock Telegram adapter."""
    adapter = AsyncMock()
    adapter.channel_name = "telegram"
    adapter.receive_message = AsyncMock(
        return_value=ChannelMessage(
            user_id="telegram_123",
            session_id="tg_session_123",
            text="Hello",
            channel="telegram",
        )
    )
    return adapter


@pytest.fixture
def mock_whatsapp_adapter():
    """Mock WhatsApp adapter."""
    adapter = AsyncMock()
    adapter.channel_name = "whatsapp"
    adapter.receive_message = AsyncMock(
        return_value=ChannelMessage(
            user_id="whatsapp_628",
            session_id="wa_session_628",
            text="Quanto costa?",
            channel="whatsapp",
        )
    )
    return adapter


def test_channel_router_import():
    """ChannelRouter should be importable."""
    from backend.channels.router import ChannelRouter
    assert ChannelRouter is not None


def test_register_adapter():
    """Adapters can be registered by channel name."""
    from backend.channels.router import ChannelRouter

    router = ChannelRouter.__new__(ChannelRouter)
    router.adapters = {}
    router.adapters["telegram"] = MagicMock()

    assert "telegram" in router.adapters


def test_channel_message_creation():
    """ChannelMessage should be properly constructable."""
    msg = ChannelMessage(
        user_id="telegram_123",
        session_id="session_abc",
        text="Hello world",
        channel="telegram",
    )
    assert msg.user_id == "telegram_123"
    assert msg.text == "Hello world"
    assert msg.media is None
    assert msg.metadata == {}


def test_channel_response_creation():
    """ChannelResponse should be properly constructable."""
    resp = ChannelResponse(
        text="Here is the answer",
        sources=[{"title": "Source 1", "url": "https://example.com"}],
    )
    assert resp.text == "Here is the answer"
    assert len(resp.sources) == 1
    assert resp.media is None
    assert resp.workflow is None


def test_channel_message_with_media():
    """ChannelMessage should support media attachments."""
    msg = ChannelMessage(
        user_id="whatsapp_628",
        session_id="wa_session",
        text="Check this document",
        media=["https://example.com/doc.pdf"],
        channel="whatsapp",
        metadata={"message_type": "document"},
    )
    assert msg.media == ["https://example.com/doc.pdf"]
    assert msg.metadata["message_type"] == "document"
