"""The identity fast-path: guilt, innocence, and the language it answers in.

Why this file exists (superscar #3, UNDER-match): the assistant-identity
trigger was one whole-string-anchored regex covering ~4 phrasings in 2
languages, with no `siapa` at all. "Chi ti ha creato e come ti chiami?" fell
through to retrieval, found nothing, scored evidence 0.0 and was discarded by
the abstain gate — which on WhatsApp is SILENCE, not a worse answer.

Innocence comes first here on purpose: widening a trigger is how you buy an
over-match, and the neighbours of "who are you" are real client questions
("Who are the directors of a PT PMA?", "Who are you going to assign to my
case?"). Every one of them must still reach retrieval.
"""

from __future__ import annotations

import pytest

from backend.app.core.config import settings
from backend.services.rag.agentic.prompt_builder import (
    _ASSISTANT_IDENTITY_PATTERNS,
    SystemPromptBuilder,
)


@pytest.fixture
def builder() -> SystemPromptBuilder:
    return SystemPromptBuilder()


# --- INNOCENCE: none of these is an identity question -----------------------

NOT_IDENTITY = [
    # The dangerous neighbours: same opening words, different entity.
    "Who are the directors of a PT PMA?",
    "Who are you going to assign to my case?",
    "Who are you sending to the immigration office?",
    "What are your office hours?",
    "What are your fees for an E28A KITAS?",
    "What are you charging for company setup?",
    "Who created this company in 2019?",
    "Who made the payment last month?",
    "What is your company registration number?",
    # Italian neighbours.
    "Chi sono i soci di una PT PMA?",
    "Chi ti ha detto che serve il KITAS?",
    "Cosa serve per aprire una PT PMA?",
    # Indonesian neighbours.
    "Siapa yang membuat laporan LKPM?",
    "Siapa saja direksi PT PMA?",
    "Apa itu KITAS?",
    # Ordinary business questions.
    "What is KITAS?",
    "Berapa modal disetor PT PMA?",
]


@pytest.mark.parametrize("query", NOT_IDENTITY)
def test_innocence_non_identity_questions_reach_retrieval(
    builder: SystemPromptBuilder, query: str
) -> None:
    """A fast-path answer here would REPLACE a grounded answer with a canned one."""
    assert builder.check_identity_questions(query) is None


# --- GUILT: these are identity questions and were silence before ------------

IDENTITY_ASKS = [
    # (query, language the answer must be in)
    ("Chi ti ha creato e come ti chiami?", "ITALIAN"),  # the live 2026-08-09 case
    ("Chi sei?", "ITALIAN"),
    ("Ciao, chi sei tu?", "ITALIAN"),
    ("Come ti chiami?", "ITALIAN"),
    ("Qual è il tuo nome?", "ITALIAN"),
    ("Chi ti ha fatto?", "ITALIAN"),
    ("Who are you?", "ENGLISH"),
    ("who are you", "ENGLISH"),
    ("What are you?", "ENGLISH"),
    ("Who created you?", "ENGLISH"),
    ("Who made you?", "ENGLISH"),
    ("What's your name?", "ENGLISH"),
    ("What is your name?", "ENGLISH"),
    ("Siapa kamu?", "INDONESIAN"),
    ("siapa kamu", "INDONESIAN"),
    ("Kamu siapa sih?", "INDONESIAN"),
    ("Siapa nama kamu?", "INDONESIAN"),
    ("Siapa yang membuat kamu?", "INDONESIAN"),
    ("Кто ты?", "RUSSIAN"),
    ("Хто ти?", "UKRAINIAN"),
]


@pytest.mark.parametrize("query,language", IDENTITY_ASKS)
def test_guilt_identity_questions_are_answered_in_their_own_language(
    builder: SystemPromptBuilder, query: str, language: str
) -> None:
    answer = builder.check_identity_questions(query)
    assert answer is not None, f"{query!r} still falls through to RAG → abstain → silence"
    assert answer == builder.assistant_identity_answer(language)


def test_the_brand_name_does_not_flip_the_reply_language(
    builder: SystemPromptBuilder,
) -> None:
    """The old marker list carried the company name and "zantara", so an
    ENGLISH question that merely NAMED the assistant was answered in Italian."""
    answer = builder.check_identity_questions("Zantara, who are you?")
    assert answer == builder.assistant_identity_answer("ENGLISH")
    assert "Sono Zantara" not in answer


def test_every_declared_identity_language_has_its_own_sentence(
    builder: SystemPromptBuilder,
) -> None:
    """Adding a pattern without adding its answer fails SILENTLY in prod — the
    asker just gets English. This is the tripwire for that."""
    english = builder.assistant_identity_answer("ENGLISH")
    declared = {language for language, _ in _ASSISTANT_IDENTITY_PATTERNS}
    assert "ENGLISH" in declared  # anti-vacuous: the default must be reachable
    for language in declared:
        answer = builder.assistant_identity_answer(language)
        if language == "ENGLISH":
            assert answer == english
        else:
            assert answer != english, (
                f"{language} is declared in _ASSISTANT_IDENTITY_PATTERNS but falls "
                "through to the English default"
            )


def test_self_description_answers_in_the_language_of_the_pattern(
    builder: SystemPromptBuilder,
) -> None:
    """ "Parlami di te" carried no word from the old Italian marker list, so an
    Italian asker was answered in English."""
    italian = builder.check_identity_questions("Parlami di te")
    english = builder.check_identity_questions("Tell me about yourself")
    indonesian = builder.check_identity_questions("Apa yang bisa kamu lakukan?")

    assert italian is not None and english is not None and indonesian is not None
    assert "Ecco cosa posso fare" in italian
    assert "Here's what I can help with" in english
    assert "Yang bisa gue bantu" in indonesian


def test_company_question_answers_in_the_language_it_was_asked_in(
    builder: SystemPromptBuilder,
) -> None:
    """The brand name is in every language's question; it used to make the
    ENGLISH form answer in Italian."""
    company = settings.COMPANY_NAME
    assert builder.check_identity_questions(f"What does {company} do?") == (
        f"{company} is a consultancy specialized in visas/KITAS, business setup (PT PMA), "
        "and legal support for foreigners in Indonesia."
    )
    assert builder.check_identity_questions(f"Cosa fa {company}?") == (
        f"{company} è una consulenza specializzata in visa, KITAS, setup aziendale (PT PMA) "
        "e questioni legali per stranieri in Indonesia."
    )


def test_who_am_i_branch_is_untouched_by_the_widening(
    builder: SystemPromptBuilder,
) -> None:
    """`siapa kamu` (who are YOU) and `siapa saya` (who am I) differ by one
    word and must not collapse into each other."""
    context = {"profile": {"name": "Marco"}, "facts": ["Interested in PT PMA"]}

    who_am_i = builder.check_identity_questions("Siapa saya?", context)
    who_are_you = builder.check_identity_questions("Siapa kamu?", context)

    assert who_am_i is not None and "Marco" in who_am_i
    assert who_are_you == builder.assistant_identity_answer("INDONESIAN")
