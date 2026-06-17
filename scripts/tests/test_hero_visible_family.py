"""Layout-aware hero-visibility gate (Antonello 2026-06-13).

The `_hero_visible_in_png` gate samples where the PHOTO is exposed for a given
layout family, instead of always sampling the top third:

  - cover-photo / photo-headline-yellow-sub / photo-fullbleed / default/unknown:
    TOP THIRD (unchanged behavior — text sits on the bottom scrim).
  - photo-fullbleed-top:  LOWER band (~55%-85%) — top is covered by scrim+text.
  - photo-fullbleed-split: MIDDLE band (~40%-60%) — clear photo band between the
    top title and the bottom body.

These tests build synthetic PNGs with PIL: a 1080x1350 image that is FLAT BLACK
in the top third but a bright varied gradient from ~38% downward (so the photo
is exposed in BOTH the split mid-band and the top-layout lower band). A
top-third sampler must see flat black (False); a lower/middle sampler must see
the bright gradient (True). A fully-flat image must be False for every family
(the covered-hero false positive the gate exists to catch).
"""
from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_html_renderer.renderer import _hero_visible_in_png  # noqa: E402

CANVAS_W = 1080
CANVAS_H = 1350


def _black_top_bright_below(path: Path, *, bright_start_frac: float = 0.38) -> None:
    """1080x1350: flat black in the top third, a bright VARIED gradient below.

    Above `bright_start_frac*h` → pure black (a covered/scrimmed top).
    Below it → a per-pixel varied gradient that is mostly non-dark and has wide
    color spread (a real exposed photo band).
    """
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (0, 0, 0))
    px = img.load()
    bright_start = int(CANVAS_H * bright_start_frac)
    for y in range(bright_start, CANVAS_H):
        for x in range(CANVAS_W):
            # bright, varied across both axes → high bright_frac AND high spread
            r = 90 + (x * 160 // CANVAS_W)          # 90..250 across width
            g = 80 + ((y - bright_start) * 150 // (CANVAS_H - bright_start))  # ramps down
            b = 110 + ((x + y) % 130)               # extra spread
            px[x, y] = (r, g, b)
    img.save(path)


def _flat_black(path: Path) -> None:
    """1080x1350 fully flat black — the covered-hero case (must be False)."""
    Image.new("RGB", (CANVAS_W, CANVAS_H), (0, 0, 0)).save(path)


# ── top-layout (lower band) sees the photo; top-third does not ────────────────


def test_top_layout_sees_lower_band_photo(tmp_path: Path) -> None:
    p = tmp_path / "black_top_bright_below.png"
    _black_top_bright_below(p)
    # photo-fullbleed-top samples ~55%-85% → the bright band → VISIBLE
    assert _hero_visible_in_png(p, "photo-fullbleed-top") is True


def test_top_third_blind_to_lower_band_photo(tmp_path: Path) -> None:
    p = tmp_path / "black_top_bright_below.png"
    _black_top_bright_below(p)
    # photo-fullbleed (top-third sampler) sees only the flat-black top → NOT visible
    assert _hero_visible_in_png(p, "photo-fullbleed") is False


# ── split-layout (middle band) sees the photo ─────────────────────────────────


def test_split_layout_sees_middle_band_photo(tmp_path: Path) -> None:
    p = tmp_path / "black_top_bright_below.png"
    _black_top_bright_below(p)
    # photo-fullbleed-split samples ~40%-60% → inside the bright band → VISIBLE
    assert _hero_visible_in_png(p, "photo-fullbleed-split") is True


# ── default / unknown / None → top-third behavior (back-compat) ───────────────


def test_default_none_is_top_third(tmp_path: Path) -> None:
    p = tmp_path / "black_top_bright_below.png"
    _black_top_bright_below(p)
    # family=None must behave EXACTLY like the legacy top-third gate → blind here
    assert _hero_visible_in_png(p, None) is False


def test_unknown_family_is_top_third(tmp_path: Path) -> None:
    p = tmp_path / "black_top_bright_below.png"
    _black_top_bright_below(p)
    # an unknown family falls back to top-third (never crashes, never lower-band)
    assert _hero_visible_in_png(p, "some-future-family") is False


def test_cover_photo_is_top_third(tmp_path: Path) -> None:
    p = tmp_path / "black_top_bright_below.png"
    _black_top_bright_below(p)
    assert _hero_visible_in_png(p, "cover-photo") is False
    assert _hero_visible_in_png(p, "photo-headline-yellow-sub") is False


# ── covered-hero (flat black) is False for EVERY family ───────────────────────


def test_flat_black_false_for_all_families(tmp_path: Path) -> None:
    p = tmp_path / "flat_black.png"
    _flat_black(p)
    for fam in (
        None,
        "cover-photo",
        "photo-headline-yellow-sub",
        "photo-fullbleed",
        "photo-fullbleed-top",
        "photo-fullbleed-split",
        "some-future-family",
    ):
        assert _hero_visible_in_png(p, fam) is False, f"flat black passed for {fam!r}"
