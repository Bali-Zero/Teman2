"""Cheap, deterministic design-critic signals (Tier 0-1 of the designer loop).

These run BEFORE any vision-model call, so a clean slide can pass at ~$0. They
turn "looks wrong" into measured numbers a patcher can act on, and they tell the
loop WHERE the photo is calm (so text can be placed there).

Signals (all from the rendered PNG + the hero image, using already-installed
numpy/PIL — skimage optional):
  - wcag_contrast(fg, bg): the standard WCAG relative-luminance contrast ratio.
  - region_luminance_stats(png, box): mean luminance + spread of a region.
  - text_region_contrast(png, text_box, fg_rgb): measured contrast of the text
    color against the actual pixels behind it (per-region, not a global guess).
  - saliency_map(image): a luminance-variance "busy map" — high where the photo
    is detailed/cluttered (bad for text), low where it's calm (good for text).
  - calmest_band(image, n_bands): which horizontal band of the image is calmest
    (least salient) → where text should go for legibility.
  - geometry_lint(...): from the HTML render we know the canvas is fixed; this
    checks the PNG for gross problems (near-empty slide, text-likely-overflow via
    bottom-edge ink).

Design note: WCAG formula is ~15 lines and trivially correct; we vendor it
rather than pin the unmaintained 2015 `wcag-contrast-ratio` dep (reuse-first
license/maturity gate). numpy does the heavy pixel math.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# WCAG 2.x thresholds
WCAG_AA_NORMAL = 4.5
WCAG_AAA_NORMAL = 7.0  # brand target (constitution Art 2 / Legibility Armor)


def _srgb_to_linear(c: float) -> float:
    """sRGB channel [0,1] → linear, per WCAG relative-luminance definition."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG relative luminance of an sRGB color (0-255 ints or 0-1 floats)."""
    r, g, b = rgb
    if r > 1 or g > 1 or b > 1:
        r, g, b = r / 255.0, g / 255.0, b / 255.0
    rl = _srgb_to_linear(r)
    gl = _srgb_to_linear(g)
    bl = _srgb_to_linear(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def wcag_contrast(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    """WCAG contrast ratio between two colors (1.0 .. 21.0). Higher = more legible."""
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _load_rgb(png_path: Path) -> np.ndarray:
    """Load a PNG/JPG as an HxWx3 uint8 numpy array (RGB)."""
    from PIL import Image

    with Image.open(png_path) as img:
        return np.asarray(img.convert("RGB"))


@dataclass
class RegionStats:
    mean_rgb: tuple[float, float, float]
    mean_luminance: float  # 0..1
    luminance_std: float  # spread (flat fill ~0, photo high)


def region_luminance_stats(png_path: Path, box: tuple[float, float, float, float]) -> RegionStats:
    """Mean RGB + luminance + spread of a region.

    box = (x0, y0, x1, y1) in FRACTIONS of width/height (0..1), so it's
    resolution-independent.
    """
    arr = _load_rgb(png_path)
    h, w, _ = arr.shape
    x0 = int(box[0] * w)
    y0 = int(box[1] * h)
    x1 = int(box[2] * w)
    y1 = int(box[3] * h)
    crop = arr[y0:y1, x0:x1, :].astype(np.float64)
    if crop.size == 0:
        return RegionStats((0, 0, 0), 0.0, 0.0)
    mean_rgb = tuple(crop.reshape(-1, 3).mean(axis=0))
    # per-pixel luminance
    lin = np.where(crop / 255.0 <= 0.03928, (crop / 255.0) / 12.92, (((crop / 255.0) + 0.055) / 1.055) ** 2.4)
    lum = 0.2126 * lin[:, :, 0] + 0.7152 * lin[:, :, 1] + 0.0722 * lin[:, :, 2]
    return RegionStats(mean_rgb, float(lum.mean()), float(lum.std()))


def text_region_contrast(
    png_path: Path,
    text_box: tuple[float, float, float, float],
    fg_rgb: tuple[float, float, float],
) -> float:
    """Measured WCAG contrast of the text color against the actual pixels behind it.

    This is the per-region number (not a theoretical guess) the patcher acts on.
    Uses the region's mean color as the background — a conservative proxy; for a
    photo with bright+dark zones this can be optimistic, which is why the loop
    ALSO uses saliency + the VLM. But it catches the gross failures cheaply.
    """
    stats = region_luminance_stats(png_path, text_box)
    return wcag_contrast(fg_rgb, stats.mean_rgb)


def saliency_map(image_path: Path, downscale: int = 64) -> np.ndarray:
    """A cheap luminance-variance 'busy map': high where the image is detailed.

    No OpenCV/skimage needed — local std of luminance on a downscaled grid.
    Returns a (downscale x downscale) float array normalized 0..1, where 1 =
    busiest (worst for text) and 0 = calmest (best for text).
    """
    from PIL import Image

    with Image.open(image_path) as img:
        g = img.convert("L").resize((downscale, downscale))
        a = np.asarray(g, dtype=np.float64) / 255.0

    # local variance via a simple 3x3 sliding window (numpy, no deps)
    pad = np.pad(a, 1, mode="edge")
    acc = np.zeros_like(a)
    acc_sq = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = pad[1 + dy : 1 + dy + a.shape[0], 1 + dx : 1 + dx + a.shape[1]]
            acc += shifted
            acc_sq += shifted * shifted
    n = 9.0
    local_var = acc_sq / n - (acc / n) ** 2
    local_var = np.clip(local_var, 0, None)
    if local_var.max() > 0:
        local_var = local_var / local_var.max()
    return local_var


def calmest_band(image_path: Path, n_bands: int = 3) -> tuple[int, list[float]]:
    """Which horizontal band of the image is calmest (least salient).

    Returns (best_band_index, per_band_busyness). band 0 = top. Use to decide
    where text should sit: prefer the calmest band for legibility.
    """
    sal = saliency_map(image_path)
    rows = sal.shape[0]
    band_h = max(1, rows // n_bands)
    busyness = []
    for b in range(n_bands):
        y0 = b * band_h
        y1 = rows if b == n_bands - 1 else (b + 1) * band_h
        busyness.append(float(sal[y0:y1, :].mean()))
    best = int(np.argmin(busyness))
    return best, busyness


# ---------------------------------------------------------------------------
# Article 2.3 palette-adherence SIGNAL (2026-07-14, cure item 13 /
# research/operations/2026-07-14-wr2-deep-audit.md §5): the constitution says
# "TEXT zones... >=95% of pixels in palette tokens. Hard fail" but no
# measurement of this existed anywhere in the engine (grep-verified). This
# adds the actual pixel measurement — but ships it as a recorded SIGNAL
# (logged + written to manifest.json), NOT a hard gate, because:
#   1. We don't have per-element zone bounding boxes at this post-render
#      stage (no structured layout JSON survives PNG rasterization) — the
#      hero-band exclusion below is a coarse family-aware approximation
#      (reusing renderer._hero_visible_in_png's band geometry), not a real
#      per-element text/hero/overlay mask. It over-excludes (the gradient
#      overlay + any text inside the excluded band is skipped too, not just
#      the photo) and under-excludes (a stray hero corner outside the band
#      still counts against the ratio).
#   2. No calibration run exists yet against real published carousels to
#      pick a defensible tolerance/threshold; fabricating a hard-fail
#      threshold without that data would over-block on the approximation's
#      noise, not the actual brand violation.
# Recording the ratio on every render is what MAKES that calibration
# possible later — see PR body for the v1-signal-not-gate rationale.
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _brand_palette_rgb() -> np.ndarray:
    """The exact 6 tokens Article 2.3 names: color.bg.* + color.text.* +
    color.accent.* + color.status.* (NOT color.overlay.* — that's a photo
    legibility scrim, not a palette color per Article 2.1's token table)."""
    from .tokens_to_css import load_tokens  # local import, mirrors renderer.py

    tokens = load_tokens()
    color = tokens["color"]
    hexes = [
        color["bg"]["antracite"]["value"],
        color["bg"]["black"]["value"],
        color["text"]["white"]["value"],
        color["text"]["muted"]["value"],
        color["accent"]["yellow"]["value"],
        color["status"]["red"]["value"],
    ]
    return np.array([_hex_to_rgb(h) for h in hexes], dtype=np.float64)


def _hero_exclusion_band(family: str | None, h: int) -> tuple[int, int] | None:
    """Row range (y0, y1) to exclude as the HERO PHOTO zone, mirroring
    renderer._hero_visible_in_png's family-aware sampling bands exactly (same
    families, same fractions) so the two never drift apart. None = no
    exclusion (measure the whole canvas)."""
    if family == "photo-fullbleed-top":
        return (11 * h // 20, 17 * h // 20)  # ~55%-85%
    if family == "photo-fullbleed-split":
        return (2 * h // 5, 3 * h // 5)  # ~40%-60%
    return (h // 12, h // 3)  # ~8%-33% (cover-photo / photo-headline-yellow-sub / photo-fullbleed / unknown)


def palette_adherence_ratio(
    png_path: Path,
    *,
    family: str | None = None,
    has_hero: bool = False,
    tolerance: float = 40.0,
    sample_stride: int = 4,
) -> float:
    """Fraction of sampled canvas pixels within `tolerance` Euclidean RGB
    distance of the nearest brand-palette token color (Article 2.3 signal).

    `has_hero=False` (text-only families — editorial-text, dark-status-list,
    evidence-carved, statement-bomb, elegant-close, qa-dialogue,
    timeline-pinboard, numbered-forces-list, stat-card-hero) measures the
    FULL canvas — there is no photo zone to exclude, so the whole slide IS
    the constitution's TEXT zone. `has_hero=True` excludes the family-aware
    hero band (see `_hero_exclusion_band`) before measuring — approximating
    Article 2.3's "HERO PHOTO zones: NO palette pixel constraint" exemption.

    `tolerance` (Euclidean RGB distance, 0-441) accounts for anti-aliased
    text edges and JPEG-ish gradient banding blending a palette color into
    its neighbor — a bare exact-hex match would undercount even a perfectly
    compliant slide. 40.0 is a starting value (~14% of the 0-255 per-channel
    range), NOT calibrated against real renders — see module comment.
    """
    palette_rgb = _brand_palette_rgb()
    arr = _load_rgb(png_path).astype(np.float64)
    h, w, _ = arr.shape
    if has_hero:
        y0, y1 = _hero_exclusion_band(family, h)
        keep = np.ones(h, dtype=bool)
        keep[y0:y1] = False
        arr = arr[keep]
    if arr.size == 0:
        return 1.0  # degenerate (nothing left to measure) — no false alarm
    sampled = arr[::sample_stride, ::sample_stride, :].reshape(-1, 3)
    if sampled.size == 0:
        return 1.0
    dists = np.sqrt(((sampled[:, None, :] - palette_rgb[None, :, :]) ** 2).sum(axis=2))
    nearest = dists.min(axis=1)
    return float((nearest <= tolerance).mean())


@dataclass
class GeometryLint:
    near_empty: bool  # slide is almost all one flat color (render likely broke)
    bottom_ink_ratio: float  # ink near very bottom edge → possible text overflow
    flags: list[str]


def geometry_lint(png_path: Path) -> GeometryLint:
    """Gross structural problems detectable from the PNG alone (Tier 0, free).

    NOTE (E2E 2026-06-07): a "top-edge ink" check for clipped titles was tried
    and REJECTED — it conflated a clipped full-width title with the legitimate
    yellow regulation pill in the top-right corner (both register as "ink near
    the top"). On real slides the good baseline read 0.71 and the clipped one
    0.97 — too close, and the good one would false-positive. Pixel-level clip
    detection isn't reliable here; clipping is prevented structurally instead
    (the dangerous text_anchor reposition lever was removed) and the vision
    critic catches any residual clip. So geometry only flags the two things it
    CAN judge reliably: near-empty render + bottom overflow.
    """
    arr = _load_rgb(png_path).astype(np.float64)
    h, w, _ = arr.shape
    flags: list[str] = []

    # near-empty: tiny global color variance = flat fill (broken render, e.g. the
    # cover-black bug). A real slide has photo + text variance.
    global_std = float(arr.std())
    near_empty = global_std < 8.0
    if near_empty:
        flags.append(f"near-empty slide (global pixel std={global_std:.1f} — render may have failed)")

    # bottom-edge ink: text running off the bottom. Sample the last 3% rows; if a
    # lot of non-background ink sits at the very edge, flag possible overflow.
    bottom = arr[int(h * 0.97) :, :, :]
    bg_like = np.abs(bottom - bottom.mean(axis=(0, 1))).sum(axis=2) < 30
    bottom_ink_ratio = float(1.0 - bg_like.mean())
    if bottom_ink_ratio > 0.25:
        flags.append(f"ink at bottom edge (ratio={bottom_ink_ratio:.2f}) — possible text overflow")

    return GeometryLint(near_empty=near_empty, bottom_ink_ratio=bottom_ink_ratio, flags=flags)
