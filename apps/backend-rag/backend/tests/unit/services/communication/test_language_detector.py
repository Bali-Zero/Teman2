"""
Unit tests for language_detector
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.communication.language_detector import detect_language, get_language_instruction


class TestLanguageDetector:
    """Tests for language detection"""

    def test_detect_language_empty(self):
        """Test detecting language from empty text"""
        result = detect_language("")
        assert result == "it"  # Default to Italian

    def test_detect_language_italian(self):
        """Test detecting Italian"""
        result = detect_language("Ciao, come posso aiutarti?")
        assert result == "it"

    def test_detect_language_english(self):
        """Test detecting English"""
        result = detect_language("Hello, how can I help you?")
        assert result == "en"

    def test_detect_language_indonesian(self):
        """Test detecting Indonesian"""
        result = detect_language("Apa yang bisa saya bantu?")
        assert result == "id"

    def test_detect_language_ukrainian(self):
        """Test detecting Ukrainian"""
        result = detect_language("Привіт, як справи?")
        assert result == "uk"

    def test_detect_language_russian(self):
        """Test detecting Russian"""
        result = detect_language("Привет, как дела?")
        assert result == "ru"

    def test_detect_language_no_markers(self):
        """Test detecting language with no markers"""
        result = detect_language("123456789")
        assert result == "auto"

    def test_detect_language_mixed(self):
        """Test detecting language with mixed markers"""
        result = detect_language("Ciao hello apa")
        # Should return the language with most markers
        assert result in ["it", "en", "id"]

    def test_get_language_instruction_italian(self):
        """Test getting language instruction for Italian"""
        instruction = get_language_instruction("it")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_english(self):
        """Test getting language instruction for English"""
        instruction = get_language_instruction("en")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_indonesian(self):
        """Test getting language instruction for Indonesian"""
        instruction = get_language_instruction("id")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_ukrainian(self):
        """Test getting language instruction for Ukrainian"""
        instruction = get_language_instruction("uk")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_russian(self):
        """Test getting language instruction for Russian"""
        instruction = get_language_instruction("ru")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_auto(self):
        """Test getting language instruction for auto"""
        instruction = get_language_instruction("auto")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_get_language_instruction_unknown(self):
        """Test getting language instruction for unknown language"""
        instruction = get_language_instruction("unknown")
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_detect_language_italian_markers(self):
        """Test detecting Italian with various markers"""
        assert detect_language("Ciao come stai?") == "it"
        assert detect_language("Cosa vuoi?") == "it"
        assert detect_language("Grazie per l'aiuto") == "it"
        assert detect_language("Quando posso venire?") == "it"

    def test_detect_language_english_markers(self):
        """Test detecting English with various markers"""
        assert detect_language("Hello how are you?") == "en"
        assert detect_language("What can I do?") == "en"
        assert detect_language("Please help me") == "en"
        assert detect_language("Why is this?") == "en"

    def test_detect_language_indonesian_markers(self):
        """Test detecting Indonesian with various markers"""
        assert detect_language("Apa yang bisa saya bantu?") == "id"
        assert detect_language("Bagaimana caranya?") == "id"
        assert detect_language("Saya mau tahu") == "id"
        assert detect_language("Bisa tolong?") == "id"

    def test_detect_language_ukrainian_markers(self):
        """Test detecting Ukrainian"""
        assert detect_language("Привіт як справи?") == "uk"
        assert detect_language("Дякую за допомогу") == "uk"

    def test_detect_language_russian_markers(self):
        """Test detecting Russian"""
        assert detect_language("Привет как дела?") == "ru"
        assert detect_language("Спасибо за помощь") == "ru"

    def test_detect_language_tie_breaker(self):
        """Test language detection with equal scores"""
        # If multiple languages have same score, should return one of them
        result = detect_language("ciao hello")
        assert result in ["it", "en", "id", "uk", "ru", "auto"]

    def test_detect_language_word_boundaries(self):
        """Test that word boundaries work correctly"""
        # Should not match "ciao" in "ciaos" (if word boundary works)
        assert detect_language("ciao") == "it"
        # But should still match if it's a word
        assert detect_language("say ciao") == "it"

    def test_get_language_instruction_ua_alias(self):
        """Test that 'ua' maps to Ukrainian instruction"""
        instruction = get_language_instruction("ua")
        assert isinstance(instruction, str)
        assert "УКРАЇНСЬКА" in instruction or "ukrainian" in instruction.lower()

    def test_get_language_instruction_contains_expected_content(self):
        """Test that instructions contain expected content"""
        it_inst = get_language_instruction("it")
        assert "ITALIANO" in it_inst or "italian" in it_inst.lower()
        assert "ZANTARA" in it_inst

        en_inst = get_language_instruction("en")
        assert "ENGLISH" in en_inst or "english" in en_inst.lower()
        assert "ZANTARA" in en_inst

        id_inst = get_language_instruction("id")
        assert "INDONESIA" in id_inst or "indonesia" in id_inst.lower()
        assert "ZANTARA" in id_inst

    def test_detect_language_none_text(self):
        """Test detecting language with None text"""
        result = detect_language(None)
        assert result == "it"  # Default to Italian

    def test_detect_language_special_characters(self):
        """Test detecting language with special characters"""
        assert detect_language("Ciao! Come stai?") == "it"
        assert detect_language("Hello! How are you?") == "en"
