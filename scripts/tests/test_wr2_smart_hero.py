"""
Locks down the 2026-06-13 Antonello decision: WR2 hero selection is FLEXIBLE
and SMART. The model decides how many slides (6-11) and which of them deserve
a full-bleed photo (is_hero_image: true), based on the story.

This SUPERSEDES the 2026-06-12 "every slide is hero" rule (PR #1374): we no
longer force is_hero_image=True on every slide. Only the cover is guaranteed
hero (as a minimum); the model's flag is preserved verbatim for the rest, and
non-hero slides route to a TEXT-ONLY layout family (editorial-text /
statement-bomb), never to the photo layout with an empty hero (the "void trap").

Contract points:
  1. _normalise_slides: 6-11 slides accepted; cover always hero; the model's
     is_hero_image flag preserved for the others; no auto-promotion.
  2. map_slide_to_family: non-hero slides route to a text-only family, NEVER to
     photo-headline-yellow-sub.
  3. editorial-text: a real text-only prose family exists and carries {{body}}
     with no .hero background photo.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import _normalise_slides  # noqa: E402
from wr2_html_renderer.composer import (  # noqa: E402
    _extract_skeleton,
    map_slide_to_family,
)


def _raw_slide(n: int, *, hero: bool = False, slide_type: str = "body", **extra) -> dict:
    s = {
        "slide_number": n,
        "slide_type": "cover" if n == 1 else slide_type,
        "is_cover": n == 1,
        "is_hero_image": hero,
        "headline": f"Headline {n}",
        "subhead": f"Sub {n}",
        "body": f"Body {n}",
        "image_prompt": f"editorial scene {n}",
    }
    s.update(extra)
    return s


def _parsed(num_slides: int, heroes: set[int] | None = None) -> dict:
    heroes = heroes or set()
    return {
        "register": "analitico",
        "slides": [_raw_slide(i, hero=i in heroes) for i in range(1, num_slides + 1)],
    }


# ── 1. _normalise_slides: smart hero, model-chosen, cover always hero ─────────


def test_normalise_preserves_model_hero_choice_not_forced() -> None:
    _, slides = _normalise_slides(_parsed(10, heroes={1, 3, 6, 10}))
    assert len(slides) == 10
    # cover (slide 1) is ALWAYS hero
    assert slides[0]["is_hero_image"] is True
    # model-marked heroes stay hero
    assert slides[2]["is_hero_image"] is True   # slide 3
    assert slides[5]["is_hero_image"] is True   # slide 6
    assert slides[9]["is_hero_image"] is True   # slide 10
    # the rest are NOT auto-promoted to hero
    for idx in (1, 3, 4, 6, 7, 8):  # slides 2,4,5,7,8,9 (0-based)
        assert slides[idx]["is_hero_image"] is False, f"slide {idx + 1} wrongly hero"


def test_normalise_zero_model_heroes_only_cover_promoted() -> None:
    _, slides = _normalise_slides(_parsed(6, heroes=set()))
    assert slides[0]["is_hero_image"] is True       # cover minimum
    assert all(not s["is_hero_image"] for s in slides[1:])  # no auto-promote


def test_normalise_cover_flags_preserved() -> None:
    _, slides = _normalise_slides(_parsed(7, heroes={1, 4}))
    assert slides[0]["is_cover"] is True
    assert all(not s["is_cover"] for s in slides[1:])


# ── 2. _normalise_slides: slide count 6-11 ───────────────────────────────────


def test_normalise_accepts_eleven_slides() -> None:
    _, slides = _normalise_slides(_parsed(11, heroes={1, 5, 11}))
    assert len(slides) == 11


def test_normalise_rejects_twelve_slides() -> None:
    with pytest.raises(ValueError, match="Expected 6-11"):
        _normalise_slides(_parsed(12, heroes={1}))


def test_normalise_rejects_five_slides() -> None:
    with pytest.raises(ValueError, match="Expected 6-11"):
        _normalise_slides(_parsed(5, heroes={1}))


# ── 3. map_slide_to_family: non-hero routes to text-only, never photo ─────────


def test_routing_cover_first() -> None:
    assert map_slide_to_family({"is_cover": True}, 1, 8) == "cover-photo"


def test_routing_last_and_cta_statement_bomb() -> None:
    assert map_slide_to_family({"slide_type": "body"}, 8, 8) == "statement-bomb"
    assert map_slide_to_family({"slide_type": "cta"}, 5, 8) == "statement-bomb"


def test_routing_mid_hero_photo_headline() -> None:
    fam = map_slide_to_family(
        {"slide_type": "body", "is_hero_image": True}, 4, 8
    )
    assert fam == "photo-headline-yellow-sub"


def test_routing_non_hero_take_editorial_text() -> None:
    # A non-hero editorial "take" is prose (often 25-40 words) → editorial-text,
    # NOT statement-bomb (which is for a 3-15 word punch). E2E 2026-06-13.
    fam = map_slide_to_family(
        {"slide_type": "take", "is_hero_image": False}, 3, 8
    )
    assert fam == "editorial-text"


def test_routing_non_hero_body_editorial_text() -> None:
    fam = map_slide_to_family(
        {"slide_type": "body", "is_hero_image": False}, 4, 8
    )
    assert fam == "editorial-text"


def test_routing_never_photo_layout_for_non_hero() -> None:
    # Every mid non-hero slide (any slide_type) must avoid the empty-photo
    # void-trap: it routes to a text-only family, NEVER photo-headline-yellow-sub.
    for st in ("body", "take", "facts", "explainer", ""):
        fam = map_slide_to_family(
            {"slide_type": st, "is_hero_image": False}, 4, 8
        )
        assert fam != "photo-headline-yellow-sub", f"st={st!r} hit photo layout"


def test_routing_full_smart_carousel() -> None:
    # 8 slides: cover hero, mid hero (3), the rest non-hero text, cta closer.
    _, slides = _normalise_slides(_parsed(8, heroes={1, 3}))
    total = len(slides)
    fams = [map_slide_to_family(s, i, total) for i, s in enumerate(slides, start=1)]
    assert fams[0] == "cover-photo"
    assert fams[-1] == "statement-bomb"
    assert fams[2] == "photo-headline-yellow-sub"  # slide 3 = model hero
    # slides 2,4,5,6,7 are non-hero body → editorial-text (text-only)
    for idx in (1, 3, 4, 5, 6):
        assert fams[idx] == "editorial-text", f"slide {idx + 1} -> {fams[idx]}"
    # no non-hero slide ever lands on the photo layout
    for i, s in enumerate(slides, start=1):
        if not s["is_hero_image"] and i != 1 and i != total:
            assert fams[i - 1] != "photo-headline-yellow-sub"


# ── 4. editorial-text layout exists, text-only, no hero photo ─────────────────


def test_editorial_text_skeleton_is_text_only() -> None:
    skel = _extract_skeleton("editorial-text")
    assert "{{body}}" in skel
    assert "{{heading}}" in skel
    # NO hero photo: neither a .hero rule nor a background-image bound to image_url
    assert ".hero" not in skel
    assert "{{image_url}}" not in skel
    # logo present per brand convention
    assert "logo" in skel
