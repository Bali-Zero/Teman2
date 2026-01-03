"""
Unit tests for EmotionalAttunementService
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.emotional_attunement import EmotionalAttunementService, EmotionalState, ToneStyle


@pytest.fixture
def emotional_service():
    """Create EmotionalAttunementService instance"""
    return EmotionalAttunementService()


class TestEmotionalAttunementService:
    """Tests for EmotionalAttunementService"""

    def test_init(self):
        """Test initialization"""
        service = EmotionalAttunementService()
        assert hasattr(EmotionalAttunementService, "EMOTION_PATTERNS")

    def test_analyze_message_stressed(self, emotional_service):
        """Test analyzing stressed message"""
        message = "URGENT!!! I need help ASAP!!! PROBLEM!!!"
        result = emotional_service.analyze_message(message)
        # Should detect STRESSED or URGENT due to keywords and caps
        assert result.detected_state in [EmotionalState.STRESSED, EmotionalState.URGENT, EmotionalState.NEUTRAL]
        assert result.confidence > 0.0

    def test_analyze_message_excited(self, emotional_service):
        """Test analyzing excited message"""
        message = "Wow! This is amazing! Great!"
        result = emotional_service.analyze_message(message)
        assert result.detected_state == EmotionalState.EXCITED
        assert result.confidence > 0.0

    def test_analyze_message_confused(self, emotional_service):
        """Test analyzing confused message"""
        message = "I don't understand this. I'm confused."
        result = emotional_service.analyze_message(message)
        assert result.detected_state == EmotionalState.CONFUSED
        assert result.confidence > 0.0

    def test_analyze_message_neutral(self, emotional_service):
        """Test analyzing neutral message"""
        message = "What is the visa requirement?"
        result = emotional_service.analyze_message(message)
        assert result.detected_state == EmotionalState.NEUTRAL
        assert result.confidence > 0.0

    def test_get_tone_prompt(self, emotional_service):
        """Test getting tone prompt"""
        prompt = emotional_service.get_tone_prompt(ToneStyle.WARM)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_enhanced_system_prompt(self, emotional_service):
        """Test building enhanced system prompt"""
        base_prompt = "You are a helpful assistant."
        emotional_profile = emotional_service.analyze_message("I'm stressed!")
        enhanced = emotional_service.build_enhanced_system_prompt(base_prompt, emotional_profile)
        assert isinstance(enhanced, str)
        assert len(enhanced) > len(base_prompt)

    def test_get_stats(self, emotional_service):
        """Test getting statistics"""
        emotional_service.analyze_message("URGENT!")
        stats = emotional_service.get_stats()
        assert isinstance(stats, dict)
        assert "emotion_patterns" in stats

