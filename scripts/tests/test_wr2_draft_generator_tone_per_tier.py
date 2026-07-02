"""
Tests for A3 — tone-per-story-type steer in the draft prompt.

A3 nudges the model's register pick by the (already-propagated) liveness_tier,
at the same injection point as A1/A2. It's a PREFERENCE, not a hard constraint:
the downstream validator only rejects tones outside VALID_TONES, so A3 must never
force a tone the validator would later reject, and must leave the model free to
deviate when the content demands it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import (  # noqa: E402
    _TONE_PREFERENCE,
    VALID_TONES,
    _build_draft_prompt,
    _tone_guidance,
)


def _build(tier: str) -> str:
    return _build_draft_prompt(
        topic="X", summary="body text", source_url="", liveness_tier=tier,
    )


# ── the load-bearing invariant: preferred tones ⊆ VALID_TONES ──────────────
def test_every_preferred_tone_is_valid() -> None:
    """A3 can only ever suggest a tone the validator accepts (never a spurious
    reject). If someone adds a preferred tone not in VALID_TONES, fail loudly."""
    preferred = {t for prefs in _TONE_PREFERENCE.values() for t in prefs}
    assert preferred <= VALID_TONES, preferred - VALID_TONES


# ── guidance selection ─────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "tier,expected_tones",
    [
        ("breaking", ("tecnico", "analitico")),
        ("developing", ("analitico", "militante")),
        ("evergreen", ("pedagogico", "rituale")),
    ],
)
def test_valid_tier_injects_its_tone_preference(tier, expected_tones) -> None:
    prompt = _build(tier)
    line = _tone_guidance(tier)
    assert line and line in prompt
    for tone in expected_tones:
        assert tone in line


@pytest.mark.parametrize("tier", ["", "manual", "unknown"])
def test_absent_or_manual_tier_injects_no_tone_line(tier) -> None:
    assert _tone_guidance(tier) == ""
    prompt = _build(tier)
    # no "TONE — for this ... story, PREFER" line leaked in
    assert "PREFER the" not in prompt


# ── preference, NOT a hard constraint (cicatrix #3) ────────────────────────
def test_guidance_is_a_preference_not_a_forced_tone() -> None:
    """The line must leave an escape hatch, not command a single tone."""
    for tier in _TONE_PREFERENCE:
        line = _tone_guidance(tier)
        low = line.lower()
        assert "prefer" in low
        # explicit escape clause so the model can deviate on content grounds
        assert "only if" in low or "unless" in low


def test_breaking_and_evergreen_prefer_different_registers() -> None:
    """The whole point: timeliness shifts the voice."""
    assert set(_TONE_PREFERENCE["breaking"]) != set(_TONE_PREFERENCE["evergreen"])


# ── back-compat ────────────────────────────────────────────────────────────
def test_default_call_injects_no_tone_line() -> None:
    prompt = _build_draft_prompt(topic="X", summary="b", source_url="")
    assert "PREFER the" not in prompt


def test_forbidden_legacy_tones_never_preferred() -> None:
    """cinico / istituzionale_severo are FORBIDDEN (WR1 legacy) — A3 must not
    resurrect them via a preference."""
    preferred = {t for prefs in _TONE_PREFERENCE.values() for t in prefs}
    assert "cinico" not in preferred
    assert "istituzionale_severo" not in preferred
