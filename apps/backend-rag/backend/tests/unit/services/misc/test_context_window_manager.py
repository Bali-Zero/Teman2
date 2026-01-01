"""
Unit tests for ContextWindowManager
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.context_window_manager import ContextWindowManager


@pytest.fixture
def context_window_manager():
    """Create ContextWindowManager instance"""
    with patch("llm.zantara_ai_client.ZantaraAIClient") as mock_client_class:
        mock_client_instance = MagicMock()
        mock_client_instance.generate_text = AsyncMock(return_value="Test summary")
        mock_client_class.return_value = mock_client_instance
        manager = ContextWindowManager()
        manager.zantara_client = mock_client_instance
        return manager


@pytest.fixture
def context_window_manager_no_ai():
    """Create ContextWindowManager instance without AI"""
    with patch("llm.zantara_ai_client.ZantaraAIClient", side_effect=Exception("Not available")):
        manager = ContextWindowManager()
        manager.zantara_client = None
        return manager


class TestContextWindowManager:
    """Tests for ContextWindowManager"""

    def test_init(self):
        """Test initialization"""
        with patch("services.misc.context_window_manager.ZantaraAIClient"):
            manager = ContextWindowManager(max_messages=10, summary_threshold=15)
            assert manager.max_messages == 10
            assert manager.summary_threshold == 15

    def test_init_no_ai(self, context_window_manager_no_ai):
        """Test initialization without AI"""
        assert context_window_manager_no_ai.zantara_client is None

    def test_trim_conversation_history_empty(self, context_window_manager):
        """Test trimming empty conversation history"""
        result = context_window_manager.trim_conversation_history([])
        assert result["trimmed_messages"] == []
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_short(self, context_window_manager):
        """Test trimming short conversation"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(5)]
        result = context_window_manager.trim_conversation_history(messages)
        assert len(result["trimmed_messages"]) == 5
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_medium(self, context_window_manager):
        """Test trimming medium conversation"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(12)]
        result = context_window_manager.trim_conversation_history(messages)
        assert len(result["trimmed_messages"]) <= context_window_manager.max_messages
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_long(self, context_window_manager):
        """Test trimming long conversation"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = context_window_manager.trim_conversation_history(messages)
        assert result["needs_summarization"] is True
        assert len(result["messages_to_summarize"]) > 0

    def test_trim_conversation_history_with_summary(self, context_window_manager):
        """Test trimming conversation with existing summary"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = context_window_manager.trim_conversation_history(
            messages,
            current_summary="Previous conversation summary"
        )
        assert result["context_summary"] == "Previous conversation summary"

    @pytest.mark.asyncio
    async def test_generate_summary(self, context_window_manager):
        """Test generating summary"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]
        
        if context_window_manager.zantara_client:
            context_window_manager.zantara_client.generate_text = AsyncMock(
                return_value="Summary of old messages"
            )
        
        result = await context_window_manager.generate_summary(messages)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_summary_no_ai(self, context_window_manager_no_ai):
        """Test generating summary without AI"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]
        
        result = await context_window_manager_no_ai.generate_summary(messages)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_summary_empty(self, context_window_manager):
        """Test generating summary for empty messages"""
        result = await context_window_manager.generate_summary([])
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_summary_with_existing_summary(self, context_window_manager):
        """Test generating summary with existing summary"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]
        
        if context_window_manager.zantara_client:
            context_window_manager.zantara_client.generate_text = AsyncMock(
                return_value="Updated summary"
            )
        
        result = await context_window_manager.generate_summary(
            messages,
            existing_summary="Previous summary"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_summarization_prompt(self, context_window_manager):
        """Test building summarization prompt"""
        messages = [
            {"role": "user", "content": "Test message 1"},
            {"role": "assistant", "content": "Test response 1"}
        ]
        prompt = context_window_manager.build_summarization_prompt(messages)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_context_status(self, context_window_manager):
        """Test getting context status"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(5)]
        status = context_window_manager.get_context_status(messages)
        assert isinstance(status, dict)
        assert "total_messages" in status
        assert "status" in status

    def test_inject_summary_into_history(self, context_window_manager):
        """Test injecting summary into history"""
        messages = [{"role": "user", "content": "Test"}]
        result = context_window_manager.inject_summary_into_history(messages, "Summary")
        assert len(result) == 2
        assert result[0]["role"] == "system"
