"""
Tests for greetings detection fix

Tests that simple greetings are detected and return direct responses
without triggering RAG/vector_search.
"""

import pytest

from services.rag.agentic.prompt_builder import SystemPromptBuilder


class TestGreetingsDetection:
    """Test greetings detection in SystemPromptBuilder"""

    @pytest.fixture
    def builder(self):
        """Create SystemPromptBuilder instance"""
        return SystemPromptBuilder()

    def test_simple_greetings_italian(self, builder):
        """Test: Italian greetings are detected"""
        greetings = ["ciao", "salve", "buongiorno", "buonasera"]

        for greeting in greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected as greeting"
            assert "Ciao" in result or "Come posso aiutarti" in result

    def test_simple_greetings_english(self, builder):
        """Test: English greetings are detected"""
        greetings = ["hello", "hi", "hey"]

        for greeting in greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected as greeting"
            assert "Hello" in result or "How can I help" in result

    def test_greetings_with_exclamation(self, builder):
        """Test: Greetings with exclamation marks are detected"""
        greetings = ["ciao!", "hello!", "hi!", "hey!"]

        for greeting in greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected as greeting"

    def test_greetings_with_name(self, builder):
        """Test: Greetings followed by name are detected"""
        greetings = ["ciao zan", "hello zantara", "hi there", "hey zan"]

        for greeting in greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected as greeting"

    def test_non_greetings_not_detected(self, builder):
        """Test: Non-greeting queries are not detected"""
        non_greetings = [
            "What is KITAS?",
            "Come aprire una PT PMA?",
            "Quanto costa il visto?",
            "Tell me about visa requirements",
            "I need help with business setup",
            "ciao ma voglio sapere qualcosa",  # Too long, not just greeting
        ]

        for query in non_greetings:
            result = builder.check_greetings(query)
            assert result is None, f"'{query}' should NOT be detected as greeting"

    def test_case_insensitive(self, builder):
        """Test: Greetings detection is case-insensitive"""
        greetings = ["CIAO", "Hello", "HI", "Hey"]

        for greeting in greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected (case-insensitive)"

    def test_whitespace_handling(self, builder):
        """Test: Whitespace is handled correctly"""
        greetings = [" ciao ", "  hello  ", "\t hi \n"]

        for greeting in greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected after whitespace trim"

    def test_empty_string(self, builder):
        """Test: Empty string returns None"""
        result = builder.check_greetings("")
        assert result is None

    def test_very_short_greetings(self, builder):
        """Test: Very short greetings (<=5 chars) are detected"""
        short_greetings = ["ciao", "hello", "hi", "hey", "salve"]

        for greeting in short_greetings:
            result = builder.check_greetings(greeting)
            assert result is not None, f"'{greeting}' should be detected as short greeting"
