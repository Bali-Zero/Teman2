"""
Tests for A2 — length-per-story-type steer in the draft prompt.

A2 hangs off the same injection point as A1: given the (already-propagated)
liveness_tier, inject a slide-count steer + a matching closing range, so the
model stops defaulting to 7 (the Socialinsider engagement trough). A2 is a
PROMPT steer, not a Python clamp — these tests verify the injected text and
that its targets stay inside the existing hard guard (6-11).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import (  # noqa: E402
    _LENGTH_GUIDANCE,
    _build_draft_prompt,
    _length_guidance,
)

# The hard guard in _normalise_slides: len(slides) < 6 or > 11 → reject.
_GUARD_MIN, _GUARD_MAX = 6, 11


def _build(tier: str) -> str:
    return _build_draft_prompt(
        topic="X", summary="body text", source_url="", liveness_tier=tier,
    )


# ── guidance selection ─────────────────────────────────────────────────────
@pytest.mark.parametrize("tier", ["breaking", "developing", "evergreen"])
def test_valid_tier_injects_its_length_line(tier) -> None:
    prompt = _build(tier)
    assert _LENGTH_GUIDANCE[tier] in prompt
    for other in (t for t in _LENGTH_GUIDANCE if t != tier):
        assert _LENGTH_GUIDANCE[other] not in prompt


@pytest.mark.parametrize("tier", ["", "manual", "unknown"])
def test_absent_or_manual_tier_injects_no_length_line(tier) -> None:
    prompt = _build(tier)
    for line in _LENGTH_GUIDANCE.values():
        assert line not in prompt
    assert _length_guidance(tier) == ""


# ── closing range matches the guidance (no "9-10" body + "6-8" footer clash) ─
@pytest.mark.parametrize(
    "tier,expected_range",
    [("breaking", "6-7"), ("developing", "7-8"), ("evergreen", "9-10"), ("", "6-8"),
     ("manual", "6-8")],
)
def test_closing_range_matches_tier(tier, expected_range) -> None:
    prompt = _build(tier)
    assert f"Produce the full {expected_range} slide JSON NOW" in prompt


# ── every target range lives inside the hard guard (never rejected) ─────────
@pytest.mark.parametrize("tier", ["breaking", "developing", "evergreen", "", "manual"])
def test_target_range_is_within_hard_guard(tier) -> None:
    prompt = _build(tier)
    m = re.search(r"Produce the full (\d+)-(\d+) slide JSON NOW", prompt)
    assert m, "closing range not found"
    lo, hi = int(m.group(1)), int(m.group(2))
    assert _GUARD_MIN <= lo <= hi <= _GUARD_MAX, f"{lo}-{hi} escapes guard {_GUARD_MIN}-{_GUARD_MAX}"


def test_breaking_is_shorter_than_evergreen() -> None:
    """The whole point: breaking steers fewer slides than evergreen."""
    def _hi(tier: str) -> int:
        m = re.search(r"Produce the full \d+-(\d+) slide", _build(tier))
        return int(m.group(1))
    assert _hi("breaking") < _hi("evergreen")


# ── back-compat: no tier → legacy 6-8, no steer lines ──────────────────────
def test_default_call_is_legacy_6_8() -> None:
    prompt = _build_draft_prompt(topic="X", summary="b", source_url="")
    assert "Produce the full 6-8 slide JSON NOW" in prompt
    for line in _LENGTH_GUIDANCE.values():
        assert line not in prompt


def test_guidance_avoids_hardcoding_a_single_number() -> None:
    """Steer must be a RANGE nudge, not a rigid 'exactly N' the model can't flex."""
    for line in _LENGTH_GUIDANCE.values():
        assert "exactly" not in line.lower()
        assert re.search(r"\d+-\d+ slides", line), f"no range in: {line!r}"
