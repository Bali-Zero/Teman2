"""Regression test for superscar #3 in _orphan_is_hard — orphan over-match (4 occurrences).

The Claude vision critic reuses orphan vocabulary ("orphan", "sits alone",
"stranded") metaphorically for SPATIAL isolation of layout elements (logo, rule,
image), not just typographic orphans. A blacklist of phrases is whack-a-mole
(4 consecutive over-matches). The structural cure identifies a typographic orphan
POSITIVELY: a text-unit (word/line/title/headline/…) co-occurring with a
bad-landing predicate, OR an explicit one-word marker. A bare bad-landing word
with no text-unit is composition.

Born from draft 4212d91a (2026-06-25): "logo sits alone", "image stranded",
"decorative orphan… a label" all blocked composition-only slides as HARD orphans,
defeating the W82 boolean cure (has_hard=True short-circuits it).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from wr2_html_renderer import designer_loop as dl  # noqa: E402

_CASES = [
    # (name, text, expected (is_orphan, is_hard))
    ("innocence_oneword_headline", "one-word orphan 'not' on the final headline line — the four-line wrap leaves a lone word.", (True, True)),
    ("innocence_title_single_word", "the title wraps leaving a single word stranded on its own line.", (True, True)),
    ("innocence_sits_alone_headline", "'nobody' sits alone on the middle line of the headline — a one-word island.", (True, True)),
    ("innocence_title_stub", "short tail: the last line of the title is a stub.", (True, True)),
    ("guilt_logo_sits_alone", "logo isolation: the bali zero mark sits alone and undersized. it floats rather than grounds.", (False, False)),
    ("guilt_image_stranded", "the hero image feels stranded — floats alone with no anchor.", (False, False)),
    ("guilt_decorative_orphan_rule", "yellow dash/rule has no kicker or eyebrow text — it functions as a decorative orphan rather than an entry point. a label that never arrives.", (False, False)),
    ("stress_eyebrow_dangling_stub", "the section eyebrow is a dangling stub with nothing after it.", (False, False)),
    ("stress_ragged_oneword_tail", "the headline's last line is a ragged one-word tail.", (True, True)),
    ("boundary_divider_stranded", "the divider bar is stranded with nothing around it.", (False, False)),
    ("boundary_stub_line_headline", "a stub of a final line dangles under the headline.", (True, True)),
]


def test_orphan_entity_intent_grading():
    for name, text, want in _CASES:
        got = dl._orphan_is_hard(text, rebalance_applied=False)
        assert got == want, f"{name}: want {want} got {got}"


def test_logo_composition_slide_not_hard():
    """The 4212d91a slide-4 issue set must no longer set has_hard via a false orphan."""
    slide4 = [
        "Top ~40% of the frame is dead anthracite void — the content block has sunk to the lower half.",
        "Yellow dash/rule functions as a decorative orphan rather than an editorial entry point. The visual grammar implies a label that never arrives.",
        "Excessive dead zone between body text end and logo. The logo floats at the bottom in isolation.",
        "Body text is rendered bold.",
        "vision: unbalanced/crammed",
    ]
    has_hard, _ = dl._classify_residual_issues(slide4, rebalance_applied=False)
    assert has_hard is False


if __name__ == "__main__":
    test_orphan_entity_intent_grading()
    print("PASS test_orphan_entity_intent_grading (11 cases)")
    test_logo_composition_slide_not_hard()
    print("PASS test_logo_composition_slide_not_hard")
    print("ALL PASS")
