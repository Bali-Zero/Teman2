"""Regression test for superscar #3 in _orphan_is_hard (orphan entity over-match).

A typographic-orphan marker ("sits alone", "stranded", "widow") must grade as a
HARD orphan ONLY when the subject is text (word/line/title/headline/wrap), NOT
when it describes a non-text composition element (logo/mark/image floating alone).
Born from draft 4212d91a slide-2 render_failed (2026-06-25): "the logo sits alone"
was mis-graded a HARD orphan, blocking a pure-composition slide the W82 boolean
cure should have accepted.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from wr2_html_renderer import designer_loop as dl  # noqa: E402


def test_logo_sits_alone_is_not_a_typographic_orphan():
    logo = ("logo isolation: the bali zero mark sits alone and undersized at ~91% "
            "height with no anchor relationship to the text block. it floats rather than grounds.")
    assert dl._orphan_is_hard(logo, rebalance_applied=False) == (False, False)


def test_image_stranded_is_composition_not_orphan():
    img = "the hero image feels stranded — floats alone with no anchor."
    assert dl._orphan_is_hard(img.lower(), rebalance_applied=False) == (False, False)


def test_real_headline_orphans_stay_hard():
    cases = [
        "one-word orphan 'not' on the final headline line — the four-line wrap leaves a lone word.",
        "the title wraps leaving a single word stranded on its own line.",
        "'nobody' sits alone on the middle line of the headline — a one-word island.",
        "short tail: the last line of the title is a stub.",
    ]
    for c in cases:
        assert dl._orphan_is_hard(c, rebalance_applied=False) == (True, True), c


def test_full_classify_accepts_logo_composition_slide():
    issues = [
        "Bottom-third dead zone: ~35% of the canvas below the body copy is pure void before the logo.",
        "Logo isolation: the Bali Zero mark sits alone and undersized with no anchor to the text block. It floats rather than grounds.",
        "Top-plus-bottom void pinch: both the top third and the bottom third are empty.",
        "vision: unbalanced/crammed",
    ]
    has_hard, _ = dl._classify_residual_issues(issues, rebalance_applied=False)
    assert has_hard is False  # no false typographic-orphan HARD anymore


if __name__ == "__main__":
    for fn in [test_logo_sits_alone_is_not_a_typographic_orphan,
               test_image_stranded_is_composition_not_orphan,
               test_real_headline_orphans_stay_hard,
               test_full_classify_accepts_logo_composition_slide]:
        fn(); print("PASS", fn.__name__)
    print("ALL PASS")
