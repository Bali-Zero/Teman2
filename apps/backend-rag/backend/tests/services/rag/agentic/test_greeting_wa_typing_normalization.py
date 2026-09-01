"""
WA greeting fast-path — normaliser for realistic WhatsApp typing shapes.

Context (measured 2026-08-25): `check_greetings` fires BEFORE RAG retrieval
via `check_greeting_gate` (query_gates.py:103), but its patterns were
exact-anchored (`^(ciao|hello|hi|hey|salve)\\s*!*$` and friends). Run against
34 realistic WhatsApp openers, that matched only 19/34 — the other 15 fell
through to full RAG retrieval and, lacking a knowledge-base match, got an
ABSTAIN instead of a greeting. All 15 misses were one of three WhatsApp
typing shapes, never a missing greeting word:

  - word-final elongation (12): ciaooo, Ciaoooo!!, buongiornoo, Salveee,
    helloooo, hiii, heyyy, haloo, haiii, selamat pagii, holaa, buonaseraa
  - trailing emoji/emoticon (2): "Ciao :)", "ciao 😊"
  - repetition (1): "ciao ciao"

The fix is `_normalize_for_greeting_match` (module-level helper in
prompt_builder.py), applied ONLY to the string used for pattern matching
inside `check_greetings` — never to `query_lower`, which still drives the
response-language detection further down the same function.

This file has two halves:
  - TestGuilt* — every measured miss now returns a greeting (non-None).
  - TestInnocence* — the 19 that already worked keep working; the
    normaliser is a no-op on non-elongated greeting words; and — the half
    that matters most — real client questions are NOT swallowed by the
    fast-path (it skips RAG entirely, so a false positive here means an
    actual question never reaches retrieval).
"""

from __future__ import annotations

import pytest

from backend.services.rag.agentic.prompt_builder import (
    SystemPromptBuilder,
    _normalize_for_greeting_match,
)

# ============================================================================
# GUILT — the 15 measured misses must now return a greeting.
# ============================================================================


class TestGuiltElongationEmojiRepetition:
    """Each of the 15 strings measured as a miss on the unmodified gate."""

    @pytest.mark.parametrize(
        "query",
        [
            "ciaooo",
            "Ciaoooo!!",
            "buongiornoo",
            "Salveee",
            "helloooo",
            "hiii",
            "heyyy",
            "haloo",
            "haiii",
            "selamat pagii",
            "holaa",
            "buonaseraa",
        ],
        ids=lambda q: f"elongation:{q}",
    )
    def test_elongated_greeting_returns_response(self, query: str) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings(query)
        assert result is not None, f"{query!r} should hit the greeting fast-path"

    @pytest.mark.parametrize(
        "query",
        ["Ciao :)", "ciao 😊"],
        ids=lambda q: f"emoticon-emoji:{q}",
    )
    def test_trailing_emoticon_or_emoji_returns_response(self, query: str) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings(query)
        assert result is not None, f"{query!r} should hit the greeting fast-path"

    def test_repeated_token_returns_response(self) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings("ciao ciao")
        assert result is not None, "'ciao ciao' should hit the greeting fast-path"


# ============================================================================
# INNOCENCE — half 1: the 19 openers that already worked must keep working.
# ============================================================================


class TestInnocenceExistingHitsUnaffected:
    """The 19/34 openers that already matched on the unmodified gate."""

    @pytest.mark.parametrize(
        "query",
        [
            "ciao",
            "Ciao!",
            "hello",
            "Hi",
            "hey",
            "salve",
            "hi there",
            "buongiorno",
            "buonasera",
            "halo",
            "hai",
            "hei",
            "selamat pagi",
            "hallo",
            "guten tag",
            "bonjour",
            "hola",
            "привіт",
            "привет",
        ],
        ids=lambda q: f"already-worked:{q}",
    )
    def test_existing_greeting_still_matches(self, query: str) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings(query)
        assert result is not None, f"{query!r} regressed — it matched before this change"


# ============================================================================
# INNOCENCE — half 2: the normaliser is a no-op on non-elongated greeting
# words (no false collapse of a legitimate mid-word double letter).
# ============================================================================


class TestInnocenceNormalizerNoOpOnMidWordDoubles:
    """Direct unit tests on the helper — must be byte-identical output."""

    @pytest.mark.parametrize(
        "word",
        ["hello", "hallo", "buongiorno", "buonasera", "selamat", "guten tag"],
    )
    def test_normalizer_leaves_word_unchanged(self, word: str) -> None:
        assert _normalize_for_greeting_match(word) == word


# ============================================================================
# INNOCENCE — half 3, THE ONE THAT MATTERS MOST: real client questions must
# NOT be swallowed by the fast-path. A false positive here means the client's
# actual question gets "Ciao! Come posso aiutarti oggi?" and never reaches
# RAG retrieval — worse than the defect being fixed.
# ============================================================================


class TestInnocenceRealQuestionsNotSwallowed:
    @pytest.mark.parametrize(
        "query",
        [
            "Ciao, quanto costa aprire una PT PMA?",
            "ciao ho bisogno di aiuto col KITAS",
            "hello, what does a KITAS cost?",
            "halo, saya mau tanya soal PT PMA",
            "hi there, I need help with taxes",
            "buongiorno, vorrei informazioni sul visto",
            # additional mixed-language real questions
            "hey, can you help me with my NPWP?",
            "hai, saya butuh bantuan visa",
            "привіт, мені потрібна допомога з візою",
            "привет, сколько стоит виза?",
        ],
        ids=lambda q: f"real-question:{q}",
    )
    def test_real_question_is_not_treated_as_greeting(self, query: str) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings(query)
        assert result is None, (
            f"{query!r} was treated as a bare greeting — this would skip RAG "
            "and answer a real question with a canned greeting"
        )


# ============================================================================
# Response language must be preserved for elongated/decorated greetings —
# the fix must not disturb the DOWNSTREAM language-detection logic, which
# still reads the untouched `query_lower`, never the normalised text.
# ============================================================================


class TestLanguagePreservedAfterNormalization:
    def test_italian_elongated_greeting_gets_italian_response(self) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings("ciaooo")
        assert result is not None
        assert "Ciao" in result and "aiutarti" in result

    def test_indonesian_elongated_greeting_gets_indonesian_response(self) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings("haloo")
        assert result is not None
        assert "Halo" in result and "bantu" in result

    def test_english_elongated_greeting_gets_english_response(self) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings("helloooo")
        assert result is not None
        assert "Hello" in result and "help" in result

    def test_repeated_token_greeting_gets_italian_response(self) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings("ciao ciao")
        assert result is not None
        assert "Ciao" in result

    def test_trailing_emoji_greeting_gets_italian_response(self) -> None:
        builder = SystemPromptBuilder()
        result = builder.check_greetings("ciao 😊")
        assert result is not None
        assert "Ciao" in result
