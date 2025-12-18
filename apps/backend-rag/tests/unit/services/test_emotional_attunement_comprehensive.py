"""
Comprehensive tests for services/emotional_attunement.py
Target: 95%+ coverage
"""

import pytest

from services.emotional_attunement import (
    EmotionalAttunementService,
    EmotionalState,
    ToneStyle,
)


class TestEmotionalAttunementService:
    """Comprehensive test suite for EmotionalAttunementService"""

    @pytest.fixture
    def service(self):
        """Create EmotionalAttunementService instance"""
        return EmotionalAttunementService()

    def test_init(self, service):
        """Test EmotionalAttunementService initialization"""
        assert service.EMOTION_PATTERNS is not None
        assert service.STATE_TO_TONE is not None

    def test_analyze_message_stressed(self, service):
        """Test analyze_message with stressed indicators"""
        profile = service.analyze_message("URGENT! I need help ASAP!")
        assert profile.detected_state == EmotionalState.STRESSED
        assert profile.confidence > 0

    def test_analyze_message_excited(self, service):
        """Test analyze_message with excited indicators"""
        profile = service.analyze_message("Wow! This is amazing!")
        assert profile.detected_state == EmotionalState.EXCITED
        assert profile.confidence > 0

    def test_analyze_message_confused(self, service):
        """Test analyze_message with confused indicators"""
        profile = service.analyze_message("I don't understand, can you explain?")
        assert profile.detected_state == EmotionalState.CONFUSED
        assert profile.confidence > 0

    def test_analyze_message_frustrated(self, service):
        """Test analyze_message with frustrated indicators"""
        profile = service.analyze_message("This is so frustrating!")
        assert profile.detected_state == EmotionalState.FRUSTRATED
        assert profile.confidence > 0

    def test_analyze_message_neutral(self, service):
        """Test analyze_message with neutral message"""
        profile = service.analyze_message("Hello, how are you?")
        assert profile.detected_state == EmotionalState.NEUTRAL

    def test_get_tone_prompt(self, service):
        """Test get_tone_prompt"""
        prompt = service.get_tone_prompt(ToneStyle.WARM)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_enhanced_system_prompt(self, service):
        """Test build_enhanced_system_prompt"""
        profile = service.analyze_message("I'm stressed about deadlines")
        enhanced = service.build_enhanced_system_prompt("Original prompt", profile)
        assert isinstance(enhanced, str)
        assert "Original prompt" in enhanced

    def test_get_stats(self, service):
        """Test get_stats"""
        stats = service.get_stats()
        assert isinstance(stats, dict)
