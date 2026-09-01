from __future__ import annotations

import ast
import inspect

import pytest

from backend.services.rag.agentic.query_helpers import (
    LANGUAGE_DISPLAY_NAMES,
    LATIN_HOMOGRAPHS,
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
        detect_query_language("\u041f\u0440\u0438\u0432\u0456\u0442, \u044f\u043a?") == "UKRAINIAN"
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


# ---------------------------------------------------------------------------
# Language-selection drift (2026-08-10). Two independent defects, one symptom:
# an English speaker never received a binding language instruction, because
# either (a) a bare-substring marker scan classified the question as Indonesian
# — 11 of 20 plain-English domain questions did — or (b) it was correctly
# classified ENGLISH and ENGLISH was missing from the display map, so the
# instruction read "MUST BE IN the user's language", naming nothing.
# ---------------------------------------------------------------------------

# GUILT: every one of these embeds an Indonesian marker inside a longer English
# stem. Measured against the pre-cure scan, all 11 returned "INDONESIAN".
_ENGLISH_WITH_EMBEDDED_MARKERS = [
    ("What is the standard corporate income tax rate?", "anda in st(anda)rd"),
    ("Please include the value of the solution plus notary costs.", "lu in va(lu)e"),
    ("Is a company in Japan eligible for a PT PMA?", "apa in J(apa)n"),
    ("What are the mandatory annual reports?", "anda in m(anda)tory"),
    ("Can I rent an apartment on a B211A visa?", "apa in (apa)rtment"),
    ("What is the evaluation process for LKPM?", "lu in eva(lu)ation"),
    ("Which column of the chart of accounts covers payroll?", "lu in co(lu)mn"),
    ("Do you have a luxury property in Canggu?", "lu in (lu)xury"),
    ("I would like a guess at the total budget.", "gue in (gue)ss"),
    ("The lease agreement includes a plus-value clause.", "lu in p(lu)s"),
    ("What are the capacity requirements for a restaurant licence?", "apa in c(apa)city"),
    # Same defect, other branches: every Latin-script marker list was a bare
    # substring scan too. These two are the ones this domain says constantly.
    ("What is the corporate income tax rate?", "come in in(come) -> ITALIAN"),
    ("What is the commercial licence for a PT PMA?", "merci in com(merci)al -> FRENCH"),
    # And two homographs that ARE English words, so whole-word matching alone
    # would not have saved them.
    ("How did this come about?", "'come' is an English word"),
    ("Can you comment on the LKPM deadline?", "'comment' is an English word"),
    # \b makes a bare "non" marker match these; that is why it is not in the list.
    ("Is a non-resident director allowed?", "non-resident must not read as Italian"),
]


@pytest.mark.parametrize(("query", "why"), _ENGLISH_WITH_EMBEDDED_MARKERS)
def test_english_question_embedding_a_marker_is_not_indonesian(query: str, why: str) -> None:
    assert detect_query_language(query) == "ENGLISH", why


def test_ambiguous_indonesian_marker_does_not_override_english_context() -> None:
    """A client name that happens to be an Indonesian word is not a verdict."""
    assert detect_query_language("Is Ada eligible for a KITAS?") == "ENGLISH"


# INNOCENCE: the obvious cure — a plain \b…\b match — is an UNDER-match twin.
# Measured on the real 188-message inbound corpus, it lost 12 genuine Indonesian
# messages, 11 of them on "berapa" (the pricing question). These must stay.
_REAL_INDONESIAN = [
    "Berapa lama Hak Pakai bisa diperpanjang?",
    "Berapa harga KITAS investor?",
    "Apakah PT PMA wajib lapor LKPM?",
    "Harganya berapa untuk paket tahunan?",
    "Kenapa permohonan saya ditolak?",
    "Zantara jelaskan visa C7A",
    "Bisakah warga asing jadi direktur?",
    "Saya mau urus izin usaha",
    "Terima kasih, saya mau KITAS",
]


@pytest.mark.parametrize("query", _REAL_INDONESIAN)
def test_real_indonesian_still_detected(query: str) -> None:
    assert detect_query_language(query) == "INDONESIAN"


# INNOCENCE for the Latin branches: demoting "come"/"comment" to homographs is
# itself an under-match risk — these are the sentences that used to depend on
# them, and the widened decisive lists must still carry them.
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Come funziona il KITAS investor?", "ITALIAN"),
        ("Come ottenere un KITAS?", "ITALIAN"),
        ("Ciao, quanto costa un E33G?", "ITALIAN"),
        ("Vorrei aprire una PT PMA, cosa serve?", "ITALIAN"),
        ("Comment ça marche, le KITAS?", "FRENCH"),
        ("Comment obtenir un KITAS ?", "FRENCH"),
        ("Il faut combien de temps pour obtenir un KITAS ?", "FRENCH"),
        ("Bonjour, combien coûte le KITAS?", "FRENCH"),
        ("Hola, gracias por la info", "SPANISH"),
        # Cross-language collision: "una" is Italian AND Spanish, and Italian is
        # tested first. Widening the Italian list with it answered this in
        # Italian. A marker shared by two candidate languages decides neither.
        ("hola cómo puedo obtener una visa?", "SPANISH"),
        ("Hallo, wie geht es?", "GERMAN"),
    ],
)
def test_real_latin_language_still_detected(query: str, expected: str) -> None:
    assert detect_query_language(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Comment obtenir un KITAS, ciao", "FRENCH"),
        ("Come ottenere un KITAS, bonjour", "ITALIAN"),
    ],
)
def test_supported_homograph_pair_outranks_one_conflicting_marker(
    query: str, expected: str
) -> None:
    assert detect_query_language(query) == expected


def test_english_homographs_never_decide_a_language_on_their_own() -> None:
    """`come` and `comment` are Italian/French markers AND English words.

    One of them alone is a coincidence, not a language — so they may reinforce
    a verdict but never produce one. Guarding the property, not the instances.
    """
    # Assert the declaration itself, or the loop below passes vacuously the
    # moment someone empties the table — which is exactly the change it exists
    # to catch. Exact equality is deliberate: it makes every ADDITION a
    # conscious act reviewed right here, next to the property it must satisfy.
    #
    # Grew on 2026-08-25, all three for the same reason — a token that names a
    # language only by coincidence:
    #   "dove"  — English, the bird.
    #   "prego" — not an English word, but a supermarket pasta-sauce brand,
    #             and this bot advises on food-import KBLI, so "Prego sauce
    #             import licence" is a message it actually receives.
    #   "qual"  — THE standard question word in PORTUGUESE. Decisive, it took
    #             "Qual é o custo do visto?" from ENGLISH (wrong, but readable)
    #             to ITALIAN (wrong AND unreadable). Italian keeps it via "è".
    assert LATIN_HOMOGRAPHS == {
        "ITALIAN": ["come", "dove", "prego", "qual"],
        "FRENCH": ["comment"],
    }

    for language, homographs in LATIN_HOMOGRAPHS.items():
        for word in homographs:
            assert detect_query_language(f"Please {word} on the tax filing") != language


def test_english_query_names_english_not_a_tautology() -> None:
    """The pre-cure instruction read 'MUST BE IN the user's language' — a
    self-reference that constrains nothing, on the detector's DEFAULT branch."""
    wrapped = wrap_query_with_language_instruction("How long does a PT PMA take to set up?")

    assert "LANGUAGE: ENGLISH" in wrapped
    assert "the user's language" not in wrapped


def test_every_language_the_detector_returns_is_named_in_the_instruction() -> None:
    """Structural guard against the class, not just today's instance.

    The display map lived as a literal INSIDE the wrapper, so a language could
    be added to the detector and not to the map, and the only symptom would be
    a vague prompt in production — exactly how ENGLISH, the detector's default
    return, ended up unnamed. Enumerate what the detector can actually RETURN,
    from its own source, and require the map to cover it.
    """
    tree = ast.parse(inspect.getsource(detect_query_language))
    returned = {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    assert "ENGLISH" in returned, "detector no longer returns ENGLISH — retarget this test"

    # INDONESIAN returns before the map is consulted; UNKNOWN is unreachable
    # from the wrapper (same len(strip()) < 2 bail that produces it).
    missing = returned - {"INDONESIAN", "UNKNOWN"} - set(LANGUAGE_DISPLAY_NAMES)
    assert not missing, f"detector can return {sorted(missing)} but the instruction names neither"


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
