"""A WhatsApp thread opens with a greeting, and the detector had no greeting.

Sibling of ``test_language_markers_cover_business_questions``, which cured the
opposite half: a client who opens with a BUSINESS QUESTION rather than a
greeting. This file cures the half that was left — the client who opens with a
GREETING and nothing else, which on WhatsApp is the commoner of the two.

Measured on 2026-08-25 against 16 real Italian openers, before this change:
**10 returned ENGLISH**, including "Buongiorno", "Salve", "Buonasera" and
"Qual e la differenza tra KITAS e KITAP". The Italian row carried exactly one
greeting ("ciao"); Spanish carried "hola" alone and German "hallo" alone, so
"Buenos dias" and "Guten Tag" fell through the same hole.

That default is not inert — ``wrap_query_with_language_instruction`` renders it
to the model as ``YOUR ENTIRE RESPONSE MUST BE IN ENGLISH``. An Italian client
saying good morning was being answered in English, by construction.

Two mechanisms are under test here and they fail differently, so both get
guilt cases: the widened marker rows, and the elongation fold that lets
"ciaooo" and "graziee" reach those rows at all.
"""

import re

import pytest

from backend.services.rag.agentic.query_helpers import (
    _LATIN_MARKERS,
    INDONESIAN_MARKERS,
    LANGUAGE_DISPLAY_NAMES,
    detect_query_language,
    wrap_query_with_language_instruction,
)

# Greetings and short openers. Every ITALIAN case here returned ENGLISH before
# 2026-08-25; the other rows are the same defect in the languages that shared it.
GUILT_GREETINGS: list[tuple[str, str]] = [
    ("ITALIAN", "Buongiorno"),
    ("ITALIAN", "Buonasera"),
    ("ITALIAN", "Buonanotte"),
    ("ITALIAN", "Salve"),
    ("ITALIAN", "Salve, avrei una domanda"),
    ("ITALIAN", "Buongiorno, ho una domanda"),
    ("ITALIAN", "Scusate, potete aiutarmi?"),
    ("ITALIAN", "Qual e la differenza tra KITAS e KITAP"),
    ("ITALIAN", "Qual \u00e8 la differenza tra KITAS e KITAP"),
    ("ITALIAN", "Mi serve aiuto con il visto"),
    ("ITALIAN", "Ho bisogno di informazioni sul permesso di soggiorno"),
    ("ITALIAN", "Volevo sapere i prezzi"),
    ("SPANISH", "Buenos dias"),
    ("SPANISH", "Buenos d\u00edas"),
    ("SPANISH", "Buenas tardes"),
    ("SPANISH", "Buenas noches"),
    ("GERMAN", "Guten Tag"),
    ("GERMAN", "Guten Morgen"),
    ("GERMAN", "Guten Abend"),
    ("FRENCH", "Bonsoir"),
    ("FRENCH", "Salut"),
]

# The SECOND mechanism: a greeting the client stretched. These reach the rows
# above only because the elongation fold runs first.
GUILT_ELONGATED: list[tuple[str, str]] = [
    ("ITALIAN", "ciaooo"),
    ("ITALIAN", "ciaoo"),
    ("ITALIAN", "graziee"),
    ("ITALIAN", "grazieee"),
    ("ITALIAN", "buongiornooo"),
]

# English is this detector's DEFAULT, so it is where a widened row does its
# damage: every case below has to stay English after the change. The last four
# are chosen against the elongation fold specifically — each ends in a doubled
# vowel, which is exactly what the trailing-vowel rule rewrites.
INNOCENCE_ENGLISH: list[str] = [
    "Hello",
    "Good morning",
    "Hi there",
    "Thanks a lot",
    "How much does a KITAS cost?",
    "I need help with my visa",
    "What is the price?",
    "How long does the process take?",
    "Can I extend my visa?",
    "Is the service free of charge?",
    "We need three copies of the deed",
    "Please send it to the committee",
    "What is the KBLI code for a coffee shop?",
]

# The languages that already worked, in the shape they already worked in.
INNOCENCE_OTHER: list[tuple[str, str]] = [
    ("ITALIAN", "Quali documenti servono per aprire una PT PMA in Indonesia?"),
    ("FRENCH", "Bonjour"),
    ("FRENCH", "Quels documents faut-il pour ouvrir une PT PMA en Indonesie?"),
    ("SPANISH", "Hola"),
    ("SPANISH", "Cu\u00e1nto cuesta constituir una empresa en Bali?"),
    ("GERMAN", "Hallo"),
    ("GERMAN", "Welche Dokumente brauche ich, um eine PT PMA zu gruenden?"),
    # GUILT for the fold's narrowness, not innocence for the rows: "muss" ends
    # in a doubled CONSONANT and is a decisive German marker. A trailing-double
    # fold written one character wider than it is would delete it here.
    ("GERMAN", "Ich muss ein Visum beantragen"),
    ("INDONESIAN", "Dokumen apa saja yang diperlukan untuk mendirikan PT PMA?"),
    ("INDONESIAN", "Berapa harga KITAS?"),
    (
        "RUSSIAN",
        "\u041a\u0430\u043a\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b \u043d\u0443\u0436\u043d\u044b?",
    ),
]


@pytest.mark.parametrize(("expected", "query"), GUILT_GREETINGS)
def test_a_bare_greeting_is_detected(expected: str, query: str) -> None:
    assert detect_query_language(query) == expected


@pytest.mark.parametrize(("expected", "query"), GUILT_ELONGATED)
def test_a_stretched_greeting_is_detected(expected: str, query: str) -> None:
    """Fails if the elongation fold is removed, even with the rows intact."""
    assert detect_query_language(query) == expected


@pytest.mark.parametrize("query", INNOCENCE_ENGLISH)
def test_english_is_still_english(query: str) -> None:
    assert detect_query_language(query) == "ENGLISH"


@pytest.mark.parametrize(("expected", "query"), INNOCENCE_OTHER)
def test_the_other_languages_are_unmoved(expected: str, query: str) -> None:
    assert detect_query_language(query) == expected


@pytest.mark.parametrize(("expected", "query"), GUILT_GREETINGS + GUILT_ELONGATED)
def test_the_model_is_not_ordered_to_answer_a_greeting_in_english(
    expected: str, query: str
) -> None:
    """The harm, asserted where it actually reached the client.

    Detection is the mechanism; the instruction built from it is the defect.
    Pinning both means an edit that fixes one while breaking the other still
    fails, the same way the business-question sibling pins its chain.
    """
    wrapped = wrap_query_with_language_instruction(query)
    assert f"MUST BE IN {LANGUAGE_DISPLAY_NAMES[expected]}" in wrapped
    assert "MUST BE IN ENGLISH" not in wrapped


# ── The two claims the fold rests on, asserted instead of asserted-in-a-comment ──


def _every_marker() -> list[tuple[str, str]]:
    """(language, marker) for every decisive and homograph marker in this module."""
    rows: list[tuple[str, str]] = [("INDONESIAN", m) for m in INDONESIAN_MARKERS]
    for language, decisive, homographs in _LATIN_MARKERS:
        rows.extend((language, m) for m in decisive + homographs)
    return rows


def test_no_marker_contains_a_run_of_three_identical_characters() -> None:
    """The 3-character floor may only fold noise, never a marker.

    ``_collapse_elongation`` runs BEFORE every marker match. If a marker ever
    carried a triple, the fold would rewrite it out of its own list and the row
    would go quietly dead — green tests, silent loss of recall. This is the
    invariant that makes the floor safe, so it is checked rather than believed.
    """
    triple = re.compile(r"(.)\1{2,}")
    offenders = [(lang, m) for lang, m in _every_marker() if triple.search(m)]
    assert not offenders, f"markers the elongation fold would rewrite: {offenders}"


def test_no_marker_ends_in_a_doubled_vowel() -> None:
    """The trailing-vowel rule may only recover a marker, never manufacture one.

    Restricting the 2-character fold to VOWELS is what keeps German "muss"
    alive. This asserts the other half: that no marker in any row ENDS in a
    doubled vowel, so the rule cannot fold a real marker into something else.
    """
    trailing = re.compile(r"([aeiou])\1+$")
    offenders = [(lang, m) for lang, m in _every_marker() if trailing.search(m)]
    assert not offenders, f"markers the trailing-vowel fold would rewrite: {offenders}"


def test_the_marker_corpus_this_file_guards_is_not_empty() -> None:
    """A structural check over an empty corpus is green and means nothing.

    Both tests above iterate a derived list. If ``_LATIN_MARKERS`` were renamed
    or emptied they would pass over zero rows and report success, so the count
    is pinned to a floor well below the real size (currently ~150).
    """
    assert len(_every_marker()) > 100
