"""The casual-conversation gate: a false positive here is a STONEWALL.

`check_casual_conversation` does not pick a different answer — when it fires,
`get_casual_response` returns a canned line ("Got it! 😊 If you have questions
about visas, business, or life in Indonesia, I'm here to help!") and retrieval
never runs. That is how a team member asked the same LKPM question four times
in a row (prod, 2026-07-28) and got the identical smiley four times: it reads
as stonewalling, and the asker has no way to tell it apart from a refusal.

Measured on this corpus before the cure: 9 of 20 realistic business questions
were captured, 0 of 8 genuinely casual ones were missed. The gate was not
sitting at a precision/recall trade-off — it was simply over-matching, and
the recall side had room to spare.
"""

from __future__ import annotations

import pytest

from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder


@pytest.fixture
def builder() -> SystemPromptBuilder:
    return SystemPromptBuilder()


# --- GUILT: every one of these was answered with the canned brush-off -------

BUSINESS_QUESTIONS = [
    # The reported shape: an ordinary word for "today" swallowed the question.
    "Do I need to file LKPM today?",
    "Is the LKPM report due today?",
    "Apakah LKPM harus dilaporkan hari ini?",
    "Cosa succede oggi con la scadenza del visto?",
    # Preference words are how clients ask for advice, not small talk.
    "Can you recommend the best structure for a villa purchase?",
    "What is the best KBLI for a surf school?",
    # A place name and a contract term that happen to be beach words.
    "Pantai Berawa property zoning — what is allowed?",
    "Sunset clause nel contratto di lease, come funziona?",
    # An operational status question about a real client.
    "Il cliente e' stanco di aspettare, a che punto e' la pratica?",
    "Mood check: is the notary appointment confirmed?",
]


@pytest.mark.parametrize("query", BUSINESS_QUESTIONS)
def test_business_questions_are_not_brushed_off(builder: SystemPromptBuilder, query: str) -> None:
    assert builder.check_casual_conversation(query) is False
    assert builder.get_casual_response(query) is None


# --- INNOCENCE: real small talk must still short-circuit --------------------

CASUAL_MESSAGES = [
    "come stai?",
    "how are you?",
    "apa kabar?",
    "ok",
    "thanks",
    "what's the weather like in Bali?",
    "consigli un ristorante a Canggu?",
    "lagi bosen nih",
    "sono stanco oggi",
    "any good music in Canggu tonight?",
]


@pytest.mark.parametrize("query", CASUAL_MESSAGES)
def test_small_talk_still_gets_a_direct_answer(builder: SystemPromptBuilder, query: str) -> None:
    assert builder.check_casual_conversation(query) is True
    assert builder.get_casual_response(query) is not None


def test_the_business_allowlist_wins_over_a_casual_word(
    builder: SystemPromptBuilder,
) -> None:
    """The allowlist runs FIRST and is the mechanism that rescues a sentence
    carrying both — deleting a casual pattern is the last resort, not the
    first move."""
    # "stanco" is a casual word AND stays in the casual list; "cliente" is what
    # makes this sentence business.
    assert builder.check_casual_conversation("sono stanco") is True
    assert builder.check_casual_conversation("il cliente e' stanco") is False


def test_casual_words_are_matched_as_words_not_substrings(
    builder: SystemPromptBuilder,
) -> None:
    """superscar #3: "sunset" must not be read out of "Sunset clause", nor
    "bar" out of a longer stem."""
    assert builder.check_casual_conversation("what time is sunset?") is False  # deleted group
    assert builder.check_casual_conversation("andiamo al bar?") is True
    assert builder.check_casual_conversation("barometric pressure trend") is False
