"""
Updated 2026-06-13 for the SMART-HERO contract (supersedes the 2026-06-12
"every slide is hero" option-A decision, PR #1374). The model now decides how
many slides (6-11) and which deserve a photo; only the cover is guaranteed hero.

This file historically locked "all slides forced hero, 6-8". The all-hero
assertions are now updated to the smart-hero contract (NOT weakened: each
assertion still proves a concrete behavior). The statement-bomb emphasis-fill
and the _hero_bg_to_img fallback-scrim tests are UNCHANGED — those behaviors
(filling {{statement_html_with_emphasis_span}}, raising content above the hero
img with a legibility scrim) remain valid regardless of hero selection.

Contract points still locked here:
  1. _normalise_slides: cover always hero, the model's is_hero_image preserved
     for the rest (no force-promote), slide count 6-11.
  2. composer._fill_placeholders fills statement-bomb's
     {{statement_html_with_emphasis_span}}.
  3. composer._hero_bg_to_img fallback inject (layouts with no .hero div, i.e.
     statement-bomb) must NOT paint the image OVER the text.
"""
from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import _normalise_slides  # noqa: E402
from wr2_html_renderer.composer import (  # noqa: E402
    _fill_placeholders,
    _hero_bg_to_img,
    map_slide_to_family,
)


def _raw_slide(n: int, *, hero: bool = False, **extra) -> dict:
    s = {
        "slide_number": n,
        "slide_type": "body",
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


def test_cover_always_hero_others_preserve_model_choice() -> None:
    # Model marks heroes {3, 5}; the cover is promoted to hero as the minimum,
    # the marked ones stay hero, and the unmarked ones are NOT force-promoted.
    _, slides = _normalise_slides(_parsed(7, heroes={3, 5}))
    assert len(slides) == 7
    assert slides[0]["is_hero_image"] is True            # cover minimum
    assert slides[2]["is_hero_image"] is True            # slide 3 (model)
    assert slides[4]["is_hero_image"] is True            # slide 5 (model)
    assert [s["is_hero_image"] for s in slides] == [
        True, False, True, False, True, False, False
    ]


def test_smart_hero_preserved_across_short_and_long_carousels() -> None:
    # 6, 8, 11 slides all accepted; only cover + model-marked heroes are hero.
    for n in (6, 8, 11):
        _, slides = _normalise_slides(_parsed(n, heroes={1, 3}))
        assert len(slides) == n, f"n={n}"
        assert slides[0]["is_hero_image"] is True, f"n={n} cover"
        assert slides[2]["is_hero_image"] is True, f"n={n} slide3"
        # everything else stays non-hero (no force-promote)
        non_hero = [i for i, s in enumerate(slides, start=1)
                    if not s["is_hero_image"]]
        assert non_hero == [i for i in range(2, n + 1) if i != 3], f"n={n}"


def test_cover_flags_preserved() -> None:
    _, slides = _normalise_slides(_parsed(6))
    assert slides[0]["is_cover"] is True
    assert all(not s["is_cover"] for s in slides[1:])


STATEMENT_SKELETON = (
    "<html><head><style>.emphasis{color:yellow}</style></head><body>"
    '<div class="statement">{{statement_html_with_emphasis_span}}</div>'
    "</body></html>"
)


def test_statement_emphasis_placeholder_filled_from_headline() -> None:
    slide = {"headline": "Where this leaves you", "body": ""}
    html = _fill_placeholders(STATEMENT_SKELETON, slide, hero_filename=None)
    assert "{{statement_html_with_emphasis_span}}" not in html
    assert "Where this leaves" in html
    assert '<span class="emphasis">you</span>' in html


def test_statement_emphasis_escapes_html() -> None:
    slide = {"headline": "A <b>risky</b> & bold move", "body": ""}
    html = _fill_placeholders(STATEMENT_SKELETON, slide, hero_filename=None)
    assert "<b>" not in html
    assert "&amp;" in html


NO_HERO_DIV_SKELETON = (
    "<html><head><style>body{background:#000}</style></head><body>"
    '<div class="statement">BIG WORDS</div>'
    "</body></html>"
)


def test_fallback_inject_adds_img_scrim_and_raises_content() -> None:
    html = _hero_bg_to_img(NO_HERO_DIV_SKELETON, "slide-08-hero.jpg")
    assert 'src="slide-08-hero.jpg"' in html
    assert "hero-scrim" in html
    assert "z-index" in html


def test_hero_div_path_unchanged() -> None:
    skeleton = (
        "<html><head><style>"
        ".hero{background-image:url('{{image_url}}');}"
        "</style></head><body>"
        '<div class="hero" data-zone-type="hero-photo"></div>'
        "</body></html>"
    )
    html = _hero_bg_to_img(skeleton, "h.jpg")
    assert '<img class="hero" src="h.jpg"' in html
    assert "hero-scrim" not in html


def test_routing_smart_hero_mix() -> None:
    # 7 slides, model heroes {1, 3}: cover->cover-photo, last->statement-bomb,
    # slide 3 (hero)->photo-headline-yellow-sub, the non-hero bodies (2,4,5,6)
    # ->editorial-text (text-only), NEVER the empty-photo layout.
    _, slides = _normalise_slides(_parsed(7, heroes={1, 3}))
    total = len(slides)
    fams = [map_slide_to_family(s, i, total) for i, s in enumerate(slides, start=1)]
    assert fams[0] == "cover-photo"
    assert fams[-1] == "statement-bomb"
    assert fams[2] == "photo-headline-yellow-sub"  # slide 3 = model hero
    for idx in (1, 3, 4, 5):  # slides 2,4,5,6 (non-hero body)
        assert fams[idx] == "editorial-text", f"slide {idx + 1} -> {fams[idx]}"
    # no non-hero mid slide ever lands on the photo (void-trap) layout
    for i, s in enumerate(slides, start=1):
        if not s["is_hero_image"] and 1 < i < total:
            assert fams[i - 1] != "photo-headline-yellow-sub"
