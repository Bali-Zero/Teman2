#!/usr/bin/env python3
"""Generate Bali Zero branded cover cards for immigration articles.

WHY THIS EXISTS
---------------
Thirteen published immigration articles shared ONE byte-identical cover image,
and that image is not a photo — it is a branded card with a title printed on
it reading "Investor KITAS (E28A)". So the retirement-visa article, the
student-visa article and eleven others each opened with a card announcing a
different product. (The E28A article itself did not even use it; it carries a
generic flag photo shared with sixteen other pieces.)

A generic photo that says nothing is merely weak. A titled card that names the
wrong visa is a false statement in the most prominent position on the page, so
these thirteen needed real covers, not a re-point to another stock image.

WHAT IS ACTUALLY LIVE (probed against balizero.com, 2026-07-26)
--------------------------------------------------------------
Of the thirteen paths, EIGHT are the cover their article really serves, and
all eight were serving the E28A card in production at the time of writing:
second-home-visa-indonesia, e31-student-visa-indonesia, au-pair-visa-indonesia,
golden-visa-case-studies-indonesia, golden-visa-investment-vehicles,
visa-agent-vs-diy-indonesia, immigration-fines-penalties-complete,
indonesia-visa-timeline-comparison.

The other five are LATENT, not live: retirement-visa-indonesia,
shareholder-kitas-requirements and director-vs-employee-kitas each serve an
on-topic photo under a different filename (retirement.jpg, shareholder.jpg,
director-employee.jpg), and golden-visa-2026-updates and
immigration-lounge-bali-malls-2026 serve no insights cover at all. Their
slug-named files still HELD the wrong card, though, so they are regenerated
too: a one-line frontmatter change would otherwise arm a landmine that is
already loaded. Replacing them costs nothing and removes that.

DESIGN
------
Matches the existing card exactly — same geometry, same brand tokens from
`skills/bali-zero-brand/tokens.json`:

    accent.yellow #F4C430   rule, kicker, wordmark, dots
    text.white    #FFFFFF   title
    text.muted    #9CA3AF   domain
    bg.black      #000000   gradient floor

Deterministic: same input always renders the same bytes, so a re-run is a
no-op in git rather than 13 spurious diffs.

USAGE
-----
    python scripts/generate_insight_cover_cards.py            # write files
    python scripts/generate_insight_cover_cards.py --check    # verify only
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ── Brand tokens (skills/bali-zero-brand/tokens.json) ─────────────────────────

YELLOW = (244, 196, 48)
WHITE = (255, 255, 255)
MUTED = (156, 163, 175)

# Gradient endpoints of the existing card: warm amber-brown down to near-black.
GRAD_TOP = (122, 84, 16)
GRAD_BOTTOM = (18, 18, 28)

WIDTH, HEIGHT = 1200, 630
MARGIN = 60
RULE_W = 10  # left gold rule

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

# The font the committed cards were actually rendered with.
#
# Font choice changes the output BYTES — measured, not assumed: the same card
# rendered with Helvetica hashes 087a2b8c…, with Arial b01a857c…. So "the
# generator is deterministic" is only true relative to a font, and on a Linux
# CI runner (no Helvetica) a re-render legitimately differs from what is on
# disk. Tests that re-render compare against this and SKIP with a stated reason
# rather than failing for a difference that is not a defect.
GENERATION_FONT = "/System/Library/Fonts/Helvetica.ttc"


@dataclass(frozen=True)
class Card:
    """One cover. `kicker` is the section eyebrow, `title` the display name.

    Titles are hand-written, not derived from the SEO `title:` frontmatter.
    An SEO title ("Second Home Visa Indonesia 2026: Complete Guide to the
    5-Year Stay Permit") truncated to fit produces a card that reads like a
    broken sentence; the card wants the product name, which is what the
    original E28A card did.
    """

    slug: str
    kicker: str
    title: str


CARDS: tuple[Card, ...] = (
    Card("second-home-visa-indonesia", "Indonesia Residence Visa", "Second Home Visa (E33)"),
    Card("retirement-visa-indonesia", "Indonesia Retirement Visa", "Retirement KITAS (E33E / E33F)"),
    Card("e31-student-visa-indonesia", "Indonesia Study Permit", "Student KITAS (E31)"),
    Card("au-pair-visa-indonesia", "Indonesia Immigration", "The Au Pair Visa Myth"),
    Card("golden-visa-2026-updates", "Indonesia Golden Visa", "Golden Visa: One Year On"),
    Card("golden-visa-case-studies-indonesia", "Indonesia Golden Visa", "Golden Visa Case Studies"),
    Card(
        "golden-visa-investment-vehicles",
        "Indonesia Golden Visa",
        "Golden Visa Investment Vehicles",
    ),
    Card("shareholder-kitas-requirements", "Indonesia Investment Visa", "Shareholder KITAS"),
    Card("director-vs-employee-kitas", "Indonesia Work Permit", "Director vs Employee KITAS"),
    Card("visa-agent-vs-diy-indonesia", "Indonesia Immigration", "Visa Agent or DIY?"),
    Card(
        "immigration-fines-penalties-complete",
        "Indonesia Immigration",
        "Fines, Overstay & Penalties",
    ),
    Card(
        "immigration-lounge-bali-malls-2026",
        "Bali Immigration Services",
        "Immigration Lounges in Bali Malls",
    ),
    Card(
        "indonesia-visa-timeline-comparison",
        "Indonesia Visa Processing",
        "Visa Timelines Compared",
    ),
)

OUT_DIR = Path("apps/mouth/public/static/insights/immigration")


def resolved_font_path() -> str:
    """The font this machine will actually render with.

    First candidate that both exists AND opens. `_font()` is defined in terms of
    this rather than repeating the loop: if the two could disagree, the tests'
    font guard would report one font while the renderer used another, and skip
    or run on a false premise.
    """
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                ImageFont.truetype(path, 12)
            except OSError:
                continue
            return path
    raise RuntimeError(
        f"no usable font among {_FONT_CANDIDATES} — refusing to render with a "
        "bitmap fallback, which would look nothing like the brand card"
    )


def _font(size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(resolved_font_path(), size, index=index)


def _gradient() -> Image.Image:
    """Vertical amber→near-black gradient, drawn per row."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        # ease-in so the warm band stays in the top third, as on the original
        t = t**0.75
        draw.line(
            [(0, y), (WIDTH, y)],
            fill=tuple(
                round(a + (b - a) * t) for a, b in zip(GRAD_TOP, GRAD_BOTTOM, strict=True)
            ),
        )
    return img


def _glow(img: Image.Image) -> Image.Image:
    """Soft amber bloom in the top-left, added (not blended) so the gradient
    underneath keeps its depth instead of being washed toward the overlay."""
    cx, cy, radius = 150, 60, 260
    overlay = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    steps = 44
    for i in range(steps, 0, -1):
        r = radius * i / steps
        a = 0.16 * (1 - i / steps) ** 2
        odraw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(round(255 * a), round(190 * a), round(60 * a)),
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(28))
    return ImageChops.add(img, overlay)


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int
) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    tracking: float,
) -> None:
    """Letter-spaced text — Pillow has no tracking, so step per glyph."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def render(card: Card) -> Image.Image:
    img = _glow(_gradient())
    draw = ImageDraw.Draw(img)

    # left gold rule
    draw.rectangle([0, 0, RULE_W - 1, HEIGHT], fill=YELLOW)

    f_mark = _font(21)
    f_kicker = _font(23)
    f_title = _font(64)
    f_url = _font(20)

    # wordmark, top right
    mark = "BALI ZERO"
    mark_w = sum(draw.textlength(c, font=f_mark) + 3.5 for c in mark) - 3.5
    _tracked(draw, (WIDTH - MARGIN - round(mark_w), 36), mark, f_mark, YELLOW, 3.5)

    # title block, wrapped, bottom-anchored so 1- and 2-line cards sit alike
    lines = _wrap(draw, card.title, f_title, WIDTH - 2 * MARGIN - 40)
    line_h = 78
    block_h = len(lines) * line_h
    title_top = 250 - (block_h - line_h) // 2

    _tracked(draw, (MARGIN, title_top - 56), card.kicker.upper(), f_kicker, YELLOW, 2.4)

    y = title_top
    for line in lines:
        draw.text((MARGIN - 2, y), line, font=f_title, fill=WHITE)
        y += line_h

    # three dots
    dot_y = y + 26
    for i in range(3):
        x = MARGIN + i * 24
        draw.ellipse([x, dot_y, x + 11, dot_y + 11], fill=YELLOW)

    draw.text((MARGIN, HEIGHT - MARGIN - 22), "zantara.balizero.com", font=f_url, fill=MUTED)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify files exist; write nothing")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    out = root / OUT_DIR
    if not out.is_dir():
        print(f"ERROR: {out} does not exist", file=sys.stderr)
        return 2

    missing = 0
    for card in CARDS:
        dest = out / f"{card.slug}.jpg"
        if args.check:
            if not dest.is_file():
                print(f"MISSING {dest.name}")
                missing += 1
            continue
        render(card).save(dest, "JPEG", quality=88, optimize=True)
        print(f"wrote {dest.name:44} {card.title}")

    if args.check:
        print(f"{len(CARDS) - missing}/{len(CARDS)} present")
        return 1 if missing else 0

    print(f"\n{len(CARDS)} cards written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
