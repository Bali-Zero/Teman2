"""
Integration Tests for EmotionalAttunementService
Tests emotional state detection and tone adaptation
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestEmotionalAttunementServiceIntegration:
    """Comprehensive integration tests for EmotionalAttunementService"""

    @pytest.fixture
    def service(self):
        """Create EmotionalAttunementService instance"""
        from services.emotional_attunement import EmotionalAttunementService

        return EmotionalAttunementService()

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert len(service.EMOTION_PATTERNS) > 0
        assert len(service.STATE_TO_TONE) > 0
        assert len(service.TONE_PROMPTS) > 0

    def test_analyze_message_neutral(self, service):
        """Test analyzing neutral message"""
        message = "Hello, how are you?"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "neutral"
        assert profile.confidence > 0
        assert profile.suggested_tone is not None
        assert len(profile.detected_indicators) == 0

    def test_analyze_message_stressed(self, service):
        """Test analyzing stressed message"""
        message = "URGENT!! I need help ASAP with this problem!"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "stressed"
        assert profile.confidence >= 0.5
        assert len(profile.detected_indicators) > 0

    def test_analyze_message_excited(self, service):
        """Test analyzing excited message"""
        message = "Wow! This is amazing! I love it!!!"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "excited"
        assert profile.confidence >= 0.5
        assert "exclamations" in str(profile.detected_indicators)

    def test_analyze_message_confused(self, service):
        """Test analyzing confused message"""
        message = "I don't understand. What does this mean? How does it work??"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "confused"
        assert profile.confidence >= 0.5

    def test_analyze_message_frustrated(self, service):
        """Test analyzing frustrated message"""
        message = "Ugh, I'm frustrated. This still not working. Seriously?"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "frustrated"
        assert profile.confidence >= 0.5

    def test_analyze_message_curious(self, service):
        """Test analyzing curious message"""
        message = "I'm curious about the technical implementation. What if we tried this?"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "curious"
        assert profile.confidence >= 0.5

    def test_analyze_message_grateful(self, service):
        """Test analyzing grateful message"""
        message = "Thank you so much! I really appreciate your help."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "grateful"
        assert profile.confidence >= 0.5

    def test_analyze_message_urgent(self, service):
        """Test analyzing urgent message"""
        message = "I need this NOW! It's critical and urgent!"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "urgent"
        assert profile.confidence >= 0.5

    def test_analyze_message_sad(self, service):
        """Test analyzing sad message"""
        message = "I feel sad and down today. I'm unhappy about this."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "sad"
        assert profile.confidence >= 0.5

    def test_analyze_message_anxious(self, service):
        """Test analyzing anxious message"""
        message = "I'm anxious and worried about this. I feel nervous."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "anxious"
        assert profile.confidence >= 0.5

    def test_analyze_message_embarrassed(self, service):
        """Test analyzing embarrassed message"""
        message = "I feel embarrassed and ashamed about this mistake."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "embarrassed"
        assert profile.confidence >= 0.5

    def test_analyze_message_lonely(self, service):
        """Test analyzing lonely message"""
        message = "I feel lonely and alone. I'm isolated."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "lonely"
        assert profile.confidence >= 0.5

    def test_analyze_message_scared(self, service):
        """Test analyzing scared message"""
        message = "I'm scared and afraid of what might happen."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "scared"
        assert profile.confidence >= 0.5

    def test_analyze_message_worried(self, service):
        """Test analyzing worried message"""
        message = "I'm worried about this. I have concerns."
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "worried"
        assert profile.confidence >= 0.5

    def test_analyze_message_with_caps_stressed(self, service):
        """Test analyzing message with high capitalization (stressed indicator)"""
        message = "THIS IS A PROBLEM AND I NEED HELP NOW!!!"
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value in ["stressed", "urgent"]
        assert any("caps" in ind for ind in profile.detected_indicators)

    def test_analyze_message_multiple_indicators(self, service):
        """Test analyzing message with multiple emotional indicators"""
        message = "URGENT!! I'm stressed and need help ASAP with this problem!!!"
        profile = service.analyze_message(message)

        assert profile is not None
        assert len(profile.detected_indicators) > 1
        assert profile.confidence >= 0.5

    def test_analyze_message_with_collaborator_preferences_formal(self, service):
        """Test analyzing message with collaborator preferences (formal)"""
        message = "Hello, I need assistance."
        preferences = {"formality": "formal", "preferred_tone": "professional"}
        profile = service.analyze_message(message, collaborator_preferences=preferences)

        assert profile is not None
        assert profile.suggested_tone.value == "professional"

    def test_analyze_message_with_collaborator_preferences_casual(self, service):
        """Test analyzing message with collaborator preferences (casual)"""
        message = "Hi there!"
        preferences = {"formality": "casual"}
        profile = service.analyze_message(message, collaborator_preferences=preferences)

        assert profile is not None
        # Should use warm tone for casual neutral messages
        assert profile.suggested_tone.value in ["warm", "professional"]

    def test_analyze_message_with_collaborator_preferences_tone_override(self, service):
        """Test analyzing message with direct tone preference override"""
        message = "I need help."
        preferences = {"preferred_tone": "direct"}
        profile = service.analyze_message(message, collaborator_preferences=preferences)

        assert profile is not None
        assert profile.suggested_tone.value == "direct"
        assert "Preference override" in profile.reasoning

    def test_analyze_message_with_invalid_tone_preference(self, service):
        """Test analyzing message with invalid tone preference (should handle gracefully)"""
        message = "Hello"
        preferences = {"preferred_tone": "invalid_tone"}
        profile = service.analyze_message(message, collaborator_preferences=preferences)

        assert profile is not None
        # Should fall back to default tone for detected state
        assert profile.suggested_tone is not None

    def test_analyze_message_empty_string(self, service):
        """Test analyzing empty message"""
        message = ""
        profile = service.analyze_message(message)

        assert profile is not None
        assert profile.detected_state.value == "neutral"
        assert profile.confidence == 1.0

    def test_analyze_message_weak_indicators(self, service):
        """Test analyzing message with weak emotional indicators (should default to neutral)"""
        message = "Maybe this could be interesting."
        profile = service.analyze_message(message)

        assert profile is not None
        # Weak indicators should default to neutral
        if profile.confidence < 0.5:
            assert profile.detected_state.value == "neutral"

    def test_get_tone_prompt_professional(self, service):
        """Test getting tone prompt for professional style"""
        from services.emotional_attunement import ToneStyle

        prompt = service.get_tone_prompt(ToneStyle.PROFESSIONAL)
        assert prompt is not None
        assert "professional" in prompt.lower()

    def test_get_tone_prompt_warm(self, service):
        """Test getting tone prompt for warm style"""
        from services.emotional_attunement import ToneStyle

        prompt = service.get_tone_prompt(ToneStyle.WARM)
        assert prompt is not None
        assert "warm" in prompt.lower() or "friendly" in prompt.lower()

    def test_get_tone_prompt_technical(self, service):
        """Test getting tone prompt for technical style"""
        from services.emotional_attunement import ToneStyle

        prompt = service.get_tone_prompt(ToneStyle.TECHNICAL)
        assert prompt is not None
        assert "technical" in prompt.lower()

    def test_get_tone_prompt_simple(self, service):
        """Test getting tone prompt for simple style"""
        from services.emotional_attunement import ToneStyle

        prompt = service.get_tone_prompt(ToneStyle.SIMPLE)
        assert prompt is not None
        assert "simple" in prompt.lower()

    def test_get_tone_prompt_encouraging(self, service):
        """Test getting tone prompt for encouraging style"""
        from services.emotional_attunement import ToneStyle

        prompt = service.get_tone_prompt(ToneStyle.ENCOURAGING)
        assert prompt is not None
        assert "encouraging" in prompt.lower() or "reassuring" in prompt.lower()

    def test_get_tone_prompt_direct(self, service):
        """Test getting tone prompt for direct style"""
        from services.emotional_attunement import ToneStyle

        prompt = service.get_tone_prompt(ToneStyle.DIRECT)
        assert prompt is not None
        assert "direct" in prompt.lower()

    def test_get_tone_prompt_invalid(self, service):
        """Test getting tone prompt for invalid style (should return default)"""

        # Create invalid tone style
        class InvalidTone:
            pass

        invalid_tone = InvalidTone()
        prompt = service.get_tone_prompt(invalid_tone)
        # Should return professional as default
        assert prompt is not None
        assert "professional" in prompt.lower()

    def test_build_enhanced_system_prompt_basic(self, service):
        """Test building enhanced system prompt with basic emotional profile"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.NEUTRAL,
            confidence=1.0,
            suggested_tone=ToneStyle.PROFESSIONAL,
            reasoning="No indicators",
            detected_indicators=[],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert base_prompt in enhanced
        assert "EMOTIONAL ATTUNEMENT" in enhanced
        assert "Detected State" in enhanced
        assert "Suggested Tone" in enhanced

    def test_build_enhanced_system_prompt_with_collaborator_name(self, service):
        """Test building enhanced system prompt with collaborator name"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.NEUTRAL,
            confidence=1.0,
            suggested_tone=ToneStyle.PROFESSIONAL,
            reasoning="No indicators",
            detected_indicators=[],
        )

        enhanced = service.build_enhanced_system_prompt(
            base_prompt, profile, collaborator_name="John Doe"
        )

        assert enhanced is not None
        assert "John Doe" in enhanced
        assert "User:" in enhanced

    def test_build_enhanced_system_prompt_stressed(self, service):
        """Test building enhanced system prompt for stressed state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.STRESSED,
            confidence=0.9,
            suggested_tone=ToneStyle.ENCOURAGING,
            reasoning="Multiple indicators",
            detected_indicators=["keyword:urgent", "pattern:!!+"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "stressed" in enhanced.lower()
        assert "reassuring" in enhanced.lower() or "actionable" in enhanced.lower()

    def test_build_enhanced_system_prompt_confused(self, service):
        """Test building enhanced system prompt for confused state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.CONFUSED,
            confidence=0.8,
            suggested_tone=ToneStyle.SIMPLE,
            reasoning="Confusion indicators",
            detected_indicators=["keyword:confused"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "confused" in enhanced.lower()
        assert "simple" in enhanced.lower() or "steps" in enhanced.lower()

    def test_build_enhanced_system_prompt_urgent(self, service):
        """Test building enhanced system prompt for urgent state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.URGENT,
            confidence=0.95,
            suggested_tone=ToneStyle.DIRECT,
            reasoning="Urgent indicators",
            detected_indicators=["keyword:urgent"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "urgent" in enhanced.lower()
        assert "direct" in enhanced.lower() or "solution" in enhanced.lower()

    def test_build_enhanced_system_prompt_sad(self, service):
        """Test building enhanced system prompt for sad state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.SAD,
            confidence=0.85,
            suggested_tone=ToneStyle.WARM,
            reasoning="Sad indicators",
            detected_indicators=["keyword:sad"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "sad" in enhanced.lower()
        assert "warm" in enhanced.lower() or "empathy" in enhanced.lower()

    def test_build_enhanced_system_prompt_anxious(self, service):
        """Test building enhanced system prompt for anxious state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.ANXIOUS,
            confidence=0.8,
            suggested_tone=ToneStyle.ENCOURAGING,
            reasoning="Anxious indicators",
            detected_indicators=["keyword:anxious"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "anxious" in enhanced.lower()
        assert "calm" in enhanced.lower() or "reassuring" in enhanced.lower()

    def test_build_enhanced_system_prompt_embarrassed(self, service):
        """Test building enhanced system prompt for embarrassed state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.EMBARRASSED,
            confidence=0.75,
            suggested_tone=ToneStyle.WARM,
            reasoning="Embarrassed indicators",
            detected_indicators=["keyword:embarrassed"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "embarrassed" in enhanced.lower()
        assert "tactful" in enhanced.lower() or "non-judgmental" in enhanced.lower()

    def test_build_enhanced_system_prompt_lonely(self, service):
        """Test building enhanced system prompt for lonely state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.LONELY,
            confidence=0.7,
            suggested_tone=ToneStyle.WARM,
            reasoning="Lonely indicators",
            detected_indicators=["keyword:lonely"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "lonely" in enhanced.lower()
        assert "warm" in enhanced.lower() or "present" in enhanced.lower()

    def test_build_enhanced_system_prompt_scared(self, service):
        """Test building enhanced system prompt for scared state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.SCARED,
            confidence=0.9,
            suggested_tone=ToneStyle.ENCOURAGING,
            reasoning="Scared indicators",
            detected_indicators=["keyword:scared"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "scared" in enhanced.lower()
        assert "gentle" in enhanced.lower() or "reassuring" in enhanced.lower()

    def test_build_enhanced_system_prompt_worried(self, service):
        """Test building enhanced system prompt for worried state"""
        from services.emotional_attunement import EmotionalProfile, EmotionalState, ToneStyle

        base_prompt = "You are a helpful assistant."
        profile = EmotionalProfile(
            detected_state=EmotionalState.WORRIED,
            confidence=0.8,
            suggested_tone=ToneStyle.ENCOURAGING,
            reasoning="Worried indicators",
            detected_indicators=["keyword:worried"],
        )

        enhanced = service.build_enhanced_system_prompt(base_prompt, profile)

        assert enhanced is not None
        assert "worried" in enhanced.lower()
        assert "supportive" in enhanced.lower() or "practical" in enhanced.lower()

    def test_get_stats(self, service):
        """Test getting service statistics"""
        stats = service.get_stats()

        assert stats is not None
        assert "supported_states" in stats
        assert "supported_tones" in stats
        assert "emotion_patterns" in stats
        assert "states" in stats
        assert "tones" in stats
        assert len(stats["states"]) > 0
        assert len(stats["tones"]) > 0

    def test_analyze_message_multilingual(self, service):
        """Test analyzing messages in multiple languages"""
        # Italian
        message_it = "Sono triste e preoccupato"
        profile_it = service.analyze_message(message_it)
        assert profile_it is not None

        # Indonesian
        message_id = "Aku sedih dan khawatir"
        profile_id = service.analyze_message(message_id)
        assert profile_id is not None

    def test_analyze_message_pattern_matching(self, service):
        """Test pattern matching in message analysis"""
        # Test regex pattern matching
        message = "What does this mean? How does it work?"
        profile = service.analyze_message(message)

        assert profile is not None
        # Should detect confused state via pattern matching
        assert any("pattern" in ind for ind in profile.detected_indicators)
