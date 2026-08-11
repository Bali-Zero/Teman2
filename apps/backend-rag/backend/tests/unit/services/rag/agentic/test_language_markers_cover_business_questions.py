"""A German or Spanish client who does not greet you must still be detected.

Before 2026-08-10 the Spanish and German marker rows held five entries each and
every one was a greeting or a courtesy — "hola"/"gracias", "hallo"/"danke". A
client who opens with a business question rather than a greeting scored zero,
and `detect_query_language` returned its ENGLISH **default**.

That default is not inert. `wrap_query_with_language_instruction` feeds the
result through `LANGUAGE_DISPLAY_NAMES` into a hard order —
``YOUR ENTIRE RESPONSE MUST BE IN {lang}`` — so "I could not identify this
language" was rendered to the model as "answer this in English". The map
already carried ``GERMAN (Deutsch)`` and ``SPANISH (Español)``; only the
detector was blind.

The guilt cases below are business questions with no greeting in them, because
that is what a real first message looks like. The innocence cases are every
other language this detector serves, asked the same way — a marker that steals
a French or Indonesian question is not an improvement.
"""

import pytest

from backend.services.rag.agentic.query_helpers import (
    LANGUAGE_DISPLAY_NAMES,
    detect_query_language,
    wrap_query_with_language_instruction,
)

# Business questions, no greeting anywhere in them. Each previously → ENGLISH.
GUILT: list[tuple[str, str]] = [
    ("GERMAN", "Welche Dokumente brauche ich, um eine PT PMA in Indonesien zu gruenden?"),
    ("GERMAN", "Ich möchte ein Unternehmen in Bali gründen, was kostet das?"),
    ("GERMAN", "Benötige ich ein Visum für eine Geschäftsreise?"),
    ("SPANISH", "Que documentos necesito para abrir una PT PMA en Indonesia?"),
    ("SPANISH", "Cuánto cuesta constituir una empresa en Bali?"),
    ("SPANISH", "Quisiera saber el trámite para extranjeros"),
]

# The languages that already worked, asked in the same shape. Widening the two
# thin rows must not move any of these.
INNOCENCE: list[tuple[str, str]] = [
    ("ENGLISH", "Which documents are required for company registration in Indonesia?"),
    ("ENGLISH", "How much does it cost to set up a PT PMA with Bali Zero?"),
    ("ENGLISH", "What is the 2026 penalty schedule for a late LKPM filing?"),
    ("ITALIAN", "Quali documenti servono per aprire una PT PMA in Indonesia?"),
    ("ITALIAN", "Quanto costa aprire una società a Bali?"),
    ("FRENCH", "Quels documents faut-il pour ouvrir une PT PMA en Indonesie?"),
    ("INDONESIAN", "Dokumen apa saja yang diperlukan untuk mendirikan PT PMA?"),
    ("RUSSIAN", "Какие документы нужны для открытия компании в Индонезии?"),
    ("UKRAINIAN", "Які документи потрібні для відкриття PT PMA в Індонезії?"),
]


@pytest.mark.parametrize(("expected", "query"), GUILT)
def test_business_question_without_a_greeting_is_detected(expected: str, query: str) -> None:
    assert detect_query_language(query) == expected


@pytest.mark.parametrize(("expected", "query"), INNOCENCE)
def test_the_languages_that_already_worked_still_work(expected: str, query: str) -> None:
    assert detect_query_language(query) == expected


@pytest.mark.parametrize(("expected", "query"), GUILT)
def test_the_model_is_no_longer_ordered_to_answer_in_english(expected: str, query: str) -> None:
    """The defect that actually reached the client, asserted end to end.

    Detection alone is not the harm; the harm is the instruction built from it.
    This pins the whole chain, so a future edit that fixes detection while
    breaking the map — or vice versa — still fails.
    """
    wrapped = wrap_query_with_language_instruction(query)
    assert f"MUST BE IN {LANGUAGE_DISPLAY_NAMES[expected]}" in wrapped
    assert "MUST BE IN ENGLISH" not in wrapped


def test_every_language_that_reaches_the_lookup_has_a_display_name() -> None:
    """No language that reaches the lookup may fall through to the vague fallback.

    `wrap_query_with_language_instruction` defaults to "the user's language" —
    a self-reference that names nothing and constrains nothing, and one of the
    two documented paths to the 2026-07-30 reply-language drift.

    INDONESIAN is excluded, and the exclusion is the point rather than a
    convenience: the wrapper returns on its own branch (Jaksel is allowed
    there) BEFORE the display-name lookup, so it never consults the map. An
    earlier draft of this test asserted the map covered every emitted language
    and went red — the assertion was wrong, not the code.

    Derived from the corpora above rather than a hand-copied list, so adding a
    case there cannot silently skip this check.
    """
    reaches_lookup = {lang for lang, _ in GUILT + INNOCENCE} - {"INDONESIAN"}
    for expected in reaches_lookup:
        assert expected in LANGUAGE_DISPLAY_NAMES, f"{expected} has no display name"
