"""
Locks down the 2026-06-12 Antonello decision (option A): every WR2 carousel
slide carries its own generated image — 6-8 slides, 6-8 images, flexible.

Three contract points:
  1. wr2_draft_generator._normalise_slides forces is_hero_image=True on EVERY
     slide (cover, bodies, CTA closer) regardless of what the model returned.
  2. composer._fill_placeholders fills statement-bomb's
     {{statement_html_with_emphasis_span}} (previously NEVER filled -> raw
     mustache shipped to the renderer on every CTA slide).
  3. composer._hero_bg_to_img fallback inject (layouts with no .hero div,
     i.e. statement-bomb) must NOT paint the image OVER the text: content is
     raised above the img and a legibility scrim sits between them.
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


def test_all_slides_forced_hero_even_when_model_marks_none() -> None:
    _, slides = _normalise_slides(_parsed(7))
    assert len(slides) == 7
    assert all(s["is_hero_image"] for s in slides)


def test_all_slides_hero_on_short_and_long_carousels() -> None:
    for n in (6, 8):
        _, slides = _normalise_slides(_parsed(n, heroes={1, 3}))
        assert all(s["is_hero_image"] for s in slides), f"n={n}"


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


def test_routing_cover_mid_cta_with_all_hero() -> None:
    _, slides = _normalise_slides(_parsed(7))
    total = len(slides)
    fams = [map_slide_to_family(s, i, total) for i, s in enumerate(slides, start=1)]
    assert fams[0] == "cover-photo"
    assert fams[-1] == "statement-bomb"
    assert all(f == "photo-headline-yellow-sub" for f in fams[1:-1])
