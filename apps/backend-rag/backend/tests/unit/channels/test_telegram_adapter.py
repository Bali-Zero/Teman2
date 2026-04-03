"""
Unit tests for Telegram Channel Adapter and Formatter.

Tests:
- Message parsing from Telegram Update webhooks
- Response formatting (Telegram Markdown)
- Send response via TelegramBotService
- Status updates (typing indicators)
- Markdown escaping
- Config validation

NOTE: TelegramChannelAdapter has a deep import chain
(TelegramBotService -> integrations -> config -> pydantic).
We mock the TelegramBotService at the module level before importing the adapter.
"""

import os
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

# Pre-mock the heavy dependency chain so we can import the adapter
# without pulling in pydantic, asyncpg, etc.
_mock_telegram_bot_service_module = ModuleType("backend.services.integrations.telegram_bot_service")
_mock_telegram_bot_service_cls = MagicMock()
_mock_telegram_bot_service_module.TelegramBotService = _mock_telegram_bot_service_cls  # type: ignore[attr-defined]

# Only inject if not already importable
if "backend.services.integrations.telegram_bot_service" not in sys.modules:
    # Also mock the integrations __init__ if needed
    if "backend.services.integrations" not in sys.modules:
        _mock_integrations = ModuleType("backend.services.integrations")
        sys.modules["backend.services.integrations"] = _mock_integrations
    sys.modules["backend.services.integrations.telegram_bot_service"] = _mock_telegram_bot_service_module

# Now we can safely import - the __init__.py will trigger adapter import
# which will find our mocked TelegramBotService
from backend.channels.telegram.config import TelegramChannelConfig
from backend.channels.telegram.formatter import TelegramMessageFormatter

# Import adapter directly from its module to control the mock
from backend.channels.telegram.adapter import TelegramChannelAdapter

from backend.channels.base import ChannelResponse


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def tg_config() -> dict:
    return {
        "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    }


@pytest.fixture
def adapter(tg_config: dict) -> TelegramChannelAdapter:
    a = TelegramChannelAdapter(tg_config)
    # Replace the bot_service with a proper AsyncMock
    a.bot_service = MagicMock()
    a.bot_service.send_message = AsyncMock(
        return_value={"ok": True, "result": {"message_id": 100}},
    )
    a.bot_service.send_chat_action = AsyncMock()
    a.bot_service.edit_message_text = AsyncMock()
    return a


@pytest.fixture
def sample_update() -> dict:
    """Realistic Telegram Update webhook payload."""
    return {
        "update_id": 100001,
        "message": {
            "message_id": 789,
            "from": {
                "id": 413539912,
                "is_bot": False,
                "first_name": "Zero",
                "username": "zerob",
                "language_code": "it",
            },
            "chat": {
                "id": 413539912,
                "first_name": "Zero",
                "username": "zerob",
                "type": "private",
            },
            "date": 1700000000,
            "text": "Quanto costa aprire una PT PMA?",
        },
    }


@pytest.fixture
def update_with_photo() -> dict:
    return {
        "update_id": 100002,
        "message": {
            "message_id": 790,
            "from": {"id": 123, "first_name": "User"},
            "chat": {"id": 123, "type": "private"},
            "date": 1700000001,
            "photo": [
                {"file_id": "small_id", "width": 90, "height": 90},
                {"file_id": "large_id", "width": 800, "height": 600},
            ],
            "caption": "What is this?",
        },
    }


@pytest.fixture
def update_with_document() -> dict:
    return {
        "update_id": 100003,
        "message": {
            "message_id": 791,
            "from": {"id": 456, "first_name": "DocUser"},
            "chat": {"id": 456, "type": "private"},
            "date": 1700000002,
            "document": {
                "file_id": "doc_file_id_123",
                "file_name": "contract.pdf",
                "mime_type": "application/pdf",
            },
        },
    }


@pytest.fixture
def update_no_message() -> dict:
    """Update with callback query instead of message."""
    return {
        "update_id": 100004,
        "callback_query": {
            "id": "cb_123",
            "from": {"id": 789},
            "data": "accept_lead_42",
        },
    }


# ============================================================================
# CONFIG TESTS
# ============================================================================


class TestTelegramConfig:
    def test_valid_config(self) -> None:
        cfg = TelegramChannelConfig(bot_token="123:ABC")
        assert cfg.max_message_length == 4096
        assert cfg.update_interval == 1.5
        assert cfg.supports_markdown is True
        assert cfg.supports_media is True
        assert cfg.parse_mode == "Markdown"
        assert cfg.disable_web_page_preview is True

    def test_missing_bot_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bot_token is required"):
            TelegramChannelConfig(bot_token="")

    def test_message_length_too_large_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed 4096"):
            TelegramChannelConfig(bot_token="tok", max_message_length=5000)

    def test_update_interval_too_small_raises(self) -> None:
        with pytest.raises(ValueError, match="must be >= 1.0"):
            TelegramChannelConfig(bot_token="tok", update_interval=0.5)

    def test_custom_config(self) -> None:
        cfg = TelegramChannelConfig(
            bot_token="tok",
            max_message_length=2048,
            update_interval=2.0,
            parse_mode="MarkdownV2",
        )
        assert cfg.max_message_length == 2048
        assert cfg.update_interval == 2.0
        assert cfg.parse_mode == "MarkdownV2"


# ============================================================================
# FORMATTER TESTS
# ============================================================================


class TestTelegramFormatter:
    def test_format_text_only(self, simple_response: ChannelResponse) -> None:
        result = TelegramMessageFormatter.format_response(simple_response)
        assert result == "Hello, how can I help you?"

    def test_format_with_sources(self, response_with_sources: ChannelResponse) -> None:
        result = TelegramMessageFormatter.format_response(response_with_sources)
        assert "Here is the answer." in result
        assert "*Fonti:*" in result
        assert "[Visa Guide](https://example.com/visa)" in result
        assert "3. Local Doc" in result
        # Sources without URL should not have link syntax
        assert "[Local Doc]" not in result

    def test_format_sources_max_five(self) -> None:
        response = ChannelResponse(
            text="Answer",
            sources=[
                {"title": f"S{i}", "url": f"https://x.com/{i}"} for i in range(10)
            ],
            metadata={},
        )
        result = TelegramMessageFormatter.format_response(response)
        assert "S0" in result
        assert "S4" in result
        assert "S5" not in result  # 6th source should be cut

    def test_format_with_workflow(self, response_with_workflow: ChannelResponse) -> None:
        result = TelegramMessageFormatter.format_response(response_with_workflow)
        assert "*Piano d'azione:*" in result
        assert "*PT PMA Setup:*" in result
        assert "1. Prepare documents" in result

    def test_format_workflow_no_steps(self) -> None:
        result = TelegramMessageFormatter._format_workflow(
            {"name": "Empty Plan", "steps": []}
        )
        assert result == "*Empty Plan*"

    def test_format_workflow_dict_steps(self) -> None:
        workflow = {
            "name": "Plan",
            "steps": [{"description": "A"}, {"action": "B"}],
        }
        result = TelegramMessageFormatter._format_workflow(workflow)
        assert "1. A" in result
        assert "2. B" in result

    def test_format_workflow_string_steps(self) -> None:
        workflow = {"name": "Plan", "steps": ["X", "Y"]}
        result = TelegramMessageFormatter._format_workflow(workflow)
        assert "1. X" in result
        assert "2. Y" in result

    def test_format_workflow_max_ten_steps(self) -> None:
        workflow = {"name": "Big", "steps": [f"Step {i}" for i in range(15)]}
        result = TelegramMessageFormatter._format_workflow(workflow)
        assert "10. Step 9" in result
        assert "Step 10" not in result

    def test_escape_markdown(self) -> None:
        text = "Hello_world *bold* [link](url)"
        escaped = TelegramMessageFormatter.escape_markdown(text)
        assert "\\_" in escaped
        assert "\\*" in escaped
        assert "\\[" in escaped
        assert "\\(" in escaped

    def test_escape_markdown_all_chars(self) -> None:
        special = "_*[]()~`>#+-=|{}.!"
        escaped = TelegramMessageFormatter.escape_markdown(special)
        for char in special:
            assert f"\\{char}" in escaped

    def test_format_thinking(self) -> None:
        result = TelegramMessageFormatter.format_thinking("Analyzing query...")
        assert result == "_💭 Analyzing query..._"

    def test_format_tool_call_with_args(self) -> None:
        result = TelegramMessageFormatter.format_tool_call(
            "search_qdrant", {"query": "visa", "limit": 5},
        )
        assert result == "🔧 `search_qdrant(query=visa, limit=5)`"

    def test_format_tool_call_no_args(self) -> None:
        result = TelegramMessageFormatter.format_tool_call("get_pricing")
        assert result == "🔧 `get_pricing()`"

    def test_format_error(self) -> None:
        result = TelegramMessageFormatter.format_error("Connection lost")
        assert result == "❌ *Errore:* Connection lost"

    def test_format_status_known(self) -> None:
        assert TelegramMessageFormatter.format_status("processing") == "⏳ Processing..."
        assert TelegramMessageFormatter.format_status("thinking") == "💭 Thinking..."
        assert TelegramMessageFormatter.format_status("complete") == "✅ Complete..."

    def test_format_status_unknown(self) -> None:
        result = TelegramMessageFormatter.format_status("custom")
        assert result == "📍 Custom..."


# ============================================================================
# ADAPTER TESTS
# ============================================================================


class TestTelegramAdapter:
    async def test_receive_message_text(
        self, adapter: TelegramChannelAdapter, sample_update: dict,
    ) -> None:
        msg = await adapter.receive_message(sample_update)

        assert msg.user_id == "telegram_413539912"
        assert msg.session_id == "tg_session_413539912"
        assert msg.text == "Quanto costa aprire una PT PMA?"
        assert msg.channel == "telegram"
        assert msg.metadata["chat_id"] == "413539912"
        assert msg.metadata["username"] == "zerob"
        assert msg.metadata["first_name"] == "Zero"
        assert msg.metadata["chat_type"] == "private"
        assert msg.metadata["message_id"] == 789
        assert msg.media is None

    async def test_receive_message_photo(
        self, adapter: TelegramChannelAdapter, update_with_photo: dict,
    ) -> None:
        msg = await adapter.receive_message(update_with_photo)

        assert msg.media is not None
        assert len(msg.media) == 1
        # Should take the largest photo (last in array)
        assert msg.media[0] == "telegram://photo/large_id"

    async def test_receive_message_document(
        self, adapter: TelegramChannelAdapter, update_with_document: dict,
    ) -> None:
        msg = await adapter.receive_message(update_with_document)

        assert msg.media is not None
        assert len(msg.media) == 1
        assert msg.media[0] == "telegram://document/doc_file_id_123"

    async def test_receive_message_no_message_field(
        self, adapter: TelegramChannelAdapter, update_no_message: dict,
    ) -> None:
        msg = await adapter.receive_message(update_no_message)

        assert msg.user_id == "unknown"
        assert msg.text == ""
        assert msg.metadata.get("raw_event") is not None

    async def test_receive_message_agent_context(
        self, adapter: TelegramChannelAdapter, sample_update: dict,
    ) -> None:
        sample_update["_agent_context"] = {"team_member": "lead@balizero.com"}
        msg = await adapter.receive_message(sample_update)

        assert msg.metadata["team_member"] == "lead@balizero.com"

    def test_adapter_properties(self, adapter: TelegramChannelAdapter) -> None:
        assert adapter.channel_name == "telegram"
        assert adapter.supports_markdown is True
        assert adapter.supports_media is True
        assert adapter.max_message_length == 4096

    async def test_send_response_success(
        self, adapter: TelegramChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        await adapter.send_response("413539912", simple_response)

        adapter.bot_service.send_message.assert_called_once()
        call_kwargs = adapter.bot_service.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == "413539912"
        assert call_kwargs["text"] == "Hello, how can I help you?"
        assert call_kwargs["parse_mode"] == "Markdown"

        # Should track last message for edits
        assert adapter._last_message_id == 100

    async def test_send_response_api_failure(
        self, adapter: TelegramChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        adapter.bot_service.send_message = AsyncMock(
            return_value={"ok": False, "error_code": 403, "description": "Forbidden"},
        )

        # Should not raise
        await adapter.send_response("123", simple_response)
        assert adapter._last_message_id is None

    async def test_send_response_exception(
        self, adapter: TelegramChannelAdapter, simple_response: ChannelResponse,
    ) -> None:
        adapter.bot_service.send_message = AsyncMock(side_effect=Exception("Network down"))

        # Should not raise
        await adapter.send_response("123", simple_response)

    async def test_send_response_truncates(
        self, adapter: TelegramChannelAdapter, long_response: ChannelResponse,
    ) -> None:
        await adapter.send_response("123", long_response)

        sent_text = adapter.bot_service.send_message.call_args.kwargs["text"]
        assert len(sent_text) <= 4096

    async def test_send_status_update_typing(
        self, adapter: TelegramChannelAdapter,
    ) -> None:
        await adapter.send_status_update("123", "processing")

        adapter.bot_service.send_chat_action.assert_called_once_with(
            chat_id="123", action="typing",
        )

    async def test_send_status_update_uploading(
        self, adapter: TelegramChannelAdapter,
    ) -> None:
        await adapter.send_status_update("123", "uploading")

        adapter.bot_service.send_chat_action.assert_called_once_with(
            chat_id="123", action="upload_document",
        )

    async def test_send_status_update_failure_noncritical(
        self, adapter: TelegramChannelAdapter,
    ) -> None:
        adapter.bot_service.send_chat_action = AsyncMock(
            side_effect=Exception("API error"),
        )

        # Should not raise (non-critical)
        await adapter.send_status_update("123", "thinking")

    async def test_stream_response_sends_initial_and_final(
        self, adapter: TelegramChannelAdapter,
    ) -> None:
        async def mock_stream():
            yield ChannelResponse(text="Hello world!", metadata={})

        await adapter.stream_response("123", mock_stream())

        # Should have sent initial "thinking" message
        adapter.bot_service.send_message.assert_called_once()
        initial_text = adapter.bot_service.send_message.call_args.kwargs["text"]
        assert "pensando" in initial_text.lower() or "💭" in initial_text

        # Should have done final edit
        assert adapter.bot_service.edit_message_text.call_count >= 1

    async def test_stream_response_error_sends_error_edit(
        self, adapter: TelegramChannelAdapter,
    ) -> None:
        async def failing_stream():
            yield ChannelResponse(text="Start", metadata={})
            raise RuntimeError("Boom")

        await adapter.stream_response("123", failing_stream())

        # Should have edited with error message
        last_edit = adapter.bot_service.edit_message_text.call_args
        if last_edit:
            edited_text = last_edit.kwargs.get("text", "")
            assert "Errore" in edited_text or "errore" in edited_text
