"""
Comprehensive tests for services/context_window_manager.py
Target: 99%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.context_window_manager import ContextWindowManager


class TestContextWindowManager:
    """Comprehensive test suite for ContextWindowManager"""

    @pytest.fixture
    def manager(self):
        """Create ContextWindowManager instance"""
        with patch("llm.zantara_ai_client.ZantaraAIClient"):
            return ContextWindowManager()

    @pytest.fixture
    def manager_custom(self):
        """Create ContextWindowManager with custom parameters"""
        with patch("llm.zantara_ai_client.ZantaraAIClient"):
            return ContextWindowManager(max_messages=5, summary_threshold=10)

    @pytest.fixture
    def manager_no_client(self):
        """Create ContextWindowManager without ZantaraAIClient"""
        with patch("llm.zantara_ai_client.ZantaraAIClient", side_effect=Exception()):
            return ContextWindowManager()

    def test_init(self, manager):
        """Test ContextWindowManager initialization"""
        assert manager.max_messages == 10
        assert manager.summary_threshold == 15

    def test_init_custom(self, manager_custom):
        """Test ContextWindowManager initialization with custom parameters"""
        assert manager_custom.max_messages == 5
        assert manager_custom.summary_threshold == 10

    def test_init_no_client(self, manager_no_client):
        """Test ContextWindowManager initialization without ZantaraAIClient"""
        assert manager_no_client.zantara_client is None

    def test_trim_conversation_history_short(self, manager):
        """Test trim_conversation_history with short history"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = manager.trim_conversation_history(history)
        assert len(result["trimmed_messages"]) == 2
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_long(self, manager):
        """Test trim_conversation_history with long history"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = manager.trim_conversation_history(history)
        assert len(result["trimmed_messages"]) <= manager.max_messages
        assert result["needs_summarization"] is True or len(result["trimmed_messages"]) == len(
            history
        )

    def test_trim_conversation_history_with_summary(self, manager):
        """Test trim_conversation_history with existing summary"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = manager.trim_conversation_history(history, current_summary="Previous summary")
        assert (
            result["context_summary"] == "Previous summary"
            or len(result["trimmed_messages"]) <= manager.max_messages
        )

    def test_build_summarization_prompt(self, manager):
        """Test build_summarization_prompt"""
        old_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        prompt = manager.build_summarization_prompt(old_messages)
        assert "summarize" in prompt.lower() or "summary" in prompt.lower()
        assert "Hello" in prompt or "Hi" in prompt

    def test_get_context_status(self, manager):
        """Test get_context_status"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
        status = manager.get_context_status(history)
        assert "total_messages" in status
        assert "status" in status
        assert "color" in status

    def test_inject_summary_into_history(self, manager):
        """Test inject_summary_into_history"""
        recent = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        summary = "Previous conversation summary"
        result = manager.inject_summary_into_history(recent, summary)
        assert len(result) > len(recent)
        assert any("summary" in str(msg).lower() for msg in result)

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, manager):
        """Test generate_summary success"""
        manager.zantara_client = MagicMock()
        manager.zantara_client.generate_text = AsyncMock(return_value="Summary text")
        old_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        summary = await manager.generate_summary(old_messages)
        assert summary == "Summary text"

    @pytest.mark.asyncio
    async def test_generate_summary_no_client(self, manager_no_client):
        """Test generate_summary without client"""
        old_messages = [
            {"role": "user", "content": "Hello"},
        ]
        summary = await manager_no_client.generate_summary(old_messages)
        assert isinstance(summary, str)
        assert len(summary) > 0  # Returns fallback message

    @pytest.mark.asyncio
    async def test_generate_summary_error(self, manager):
        """Test generate_summary with error"""
        manager.zantara_client = MagicMock()
        manager.zantara_client.generate_text = AsyncMock(side_effect=Exception("Error"))
        old_messages = [
            {"role": "user", "content": "Hello"},
        ]
        summary = await manager.generate_summary(old_messages)
        assert isinstance(summary, str)  # Returns fallback or empty string
