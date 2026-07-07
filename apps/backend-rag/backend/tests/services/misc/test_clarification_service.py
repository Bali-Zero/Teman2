from __future__ import annotations

from backend.services.misc.clarification_service import (
    AmbiguityType,
    ClarificationService,
)


def test_detect_ambiguity_flags_short_incomplete_question() -> None:
    service = ClarificationService()

    result = service.detect_ambiguity("how much")

    assert result["is_ambiguous"] is True
    assert result["confidence"] == 0.6000000000000001
    assert result["ambiguity_type"] == AmbiguityType.INCOMPLETE.value
    assert result["clarification_needed"] is True
    assert len(result["reasons"]) == 2


def test_detect_ambiguity_uses_conversation_history_for_pronouns() -> None:
    service = ClarificationService()

    first_message = service.detect_ambiguity("Can I use this now")
    with_context = service.detect_ambiguity(
        "Can I use this now",
        conversation_history=[{"role": "user", "content": "We discussed KITAS"}],
    )

    assert first_message["ambiguity_type"] == AmbiguityType.UNCLEAR_CONTEXT.value
    assert first_message["confidence"] >= 0.5
    assert with_context["confidence"] < first_message["confidence"]


def test_generate_clarification_request_adds_topic_options() -> None:
    service = ClarificationService()

    message = service.generate_clarification_request(
        "tell me about visa",
        {"ambiguity_type": AmbiguityType.VAGUE.value},
        language="en",
    )

    assert "aspect of visa" in message
    assert "For example:" in message
    assert "- Tourist visa" in message


def test_should_request_clarification_respects_context_and_force_threshold() -> None:
    service = ClarificationService()

    assert service.should_request_clarification("how much") is True
    assert (
        service.should_request_clarification(
            "how much",
            conversation_history=[{"role": "user", "content": "visa"}],
        )
        is False
    )
    assert service.should_request_clarification("Can I use this now", force_threshold=0.4) is True


async def test_health_check_reports_configuration_and_features() -> None:
    health = await ClarificationService().health_check()

    assert health["status"] == "healthy"
    assert health["features"]["pattern_based"] is True
    assert health["features"]["supported_languages"] == ["en", "it", "id"]
    assert "vague" in health["features"]["ambiguity_types"]
    assert health["configuration"]["ambiguity_threshold"] == 0.6
