"""
Unit tests for WebChannelAdapter.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import json

import pytest

from backend.channels.base import ChannelMessage, ChannelResponse
from backend.channels.web.adapter import WebChannelAdapter
from backend.channels.web.config import WebChannelConfig


@pytest.fixture
def web_config():
    """Create Web configuration for testing."""
    return {
        "max_message_length": 100000,
        "supports_markdown": True,
        "supports_media": True,
        "stream_mode": "sse",
    }


@pytest.fixture
def web_adapter(web_config):
    """Create WebChannelAdapter instance."""
    return WebChannelAdapter(web_config)


def test_web_adapter_init(web_config):
    """Test WebChannelAdapter initialization."""
    adapter = WebChannelAdapter(web_config)

    assert adapter.channel_name == "web"
    assert adapter.supports_markdown is True
    assert adapter.supports_media is True
    assert adapter.max_message_length == 100000
    assert adapter.web_config.stream_mode == "sse"


@pytest.mark.asyncio
async def test_receive_message_basic(web_adapter):
    """Test parsing web request into ChannelMessage."""
    request = {
        "query": "What is the capital of France?",
        "user_id": "user@example.com",
        "session_id": "web_session_123",
    }

    message = await web_adapter.receive_message(request)

    assert isinstance(message, ChannelMessage)
    assert message.user_id == "user@example.com"
    assert message.session_id == "web_session_123"
    assert message.text == "What is the capital of France?"
    assert message.channel == "web"


@pytest.mark.asyncio
async def test_receive_message_with_history(web_adapter):
    """Test parsing web request with conversation history."""
    request = {
        "query": "Tell me more",
        "user_id": "user@example.com",
        "session_id": "web_session_123",
        "conversation_history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ],
    }

    message = await web_adapter.receive_message(request)

    assert message.metadata["conversation_history_length"] == 2


@pytest.mark.asyncio
async def test_receive_message_with_images(web_adapter):
    """Test parsing web request with image attachments."""
    request = {
        "query": "What's in this image?",
        "user_id": "user@example.com",
        "session_id": "web_session_123",
        "images": [{"base64": "data:image/png;base64,iVBORw0KG...", "name": "photo.png"}],
        "enable_vision": True,
    }

    message = await web_adapter.receive_message(request)

    assert message.media is not None
    assert len(message.media) == 1
    assert message.metadata["has_images"] is True
    assert message.metadata["enable_vision"] is True


@pytest.mark.asyncio
async def test_stream_response_sse_format(web_adapter):
    """Test SSE streaming format."""

    # Create mock response stream
    async def mock_stream():
        yield ChannelResponse(text="Hello", metadata={"event_type": "token"})
        yield ChannelResponse(text=" world", metadata={"event_type": "token"})
        yield ChannelResponse(
            text="Hello world",
            sources=[{"title": "Source 1", "url": "https://example.com"}],
            metadata={"event_type": "answer"},
        )

    # Collect SSE events
    sse_events = []
    async for sse_event in web_adapter.stream_response("correlation_123", mock_stream()):
        sse_events.append(sse_event)

    # Verify SSE format
    assert len(sse_events) > 0

    # First event should be status
    first_event = sse_events[0]
    assert first_event.startswith("data: ")
    event_data = json.loads(first_event.replace("data: ", "").strip())
    assert event_data["type"] == "status"
    assert event_data["data"]["status"] == "processing"

    # Should contain token events
    token_events = [e for e in sse_events if '"type": "token"' in e]
    assert len(token_events) >= 2

    # Last event should be completed status
    last_event = sse_events[-1]
    event_data = json.loads(last_event.replace("data: ", "").strip())
    assert event_data["type"] == "status"
    assert event_data["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_channel_response_to_sse_token(web_adapter):
    """Test converting token event to SSE."""
    response = ChannelResponse(text="Hello", metadata={"event_type": "token"})

    sse_event = web_adapter._channel_response_to_sse(response)

    assert sse_event["type"] == "token"
    assert sse_event["data"] == "Hello"


@pytest.mark.asyncio
async def test_channel_response_to_sse_thinking(web_adapter):
    """Test converting thinking event to SSE."""
    response = ChannelResponse(text="Let me analyze this...", metadata={"event_type": "thinking"})

    sse_event = web_adapter._channel_response_to_sse(response)

    assert sse_event["type"] == "thinking"
    assert sse_event["data"] == "Let me analyze this..."


@pytest.mark.asyncio
async def test_channel_response_to_sse_sources(web_adapter):
    """Test converting sources event to SSE."""
    sources = [
        {"title": "Source 1", "url": "https://example.com/1"},
        {"title": "Source 2", "url": "https://example.com/2"},
    ]
    response = ChannelResponse(text="", sources=sources, metadata={"event_type": "sources"})

    sse_event = web_adapter._channel_response_to_sse(response)

    assert sse_event["type"] == "sources"
    assert sse_event["data"] == sources


@pytest.mark.asyncio
async def test_channel_response_to_sse_workflow(web_adapter):
    """Test converting workflow event to SSE."""
    workflow = {
        "name": "PT PMA Setup",
        "steps": ["Step 1", "Step 2", "Step 3"],
    }
    response = ChannelResponse(text="", workflow=workflow, metadata={"event_type": "workflow"})

    sse_event = web_adapter._channel_response_to_sse(response)

    assert sse_event["type"] == "workflow"
    assert sse_event["data"] == workflow


@pytest.mark.asyncio
async def test_channel_response_to_sse_answer(web_adapter):
    """Test converting final answer event to SSE."""
    response = ChannelResponse(
        text="Complete answer",
        sources=[{"title": "Source 1", "url": "https://example.com"}],
        workflow={"name": "Workflow", "steps": []},
        metadata={"event_type": "answer"},
    )

    sse_event = web_adapter._channel_response_to_sse(response)

    assert sse_event["type"] == "answer"
    assert sse_event["data"]["text"] == "Complete answer"
    assert sse_event["data"]["sources"] is not None
    assert sse_event["data"]["workflow"] is not None


def test_format_sse_event(web_adapter):
    """Test SSE event formatting."""
    event = {"type": "token", "data": "Hello"}

    sse_string = web_adapter._format_sse_event(event)

    assert sse_string.startswith("data: ")
    assert sse_string.endswith("\n\n")

    # Verify JSON is valid
    json_str = sse_string.replace("data: ", "").strip()
    parsed = json.loads(json_str)
    assert parsed["type"] == "token"
    assert parsed["data"] == "Hello"


@pytest.mark.asyncio
async def test_stream_response_error_handling(web_adapter):
    """Test error handling in SSE streaming."""

    # Create mock stream that raises error
    async def error_stream():
        yield ChannelResponse(text="Hello", metadata={"event_type": "token"})
        raise ValueError("Test error")

    # Collect SSE events
    sse_events = []
    async for sse_event in web_adapter.stream_response("correlation_123", error_stream()):
        sse_events.append(sse_event)

    # Should contain error event
    error_events = [e for e in sse_events if '"type": "error"' in e]
    assert len(error_events) == 1

    # Parse error event
    error_event = error_events[0]
    event_data = json.loads(error_event.replace("data: ", "").strip())
    assert event_data["type"] == "error"
    assert "Test error" in event_data["data"]["message"]


def test_web_config_defaults():
    """Test WebChannelConfig default values."""
    config = WebChannelConfig()

    assert config.max_message_length == 100000
    assert config.supports_markdown is True
    assert config.supports_media is True
    assert config.stream_mode == "sse"
