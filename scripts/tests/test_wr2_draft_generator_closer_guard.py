"""
Tests for A4 — closer single-line guard.

Constitution 6.6 / 9.5: the closing slide is a single-line bold statement-bomb.
A long closer body wraps into a text-brick (the recurring slide-8 defect). A4
guards the CLASS with a preventive prompt line + a word-count check that drives
a targeted regen (WARN + regen, not a hard reject). We count WORDS, not chars.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import (  # noqa: E402
    _CLOSER_STEER,
    CLOSER_MAX_WORDS,
    _build_draft_prompt,
    _closer_too_long,
    _closer_word_count,
)


def _slides(closer_body: str) -> list[dict]:
    return [
        {"body": "some cover"},
        {"body": "a middle slide body"},
        {"body": closer_body},
    ]


# ── word count on the LAST slide ───────────────────────────────────────────
def test_word_count_reads_last_slide_body() -> None:
    assert _closer_word_count(_slides("one two three")) == 3
    assert _closer_word_count([]) == 0
    assert _closer_word_count([{"body": ""}]) == 0


def test_short_closer_is_not_flagged() -> None:
    assert not _closer_too_long(_slides("Bali doesn't wait. Neither should you."))  # 6 words


def test_long_closer_is_flagged() -> None:
    long_body = " ".join(f"word{i}" for i in range(CLOSER_MAX_WORDS + 3))
    assert _closer_too_long(_slides(long_body))


def test_exactly_at_threshold_is_allowed() -> None:
    body = " ".join(f"w{i}" for i in range(CLOSER_MAX_WORDS))
    assert _closer_word_count(_slides(body)) == CLOSER_MAX_WORDS
    assert not _closer_too_long(_slides(body))


# ── WORDS, not characters (cicatrix #3: a char cap trips on one long word/URL) ─
def test_counts_words_not_characters() -> None:
    """A single very long word (or URL) is ONE word — must not be flagged, even
    though its character count is huge."""
    one_huge_word = "https://balizero.com/" + "x" * 300
    assert _closer_word_count(_slides(one_huge_word)) == 1
    assert not _closer_too_long(_slides(one_huge_word))


# ── preventive prompt steer is always present ──────────────────────────────
@pytest.mark.parametrize("tier", ["breaking", "developing", "evergreen", "", "manual"])
def test_closer_steer_always_injected_regardless_of_tier(tier) -> None:
    """The closer must be single-line regardless of timeliness, so the steer is
    tier-independent (present even when tier is empty/manual)."""
    prompt = _build_draft_prompt(
        topic="X", summary="body", source_url="", liveness_tier=tier,
    )
    assert _CLOSER_STEER in prompt
    assert str(CLOSER_MAX_WORDS) in _CLOSER_STEER


def test_steer_asks_for_single_line_not_a_paragraph() -> None:
    low = _CLOSER_STEER.lower()
    assert "single-line" in low
    assert "word" in low  # it states a word budget
