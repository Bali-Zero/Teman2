"""Guilt + innocence coverage for `is_text_legibility_claim` (ocr_check.py).

WR2 deep audit 2026-07-14, §5a / D3 wiring follow-up: the classifier decides
whether a claude_brand_verifier rejection is eligible for OCR-adjudicated
override (designer_loop.py:899-913). Before this PR the classifier had ZERO
test coverage — this file is that gap closed, per the audit's explicit flag
("worth doing before merge, not just after").

Finding while closing the gap: the bare keywords "headline"/"title"/"titolo"
in TEXT_CLAIM_KEYWORDS over-match (scar family #3) — a font or color
violation phrased about the headline ("the headline uses a serif font, not
Montserrat") contains "headline" and would have been misclassified as an
OCR-overridable text-legibility claim, even though OCR only adjudicates text
CONTENT, not font family or color. Fixed with
_NON_TEXT_LEGIBILITY_CATEGORY_WORDS: an issue naming a font/color/logo/emoji
category is never (also) a pure text-legibility claim, regardless of whether
it happens to mention "headline"/"title" as the noun the problem is about.
"""
from __future__ import annotations

from wr2_html_renderer.ocr_check import is_text_legibility_claim

# ── GUILT: real text-legibility claims (verifier prompt's actual phrasing for
#    "The headline text is intact and not garbled/cut off.") must still fire —
#    these are exactly the claims OCR CAN adjudicate. ─────────────────────────


def test_headline_garbled_is_a_text_legibility_claim():
    assert is_text_legibility_claim("The headline text is garbled") is True


def test_headline_cut_off_is_a_text_legibility_claim():
    assert is_text_legibility_claim("Title appears cut off at the edge") is True


def test_bare_illegible_is_a_text_legibility_claim():
    """A corruption keyword alone (no headline/title noun) still fires — the
    verifier sometimes phrases it without naming the element."""
    assert is_text_legibility_claim("text is illegible in the lower third") is True


def test_italian_phrasing_is_a_text_legibility_claim():
    """The verifier sometimes replies in Italian (module docstring note)."""
    assert is_text_legibility_claim("il titolo appare troncato") is True


# ── INNOCENCE: font/color/logo/emoji violations that happen to name
#    "headline"/"title" as their subject must NOT fire — OCR cannot
#    adjudicate font family or color, only text content. This is the
#    over-match this PR fixes; these three are the direct repro cases. ───────


def test_headline_wrong_font_is_not_a_text_legibility_claim():
    assert is_text_legibility_claim("The headline uses a serif font, not Montserrat") is False


def test_headline_off_palette_color_is_not_a_text_legibility_claim():
    assert is_text_legibility_claim("The headline text has an off-palette purple tint") is False


def test_title_missing_logo_is_not_a_text_legibility_claim():
    """A logo-missing violation should never trip the classifier even if the
    issue string happens to be near a title/headline mention in the same
    sentence."""
    assert is_text_legibility_claim("Below the title, the Bali Zero logo is missing") is False


def test_emoji_in_title_is_not_a_text_legibility_claim():
    assert is_text_legibility_claim("There is an emoji in the title") is False


# ── INNOCENCE (baseline): a violation about something else entirely, with no
#    headline/title/corruption vocabulary at all, correctly never fires. ─────


def test_unrelated_color_violation_is_not_a_text_legibility_claim():
    assert is_text_legibility_claim("Background uses an off-palette blue") is False
