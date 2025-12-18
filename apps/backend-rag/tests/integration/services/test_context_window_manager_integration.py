"""
Integration Tests for ContextWindowManager
Tests conversation history trimming and summarization
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestContextWindowManagerIntegration:
    """Comprehensive integration tests for ContextWindowManager"""

    @pytest.fixture
    def manager(self):
        """Create ContextWindowManager instance"""
        with patch("services.context_window_manager.ZantaraAIClient") as mock_client:
            from services.context_window_manager import ContextWindowManager

            manager = ContextWindowManager(max_messages=10, summary_threshold=15)
            manager.zantara_client = None  # Disable AI for tests
            return manager

    def test_initialization(self, manager):
        """Test manager initialization"""
        assert manager is not None
        assert manager.max_messages == 10
        assert manager.summary_threshold == 15

    def test_trim_conversation_history_short(self, manager):
        """Test trimming short conversation"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        result = manager.trim_conversation_history(history)

        assert result is not None
        assert len(result["trimmed_messages"]) == 2
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_medium(self, manager):
        """Test trimming medium conversation"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(12)]  # 12 messages

        result = manager.trim_conversation_history(history)

        assert result is not None
        assert len(result["trimmed_messages"]) <= manager.max_messages
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_long(self, manager):
        """Test trimming long conversation that needs summarization"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(20)]  # 20 messages

        result = manager.trim_conversation_history(history)

        assert result is not None
        assert result["needs_summarization"] is True
        assert len(result["messages_to_summarize"]) > 0

    def test_trim_conversation_history_empty(self, manager):
        """Test trimming empty conversation"""
        result = manager.trim_conversation_history([])

        assert result is not None
        assert result["trimmed_messages"] == []
        assert result["needs_summarization"] is False

    def test_trim_conversation_history_with_summary(self, manager):
        """Test trimming with existing summary"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        existing_summary = "Previous conversation summary"

        result = manager.trim_conversation_history(history, current_summary=existing_summary)

        assert result is not None
        assert result["context_summary"] == existing_summary

    def test_build_summarization_prompt(self, manager):
        """Test building summarization prompt"""
        messages = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
        ]

        prompt = manager.build_summarization_prompt(messages)

        assert prompt is not None
        assert isinstance(prompt, str)
        assert "Summarize" in prompt or "summary" in prompt.lower()

    def test_get_context_status_healthy(self, manager):
        """Test getting context status for healthy conversation"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(5)]

        status = manager.get_context_status(history)

        assert status is not None
        assert status["status"] == "healthy"
        assert status["color"] == "green"

    def test_get_context_status_approaching_limit(self, manager):
        """Test getting context status for conversation approaching limit"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(12)]

        status = manager.get_context_status(history)

        assert status is not None
        assert status["status"] == "approaching_limit"
        assert status["color"] == "yellow"

    def test_get_context_status_needs_summarization(self, manager):
        """Test getting context status for conversation needing summarization"""
        history = [{"role": "user", "content": f"Message {i}"} for i in range(20)]

        status = manager.get_context_status(history)

        assert status is not None
        assert status["status"] == "needs_summarization"
        assert status["color"] == "red"

    def test_inject_summary_into_history(self, manager):
        """Test injecting summary into history"""
        recent_messages = [
            {"role": "user", "content": "Recent message"},
            {"role": "assistant", "content": "Recent response"},
        ]
        summary = "Previous conversation summary"

        result = manager.inject_summary_into_history(recent_messages, summary)

        assert result is not None
        assert len(result) > len(recent_messages)  # Should include summary message

    def test_inject_summary_into_history_no_summary(self, manager):
        """Test injecting empty summary"""
        recent_messages = [{"role": "user", "content": "Message"}]

        result = manager.inject_summary_into_history(recent_messages, "")

        assert result == recent_messages  # Should return unchanged
