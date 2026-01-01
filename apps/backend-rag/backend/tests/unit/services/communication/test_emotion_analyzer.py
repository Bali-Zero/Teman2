"""
Unit tests for emotion_analyzer
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.communication.emotion_analyzer import (
    has_emotional_content,
    get_emotional_response_instruction
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
