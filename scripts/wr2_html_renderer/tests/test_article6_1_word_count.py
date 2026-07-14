"""Article 6.1 (body word count) hard-gate tests (cure item 13, 2026-07-14 —
research/operations/2026-07-14-wr2-deep-audit.md §5: "Art 6.1 body
word-count... [NONE — hard fail on paper, nothing executable]").

Guilt (too short / too long fails) AND innocence (in-range passes, AND
families that legitimately render no {{body}} prose are untouched — cover
per the constitution's explicit exemption, statement-bomb per Article 6.6's
short-closing mandate).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from wr2_html_renderer import composer as C  # noqa: E402

_SKELETON_WITH_BODY = "<html><head></head><body>{{heading}}{{body}}</body></html>"
_SKELETON_WITHOUT_BODY = "<html><head></head><body>{{statement}}</body></html>"


def _words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


# --- GUILT ------------------------------------------------------------------

def test_guilt_body_too_short_hard_fails():
    slide = {"body": _words(10)}
    with pytest.raises(ValueError, match=r"Article 6\.1"):
        C._check_body_word_count(_SKELETON_WITH_BODY, slide, index=2, family="editorial-text")


def test_guilt_body_too_long_hard_fails():
    slide = {"body": _words(75)}
    with pytest.raises(ValueError, match=r"Article 6\.1"):
        C._check_body_word_count(_SKELETON_WITH_BODY, slide, index=2, family="editorial-text")


def test_guilt_empty_body_on_a_body_family_hard_fails():
    slide = {"body": ""}
    with pytest.raises(ValueError):
        C._check_body_word_count(_SKELETON_WITH_BODY, slide, index=2, family="editorial-text")


def test_guilt_error_names_slide_family_and_count():
    slide = {"body": _words(10)}
    with pytest.raises(ValueError) as exc_info:
        C._check_body_word_count(_SKELETON_WITH_BODY, slide, index=4, family="stat-card-hero")
    msg = str(exc_info.value)
    assert "slide 4" in msg
    assert "stat-card-hero" in msg
    assert "10" in msg


# --- INNOCENCE ----------------------------------------------------------------

@pytest.mark.parametrize("n", [25, 37, 50])
def test_innocence_in_range_passes(n):
    slide = {"body": _words(n)}
    result = C._check_body_word_count(_SKELETON_WITH_BODY, slide, index=2, family="editorial-text")
    assert result is None  # did not raise


def test_innocence_body_text_fallback_key_also_checked():
    slide = {"body_text": _words(30)}
    result = C._check_body_word_count(_SKELETON_WITH_BODY, slide, index=2, family="photo-fullbleed")
    assert result is None  # did not raise


def test_innocence_facts_stack_body_exempt_even_when_short():
    """A body the composer parses as LABEL: value fact pairs renders as a
    discrete facts STACK, not prose — Article 6.1's prose word band does not
    apply (exemption predicate = the composer's own facts-branch condition).
    This exact 20-word shape is the real _FACTS_BODY fixture that the
    backend-side consumer test (test_wr2_html_render_apply.py) pushes
    through materialize_slide_html."""
    facts_body = (
        "NEW FEE: IDR 3,500,000. OLD FEE: IDR 2,000,000. REGULATION: PMK 47/2026. "
        "EFFECTIVE: 1 JUNE 2026. [SOURCE: KEMENKEU, 24 APR 2026]"
    )
    assert len(facts_body.split()) < C._ART_6_1_BODY_WORD_MIN  # would fail as prose
    result = C._check_body_word_count(
        _SKELETON_WITH_BODY, {"body": facts_body}, index=2, family="editorial-text"
    )
    assert result is None  # did not raise


def test_guilt_short_prose_body_still_fails_next_to_facts_exemption():
    """Boundary guard for the exemption itself: a 20-word body that does NOT
    parse as fact pairs (plain prose) must still hard-fail — the facts
    exemption must not become an under-match hole for any short body."""
    prose_20 = (
        "The new regulation changes everything about how foreign companies "
        "register their business activities in Indonesia starting from June"
    )
    assert len(prose_20.split()) < C._ART_6_1_BODY_WORD_MIN  # genuinely short prose
    with pytest.raises(ValueError, match=r"Article 6\.1"):
        C._check_body_word_count(
            _SKELETON_WITH_BODY, {"body": prose_20}, index=3, family="editorial-text"
        )


def test_innocence_family_without_body_placeholder_is_untouched():
    """statement-bomb: Article 6.6 wants a SHORT closing line — a 3-word
    statement must not trip the 25-50-word body gate. Its skeleton has no
    {{body}} token, so the gate is a structural no-op for it."""
    slide = {"statement": "ZERO PENALTY", "body": ""}  # body irrelevant/absent
    result = C._check_body_word_count(_SKELETON_WITHOUT_BODY, slide, index=9, family="statement-bomb")
    assert result is None  # did not raise


def test_innocence_cover_family_has_no_body_placeholder():
    """Constitution: 'Cover slide exempt (title only)' — verified structurally:
    the real cover-photo skeleton has no {{body}} token."""
    skeleton = C._extract_skeleton("cover-photo")
    assert "{{body}}" not in skeleton
    slide = {"headline": "SHORT COVER TITLE", "body": ""}
    C._check_body_word_count(skeleton, slide, index=1, family="cover-photo")  # no raise


def test_sweep_real_layout_library_body_placeholder_families_match_expectation():
    """Ground-truth sweep (guard-conformance doctrine): the families this
    module's docstring claims render {{body}} must match what's actually in
    the layout library on disk, so the gate scope never silently drifts."""
    from pathlib import Path

    expected_with_body = {
        "editorial-text",
        "photo-fullbleed-split",
        "photo-fullbleed-top",
        "photo-headline-yellow-sub",
        "photo-fullbleed",
        "source-citation",
        "stat-card-hero",
    }
    layouts_dir = Path(C._LAYOUTS)
    if not layouts_dir.is_dir():
        pytest.skip("brand layouts dir not present on this machine")
    found_with_body = set()
    for md in sorted(layouts_dir.glob("*.md")):
        try:
            skeleton = C._extract_skeleton(md.stem)
        except (FileNotFoundError, ValueError):
            continue
        if "{{body}}" in skeleton:
            found_with_body.add(md.stem)
    assert found_with_body == expected_with_body
