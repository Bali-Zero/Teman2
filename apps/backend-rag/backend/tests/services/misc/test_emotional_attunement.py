from __future__ import annotations

from backend.services.misc.emotional_attunement import (
    EmotionalAttunementService,
    EmotionalProfile,
    EmotionalState,
    ToneStyle,
)


def test_analyze_message_detects_confusion_and_suggests_simple_tone() -> None:
    service = EmotionalAttunementService()

    profile = service.analyze_message("I am confused?? what does this mean?")

    assert profile.detected_state is EmotionalState.CONFUSED
    assert profile.suggested_tone is ToneStyle.SIMPLE
    assert "questions:3" in profile.detected_indicators


def test_analyze_message_applies_valid_collaborator_tone_preference() -> None:
    service = EmotionalAttunementService()

    profile = service.analyze_message(
        "thanks, really appreciate this",
        collaborator_preferences={"preferred_tone": "direct"},
    )

    assert profile.detected_state is EmotionalState.GRATEFUL
    assert profile.suggested_tone is ToneStyle.DIRECT
    assert "Preference override: direct" in profile.reasoning


def test_get_tone_prompt_returns_fallback_for_unknown_tone() -> None:
    service = EmotionalAttunementService()

    assert service.get_tone_prompt(ToneStyle.WARM).startswith("Use a warm")
    assert service.get_tone_prompt("missing").startswith(  # type: ignore[arg-type]
        "Maintain a professional"
    )


def test_build_enhanced_system_prompt_includes_emotional_context() -> None:
    service = EmotionalAttunementService()
    profile = EmotionalProfile(
        detected_state=EmotionalState.STRESSED,
        confidence=0.9,
        suggested_tone=ToneStyle.ENCOURAGING,
        reasoning="test",
        detected_indicators=["keyword:urgent"],
    )

    prompt = service.build_enhanced_system_prompt(
        "Base prompt",
        profile,
        collaborator_name="Ada",
    )

    assert prompt.startswith("Base prompt")
    assert "User: Ada" in prompt
    assert "Detected State: Stressed" in prompt
    assert "Suggested Tone: Encouraging" in prompt
    assert "User appears stressed" in prompt


def test_get_stats_reports_supported_states_and_tones() -> None:
    stats = EmotionalAttunementService().get_stats()

    assert stats["supported_states"] == len(EmotionalState)
    assert stats["supported_tones"] == len(ToneStyle)
    assert "confused" in stats["states"]
    assert "direct" in stats["tones"]
