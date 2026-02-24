"""Tests for channel adapters — formatting and parsing."""

import pytest

from nuzantara_graph.channels import (
    WebChannelAdapter,
    TelegramChannelAdapter,
    WhatsAppChannelAdapter,
    get_channel_adapter,
)
from nuzantara_graph.channels.base import ChannelAdapter
from nuzantara_schemas.state import ChannelType, GraphState


def _make_state(**overrides) -> GraphState:
    """Create a GraphState with sensible defaults for channel tests."""
    defaults = {
        "query": "What is a PT PMA?",
        "answer": "A PT PMA is a foreign-owned limited liability company in Indonesia.",
        "sources": [
            {"title": "Company Guide", "id": "cg1"},
            {"title": "BKPM Regulation", "id": "bkpm1"},
        ],
        "intent": "business_setup",
        "domain": "pt_pma",
    }
    defaults.update(overrides)
    return GraphState(**defaults)


class TestGetChannelAdapter:
    def test_web_adapter(self):
        adapter = get_channel_adapter(ChannelType.WEB)
        assert isinstance(adapter, WebChannelAdapter)

    def test_telegram_adapter(self):
        adapter = get_channel_adapter(ChannelType.TELEGRAM)
        assert isinstance(adapter, TelegramChannelAdapter)

    def test_whatsapp_adapter(self):
        adapter = get_channel_adapter(ChannelType.WHATSAPP)
        assert isinstance(adapter, WhatsAppChannelAdapter)

    def test_unknown_falls_back_to_web(self):
        # Instagram/Twitter not implemented yet → fall back to web
        adapter = get_channel_adapter(ChannelType.INSTAGRAM)
        assert isinstance(adapter, WebChannelAdapter)


class TestWebChannel:
    def test_format_includes_answer(self):
        adapter = WebChannelAdapter()
        state = _make_state()
        result = adapter.format_response(state)
        assert "PT PMA" in result["text"]

    def test_format_includes_sources(self):
        adapter = WebChannelAdapter()
        state = _make_state()
        result = adapter.format_response(state)
        assert "Company Guide" in result["text"]
        assert "Sources" in result["text"]

    def test_format_includes_confidence(self):
        adapter = WebChannelAdapter()
        state = _make_state()
        result = adapter.format_response(state)
        assert "confidence" in result["text"].lower()

    def test_metadata_has_run_id(self):
        adapter = WebChannelAdapter()
        state = _make_state()
        result = adapter.format_response(state)
        assert "run_id" in result["metadata"]

    def test_supports_streaming(self):
        adapter = WebChannelAdapter()
        assert adapter.supports_streaming is True
        assert adapter.supports_markdown is True

    def test_parse_incoming(self):
        adapter = WebChannelAdapter()
        result = adapter.parse_incoming({
            "query": "Hello",
            "user_id": "u1",
            "session_id": "s1",
        })
        assert result["query"] == "Hello"
        assert result["user_id"] == "u1"


class TestTelegramChannel:
    def test_format_truncates_at_4096(self):
        adapter = TelegramChannelAdapter()
        long_answer = "A" * 5000
        state = _make_state(answer=long_answer)
        result = adapter.format_response(state)
        assert len(result["text"]) <= 4096

    def test_format_has_parse_mode(self):
        adapter = TelegramChannelAdapter()
        state = _make_state()
        result = adapter.format_response(state)
        assert result["parse_mode"] == "MarkdownV2"

    def test_supports_streaming(self):
        adapter = TelegramChannelAdapter()
        assert adapter.supports_streaming is True

    def test_parse_message(self):
        adapter = TelegramChannelAdapter()
        result = adapter.parse_incoming({
            "message": {
                "text": "Hello bot",
                "from": {"id": 12345, "first_name": "Zero"},
                "chat": {"id": 67890},
                "message_id": 1,
            },
        })
        assert result["query"] == "Hello bot"
        assert result["user_id"] == "12345"
        assert result["metadata"]["chat_id"] == 67890

    def test_parse_callback_query(self):
        adapter = TelegramChannelAdapter()
        result = adapter.parse_incoming({
            "callback_query": {
                "data": "select_pt_pma",
                "from": {"id": 12345},
                "message": {
                    "chat": {"id": 67890},
                    "message_id": 2,
                },
            },
        })
        assert result["query"] == "select_pt_pma"
        assert result["metadata"]["is_callback"] is True

    def test_escape_markdown_v2(self):
        escaped = TelegramChannelAdapter.escape_markdown_v2("Hello *world*!")
        assert "\\*" in escaped
        assert "\\!" in escaped


class TestWhatsAppChannel:
    def test_format_truncates_at_1600(self):
        adapter = WhatsAppChannelAdapter()
        long_answer = "A" * 2000
        state = _make_state(answer=long_answer)
        result = adapter.format_response(state)
        assert len(result["text"]) <= 1600

    def test_format_strips_markdown(self):
        adapter = WhatsAppChannelAdapter()
        state = _make_state(answer="**Bold** and *italic* text")
        result = adapter.format_response(state)
        assert "**" not in result["text"]
        assert "*" not in result["text"]
        assert "Bold" in result["text"]
        assert "italic" in result["text"]

    def test_no_streaming(self):
        adapter = WhatsAppChannelAdapter()
        assert adapter.supports_streaming is False
        assert adapter.supports_markdown is False

    def test_parse_webhook(self):
        adapter = WhatsAppChannelAdapter()
        result = adapter.parse_incoming({
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "text": {"body": "Hello from WhatsApp"},
                            "from": "6281234567890",
                            "id": "wamid.123",
                            "timestamp": "1234567890",
                        }],
                        "metadata": {"phone_number_id": "pn123"},
                    },
                }],
            }],
        })
        assert result["query"] == "Hello from WhatsApp"
        assert result["user_id"] == "6281234567890"
        assert result["metadata"]["wa_id"] == "wamid.123"

    def test_parse_empty_webhook(self):
        adapter = WhatsAppChannelAdapter()
        result = adapter.parse_incoming({"entry": []})
        assert result["query"] == ""
        assert result["metadata"]["empty"] is True

    def test_compact_sources(self):
        adapter = WhatsAppChannelAdapter()
        state = _make_state(sources=[
            {"title": f"Source {i}", "id": f"s{i}"} for i in range(1, 11)
        ])
        result = adapter.format_response(state)
        # Only first 3 sources due to length constraints
        assert "Source 1" in result["text"]
        assert "Source 3" in result["text"]
        assert "Source 4" not in result["text"]


class TestBaseChannelAdapter:
    def test_truncate_short_text(self):
        adapter = WebChannelAdapter()
        assert adapter.truncate("hello") == "hello"

    def test_truncate_long_text(self):
        adapter = TelegramChannelAdapter()
        long_text = "A" * 5000
        result = adapter.truncate(long_text)
        assert len(result) == 4096
        assert result.endswith("...")

    def test_format_sources_empty(self):
        adapter = WebChannelAdapter()
        state = _make_state(sources=[])
        sources = adapter._format_sources(state)
        assert sources == ""

    def test_format_confidence_high(self):
        adapter = WebChannelAdapter()
        state = _make_state()
        # Default confidence is all 0.0 → low
        text = adapter._format_confidence(state)
        assert "Low confidence" in text
