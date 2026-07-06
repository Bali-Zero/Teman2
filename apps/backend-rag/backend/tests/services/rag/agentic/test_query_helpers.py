from __future__ import annotations

from backend.services.rag.agentic.query_helpers import (
    build_recall_prompt,
    detect_query_language,
    format_conversation_history_for_recall,
    is_conversation_recall_query,
    wrap_query_with_language_instruction,
)


def test_detect_query_language_handles_supported_markers_and_defaults() -> None:
    assert detect_query_language("") == "UNKNOWN"
    assert detect_query_language("Terima kasih, saya mau KITAS") == "INDONESIAN"
    assert detect_query_language("ciao, posso avere info?") == "ITALIAN"
    assert detect_query_language("bonjour merci") == "FRENCH"
    assert detect_query_language("hola gracias") == "SPANISH"
    assert detect_query_language("hallo danke") == "GERMAN"
    assert (
        detect_query_language("\u041f\u0440\u0438\u0432\u0456\u0442, \u044f\u043a?")
        == "UKRAINIAN"
    )
    assert detect_query_language("\u041f\u0440\u0438\u0432\u0435\u0442") == "RUSSIAN"
    assert detect_query_language("\u0645\u0631\u062d\u0628\u0627") == "ARABIC"
    assert detect_query_language("\u4f60\u597d") == "CHINESE"
    assert detect_query_language("How much is KITAS?") == "ENGLISH"


def test_wrap_query_with_language_instruction_keeps_indonesian_tool_policy() -> None:
    wrapped = wrap_query_with_language_instruction("Saya mau tahu harga KITAS")

    assert wrapped.endswith("Saya mau tahu harga KITAS")
    assert "TOOL USAGE" in wrapped
    assert "pricing_tool" in wrapped
    assert "LANGUAGE:" not in wrapped


def test_wrap_query_with_language_instruction_adds_same_language_instruction() -> None:
    wrapped = wrap_query_with_language_instruction("ciao, quanto costa E31A?")

    assert wrapped.endswith("ciao, quanto costa E31A?")
    assert "LANGUAGE: ITALIAN" in wrapped
    assert "ALWAYS use vector_search FIRST" in wrapped
    assert wrap_query_with_language_instruction(" ") == " "


def test_is_conversation_recall_query_matches_only_recall_phrases() -> None:
    assert is_conversation_recall_query("Ti ricordi il cliente di cui parlavamo?") is True
    assert is_conversation_recall_query("do you remember what I said?") is True
    assert is_conversation_recall_query("Quanto costa un visto E31A?") is False


def test_format_conversation_history_for_recall_limits_recent_dict_messages() -> None:
    history = [
        {"role": "system", "content": "ignored role becomes assistant"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        "malformed",
        {"role": "user", "content": "third"},
    ]

    formatted = format_conversation_history_for_recall(history, max_messages=3)

    assert formatted == "ASSISTANT: second\nUSER: third"


def test_build_recall_prompt_includes_history_question_and_response_contract() -> None:
    prompt = build_recall_prompt("Come si chiama il cliente?", "USER: cliente Marco")

    assert "CONVERSATION HISTORY:" in prompt
    assert "USER: cliente Marco" in prompt
    assert "USER QUESTION: Come si chiama il cliente?" in prompt
    assert "Respond in the SAME language" in prompt
