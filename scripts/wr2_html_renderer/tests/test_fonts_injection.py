"""Regression tests for the _fonts.css injection (font-fallback bug, 2026-07-14).

The disease: _normalize_skeleton() CHECKED for `href="_base.css"` (loose) but
REPLACED on `href="_base.css">` (strict). Skeletons using a self-closing
`<link ... />` — editorial-text, stat-card-hero, numbered-forces-list,
photo-headline-yellow-sub, evidence-carved — passed the check, missed the
replace, and rendered with no @font-face at all: Chromium silently painted the
system font. 6/9 slides of bali-pma-rental-crackdown and 4/9 of the PUBLISHED
Rp2.8T revenue carousel shipped that way (check≠action — superscar #3 shape).

Guilt AND innocence per the guard-conformance doctrine: every skeleton variant
must end up with exactly one _fonts.css link, and an already-correct skeleton
must not be double-injected.
"""

import pytest

from wr2_html_renderer.composer import _normalize_skeleton


def _count_fonts_links(html: str) -> int:
    return html.count('href="_fonts.css"')


class TestFontsInjection:
    def test_self_closing_base_link_gets_fonts(self):
        """The 2026-07-14 bug: `<link ... />` skeletons shipped without fonts."""
        html = '<html><head>\n<link rel="stylesheet" href="_base.css" />\n</head><body></body></html>'
        out = _normalize_skeleton(html)
        assert _count_fonts_links(out) == 1

    def test_plain_base_link_gets_fonts(self):
        html = '<html><head>\n<link rel="stylesheet" href="_base.css">\n</head><body></body></html>'
        out = _normalize_skeleton(html)
        assert _count_fonts_links(out) == 1

    def test_relative_base_href_variants_get_fonts(self):
        for href in ("../_base.css", "./_base.css"):
            html = f'<html><head><link rel="stylesheet" href="{href}" /></head><body></body></html>'
            out = _normalize_skeleton(html)
            assert _count_fonts_links(out) == 1, href

    def test_no_base_link_still_gets_fonts(self):
        html = "<html><head><style>.x{}</style></head><body></body></html>"
        out = _normalize_skeleton(html)
        assert _count_fonts_links(out) == 1

    def test_head_with_attributes(self):
        html = '<html><head lang="en"><link rel="stylesheet" href="_base.css" /></head><body></body></html>'
        out = _normalize_skeleton(html)
        assert _count_fonts_links(out) == 1

    def test_already_present_not_duplicated(self):
        """Innocence: a skeleton that already links _fonts.css is left alone."""
        html = (
            '<html><head><link rel="stylesheet" href="_base.css">'
            '<link rel="stylesheet" href="_fonts.css"></head><body></body></html>'
        )
        out = _normalize_skeleton(html)
        assert _count_fonts_links(out) == 1

    def test_no_head_is_fail_visible(self):
        """A skeleton with no <head> cannot host @font-face — refuse loudly."""
        with pytest.raises(ValueError):
            _normalize_skeleton("<html><body>no head here</body></html>")

    def test_all_brand_skeletons_get_fonts(self):
        """Sweep the REAL layout library: every extractable skeleton must end up
        with the fonts link after normalization (class-audit, W89 discipline)."""
        from pathlib import Path

        from wr2_html_renderer.composer import _LAYOUTS, _extract_skeleton

        layouts_dir = Path(_LAYOUTS)
        if not layouts_dir.is_dir():
            pytest.skip("brand layouts dir not present on this machine")
        checked = 0
        for md in sorted(layouts_dir.glob("*.md")):
            try:
                skeleton = _extract_skeleton(md.stem)
            except (FileNotFoundError, ValueError):
                continue
            out = _normalize_skeleton(skeleton)
            assert _count_fonts_links(out) == 1, md.name
            checked += 1
        assert checked > 0, "no skeletons extracted — blind sweep (W84 guard)"
