"""
Unit tests for ContextWindowManager
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.context_window_manager import ContextWindowManager


@pytest.fixture
def context_window_manager():
    """Create ContextWindowManager instance"""
    with patch('llm.zantara_ai_client.ZantaraAIClient'):
        manager = ContextWindowManager()
        return manager


class TestContextWindowManager:
    """Tests for ContextWindowManager"""

    def test_init(self):
        """Test initialization"""
        with patch('llm.zantara_ai_client.ZantaraAIClient'):
            manager = ContextWindowManager()
            assert manager.max_messages == 10
            assert manager.summary_threshold == 15

    def test_init_custom_params(self):
        """Test initialization with custom parameters"""
        with patch('llm.zantara_ai_client.ZantaraAIClient'):
            manager = ContextWindowManager(max_messages=5, summary_threshold=10)
            assert manager.max_messages == 5
            assert manager.summary_threshold == 10

    def test_trim_conversation_history_empty(self, context_window_manager):
        """Test trimming empty conversation history"""
        result = context_window_manager.trim_conversation_history([])
        assert result["trimmed_messages"] == []
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_short(self, context_window_manager):
        """Test trimming short conversation"""
        history = [{"role": "user", "content": f"message {i}"} for i in range(5)]
        result = context_window_manager.trim_conversation_history(history)
        assert len(result["trimmed_messages"]) == 5
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_medium(self, context_window_manager):
        """Test trimming medium conversation"""
        history = [{"role": "user", "content": f"message {i}"} for i in range(12)]
        result = context_window_manager.trim_conversation_history(history)
        assert len(result["trimmed_messages"]) <= context_window_manager.max_messages
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_long(self, context_window_manager):
        """Test trimming long conversation"""
        history = [{"role": "user", "content": f"message {i}"} for i in range(20)]
        result = context_window_manager.trim_conversation_history(history)
        assert result["needs_summarization"] is True
        assert len(result["messages_to_summarize"]) > 0

    def test_trim_conversation_history_with_summary(self, context_window_manager):
        """Test trimming with existing summary"""
        history = [{"role": "user", "content": f"message {i}"} for i in range(20)]
        result = context_window_manager.trim_conversation_history(history, current_summary="Previous summary")
        assert result["context_summary"] == "Previous summary"

