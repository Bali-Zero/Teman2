"""Smoke test for the WR2 HTML renderer — proves the anti-Canva gate works.

Two cases on the SAME cover template:
  A) hero image present  → RenderResult.ok == True,  hero pixels in the PNG.
  B) hero image MISSING  → RenderResult.ok == False (the gate fires — this is
     exactly what the Canva path failed to detect: a "rendered" carousel with
     no hero image).

Run from the package dir with the backend venv python (has Playwright + PIL):
    PYTHONPATH=<worktree>/scripts python -m wr2_html_renderer._smoke_test <hero.png>

Exit 0 = both cases behaved correctly. Exit 1 = the gate is broken.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_TEMPLATES = _PKG / "templates"


def _build_slide_html(out_dir: Path, hero_filename: str | None, name: str) -> Path:
    """Materialize the cover template with a hero (or a missing hero) into out_dir."""
    tpl = (_TEMPLATES / "cover_test.html").read_text(encoding="utf-8")
    hero_ref = hero_filename if hero_filename else "does-not-exist.jpg"
    html = (
        tpl.replace("{{HERO_FILE}}", hero_ref)
        .replace("{{SUBHEAD}}", "PROPERTY · 2026")
        .replace("{{HEADLINE}}", "PT PMA OR DIRECT TITLE?")
    )
    p = out_dir / f"{name}.html"
    p.write_text(html, encoding="utf-8")
    return p


def _hero_pixel_present(png_path: Path) -> bool:
    """Heuristic: a slide WITH a hero photo has color variance in the top half
    (the photo), whereas a missing-hero slide is flat black there. We sample
    the top-center region and check it's not uniformly near-black.
    """
    from PIL import Image

    with Image.open(png_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        # sample a grid in the TOP third (where the hero photo dominates, above
        # the gradient+text block at bottom 180px)
        xs = range(w // 4, 3 * w // 4, 40)
        ys = range(h // 12, h // 3, 40)
        non_black = 0
        total = 0
        for y in ys:
            for x in xs:
                r, g, b = img.getpixel((x, y))
                total += 1
                if (r + g + b) > 60:  # not near-black
                    non_black += 1
        # a real photo lights up most samples; flat black lights up ~none
        return total > 0 and (non_black / total) > 0.5


async def _run(hero_src: Path) -> int:
    from wr2_html_renderer import render_html_files
    from wr2_html_renderer.renderer import _stage_assets

    import tempfile

    rc = 0
    with tempfile.TemporaryDirectory(prefix="wr2-render-smoke-") as td:
        work = Path(td)

        # ---- CASE A: hero present ----
        a_dir = work / "case_a"
        a_dir.mkdir()
        _stage_assets(a_dir)
        # copy the real hero into the slides dir
        slides_a = a_dir / "slides"
        slides_a.mkdir(exist_ok=True)
        hero_dst = slides_a / "slide-hero.jpg"
        hero_dst.write_bytes(hero_src.read_bytes())
        html_a = _build_slide_html(slides_a, "slide-hero.jpg", "01")
        res_a = await render_html_files([(html_a, True)], a_dir, make_pdf=False)

        print("=== CASE A: hero PRESENT ===")
        print(f"  ok={res_a.ok} rendered={res_a.slides_rendered} "
              f"heroes_expected={res_a.heroes_expected} heroes_placed={res_a.heroes_placed}")
        print(f"  failures={res_a.failures}")
        a_png = res_a.png_paths[0] if res_a.png_paths else None
        a_has_hero_pixels = _hero_pixel_present(a_png) if a_png else False
        print(f"  hero pixels in PNG: {a_has_hero_pixels}")
        if not (res_a.ok and a_has_hero_pixels):
            print("  ❌ CASE A FAILED — hero present should render ok WITH visible pixels")
            rc = 1
        else:
            print("  ✓ CASE A PASS")

        # ---- CASE B: hero MISSING ----
        b_dir = work / "case_b"
        b_dir.mkdir()
        _stage_assets(b_dir)
        slides_b = b_dir / "slides"
        slides_b.mkdir(exist_ok=True)
        # deliberately do NOT place the hero file
        html_b = _build_slide_html(slides_b, "does-not-exist.jpg", "01")
        res_b = await render_html_files([(html_b, True)], b_dir, make_pdf=False)

        print("=== CASE B: hero MISSING (gate should FIRE) ===")
        print(f"  ok={res_b.ok} rendered={res_b.slides_rendered} "
              f"heroes_expected={res_b.heroes_expected} heroes_placed={res_b.heroes_placed}")
        print(f"  failures={res_b.failures}")
        if res_b.ok:
            print("  ❌ CASE B FAILED — missing hero must make ok=False (anti-Canva gate)")
            rc = 1
        elif res_b.heroes_placed != 0:
            print("  ❌ CASE B FAILED — missing hero should count heroes_placed=0")
            rc = 1
        else:
            print("  ✓ CASE B PASS — gate correctly refused to call it rendered")

    return rc


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m wr2_html_renderer._smoke_test <hero-image-path>")
        return 2
    hero = Path(sys.argv[1])
    if not hero.is_file():
        print(f"hero image not found: {hero}")
        return 2
    return asyncio.run(_run(hero))


if __name__ == "__main__":
    raise SystemExit(main())
