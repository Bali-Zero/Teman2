"""Article 2.3 (palette >=95% pixel adherence) SIGNAL tests (cure item 13,
2026-07-14 — research/operations/2026-07-14-wr2-deep-audit.md §5: "Art 2.3
'>=95% palette pixels' (the measurement does not exist in code)").

This ships as a recorded SIGNAL (manifest.json `palette_adherence`), not a
hard gate — see critic_signals.py module comment for why (no per-element
zone bounding boxes survive to the PNG, no calibration data yet). These
tests pin the measurement itself: guilt (off-palette fill scores low),
innocence (on-palette fill scores ~1.0), and the hero-band exclusion
(an off-palette hero region must not drag down a compliant text canvas).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from wr2_html_renderer import critic_signals as CS  # noqa: E402

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from PIL import Image  # noqa: E402


def _solid_png(path, rgb, size=(200, 250)):
    Image.new("RGB", size, rgb).save(path)


def _split_png(path, top_rgb, bottom_rgb, size=(200, 250), split_frac=0.33):
    img = Image.new("RGB", size)
    w, h = size
    split_y = int(h * split_frac)
    for y in range(h):
        color = top_rgb if y < split_y else bottom_rgb
        for x in range(w):
            img.putpixel((x, y), color)
    img.save(path)


# --- INNOCENCE: a slide painted entirely in a brand palette color ----------

def test_innocence_pure_antracite_scores_full_adherence(tmp_path):
    p = tmp_path / "slide.png"
    _solid_png(p, (0x37, 0x3D, 0x42))  # color.bg.antracite
    ratio = CS.palette_adherence_ratio(p, has_hero=False)
    assert ratio > 0.99


def test_innocence_pure_yellow_accent_scores_full_adherence(tmp_path):
    p = tmp_path / "slide.png"
    _solid_png(p, (0xF4, 0xC4, 0x30))  # color.accent.yellow
    ratio = CS.palette_adherence_ratio(p, has_hero=False)
    assert ratio > 0.99


# --- GUILT: a slide painted in a banned color -------------------------------

@pytest.mark.parametrize(
    "rgb",
    [
        (0, 200, 0),  # banned green
        (0, 0, 220),  # banned blue
        (150, 50, 200),  # banned purple
    ],
)
def test_guilt_banned_color_scores_low_adherence(tmp_path, rgb):
    p = tmp_path / "slide.png"
    _solid_png(p, rgb)
    ratio = CS.palette_adherence_ratio(p, has_hero=False)
    assert ratio < 0.05


# --- Hero-band exclusion: has_hero=True must exclude the photo zone --------

def test_hero_band_exclusion_ignores_offpalette_top_third(tmp_path):
    """A cover-photo slide: the family's exposed photo band (~8%-33%, the
    same fractions renderer._hero_visible_in_png samples) is a (simulated)
    cinematic photo full of banned-palette colors; everywhere else is
    compliant antracite bg + white text. Article 2.3 exempts the hero zone
    entirely — has_hero=True with family='cover-photo' should score
    near-1.0 despite the noisy band, while measuring the FULL canvas (no
    exclusion) must score visibly lower."""
    p = tmp_path / "slide.png"
    w, h = 200, 250
    img = Image.new("RGB", (w, h), (0x37, 0x3D, 0x42))
    y0, y1 = h // 12, h // 3  # exact band CS._hero_exclusion_band computes
    for y in range(y0, y1):
        for x in range(w):
            img.putpixel((x, y), (0, 180, 0))
    img.save(p)
    ratio_excluding_hero = CS.palette_adherence_ratio(p, family="cover-photo", has_hero=True)
    ratio_full_canvas = CS.palette_adherence_ratio(p, has_hero=False)
    assert ratio_excluding_hero > 0.99
    assert ratio_full_canvas < ratio_excluding_hero  # exclusion demonstrably matters


def test_hero_band_exclusion_family_aware_lower_band(tmp_path):
    """photo-fullbleed-top exposes its photo LOWER (~55%-85%), not top-third
    — verifies the band mirrors renderer._hero_visible_in_png's per-family
    geometry rather than always assuming top-third."""
    p = tmp_path / "slide.png"
    w, h = 200, 250
    img = Image.new("RGB", (w, h), (0x37, 0x3D, 0x42))
    # paint the family's actual exposed band (55%-85%) with a banned color
    y0, y1 = int(h * 0.55), int(h * 0.85)
    for y in range(y0, y1):
        for x in range(w):
            img.putpixel((x, y), (0, 0, 220))
    img.save(p)
    ratio = CS.palette_adherence_ratio(p, family="photo-fullbleed-top", has_hero=True)
    assert ratio > 0.9


def test_signal_returns_plain_float_not_a_verdict_object(tmp_path):
    """Contract check: the function returns a plain float ratio (a SIGNAL),
    never a pass/fail verdict object — callers decide what to do with it."""
    p = tmp_path / "slide.png"
    _solid_png(p, (0x37, 0x3D, 0x42))
    ratio = CS.palette_adherence_ratio(p, has_hero=False)
    assert isinstance(ratio, float)
    assert 0.0 <= ratio <= 1.0


def test_degenerate_full_exclusion_returns_neutral_one(tmp_path, monkeypatch):
    """Defensive edge case: if the hero-band exclusion were ever to consume
    the ENTIRE canvas (not reachable via the real per-family bands, which
    are always a proper subset — verified by the other hero-band tests —
    but the code must not crash or manufacture a false alarm if it were),
    fall back to a neutral 1.0 rather than dividing by zero samples."""
    p = tmp_path / "slide.png"
    _solid_png(p, (0, 200, 0), size=(10, 10))
    monkeypatch.setattr(CS, "_hero_exclusion_band", lambda family, h: (0, h))
    ratio = CS.palette_adherence_ratio(p, family="cover-photo", has_hero=True)
    assert ratio == 1.0
