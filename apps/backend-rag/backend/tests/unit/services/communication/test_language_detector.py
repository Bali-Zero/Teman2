"""
Unit tests for language_detector
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

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
