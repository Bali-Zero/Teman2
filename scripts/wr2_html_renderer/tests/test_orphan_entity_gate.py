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


def test_dead_air_float_slide_is_debt_not_hard():
    """BUGFIX 2026-06-30 (W82 under-match, 2nd occurrence): the critic names the
    SAME vertical-balance debt as 'dead air', a body that 'floats'/'sits
    unanchored'/'sunken into the lower half', a layout that 'looks unfinished'.
    These were NOT in the composition vocabulary → flipped all_composition False
    → HARD reject → render_failed. They are placement/balance notes, not
    legibility/clip/brand → must be acceptable composition debt.

    Verbatim from draft 62b6b577 slide 3 (the reject that exposed this):
    """
    slide3 = [
        "Dead air below body copy: the body text sits at ~73% of the slide with a "
        "large void before the logo at ~90%. The composition feels unanchored — "
        "body floats mid-dark-section with no visual weight to close the layout.",
        "Body type is small and all-caps. At full open size it reads, but the "
        "combination of small size + all-caps for a 2-line paragraph strains comfort.",
        "Logo is isolated at the bottom of the frame.",
        "vision: unbalanced/crammed",
    ]
    has_hard, all_comp = dl._classify_residual_issues(slide3, rebalance_applied=False)
    assert has_hard is False, "dead-air/float/unanchored are composition, not HARD"
    assert all_comp is True, "the whole slide-3 residual is editorial debt → acceptable"

    # the slide-1 residual (also accepted live as debt) must stay acceptable too
    slide1 = [
        "Top ~35% of the canvas is a featureless dark void — the content block is "
        "sunken into the lower half of the frame. As-is the slide looks unfinished.",
        "Large dead zone also below the body text before the logo — the logo floats "
        "in isolation at the very bottom of a ~20% gap.",
        "Body copy is full-bold throughout — no weight contrast.",
        "vision: unbalanced/crammed",
    ]
    has_hard, all_comp = dl._classify_residual_issues(slide1, rebalance_applied=False)
    assert has_hard is False and all_comp is True


def test_dead_air_does_not_swallow_real_hard_defect():
    """Innocence guard: adding dead-air/float vocabulary must NOT let a genuine
    HARD defect (illegible / clipped) slip through when it co-occurs."""
    mixed = [
        "Dead air below the body, logo floats unanchored at the bottom.",  # composition
        "The headline is clipped — the last word is cut off the right edge.",  # HARD
    ]
    has_hard, all_comp = dl._classify_residual_issues(mixed, rebalance_applied=False)
    assert has_hard is True, "a real clip defect must still win over composition debt"
    assert all_comp is False


def test_soft_comfort_size_wording_is_NOT_auto_accepted_by_text():
    """Codex refuter guard (2026-06-30): soft comfort/size judgements
    ('strains comfort', 'could be larger', 'a few more points', 'footnote')
    must NOT be auto-classified as composition debt by WORDING — they can mask a
    real readability failure on mobile. The readability axis is owned by the
    DETERMINISTIC cheap tiers (legibility contrast + OCR read-back) that gate
    BEFORE this classifier; text wording must not pre-empt them. So a bare
    comfort/size complaint with no explicit readability affirmation and no
    layout/hierarchy term stays unclassified → blocks (all_composition=False)."""
    # Bare comfort/size complaints with no conditional/affirmation/layout term
    # must NOT be auto-classified as debt by wording — they fall to the
    # deterministic cheap tiers (legibility + OCR), i.e. block here.
    for soft in [
        "The body text strains comfort at phone size.",
        "The body feels like a footnote.",
    ]:
        has_hard, all_comp = dl._classify_residual_issues([soft], rebalance_applied=False)
        assert all_comp is False, f"soft size/comfort wording must not auto-accept: {soft!r}"
        assert has_hard is False, "but it is not HARD either (not 'illegible')"
    # NOTE: a phrasing like "could be larger" DOES match the pre-existing
    # _CONDITIONAL_MARKERS ('could'/'would') and classifies as a suggestion —
    # that predates this change and is acceptable because a body that is *really*
    # too small is caught upstream by OCR/legibility regardless of wording. The
    # point of THIS guard is only that we did not ADD bare comfort/size terms.

    # but an EXPLICIT readability affirmation IS a legitimate concession → debt
    affirmed = "At full open size it reads; the only note is the large top dead zone."
    has_hard, all_comp = dl._classify_residual_issues([affirmed], rebalance_applied=False)
    assert has_hard is False and all_comp is True


def test_empty_residual_is_acceptable():
    """BUGFIX 2026-06-29: a clean slide (critic returns ZERO atomic defects)
    must classify as all_composition=True so the accept-gate converges it,
    NOT render_failed.

    Repro: drafts 8e582ce0 / d2d308bf / 9b923976 all died on slide 8 with
    `critiques=[]` — the empty residual was seeded all_composition=False by the
    old `bool(issues)` and sank the whole carousel (~5 days, zero WR2 output).
    An empty list, or a list of ONLY synthetic 'vision: …' summary markers, has
    no atomic blocker → must be acceptable.
    """
    # truly empty residual — the most acceptable case of all
    has_hard, all_comp = dl._classify_residual_issues([], rebalance_applied=False)
    assert has_hard is False
    assert all_comp is True, "empty residual must be all_composition (clean slide)"

    # only a synthetic summary marker, no atomic defect → still acceptable
    has_hard, all_comp = dl._classify_residual_issues(
        ["vision: balanced/clean"], rebalance_applied=False
    )
    assert has_hard is False
    assert all_comp is True, "summary-marker-only residual must be all_composition"

    # sanity: a genuine unclassifiable atomic claim still blocks (no regression)
    has_hard, all_comp = dl._classify_residual_issues(
        ["the headline color clashes with the brand palette in a way that"],
        rebalance_applied=False,
    )
    assert all_comp is False, "an unclassifiable atomic claim must still block"


if __name__ == "__main__":
    test_orphan_entity_intent_grading()
    print("PASS test_orphan_entity_intent_grading (11 cases)")
    test_logo_composition_slide_not_hard()
    print("PASS test_logo_composition_slide_not_hard")
    test_empty_residual_is_acceptable()
    print("PASS test_empty_residual_is_acceptable")
    print("ALL PASS")
