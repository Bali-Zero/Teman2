"""
B2 — critic parity: the composition-calibration rubric in _CRITIC_PROMPT.

The vision critic judged balanced/hierarchy_ok "by feel", which fed the huge
prose taxonomy in designer_loop (the W82 whack-a-mole). B2 makes the three
judgments concrete — a quantitative marker rubric (2+/3+, mirroring the
off-tone rubric) — WITHOUT touching designer_loop's classifier.

These tests lock the rubric text + guard the .format() brace hazard (a stray
single brace would make _CRITIC_PROMPT.format(png_path=...) raise at runtime,
silently killing every critic call).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_html_renderer.claude_vision as cv  # noqa: E402


def test_prompt_still_formats_after_rubric_injection() -> None:
    """The load-bearing hazard: a stray single { in the added prose would make
    .format() raise. Prove it still substitutes png_path cleanly."""
    out = cv._CRITIC_PROMPT.format(png_path="/tmp/slide.png")
    assert "/tmp/slide.png" in out
    # {png_path} is the ONLY intended field — no leftover placeholder braces.
    assert "{" not in out and "}" not in out


def test_no_stray_single_braces_in_prompt() -> None:
    """Every { in the template must be {png_path} or an escaped {{ (same for })."""
    p = cv._CRITIC_PROMPT
    suspicious = re.findall(r"(?<!\{)\{(?!\{)(?!png_path\})", p)
    assert suspicious == [], f"stray single-brace(s) would break .format(): {suspicious}"


def test_rubric_is_present_for_all_three_dimensions() -> None:
    p = cv._CRITIC_PROMPT
    assert "CALIBRATION RUBRIC" in p
    assert "hierarchy_ok = false only if 2+" in p
    assert "balanced = false only if 2+" in p
    assert "readable is a HARD signal" in p


def test_readable_stays_a_hard_single_defect_signal() -> None:
    """readable must NOT be softened by the 2+ rule — one real illegibility fails.
    (A composition dimension can tolerate a single nudge; legibility cannot.)"""
    p = cv._CRITIC_PROMPT.lower()
    assert "readable is a hard signal, not a rubric" in p
    assert "one real illegibility is enough" in p
    assert "do not soften readable with the 2+ rule" in p


def test_rubric_prefers_passing_on_uncertainty_not_false_verdicts() -> None:
    """B2 must calibrate, not tighten into spurious rejects (the W73 over-match
    risk). The rubric must instruct 'prefer passing' when unsure."""
    p = cv._CRITIC_PROMPT.lower()
    assert "prefer passing" in p
    assert "publish-quality" in p


def test_rubric_anchors_to_brand_reference_not_generic_marketing() -> None:
    p = cv._CRITIC_PROMPT
    assert "NYT/FT/Bloomberg" in p
    # the framed-margin exception (dead-air #1873) must survive — B2 builds ON it.
    assert "generous margin is NOT dead-air when it is FRAMED" in p


def test_rubric_does_not_touch_the_lever_vocabulary() -> None:
    """B2 is prompt-calibration only. It must NOT introduce a new lever the
    designer_loop can't apply (that would be B1 territory / a schema drift)."""
    p = cv._CRITIC_PROMPT
    # the exact lever set is unchanged — no 'swap'/'reroute'/'layout' lever leaked in
    for forbidden in ("swap_layout", "reroute", "swap_family", "change_family"):
        assert forbidden not in p
