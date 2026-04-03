"""
Tests for emotion_analyzer.py - Emotional content detection and response instructions.
"""

import pytest

from backend.services.communication.emotion_analyzer import (
    get_emotional_response_instruction,
    has_emotional_content,
)


class TestHasEmotionalContent:
    """Tests for has_emotional_content function."""

    def test_italian_frustration(self):
        assert has_emotional_content("Sono molto frustrato con questa situazione") is True

    def test_italian_worry(self):
        assert has_emotional_content("Sono preoccupato per il mio visto") is True

    def test_italian_happiness(self):
        assert has_emotional_content("Sono molto felice della notizia!") is True

    def test_english_desperation(self):
        assert has_emotional_content("I am desperate, my visa is expiring") is True

    def test_english_stress(self):
        assert has_emotional_content("I'm really stressed about the deadline") is True

    def test_english_anger(self):
        assert has_emotional_content("I'm so angry about the delays") is True

    def test_english_fear(self):
        assert has_emotional_content("I'm afraid of losing my business permit") is True

    def test_english_hope(self):
        assert has_emotional_content("I'm hopeful this will work out") is True

    def test_indonesian_emotion(self):
        assert has_emotional_content("Saya sangat khawatir dengan situasi ini") is True
        assert has_emotional_content("Saya takut kehilangan visa") is True

    def test_neutral_content(self):
        assert has_emotional_content("What documents do I need for KITAS?") is False
        assert has_emotional_content("How much does PT PMA cost?") is False

    def test_empty_text(self):
        assert has_emotional_content("") is False

    def test_none_text(self):
        assert has_emotional_content(None) is False

    def test_case_insensitive(self):
        assert has_emotional_content("I am FRUSTRATED with this process") is True


class TestGetEmotionalResponseInstruction:
    """Tests for get_emotional_response_instruction function."""

    def test_italian_instructions(self):
        result = get_emotional_response_instruction("it")
        assert "capisco" in result.lower()
        assert "EMOTIVI" in result

    def test_english_instructions(self):
        result = get_emotional_response_instruction("en")
        assert "understand" in result.lower()
        assert "EMOTIONAL CONTENT" in result

    def test_indonesian_instructions(self):
        result = get_emotional_response_instruction("id")
        assert "mengerti" in result.lower()

    def test_unknown_language_defaults_to_italian(self):
        result = get_emotional_response_instruction("de")
        assert "capisco" in result.lower()

    def test_instructions_not_empty(self):
        for lang in ["it", "en", "id"]:
            result = get_emotional_response_instruction(lang)
            assert len(result) > 50
