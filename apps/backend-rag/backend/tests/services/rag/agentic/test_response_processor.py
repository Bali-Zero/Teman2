from __future__ import annotations

import pytest

from backend.services.rag.agentic import response_processor as module
from backend.services.rag.agentic.response_processor import post_process_response


def test_post_process_response_cleans_and_formats_procedural_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "clean_response",
        lambda response: "Prepare all sponsor documents carefully. Submit the application online.",
    )
    monkeypatch.setattr(module, "detect_language", lambda query: "en")
    monkeypatch.setattr(module, "is_procedural_question", lambda query: True)
    monkeypatch.setattr(module, "has_emotional_content", lambda query: False)

    result = post_process_response("THOUGHT: hidden", "How do I apply?")

    assert result == (
        "1. Prepare all sponsor documents carefully\n"
        "2. Submit the application online."
    )


def test_post_process_response_keeps_existing_numbered_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "clean_response", lambda response: "1. Prepare docs\n2. Apply")
    monkeypatch.setattr(module, "detect_language", lambda query: "en")
    monkeypatch.setattr(module, "is_procedural_question", lambda query: True)
    monkeypatch.setattr(module, "has_emotional_content", lambda query: False)

    assert post_process_response("raw", "How to renew?") == "1. Prepare docs\n2. Apply"


def test_post_process_response_adds_emotional_acknowledgment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "clean_response", lambda response: "You can still fix it.")
    monkeypatch.setattr(module, "detect_language", lambda query: "en")
    monkeypatch.setattr(module, "is_procedural_question", lambda query: False)
    monkeypatch.setattr(module, "has_emotional_content", lambda query: True)

    result = post_process_response("raw", "I am stressed about my visa")

    assert result.startswith("I understand the frustration")
    assert result.endswith("You can still fix it.")


def test_post_process_response_does_not_duplicate_emotional_acknowledgment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "clean_response",
        lambda response: "I understand this is stressful. You can still fix it.",
    )
    monkeypatch.setattr(module, "detect_language", lambda query: "en")
    monkeypatch.setattr(module, "is_procedural_question", lambda query: False)
    monkeypatch.setattr(module, "has_emotional_content", lambda query: True)

    result = post_process_response("raw", "I am stressed")

    assert result == "I understand this is stressful. You can still fix it."


def test_post_process_response_strips_outer_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "clean_response", lambda response: "  Clean answer  ")
    monkeypatch.setattr(module, "detect_language", lambda query: "en")
    monkeypatch.setattr(module, "is_procedural_question", lambda query: False)
    monkeypatch.setattr(module, "has_emotional_content", lambda query: False)

    assert post_process_response("raw", "KITAS") == "Clean answer"
