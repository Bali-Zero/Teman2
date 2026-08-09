"""
Unit tests for ChannelRouter.

Author: Claude Sonnet
Date: 2026-02-10
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.base import BaseChannel, ChannelMessage, ChannelResponse
from backend.channels.router import ChannelRouter


class MockChannel(BaseChannel):
    """Mock channel for testing."""

    def __init__(self, config: dict) -> None:
        # Initialize attributes BEFORE calling super().__init__()
        # because super().__init__() calls self.channel_name property
        self._channel_name = config.get("channel_name", "mock")
        self.receive_message_calls = []
        self.send_status_update_calls = []
        self.stream_response_calls = []
        super().__init__(config)

    async def receive_message(self, raw_event: dict):
        self.receive_message_calls.append(raw_event)
        return ChannelMessage(
            user_id=f"{self._channel_name}_user",
            session_id=f"{self._channel_name}_session",
            text=raw_event.get("text", ""),
            metadata=raw_event.get("metadata", {}),
            channel=self._channel_name,
        )

    async def send_response(self, channel_id: str, response: ChannelResponse):
        pass

    async def send_status_update(self, channel_id: str, status: str):
        self.send_status_update_calls.append((channel_id, status))

    async def stream_response(self, channel_id: str, response_stream):
        self.stream_response_calls.append(channel_id)
        # Consume the stream
        async for _ in response_stream:
            pass

    @property
    def channel_name(self):
        return self._channel_name

    @property
    def supports_markdown(self):
        return True

    @property
    def supports_media(self):
        return True

    @property
    def max_message_length(self):
        return 4096


@pytest.fixture
def mock_conversation_engine():
    """Mock ConversationEngine."""
    engine = MagicMock()

    async def mock_process_message(message, channel_config):
        yield ChannelResponse(text="Test response", metadata={"event_type": "token"})

    engine.process_message = mock_process_message
    return engine


@pytest.fixture
def channel_router(mock_conversation_engine):
    """Create ChannelRouter with mock engine."""
    return ChannelRouter(mock_conversation_engine)


def test_channel_router_init(mock_conversation_engine):
    """Test ChannelRouter initialization."""
    router = ChannelRouter(mock_conversation_engine)

    assert router.conversation_engine == mock_conversation_engine
    assert router.adapters == {}
    assert router.get_available_channels() == []


def test_register_adapter(channel_router):
    """Test registering channel adapters."""
    telegram_adapter = MockChannel({"channel_name": "telegram"})
    whatsapp_adapter = MockChannel({"channel_name": "whatsapp"})

    channel_router.register_adapter("telegram", telegram_adapter)
    channel_router.register_adapter("whatsapp", whatsapp_adapter)

    assert channel_router.is_channel_registered("telegram")
    assert channel_router.is_channel_registered("whatsapp")
    assert not channel_router.is_channel_registered("instagram")
    assert channel_router.get_available_channels() == ["telegram", "whatsapp"]


@pytest.mark.asyncio
async def test_route_message_success(channel_router):
    """Test successful message routing."""
    # Register mock adapter
    mock_adapter = MockChannel({"channel_name": "telegram", "timeout": 30.0})
    channel_router.register_adapter("telegram", mock_adapter)

    # Route message
    raw_event = {
        "text": "Hello world",
        "metadata": {"chat_id": "123456"},
    }

    await channel_router.route_message("telegram", raw_event)

    # Verify adapter was called
    assert len(mock_adapter.receive_message_calls) == 1
    assert len(mock_adapter.send_status_update_calls) == 1
    assert len(mock_adapter.stream_response_calls) == 1

    # Verify status update
    channel_id, status = mock_adapter.send_status_update_calls[0]
    assert channel_id == "123456"
    assert status == "processing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "route_channel",
        "normalized_channel",
        "trusted_whatsapp_ingress",
        "expected_trusted_whatsapp",
    ),
    [
        ("whatsapp", "whatsapp", True, True),
        ("instagram", "whatsapp", False, False),
        ("telegram", "telegram", False, False),
    ],
)
async def test_route_authority_not_message_body_controls_whatsapp_l0(
    route_channel: str,
    normalized_channel: str,
    trusted_whatsapp_ingress: bool,
    expected_trusted_whatsapp: bool,
) -> None:
    """Only the server-selected adapter key may arm WhatsApp's L0 lane."""
    calls: list[dict] = []

    class CapturingEngine:
        async def process_message(self, **kwargs):
            calls.append(kwargs)
            yield ChannelResponse(text="ok", metadata={"event_type": "answer"})

    router = ChannelRouter(CapturingEngine())
    adapter = MockChannel({"channel_name": route_channel})

    async def receive_message(_raw_event):
        return ChannelMessage(
            user_id="synthetic-user",
            session_id="synthetic-session",
            text="public question",
            metadata={"phone": "synthetic-phone"},
            channel=normalized_channel,
        )

    adapter.receive_message = receive_message
    router.register_adapter(route_channel, adapter)
    router._persist_message = AsyncMock(
        side_effect=AssertionError("persistence reached") if expected_trusted_whatsapp else None
    )
    router._enrich_with_routing = AsyncMock()
    deduplicator = MagicMock()
    deduplicator.is_duplicate = AsyncMock(
        side_effect=AssertionError("dedup received trusted WhatsApp data")
        if expected_trusted_whatsapp
        else None,
        return_value=False,
    )

    with patch("backend.channels.router.message_deduplicator", deduplicator):
        await router.route_message(
            route_channel,
            {"channel": "whatsapp"},
            trusted_whatsapp_ingress=trusted_whatsapp_ingress,
        )

    assert calls[0].get("trusted_whatsapp_ingress", False) is expected_trusted_whatsapp
    if expected_trusted_whatsapp:
        router._enrich_with_routing.assert_not_awaited()
        router._persist_message.assert_not_awaited()
        deduplicator.is_duplicate.assert_not_awaited()
    else:
        router._enrich_with_routing.assert_awaited_once()
        deduplicator.is_duplicate.assert_awaited_once()


@pytest.mark.asyncio
async def test_whatsapp_route_without_server_trust_fails_closed() -> None:
    class UnreachableEngine:
        def process_message(self, **_kwargs):
            raise AssertionError("ConversationEngine reached")

    router = ChannelRouter(UnreachableEngine())
    router.register_adapter("whatsapp", MockChannel({"channel_name": "whatsapp"}))

    with pytest.raises(ValueError, match="trusted WhatsApp ingress"):
        await router.route_message("whatsapp", {"channel": "whatsapp"})


@pytest.mark.asyncio
async def test_trusted_whatsapp_route_logs_no_raw_identifiers_or_errors(caplog) -> None:
    user_canary = "WHATSAPP_USER_LOG_CANARY"
    session_canary = "WHATSAPP_SESSION_LOG_CANARY"
    query_canary = "WHATSAPP_QUERY_LOG_CANARY"
    error_canary = "WHATSAPP_ROUTER_ERROR_CANARY"

    class ExplodingEngine:
        async def process_message(self, **_kwargs):
            raise RuntimeError(error_canary)
            yield  # pragma: no cover - preserve async-generator shape

    router = ChannelRouter(ExplodingEngine())
    adapter = MockChannel({"channel_name": "whatsapp"})

    async def receive_message(_raw_event):
        return ChannelMessage(
            user_id=user_canary,
            session_id=session_canary,
            text=query_canary,
            metadata={"phone": user_canary},
            channel="whatsapp",
        )

    adapter.receive_message = receive_message
    router.register_adapter("whatsapp", adapter)

    with caplog.at_level("INFO", logger="backend.channels.router"):
        with pytest.raises(RuntimeError, match=error_canary):
            await router.route_message(
                "whatsapp",
                {"text": query_canary},
                trusted_whatsapp_ingress=True,
            )

    for canary in (user_canary, session_canary, query_canary, error_canary):
        assert canary not in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_route_message_unregistered_channel(channel_router):
    """Test routing to unregistered channel raises error."""
    with pytest.raises(ValueError, match="Channel 'unknown' not registered"):
        await channel_router.route_message("unknown", {})


def test_extract_channel_id_telegram(channel_router):
    """Test extracting Telegram chat_id."""
    metadata = {"chat_id": "123456", "message_id": "789"}
    channel_id = channel_router._extract_channel_id(metadata)
    assert channel_id == "123456"


def test_extract_channel_id_whatsapp(channel_router):
    """Test extracting WhatsApp phone number."""
    metadata = {"phone_number": "+6281234567890"}
    channel_id = channel_router._extract_channel_id(metadata)
    assert channel_id == "+6281234567890"


def test_extract_channel_id_instagram(channel_router):
    """Test extracting Instagram thread_id."""
    metadata = {"thread_id": "ig_thread_123"}
    channel_id = channel_router._extract_channel_id(metadata)
    assert channel_id == "ig_thread_123"


def test_extract_channel_id_twitter(channel_router):
    """Test extracting Twitter conversation_id."""
    metadata = {"conversation_id": "tw_conv_456"}
    channel_id = channel_router._extract_channel_id(metadata)
    assert channel_id == "tw_conv_456"


def test_extract_channel_id_unknown(channel_router):
    """Test extracting from unknown metadata returns empty string."""
    metadata = {"unknown_field": "value"}
    channel_id = channel_router._extract_channel_id(metadata)
    assert channel_id == ""
