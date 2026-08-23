"""The stub table must cover every language the detector can emit — or say it doesn't.

WHY THIS FILE EXISTS
--------------------
``detect_query_language`` emits ten language identifiers. ``STUB_MESSAGES``
carried three (ITALIAN / ENGLISH / INDONESIAN). The gap was invisible because
``get_localized_stub`` degrades to ENGLISH *silently* and every existing test
asked only "did a non-empty string come back?" — which the fallback satisfies.
Net effect until 2026-07-27: a client writing in Russian got a refusal in
English, and nothing anywhere failed.

So the tests here do not check that a string exists. They check the two claims
that actually matter:

  GUILT     — every protocol language resolves to its OWN text, not to the
              English one wearing its name.
  INNOCENCE — the documented fallback still works for languages we have
              deliberately not translated, and for unknown keys.

The coverage test derives the detector's output vocabulary from the AST of
``query_helpers.py`` rather than from a hand-written list. A hand-written list
would be a second copy of the truth, and would keep passing on the day someone
adds a language to the detector — which is the exact failure this file exists
to catch.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.services.rag.agentic import query_helpers
from backend.services.rag.agentic._reasoning_stubs import (
    _FALLBACK_MESSAGE,
    PROTOCOL_LANGUAGES,
    STUB_MESSAGES,
    get_localized_stub,
)

#: Languages ``detect_query_language`` can return that we knowingly serve in
#: English. Adding a language to the detector without translating it forces a
#: deliberate entry here — that is the point. "UNKNOWN" is not a language.
#:
#: GERMAN and SPANISH moved OUT of this set on 2026-08-23 (translated into
#: PROTOCOL_LANGUAGES instead) — see _reasoning_stubs.py's module docstring.
DECLARED_ENGLISH_FALLBACK: frozenset[str] = frozenset({"CHINESE", "ARABIC", "FRENCH"})


def _languages_the_detector_can_emit() -> set[str]:
    """Every string literal ``detect_query_language`` can return, from its AST.

    Derived, never hand-listed: a hand-written copy would silently stay green
    when the detector grows a new language.
    """
    source = Path(query_helpers.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "detect_query_language":
            emitted = {
                stmt.value.value
                for stmt in ast.walk(node)
                if isinstance(stmt, ast.Return)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            }
            assert emitted, "parsed detect_query_language but found no returned literals"
            return emitted
    raise AssertionError("detect_query_language not found in query_helpers.py")


class TestGuiltEveryProtocolLanguageIsReallyTranslated:
    """A protocol language must resolve to its own text, never to English."""

    @pytest.mark.parametrize("key", sorted(STUB_MESSAGES))
    @pytest.mark.parametrize("language", PROTOCOL_LANGUAGES)
    def test_key_has_an_entry_for_every_protocol_language(self, key: str, language: str) -> None:
        assert language in STUB_MESSAGES[key], (
            f"stub {key!r} has no {language} entry — clients writing {language} "
            f"receive English and nothing fails"
        )

    @pytest.mark.parametrize("key", sorted(STUB_MESSAGES))
    @pytest.mark.parametrize(
        "language", [lang for lang in PROTOCOL_LANGUAGES if lang != "ENGLISH"]
    )
    def test_translation_is_not_the_english_text(self, key: str, language: str) -> None:
        """Catches the fallback masquerading as a translation, and copy-paste."""
        assert get_localized_stub(key, language) != get_localized_stub(key, "ENGLISH"), (
            f"stub {key!r} for {language} is byte-identical to the English text"
        )

    @pytest.mark.parametrize("key", sorted(STUB_MESSAGES))
    @pytest.mark.parametrize("language", PROTOCOL_LANGUAGES)
    def test_no_stub_is_blank(self, key: str, language: str) -> None:
        assert get_localized_stub(key, language).strip()


class TestGuiltTheDetectorCannotOUTGROWTheTable:
    """A language the detector emits is translated, or declared as a fallback."""

    def test_every_emitted_language_is_translated_or_declared(self) -> None:
        emitted = _languages_the_detector_can_emit() - {"UNKNOWN"}
        accounted = set(PROTOCOL_LANGUAGES) | DECLARED_ENGLISH_FALLBACK
        orphans = emitted - accounted
        assert not orphans, (
            f"detect_query_language can return {sorted(orphans)}, which STUB_MESSAGES "
            f"does not translate and DECLARED_ENGLISH_FALLBACK does not declare. "
            f"Either translate it or add it to the declared set on purpose."
        )

    def test_the_declared_fallback_set_is_not_stale(self) -> None:
        """A declared fallback that the detector can no longer emit is dead weight."""
        emitted = _languages_the_detector_can_emit()
        stale = DECLARED_ENGLISH_FALLBACK - emitted
        assert not stale, f"DECLARED_ENGLISH_FALLBACK lists {sorted(stale)}, never emitted"


class TestInnocenceTheDocumentedFallbacksStillWork:
    """Changing coverage must not change the resolver's contract."""

    def test_undeclared_language_still_gets_english(self) -> None:
        assert get_localized_stub("abstain", "KLINGON") == STUB_MESSAGES["abstain"]["ENGLISH"]

    @pytest.mark.parametrize("language", sorted(DECLARED_ENGLISH_FALLBACK))
    def test_declared_fallback_languages_get_english_not_a_crash(self, language: str) -> None:
        assert get_localized_stub("abstain", language) == STUB_MESSAGES["abstain"]["ENGLISH"]

    def test_unknown_key_returns_the_generic_message(self) -> None:
        assert get_localized_stub("nonexistent_key", "ENGLISH") == _FALLBACK_MESSAGE

    def test_unknown_key_and_unknown_language_returns_the_generic_message(self) -> None:
        assert get_localized_stub("nonexistent_key", "KLINGON") == _FALLBACK_MESSAGE


class TestTheTwoAbstainVariantsStayDistinct:
    """``abstain`` and ``abstain_detailed`` are used at different call sites."""

    @pytest.mark.parametrize("language", PROTOCOL_LANGUAGES)
    def test_short_and_detailed_differ(self, language: str) -> None:
        assert get_localized_stub("abstain", language) != get_localized_stub(
            "abstain_detailed", language
        )

    @pytest.mark.parametrize("language", PROTOCOL_LANGUAGES)
    def test_detailed_variant_actually_lists_what_the_bot_can_do(self, language: str) -> None:
        """The detailed variant's whole reason to exist is the bullet menu."""
        assert get_localized_stub("abstain_detailed", language).count("•") >= 3
