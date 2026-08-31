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
    _collapse_elongation,
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


def test_the_fold_is_a_no_op_on_every_marker() -> None:
    """DESTROY direction: the fold must not rewrite any marker out of its list.

    ``_collapse_elongation`` runs BEFORE every marker match, so a marker the
    fold rewrites can never be matched again — its row would go quietly dead:
    green tests, silent loss of recall. Asserting the fold directly (rather
    than asserting the two regex shapes it happens to be built from) is what
    keeps this true if the fold's rules are ever widened. German "muss" is the
    entry that makes the trailing rule vowel-only; it is checked here by being
    in the corpus, not by being named.
    """
    rewritten = [(lang, m, _collapse_elongation(m)) for lang, m in _every_marker()]
    offenders = [(lang, m, f) for lang, m, f in rewritten if f != m]
    assert not offenders, f"the fold rewrites these markers: {offenders}"


# Words that end in a doubled vowel and are NOT markers. If any of them folded
# ONTO a marker, the fold would manufacture a language out of ordinary English.
FOREIGN_WORDS_ENDING_IN_A_DOUBLED_VOWEL: list[str] = [
    "see",
    "free",
    "three",
    "agree",
    "coffee",
    "committee",
    "employee",
    "guarantee",
    "fee",
    "tee",
    "too",
    "zoo",
    "bee",
]


@pytest.mark.parametrize("word", FOREIGN_WORDS_ENDING_IN_A_DOUBLED_VOWEL)
def test_the_fold_does_not_manufacture_a_marker(word: str) -> None:
    """MANUFACTURE direction — and it needs its OWN test, which is the point.

    The first draft of this file asserted "no marker ends in a doubled vowel"
    and called that proof the fold cannot manufacture one. It is not: an
    adversarial pass pointed out that manufacture runs the other way — a
    NON-marker word ending in a doubled vowel folding ONTO a marker — which
    depends on markers ending in a SINGLE vowel, and several do ("come",
    "tra", "hola", "eine"). The invariant was true and irrelevant; a short
    vowel-final marker like "se" added tomorrow would let "see" manufacture it
    with that invariant still green.

    So this checks the thing itself: fold the words that actually have the
    shape, and assert none of them lands on a marker.
    """
    markers = {m for _lang, m in _every_marker()}
    folded = _collapse_elongation(word)
    assert folded not in markers, (
        f"{word!r} folds to {folded!r}, which IS a marker — the fold would "
        f"manufacture a language out of an ordinary English word"
    )


# ── The fold is INTERNAL: it may decide, it may never reach the model ──


def test_the_folded_string_never_reaches_the_prompt() -> None:
    """The worst thing this fold could do is not misdetect — it is CORRUPT.

    ``_collapse_elongation`` rewrites digits as readily as letters: measured,
    "rp 2.500.000.000" folds to "rp 2.500.0.0" and "kbli 55111" to "kbli 551".
    Those are a paid-up capital figure and a business classification code — if
    the folded text were ever the text handed to the model instead of merely
    the text scored for language, this change would silently falsify the
    client's own numbers. It is not, and this pins that.

    Note on the probe: the obvious check — ``"kbli 551" not in output`` — is
    VACUOUS, because "kbli 551" is a substring of the correct "kbli 55111".
    It reports success on a corrupted prompt too. The assertion below compares
    the full numeric tokens instead, which cannot pass by coincidence.
    """
    query = "Serve Rp 2.500.000.000 di capitale per KBLI 55111? Buongiorno"
    wrapped = wrap_query_with_language_instruction(query)

    assert query in wrapped, "the original query must be forwarded byte-identical"
    numbers_in = re.findall(r"[\d.]{3,}", query)
    numbers_out = re.findall(r"[\d.]{3,}", wrapped)
    assert sorted(set(numbers_out)) == sorted(set(numbers_in)), (
        f"a folded numeric token reached the prompt: {numbers_out} != {numbers_in}"
    )
    # And the detection still had to work on this input, or the test is proving
    # the fold is harmless by proving it never ran.
    assert detect_query_language(query) == "ITALIAN"


# ── Collisions found by an adversarial pass, and the one that was ACCEPTED ──


ADVERSARIAL_ENGLISH: list[str] = [
    # "prego" was originally added as a DECISIVE Italian marker. It is not an
    # English word — it is a supermarket pasta-sauce brand, and this bot
    # advises on food-import KBLI, so these are messages it actually receives.
    # Demoted to a homograph, which is what the row's own rule already
    # required: a token that names a language by coincidence decides nothing
    # alone.
    "Prego sauce import licence",
    "Is Prego pasta sauce importable under KBLI 46331?",
]


@pytest.mark.parametrize("query", ADVERSARIAL_ENGLISH)
def test_a_brand_name_that_looks_italian_does_not_decide(query: str) -> None:
    assert detect_query_language(query) == "ENGLISH"


# Portuguese is NOT a language this detector serves — it has no row, so it can
# only ever land on the ENGLISH default. That default is the LEAST wrong answer
# available, and the first draft of this diff took it away: "qual" was decisive
# for Italian, and "qual" is THE standard Portuguese question word. A Brazilian
# — a real client demographic in Bali — went from being answered in English
# (wrong, but readable) to being answered entirely in Italian (wrong AND
# unreadable). Demoting "qual" to a homograph restores the default at no cost,
# because Italian "Qual è ..." is already carried by "è" (grave accent; the
# Portuguese "é" is acute, a different code point).
PORTUGUESE_MUST_NOT_BECOME_ITALIAN: list[str] = [
    "Qual é o custo do visto de investidor em Bali?",
    "Qual é o prazo para o KITAS?",
    "Qual documento preciso?",
]


@pytest.mark.parametrize("query", PORTUGUESE_MUST_NOT_BECOME_ITALIAN)
def test_an_unserved_language_falls_to_english_not_to_italian(query: str) -> None:
    assert detect_query_language(query) != "ITALIAN"


def test_qual_still_counts_for_a_real_italian_question() -> None:
    """The demotion must not make it inert."""
    assert detect_query_language("Qual è la differenza tra KITAS e KITAP") == "ITALIAN"


def test_prego_still_counts_once_real_italian_is_present() -> None:
    """Demoting it must not make it inert — that would be a silent loss."""
    assert detect_query_language("Prego, mi dica quanto costa il KITAS") == "ITALIAN"


# Inputs this detector KNOWINGLY gets wrong. Asserting the wrong answer is
# deliberate: it is the only way a trade-off stays visible. Whoever later
# removes "salve" will see this test go red and be sent to this docstring
# instead of discovering the reasoning by rediscovering the bug.
DECLARED_ACCEPTED_MISSES: list[str] = [
    # "salve" IS an ordinary English noun (an ointment), so by this module's
    # own anti-homograph rule it should not be decisive. It is anyway, and the
    # justification is the DOMAIN, not the word: this is an immigration,
    # company-setup, tax and property bot. An Italian client opening with
    # "Salve, avrei una domanda" is routine; a client asking about ointment is
    # not a client. The cost is asymmetric — the first mislabels a whole
    # conversation, the second mislabels a message nobody sends.
    "Please apply the salve twice daily",
    # "tra" collides only with the English interjection "tra la la", which is
    # likewise not a message this bot receives, while "differenza tra KITAS e
    # KITAP" is.
    "Tra la la, just testing",
]


@pytest.mark.parametrize("query", DECLARED_ACCEPTED_MISSES)
def test_the_accepted_over_matches_are_declared_not_hidden(query: str) -> None:
    assert detect_query_language(query) == "ITALIAN"


def test_the_marker_corpus_this_file_guards_is_not_empty() -> None:
    """A structural check over an empty corpus is green and means nothing.

    Both tests above iterate a derived list. If ``_LATIN_MARKERS`` were renamed
    or emptied they would pass over zero rows and report success, so the count
    is pinned to a floor well below the real size (currently ~150).
    """
    assert len(_every_marker()) > 100
