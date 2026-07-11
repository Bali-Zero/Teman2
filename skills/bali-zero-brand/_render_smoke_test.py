#!/usr/bin/env python3
"""WR2 layout render smoke test.

Renders one cover-photo slide using the actual layout HTML/CSS skeleton
from the bali-zero-brand skill, with empirical verification:
- Montserrat font loads before screenshot (document.fonts.ready)
- PNG dimensions = 1080x1350
- Palette compliance in text-zones (region-aware)
- No hex code leaks beyond _base.css :root vars
"""

import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

SKILL_DIR = Path.home() / ".claude/skills/bali-zero-brand"
OUT_DIR = Path("/tmp/wr2-render-smoke")
OUT_DIR.mkdir(exist_ok=True)

# Test data — minimal cover slide
TEST_SLIDE = {
    "heading": "INVESTMENT IS NOT IMMIGRATION",
    "subheading": "GOLDEN VISA REALITY",
    "image_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1080&h=1350&fit=crop",
}

ALLOWED_HEX_IN_CSS = {
    # Palette tokens — these are OK in _base.css :root only
    "#373D42", "#000000", "#FFFFFF", "#9CA3AF",
    "#F4C430", "#C8102E",
}

async def render_smoke():
    base_css = (SKILL_DIR / "layouts/_base.css").read_text()

    # Build full HTML using cover-photo template
    html = f"""<!doctype html>
<html><head>
<style>{base_css}</style>
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap');
.hero {{
  position: absolute; inset: 0;
  background-image: url('{TEST_SLIDE["image_url"]}');
  background-size: cover; background-position: center;
}}
.gradient {{
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.0) 30%, var(--color-overlay-darken-60) 70%, var(--color-bg-black) 100%);
}}
.content {{
  position: absolute;
  left: var(--spacing-edge-margin);
  right: var(--spacing-edge-margin);
  bottom: 180px;
  color: var(--color-text-white);
}}
.subheading {{
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-subheadline);
  line-height: var(--line-height-snug);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-accent-yellow);
  margin-bottom: 24px;
  text-transform: uppercase;
}}
.heading {{
  font-weight: var(--font-weight-extrabold);
  font-size: var(--font-size-headline-cover);
  line-height: var(--line-height-tight);
  letter-spacing: var(--letter-spacing-title);
  color: var(--color-text-white);
  text-transform: uppercase;
}}
</style></head>
<body>
  <div class="hero" data-zone-type="hero-photo"></div>
  <div class="gradient" data-zone-type="overlay"></div>
  <div class="content" data-zone-type="text">
    <div class="subheading">{TEST_SLIDE["subheading"]}</div>
    <div class="heading">{TEST_SLIDE["heading"]}</div>
  </div>
  <div class="logo" data-zone-type="logo">3 ALI ZERO</div>
</body></html>"""

    html_path = OUT_DIR / "smoke-cover.html"
    html_path.write_text(html)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page = await ctx.new_page()

        await page.goto(f"file://{html_path}")

        # Wait for Montserrat to load — addresses Gemini FLAW HIGH (font race)
        await page.evaluate("() => document.fonts.ready")
        # Extra safety: ensure Montserrat is resolved
        montserrat_loaded = await page.evaluate("""
          () => {
            return Array.from(document.fonts).some(
              f => f.family.toLowerCase().includes('montserrat') && f.status === 'loaded'
            );
          }
        """)

        # Read computed styles to verify token substitution worked
        heading_styles = await page.evaluate("""
          () => {
            const el = document.querySelector('.heading');
            const cs = getComputedStyle(el);
            return {
              fontFamily: cs.fontFamily,
              fontSize: cs.fontSize,
              fontWeight: cs.fontWeight,
              color: cs.color,
              letterSpacing: cs.letterSpacing,
              textTransform: cs.textTransform,
            };
          }
        """)

        subheading_styles = await page.evaluate("""
          () => {
            const el = document.querySelector('.subheading');
            const cs = getComputedStyle(el);
            return { color: cs.color, fontSize: cs.fontSize };
          }
        """)

        logo_styles = await page.evaluate("""
          () => {
            const el = document.querySelector('.logo');
            const cs = getComputedStyle(el);
            return { backgroundColor: cs.backgroundColor };
          }
        """)

        # Body bg should be antracite (text panel)
        body_bg = await page.evaluate("() => getComputedStyle(document.body).backgroundColor")

        # Take screenshot
        png_path = OUT_DIR / "smoke-cover.png"
        await page.screenshot(path=str(png_path), full_page=False, omit_background=False)

        await browser.close()

    # Verify PNG dimensions
    from PIL import Image
    img = Image.open(png_path)
    dim_ok = img.size == (1080, 1350)

    # Region-aware palette check on logo zone (red = #C8102E ≈ rgb(200,16,46))
    # Logo is centered bottom ~y=1240; sample 5x5 grid centered (540,1240)
    logo_red_hits = 0
    for dy in range(-15, 16, 5):
        for dx in range(-15, 16, 5):
            r, g, b = img.getpixel((540 + dx, 1240 + dy))[:3]
            if abs(r - 0xC8) < 15 and abs(g - 0x10) < 30 and abs(b - 0x2E) < 30:
                logo_red_hits += 1
    logo_red_ok = logo_red_hits >= 5  # at least 5/49 grid pixels match

    # Subheading yellow: scan bottom half for yellow pixels (count)
    yellow_count = 0
    for y in range(800, 1200):
        for x in range(60, 1020):
            r, g, b = img.getpixel((x, y))[:3]
            if r > 200 and g > 160 and b < 80 and r > g:
                yellow_count += 1
    yellow_present = yellow_count > 500  # subheading text spans hundreds of pixels

    report = {
        "html_path": str(html_path),
        "png_path": str(png_path),
        "montserrat_loaded": montserrat_loaded,
        "heading_styles": heading_styles,
        "subheading_styles": subheading_styles,
        "logo_styles": logo_styles,
        "body_bg": body_bg,
        "png_dimensions_ok": dim_ok,
        "png_actual_size": img.size,
        "logo_red_pixel_check": logo_red_ok,
        "logo_red_hits_in_grid": logo_red_hits,
        "subheading_yellow_pixel_check": yellow_present,
        "yellow_pixel_count": yellow_count,
    }

    # Hex leak check on layout files (all should reference var(--*) not hex codes)
    hex_pattern = re.compile(r"#[0-9A-Fa-f]{3,6}\b")
    layouts_dir = SKILL_DIR / "layouts"
    leaks = {}
    for layout_md in layouts_dir.glob("*.md"):
        content = layout_md.read_text()
        # Strip code-fence regions for image URLs (background-image url(...))
        # Find hex codes outside _base.css :root context
        matches = hex_pattern.findall(content)
        leaks[layout_md.name] = matches
    report["hex_leaks_in_layouts"] = leaks

    # Hex check on _base.css — these are ALLOWED (canonical token vars)
    base_css_hex = hex_pattern.findall(base_css)
    report["base_css_hex_codes"] = base_css_hex
    report["base_css_hex_codes_unexpected"] = [
        h for h in base_css_hex if h.upper() not in {a.upper() for a in ALLOWED_HEX_IN_CSS}
    ]

    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    result = asyncio.run(render_smoke())
    # Exit code: 0 if smoke passes, 1 if any check failed
    failed = (
        not result["montserrat_loaded"]
        or not result["png_dimensions_ok"]
        or not result["logo_red_pixel_check"]
        or not result["subheading_yellow_pixel_check"]
        or any(result["hex_leaks_in_layouts"].values())
        or result["base_css_hex_codes_unexpected"]
    )
    sys.exit(1 if failed else 0)
