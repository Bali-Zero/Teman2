"""
Tests for conversation_title_generator.py - Title generation for chat conversations.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.crm.conversation_title_generator import (
    _clean_title,
    generate_conversation_title,
)


class TestCleanTitle:
    """Tests for _clean_title helper function."""

    def test_strips_quotes(self):
        assert _clean_title('"Hello World"', 50) == "Hello World"
        assert _clean_title("'Hello World'", 50) == "Hello World"

    def test_strips_whitespace(self):
        assert _clean_title("  Hello World  ", 50) == "Hello World"

    def test_truncates_to_max_length(self):
        result = _clean_title("A very long title that exceeds the limit", 10)
        assert len(result) == 10

    def test_removes_thinking_tags(self):
        result = _clean_title("<think>some reasoning</think>Actual Title", 50)
        assert result == "Actual Title"

    def test_empty_input(self):
        result = _clean_title("", 50)
        assert result == ""

    def test_combined_cleaning(self):
        result = _clean_title('  "<think>hmm</think>Clean Title"  ', 50)
        assert result == "Clean Title"


class TestGenerateConversationTitle:
    """Tests for generate_conversation_title function."""

    @pytest.mark.asyncio
    async def test_short_message_returns_none(self):
        result = await generate_conversation_title("conv_1", "hi", max_length=50)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_message_returns_none(self):
        result = await generate_conversation_title("conv_1", "", max_length=50)
        assert result is None

    @pytest.mark.asyncio
    @patch("backend.services.crm.conversation_title_generator._generate_via_ollama")
    async def test_ollama_success(self, mock_ollama):
        mock_ollama.return_value = "PT PMA Setup Guide"
        result = await generate_conversation_title(
            "conv_1", "How do I set up a PT PMA in Bali?"
        )
        assert result == "PT PMA Setup Guide"
        mock_ollama.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.crm.conversation_title_generator._generate_via_ollama")
    @patch("backend.services.crm.conversation_title_generator._generate_via_gemini")
    async def test_ollama_fails_gemini_fallback(self, mock_gemini, mock_ollama):
        mock_ollama.return_value = None
        mock_gemini.return_value = "Visa Requirements"
        result = await generate_conversation_title(
            "conv_1", "What are the requirements for a KITAS visa?"
        )
        assert result == "Visa Requirements"
        mock_ollama.assert_called_once()
        mock_gemini.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.crm.conversation_title_generator._generate_via_ollama")
    @patch("backend.services.crm.conversation_title_generator._generate_via_gemini")
    async def test_all_methods_fail_returns_none(self, mock_gemini, mock_ollama):
        mock_ollama.return_value = None
        mock_gemini.return_value = None
        result = await generate_conversation_title(
            "conv_1", "Tell me about Indonesian business regulations"
        )
        assert result is None

    @pytest.mark.asyncio
    @patch("backend.services.crm.conversation_title_generator._generate_via_ollama")
    async def test_max_length_respected(self, mock_ollama):
        mock_ollama.return_value = "Short"
        result = await generate_conversation_title(
            "conv_1", "How do I set up a business in Indonesia?", max_length=20
        )
        assert result is not None
        assert len(result) <= 20

    @pytest.mark.asyncio
    async def test_message_too_short_threshold(self):
        """Messages under 10 chars should be skipped."""
        result = await generate_conversation_title("conv_1", "short msg")
        assert result is None  # 9 chars

        result = await generate_conversation_title("conv_1", "0123456789")
        # Exactly 10 chars - should proceed (not return None for being too short)
        # But since no LLM is available, it will return None from LLM failure
