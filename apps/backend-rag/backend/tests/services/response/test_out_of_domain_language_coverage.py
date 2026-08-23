"""The out-of-domain refusals must cover every language the detector can emit.

WHY A SECOND COVERAGE FILE
--------------------------
``_reasoning_stubs.STUB_MESSAGES`` is the refusal-copy SSOT and
``test_reasoning_stubs_language_coverage.py`` guards it. ``cleaner`` cannot
import that module — ``query_gates`` imports ``cleaner``, so reaching
``backend.services.rag.agentic._reasoning_stubs`` would execute that package's
``__init__``, pull the orchestrator, and land back in a half-initialised
``cleaner``. The COPY therefore lives in two places.

The LANGUAGE SET does not. This file imports ``PROTOCOL_LANGUAGES`` from the
SSOT and derives the detector's output vocabulary from its AST, exactly as the
stub test does — so adding a language to ``detect_query_language`` turns BOTH
tables red, never one. A hand-written list here would be the second copy of the
truth that the stub test explicitly refuses to keep.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.services.rag.agentic import query_helpers
from backend.services.rag.agentic._reasoning_stubs import PROTOCOL_LANGUAGES
from backend.services.response.cleaner import (
    _OUT_OF_DOMAIN_BY_LANGUAGE,
    get_out_of_domain_response,
)

#: Languages the detector emits that these refusals knowingly serve in English.
#: Kept identical in spirit to the stub table's declaration: a new detector
#: language must be translated or declared here on purpose.
#:
#: GERMAN and SPANISH moved OUT of this set on 2026-08-23, in lockstep with
#: _reasoning_stubs.PROTOCOL_LANGUAGES — see that module's docstring.
DECLARED_ENGLISH_FALLBACK: frozenset[str] = frozenset({"CHINESE", "ARABIC", "FRENCH"})


def _languages_the_detector_can_emit() -> set[str]:
    """Every string literal ``detect_query_language`` can return, from its AST."""
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
    @pytest.mark.parametrize("reason", sorted(_OUT_OF_DOMAIN_BY_LANGUAGE))
    @pytest.mark.parametrize("language", PROTOCOL_LANGUAGES)
    def test_reason_has_an_entry_for_every_protocol_language(
        self, reason: str, language: str
    ) -> None:
        assert language in _OUT_OF_DOMAIN_BY_LANGUAGE[reason], (
            f"out-of-domain refusal {reason!r} has no {language} entry — clients "
            f"writing {language} receive English and nothing fails"
        )

    @pytest.mark.parametrize("reason", sorted(_OUT_OF_DOMAIN_BY_LANGUAGE))
    @pytest.mark.parametrize("language", [lang for lang in PROTOCOL_LANGUAGES if lang != "ENGLISH"])
    def test_translation_is_not_the_english_text(self, reason: str, language: str) -> None:
        assert get_out_of_domain_response(reason, language) != get_out_of_domain_response(
            reason, "ENGLISH"
        ), f"refusal {reason!r} for {language} is byte-identical to the English text"

    @pytest.mark.parametrize("reason", sorted(_OUT_OF_DOMAIN_BY_LANGUAGE))
    @pytest.mark.parametrize("language", PROTOCOL_LANGUAGES)
    def test_no_refusal_is_blank_or_carries_an_unfilled_placeholder(
        self, reason: str, language: str
    ) -> None:
        text = get_out_of_domain_response(reason, language)
        assert text.strip()
        assert "{" not in text, f"{reason}/{language} still carries a format placeholder"


class TestGuiltTheDetectorCannotOutgrowTheTable:
    def test_every_emitted_language_is_translated_or_declared(self) -> None:
        emitted = _languages_the_detector_can_emit() - {"UNKNOWN"}
        orphans = emitted - (set(PROTOCOL_LANGUAGES) | DECLARED_ENGLISH_FALLBACK)
        assert not orphans, (
            f"detect_query_language can return {sorted(orphans)}, which the "
            f"out-of-domain table does not translate and does not declare."
        )

    def test_the_declared_fallback_set_is_not_stale(self) -> None:
        stale = DECLARED_ENGLISH_FALLBACK - _languages_the_detector_can_emit()
        assert not stale, f"DECLARED_ENGLISH_FALLBACK lists {sorted(stale)}, never emitted"


class TestInnocenceTheResolverContract:
    def test_unknown_language_gets_english(self) -> None:
        assert get_out_of_domain_response("off_topic", "KLINGON") == get_out_of_domain_response(
            "off_topic", "ENGLISH"
        )

    def test_default_language_is_italian_for_callers_that_pass_none(self) -> None:
        """Back-compat with the pre-2026-08-10 signature, which had no language."""
        assert get_out_of_domain_response("unknown") == get_out_of_domain_response(
            "unknown", "ITALIAN"
        )
