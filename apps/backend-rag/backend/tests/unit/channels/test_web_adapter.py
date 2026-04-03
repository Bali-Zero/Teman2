"""
Unit tests for Web Channel Adapter and Formatter.

Tests:
- Message parsing from web requests
- SSE event formatting
- Response formatting (rich Markdown)
- Stream response yields correct SSE events
- Helper formatters (thinking, tool_call, error, status)
- Config defaults
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.channels.base import ChannelResponse
from backend.channels.web.adapter import WebChannelAdapter
from backend.channels.web.config import WebChannelConfig
from backend.channels.web.formatter import WebMessageFormatter


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def web_config() -> dict:
    return {}


@pytest.fixture
def adapter(web_config: dict) -> WebChannelAdapter:
    return WebChannelAdapter(web_config)


@pytest.fixture
def sample_web_request() -> dict:
    return {
        "query": "What documents do I need for a KITAS?",
        "user_id": "user@example.com",
        "session_id": "web_session_abc123",
        "conversation_history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "conversation_id": "conv_42",
        "images": [],
    }


@pytest.fixture
def web_request_with_images() -> dict:
    return {
        "query": "What is this document?",
        "user_id": "vision_user",
        "session_id": "web_session_vision",
        "images": ["data:image/png;base64,iVBOR..."],
        "enable_vision": True,
    }


# ============================================================================
# CONFIG TESTS
# ============================================================================


class TestWebConfig:
    def test_defaults(self) -> None:
        cfg = WebChannelConfig()
        assert cfg.max_message_length == 100000
        assert cfg.supports_markdown is True
        assert cfg.supports_media is True
        assert cfg.stream_mode == "sse"
        assert cfg.include_metadata is True
        assert cfg.sse_retry_ms == 3000
        assert cfg.sse_heartbeat_interval == 30

    def test_custom_values(self) -> None:
        cfg = WebChannelConfig(max_message_length=50000, stream_mode="ws")
        assert cfg.max_message_length == 50000
        assert cfg.stream_mode == "ws"


# ============================================================================
# FORMATTER TESTS
# ============================================================================


class TestWebFormatter:
    def test_format_text_only(self, simple_response: ChannelResponse) -> None:
        result = WebMessageFormatter.format_response(simple_response)
        assert result == "Hello, how can I help you?"

    def test_format_with_sources(self, response_with_sources: ChannelResponse) -> None:
        result = WebMessageFormatter.format_response(response_with_sources)
        assert "Here is the answer." in result
        assert "## 📚 Fonti" in result
        assert "[Visa Guide](https://example.com/visa)" in result
        assert "_(visa_oracle)_" in result
        assert "3. Local Doc _(legal_unified)_" in result

    def test_format_with_workflow(self, response_with_workflow: ChannelResponse) -> None:
        result = WebMessageFormatter.format_response(response_with_workflow)
        assert "Follow these steps." in result
        assert "## 📋 Piano d'azione" in result
        assert "**PT PMA Setup:**" in result
        assert "1. Prepare documents" in result
        assert "3. Register at OSS" in result

    def test_format_sources_with_url(self) -> None:
        sources = [{"title": "Doc A", "url": "https://a.com", "collection": "col_a"}]
        result = WebMessageFormatter._format_sources(sources)
        assert result == "1. [Doc A](https://a.com) _(col_a)_"

    def test_format_sources_without_url(self) -> None:
        sources = [{"title": "Doc B", "collection": "col_b"}]
        result = WebMessageFormatter._format_sources(sources)
        assert result == "1. Doc B _(col_b)_"

    def test_format_workflow_no_steps(self) -> None:
        result = WebMessageFormatter._format_workflow({"name": "Simple Plan", "steps": []})
        assert result == "**Simple Plan**"

    def test_format_workflow_dict_steps(self) -> None:
        workflow = {
            "name": "Plan",
            "steps": [{"description": "Step A"}, {"action": "Step B"}],
        }
        result = WebMessageFormatter._format_workflow(workflow)
        assert "1. Step A" in result
        assert "2. Step B" in result

    def test_format_workflow_string_steps(self) -> None:
        workflow = {"name": "Plan", "steps": ["Do X", "Do Y"]}
        result = WebMessageFormatter._format_workflow(workflow)
        assert "1. Do X" in result
        assert "2. Do Y" in result

    def test_format_thinking(self) -> None:
        result = WebMessageFormatter.format_thinking("Analyzing the query...")
        assert result == "> 💭 Analyzing the query..."

    def test_format_tool_call_with_args(self) -> None:
        result = WebMessageFormatter.format_tool_call(
            "search_qdrant", {"query": "visa", "limit": 5},
        )
        assert result == "🔧 `search_qdrant(query=visa, limit=5)`"

    def test_format_tool_call_no_args(self) -> None:
        result = WebMessageFormatter.format_tool_call("get_pricing")
        assert result == "🔧 `get_pricing()`"

    def test_format_tool_call_limits_args(self) -> None:
        """Only first 2 args should be shown."""
        result = WebMessageFormatter.format_tool_call(
            "func", {"a": 1, "b": 2, "c": 3, "d": 4},
        )
        # Should contain exactly 2 arg pairs
        assert "a=1" in result
        assert "b=2" in result

    def test_format_error(self) -> None:
        result = WebMessageFormatter.format_error("Something went wrong")
        assert result == "❌ **Errore:** Something went wrong"

    def test_format_status_known(self) -> None:
        assert WebMessageFormatter.format_status("processing") == "⏳ Processing..."
        assert WebMessageFormatter.format_status("thinking") == "💭 Thinking..."
        assert WebMessageFormatter.format_status("searching") == "🔍 Searching..."
        assert WebMessageFormatter.format_status("analyzing") == "🔬 Analyzing..."
        assert WebMessageFormatter.format_status("complete") == "✅ Complete..."
        assert WebMessageFormatter.format_status("error") == "❌ Error..."

    def test_format_status_unknown(self) -> None:
        result = WebMessageFormatter.format_status("custom_status")
        assert result == "📍 Custom_status..."


# ============================================================================
# ADAPTER TESTS
# ============================================================================


class TestWebAdapter:
    def test_adapter_properties(self, adapter: WebChannelAdapter) -> None:
        assert adapter.channel_name == "web"
        assert adapter.supports_markdown is True
        assert adapter.supports_media is True
        assert adapter.max_message_length == 100000

    async def test_receive_message_valid(
        self, adapter: WebChannelAdapter, sample_web_request: dict,
    ) -> None:
        msg = await adapter.receive_message(sample_web_request)
        assert msg.user_id == "user@example.com"
        assert msg.session_id == "web_session_abc123"
        assert msg.text == "What documents do I need for a KITAS?"
        assert msg.channel == "web"
        assert msg.metadata["conversation_id"] == "conv_42"
        assert msg.metadata["conversation_history_length"] == 2
        assert msg.metadata["has_images"] is False
        assert msg.media is None

    async def test_receive_message_with_images(
        self, adapter: WebChannelAdapter, web_request_with_images: dict,
    ) -> None:
        msg = await adapter.receive_message(web_request_with_images)
        assert msg.user_id == "vision_user"
        assert msg.media is not None
        assert len(msg.media) == 1
        assert msg.metadata["has_images"] is True
        assert msg.metadata["enable_vision"] is True

    async def test_receive_message_defaults(
        self, adapter: WebChannelAdapter,
    ) -> None:
        msg = await adapter.receive_message({})
        assert msg.user_id == "anonymous"
        assert msg.session_id == "web_session_unknown"
        assert msg.text == ""
        assert msg.channel == "web"

    async def test_send_response_logs_warning(
        self, adapter: WebChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        # send_response for web is a no-op (should use stream_response)
        await adapter.send_response("session_123", simple_response)

    async def test_send_status_update(
        self, adapter: WebChannelAdapter,
    ) -> None:
        # Should not raise
        await adapter.send_status_update("session_123", "processing")

    def test_format_sse_event(self, adapter: WebChannelAdapter) -> None:
        event = {"type": "token", "data": "Hello"}
        result = adapter._format_sse_event(event)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result[len("data: "):].strip())
        assert parsed["type"] == "token"
        assert parsed["data"] == "Hello"

    def test_channel_response_to_sse_token(self, adapter: WebChannelAdapter) -> None:
        resp = ChannelResponse(text="Hi", metadata={"event_type": "token"})
        event = adapter._channel_response_to_sse(resp)
        assert event == {"type": "token", "data": "Hi"}

    def test_channel_response_to_sse_thinking(self, adapter: WebChannelAdapter) -> None:
        resp = ChannelResponse(text="Analyzing...", metadata={"event_type": "thinking"})
        event = adapter._channel_response_to_sse(resp)
        assert event == {"type": "thinking", "data": "Analyzing..."}

    def test_channel_response_to_sse_tool_call(self, adapter: WebChannelAdapter) -> None:
        meta = {"event_type": "tool_call", "tool": "search"}
        resp = ChannelResponse(text="", metadata=meta)
        event = adapter._channel_response_to_sse(resp)
        assert event["type"] == "tool_call"
        assert event["data"] == meta

    def test_channel_response_to_sse_sources(self, adapter: WebChannelAdapter) -> None:
        sources = [{"title": "Doc", "url": "https://x.com"}]
        resp = ChannelResponse(text="", sources=sources, metadata={"event_type": "sources"})
        event = adapter._channel_response_to_sse(resp)
        assert event == {"type": "sources", "data": sources}

    def test_channel_response_to_sse_workflow(self, adapter: WebChannelAdapter) -> None:
        wf = {"name": "Plan", "steps": []}
        resp = ChannelResponse(text="", workflow=wf, metadata={"event_type": "workflow"})
        event = adapter._channel_response_to_sse(resp)
        assert event == {"type": "workflow", "data": wf}

    def test_channel_response_to_sse_answer(self, adapter: WebChannelAdapter) -> None:
        sources = [{"title": "A"}]
        wf = {"name": "B"}
        resp = ChannelResponse(
            text="Final answer", sources=sources, workflow=wf,
            metadata={"event_type": "answer"},
        )
        event = adapter._channel_response_to_sse(resp)
        assert event["type"] == "answer"
        assert event["data"]["text"] == "Final answer"
        assert event["data"]["sources"] == sources
        assert event["data"]["workflow"] == wf

    def test_channel_response_to_sse_observation(self, adapter: WebChannelAdapter) -> None:
        resp = ChannelResponse(text="Found 5 docs", metadata={"event_type": "observation"})
        event = adapter._channel_response_to_sse(resp)
        assert event == {"type": "observation", "data": "Found 5 docs"}

    def test_channel_response_to_sse_unknown(self, adapter: WebChannelAdapter) -> None:
        resp = ChannelResponse(text="custom data", metadata={"event_type": "custom_evt"})
        event = adapter._channel_response_to_sse(resp)
        assert event["type"] == "custom_evt"
        assert event["data"] == "custom data"

    def test_channel_response_to_sse_default_token(self, adapter: WebChannelAdapter) -> None:
        """When no event_type in metadata, defaults to 'token'."""
        resp = ChannelResponse(text="Hello", metadata={})
        event = adapter._channel_response_to_sse(resp)
        assert event["type"] == "token"

    async def test_stream_response_yields_sse(self, adapter: WebChannelAdapter) -> None:
        async def mock_stream():
            yield ChannelResponse(text="Hello ", metadata={"event_type": "token"})
            yield ChannelResponse(text="world", metadata={"event_type": "token"})

        events: list[str] = []
        async for sse_str in adapter.stream_response("session_1", mock_stream()):
            events.append(sse_str)

        # Should have: status(processing) + token + token + status(completed) = 4
        assert len(events) == 4

        # First event: processing status
        first = json.loads(events[0][len("data: "):].strip())
        assert first["type"] == "status"
        assert first["data"]["status"] == "processing"

        # Last event: completed status
        last = json.loads(events[-1][len("data: "):].strip())
        assert last["type"] == "status"
        assert last["data"]["status"] == "completed"

        # Middle events: tokens
        tok1 = json.loads(events[1][len("data: "):].strip())
        assert tok1["type"] == "token"
        assert tok1["data"] == "Hello "

    async def test_stream_response_error_yields_error_event(
        self, adapter: WebChannelAdapter,
    ) -> None:
        async def failing_stream():
            yield ChannelResponse(text="start", metadata={})
            raise RuntimeError("Stream crashed")

        events: list[str] = []
        async for sse_str in adapter.stream_response("session_err", failing_stream()):
            events.append(sse_str)

        # Last event should be error
        last = json.loads(events[-1][len("data: "):].strip())
        assert last["type"] == "error"
        assert "Stream failed" in last["data"]["message"]
        assert last["data"]["fatal"] is True
