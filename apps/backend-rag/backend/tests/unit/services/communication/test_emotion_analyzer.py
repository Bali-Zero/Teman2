"""
Unit tests for emotion_analyzer
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.communication.emotion_analyzer import (
    get_emotional_response_instruction,
    has_emotional_content,
)


class TestEmotionAnalyzer:
    """Tests for emotion analyzer"""

    def test_has_emotional_content_true_italian(self):
        """Test detecting emotional content in Italian"""
        result = has_emotional_content("Sono disperato")
        assert result is True

    def test_has_emotional_content_true_english(self):
        """Test detecting emotional content in English"""
        result = has_emotional_content("I'm frustrated")
        assert result is True

    def test_has_emotional_content_true_indonesian(self):
        """Test detecting emotional content in Indonesian"""
        result = has_emotional_content("Saya putus asa")
        assert result is True

    def test_has_emotional_content_false(self):
        """Test detecting no emotional content"""
        result = has_emotional_content("Hello")
        assert result is False

    def test_has_emotional_content_empty(self):
        """Test detecting emotional content with empty text"""
        result = has_emotional_content("")
        assert result is False

    def test_get_emotional_response_instruction_it(self):
        """Test getting emotional response instruction for Italian"""
        result = get_emotional_response_instruction("it")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_emotional_response_instruction_en(self):
        """Test getting emotional response instruction for English"""
        result = get_emotional_response_instruction("en")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_emotional_response_instruction_id(self):
        """Test getting emotional response instruction for Indonesian"""
        result = get_emotional_response_instruction("id")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_emotional_response_instruction_default(self):
        """Test getting emotional response instruction for unknown language"""
        result = get_emotional_response_instruction("unknown")
        assert isinstance(result, str)
        assert len(result) > 0
        # Should default to Italian
        assert "RISPOSTE" in result or "capisco" in result.lower()

    def test_has_emotional_content_case_insensitive(self):
        """Test that emotional detection is case-insensitive"""
        assert has_emotional_content("SONO DISPERATO") is True
        assert has_emotional_content("I'm FRUSTRATED") is True
        assert has_emotional_content("Saya PUTUS ASA") is True

    def test_has_emotional_content_multiple_words(self):
        """Test detecting multiple emotional words"""
        assert has_emotional_content("Sono frustrato e arrabbiato") is True
        assert has_emotional_content("I'm worried and stressed") is True

    def test_has_emotional_content_partial_match(self):
        """Test detecting emotional words as part of larger words"""
        # Should match "frustrated" in "frustratedly"
        assert has_emotional_content("frustratedly") is True

    def test_has_emotional_content_none(self):
        """Test detecting no emotional content in neutral text"""
        assert has_emotional_content("What is the price?") is False
        assert has_emotional_content("How do I apply?") is False
        assert has_emotional_content("Tell me about KITAS") is False

    def test_get_emotional_response_instruction_contains_keywords(self):
        """Test that instructions contain expected keywords"""
        result_it = get_emotional_response_instruction("it")
        assert "capisco" in result_it.lower() or "RISPOSTE" in result_it

        result_en = get_emotional_response_instruction("en")
        assert "understand" in result_en.lower() or "RESPONSES" in result_en

        result_id = get_emotional_response_instruction("id")
        assert "mengerti" in result_id.lower() or "RESPON" in result_id

    def test_has_emotional_content_all_italian_words(self):
        """Test all Italian emotional words"""
        italian_words = [
            "disperato", "disperata", "frustrato", "frustrata",
            "arrabbiato", "arrabbiata", "felice", "preoccupato",
            "ansioso", "triste", "spaventato", "speranza"
        ]
        for word in italian_words:
            assert has_emotional_content(f"Sono {word}") is True

    def test_has_emotional_content_all_english_words(self):
        """Test all English emotional words"""
        english_words = [
            "desperate", "frustrated", "angry", "happy",
            "worried", "stressed", "sad", "afraid", "hopeful"
        ]
        for word in english_words:
            assert has_emotional_content(f"I'm {word}") is True

    def test_has_emotional_content_all_indonesian_words(self):
        """Test all Indonesian emotional words"""
        indonesian_words = [
            "putus asa", "frustrasi", "marah", "bahagia",
            "khawatir", "stres", "sedih", "takut", "harapan"
        ]
        for phrase in indonesian_words:
            assert has_emotional_content(f"Saya {phrase}") is True
