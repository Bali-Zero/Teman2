"""WR2 HTML→PNG carousel renderer (Playwright Chromium).

Replaces the Canva path (which marked drafts `rendered` without verifying hero
images were actually placed — see diag_wr2_canva_hero_images_not_placed_weak_gate
2026-06-07). This renderer's central guarantee is the OPPOSITE: a slide is only
"rendered" once every hero image has decoded in-page BEFORE the screenshot.

Reuse provenance (reuse-first, GROUND phase 2026-06-07):
- The Playwright render core (viewport 1080x1350, dsf=1, fonts.ready gate,
  screenshot) is adapted from `scripts/wr2_carousel_orchestrator.py::
  _render_html_to_png` (~95% lifted) — decoupled here from asyncpg / the PG
  state machine / critic / Telegram so it's a pure function of (slides_json,
  output_dir) → list[PNG].
- The PDF compose is adapted from the same file's `_compose_pdf` (PIL).
- Brand tokens come from `tokens_to_css.py` (this package), generated from
  `~/.claude/skills/bali-zero-brand/tokens.json` — no drift.
- Fonts are vendored locally (fonts/_fonts.css + *.woff2) — no network at
  render time (Law 6).

Gaps fixed vs the existing render core:
1. Fonts vendored local @font-face (was Google-Fonts @import over network).
2. Hero images: real <img> + `await img.decode()` gate, not just CSS background
   + networkidle. This is the exact failure the Canva path had.
3. `wait_until="load"` + explicit fonts.ready + per-image decode, instead of the
   flaky `networkidle` (Playwright docs discourage networkidle).

Layout templating (which HTML skeleton per slide) is a SEPARATE concern handled
by the composer (Phase 2) — this module renders whatever HTML files it's given,
and additionally offers `render_slides_json` which uses the bundled minimal
templates as a baseline. The 9 brand layout families live in
`~/.claude/skills/bali-zero-brand/layouts/*.md` and are wired by the composer.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("wr2.html_renderer")

CANVAS_W = 1080
CANVAS_H = 1350

_PKG_DIR = Path(__file__).resolve().parent
_FONTS_DIR = _PKG_DIR / "fonts"
_BRAND_LOGO = Path.home() / ".claude" / "skills" / "bali-zero-brand" / "assets" / "logo.png"


@dataclass
class RenderResult:
    """Outcome of rendering one carousel."""

    png_paths: list[Path] = field(default_factory=list)
    pdf_path: Path | None = None
    slides_rendered: int = 0
    heroes_expected: int = 0
    heroes_placed: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True only if every slide rendered AND every expected hero was placed.

        This is the anti-Canva gate: no silent "rendered" when heroes are
        missing. heroes_placed must equal heroes_expected.
        """
        return (
            not self.failures
            and self.slides_rendered > 0
            and self.heroes_placed == self.heroes_expected
        )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


async def _download_image(url: str, dest: Path, *, client: Any) -> bool:
    """Download a remote hero image to dest. Returns True on a real image.

    Uses httpx (async, Golden Rule #4). Follows redirects (Tigris public URLs
    are direct 200 today, but a 302 must NOT silently break placement — the
    Canva path's documented failure mode). Verifies non-empty + image-ish
    content-type.
    """
    try:
        resp = await client.get(url, follow_redirects=True, timeout=30.0)
    except Exception as exc:  # network/timeout
        logger.warning("hero download failed url=%s err=%s", url, exc)
        return False
    if resp.status_code != 200:
        logger.warning("hero download non-200 url=%s status=%s", url, resp.status_code)
        return False
    ctype = resp.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        logger.warning("hero download not-an-image url=%s ctype=%s", url, ctype)
        return False
    data = resp.content
    if not data:
        logger.warning("hero download empty url=%s", url)
        return False
    dest.write_bytes(data)
    return True


def _stage_assets(output_dir: Path) -> None:
    """Copy fonts (_fonts.css + woff2), logo, and the generated _base.css into
    output_dir/ so every per-slide HTML resolves them under one file:// origin.
    """
    slides_dir = output_dir
    slides_dir.mkdir(parents=True, exist_ok=True)

    # fonts
    for f in _FONTS_DIR.glob("*.woff2"):
        shutil.copy2(f, slides_dir / f.name)
    shutil.copy2(_FONTS_DIR / "_fonts.css", slides_dir / "_fonts.css")

    # logo (Art 4.1 — official PNG, never recreated)
    if _BRAND_LOGO.is_file():
        shutil.copy2(_BRAND_LOGO, slides_dir / "logo.png")
    else:
        logger.warning("brand logo not found at %s — slides will miss the logo", _BRAND_LOGO)

    # _base.css with token :root injected from tokens.json (no drift)
    from .tokens_to_css import load_tokens, render_root_block  # local import

    base_css_src = _brand_base_css_body()
    root_block = render_root_block(load_tokens())
    # The brand _base.css already begins with a :root block; we replace it with
    # the freshly-generated one to guarantee tokens match tokens.json exactly.
    merged = _replace_root_block(base_css_src, root_block)
    (slides_dir / "_base.css").write_text(merged, encoding="utf-8")


def _brand_base_css_body() -> str:
    """Read the brand _base.css (component classes below the :root block)."""
    brand_base = Path.home() / ".claude" / "skills" / "bali-zero-brand" / "layouts" / "_base.css"
    if not brand_base.is_file():
        raise FileNotFoundError(f"brand _base.css not found at {brand_base}")
    return brand_base.read_text(encoding="utf-8")


def _replace_root_block(css: str, new_root_block: str) -> str:
    """Replace the first `:root { ... }` block in css with new_root_block.

    Falls back to prepending if no :root is found.
    """
    import re

    pattern = re.compile(r":root\s*\{[^}]*\}", re.DOTALL)
    if pattern.search(css):
        return pattern.sub(new_root_block, css, count=1)
    return new_root_block + "\n\n" + css


# The in-page JS that GUARANTEES fonts + every hero <img> are ready before the
# screenshot. This is the heart of the anti-Canva fix: we await each image's
# decode(), and report how many decoded, so the caller can assert placement.
_READINESS_JS = """
async () => {
  // 1. Fonts: explicitly LOAD the weights the brand uses, then await ready.
  //    document.fonts.load() forces the @font-face to fetch+parse even if no
  //    node has triggered it yet, and resolves when that face is usable —
  //    more reliable than relying on font-display:block + a status scan, which
  //    can race (the face shows 'unloaded' until first paint uses it).
  const fontProbes = [
    '700 16px Montserrat',
    '800 16px Montserrat',
  ];
  try { await Promise.all(fontProbes.map(spec => document.fonts.load(spec))); } catch (e) {}
  await document.fonts.ready;
  // 2. Images: await decode() on every <img>, count successes
  const imgs = Array.from(document.images);
  let decoded = 0;
  await Promise.all(imgs.map(async (img) => {
    try {
      if (img.complete && img.naturalWidth > 0) { decoded++; return; }
      await img.decode();
      if (img.naturalWidth > 0) decoded++;
    } catch (e) { /* failed image — not counted */ }
  }));
  // 3. Report: total imgs, decoded imgs, montserrat loaded (via check(), which
  //    reflects post-load() truth rather than the lazy status field).
  const montserrat = document.fonts.check('800 16px Montserrat')
                  || document.fonts.check('700 16px Montserrat');
  return { total_images: imgs.length, decoded_images: decoded, montserrat };
}
"""


async def _render_one(
    page: Any,
    html_path: Path,
    png_path: Path,
    *,
    expect_hero: bool,
    timeout_ms: int,
) -> tuple[bool, bool, str | None]:
    """Render one HTML file to PNG. Returns (rendered_ok, hero_placed, error).

    hero_placed is True if expect_hero and at least one non-logo image decoded.
    (The logo is also an <img>/background; we treat decoded_images > logo-count
    as the hero signal — see caller which passes expect_hero per slide.)
    """
    try:
        await page.goto(html_path.resolve().as_uri(), wait_until="load")
        readiness = await page.evaluate(_READINESS_JS)
        await page.screenshot(path=str(png_path), full_page=False, omit_background=False)
    except Exception as exc:
        return (False, False, f"{html_path.name}: render error {exc}")

    total = readiness.get("total_images", 0)
    decoded = readiness.get("decoded_images", 0)
    montserrat = readiness.get("montserrat", False)

    if not montserrat:
        logger.warning("%s: Montserrat NOT loaded — font may be wrong", html_path.name)

    if expect_hero:
        # logo.png is loaded via CSS background-image, NOT an <img>, so any
        # decoded <img> here is a hero. Require >=1 decoded image.
        hero_placed = decoded >= 1
        if not hero_placed:
            return (
                True,
                False,
                f"{html_path.name}: HERO MISSING — expected hero image, "
                f"decoded {decoded}/{total} <img> (the exact Canva failure)",
            )
        return (True, True, None)

    return (True, False, None)


async def render_html_files(
    html_specs: list[tuple[Path, bool]],
    output_dir: Path,
    *,
    timeout_ms: int = 30000,
    make_pdf: bool = True,
) -> RenderResult:
    """Render a list of (html_path, expect_hero) to PNGs in output_dir/slides.

    html_specs: ordered list; each is (path-to-html, whether-this-slide-has-a-hero).
    Assets (fonts, logo, _base.css) must already be staged in output_dir by the
    caller (or call render_slides_json which stages them).

    Returns a RenderResult whose .ok is True ONLY if all slides rendered and
    every expected hero was actually placed.
    """
    from playwright.async_api import async_playwright  # lazy import

    result = RenderResult(heroes_expected=sum(1 for _, h in html_specs if h))
    slides_out = output_dir / "slides"
    slides_out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": CANVAS_W, "height": CANVAS_H},
                device_scale_factor=1,
            )
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)

            for idx, (html_path, expect_hero) in enumerate(html_specs, start=1):
                png_path = slides_out / f"{idx:02d}.png"
                rendered_ok, hero_placed, error = await _render_one(
                    page, html_path, png_path, expect_hero=expect_hero, timeout_ms=timeout_ms
                )
                if rendered_ok and png_path.is_file():
                    # verify dimensions
                    if not _verify_png_dims(png_path):
                        result.failures.append(f"{png_path.name}: wrong dimensions")
                        continue
                    result.png_paths.append(png_path)
                    result.slides_rendered += 1
                    if hero_placed:
                        # Second gate (anti false-positive): decode() proved the
                        # bytes loaded; now prove the hero is VISIBLE on canvas
                        # (not covered/painted-over — the 2026-06-07 cover bug).
                        if _hero_visible_in_png(png_path):
                            result.heroes_placed += 1
                        else:
                            result.failures.append(
                                f"{png_path.name}: HERO DECODED BUT NOT VISIBLE — "
                                f"top region is flat/empty (covered or mis-layered); "
                                f"not counting as placed"
                            )
                if error:
                    result.failures.append(error)
        finally:
            await browser.close()

    if make_pdf and result.png_paths:
        pdf_path = output_dir / "carousel.pdf"
        try:
            _compose_pdf(result.png_paths, pdf_path)
            result.pdf_path = pdf_path
        except Exception as exc:
            result.failures.append(f"pdf compose failed: {exc}")

    return result


def _verify_png_dims(png_path: Path) -> bool:
    from PIL import Image  # lazy

    with Image.open(png_path) as img:
        return img.size == (CANVAS_W, CANVAS_H)


def _hero_visible_in_png(png_path: Path) -> bool:
    """Pixel-level check that a hero photo is actually VISIBLE in the top region.

    Defends against the decode-but-covered false positive found 2026-06-07 (the
    cover slide: the hero <img> decoded fine — gate said placed — but a sibling
    .hero div with background-color painted over it, so the rendered top was flat
    black). `img.decode()` proves the bytes loaded; THIS proves they reached the
    canvas. A real photo has color variance in the top third; a covered/missing
    hero is near-uniform (flat black or flat antracite).

    Returns True if the top third shows enough non-background, varied pixels.
    """
    from PIL import Image  # lazy

    with Image.open(png_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        # Sample the TOP THIRD (hero photo dominates above the gradient+text
        # block which sits in the bottom ~180px+).
        xs = range(w // 8, 7 * w // 8, 30)
        ys = range(h // 12, h // 3, 30)
        samples = []
        for y in ys:
            for x in xs:
                samples.append(img.getpixel((x, y)))
        if not samples:
            return False
        # (a) brightness: fraction of samples that are not near-black
        non_dark = sum(1 for (r, g, b) in samples if (r + g + b) > 60)
        bright_frac = non_dark / len(samples)
        # (b) variance: a flat fill (even a grey one) has tiny spread; a photo
        # has real spread across samples. Use per-channel range as a cheap proxy.
        rs = [s[0] for s in samples]
        gs = [s[1] for s in samples]
        bs = [s[2] for s in samples]
        spread = (max(rs) - min(rs)) + (max(gs) - min(gs)) + (max(bs) - min(bs))
        # A photo lights up most samples AND has color spread. Thresholds chosen
        # so a flat antracite (#2C2F38, spread 0) or flat black fails, while a
        # real cinematic hero passes.
        return bright_frac > 0.4 and spread > 40


def _compose_pdf(png_paths: list[Path], pdf_path: Path) -> None:
    """Combine PNG slides into a multipage PDF (adapted from orchestrator)."""
    from PIL import Image  # lazy

    if not png_paths:
        raise ValueError("cannot compose PDF from empty PNG list")
    images: list[Any] = []
    for p in png_paths:
        img = Image.open(p)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)
    first, *rest = images
    first.save(str(pdf_path), save_all=True, append_images=rest, format="PDF", resolution=72.0)
    for img in images:
        img.close()
