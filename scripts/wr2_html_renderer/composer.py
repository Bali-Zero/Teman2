"""WR2 carousel composer: war_room_drafts slides_json → per-slide HTML → render.

This is Phase 2. It turns a real draft (the slides_json the live
wr2_draft_generator writes) into a fully rendered carousel by:

  1. Mapping each slide to a brand layout family (slides_json carries no
     `layout` field — gap #2 from GROUND — so we derive it from slide_type /
     is_cover / is_hero_image / position).
  2. Loading that family's HTML/CSS skeleton from
     `~/.claude/skills/bali-zero-brand/layouts/<family>.md` and filling its
     {{placeholders}} + {{#if}} / {{#each}} blocks.
  3. Normalizing the skeleton for the local renderer:
       - strip the Google-Fonts `@import` (we vendor fonts locally — _fonts.css)
       - rewrite the hero from CSS `background-image:url(...)` to a real `<img>`
         so the renderer's `img.decode()` gate can verify placement (the exact
         thing the Canva path failed at). The `data-zone-type="hero-photo"` and
         the gradient overlay are preserved.
       - point `_base.css` href at the co-located generated file.
  4. Downloading each hero's Tigris URL into the slides dir (so file:// sees it).
  5. Rendering via renderer.render_html_files with per-slide expect_hero, which
     ENFORCES heroes_placed == heroes_expected before calling it rendered.

It does NOT write to any DB and does NOT touch the live pipeline. Output is a
directory of PNGs + carousel.pdf + a manifest.json. Wiring to war_room_drafts
is Phase 3 (gated by the 4-LLM panel).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from dataclasses import dataclass
from html import escape as _html_escape
from pathlib import Path
from typing import Any

from .renderer import RenderResult, _stage_assets, render_html_files

logger = logging.getLogger("wr2.composer")

_BRAND = Path.home() / ".claude" / "skills" / "bali-zero-brand"
_LAYOUTS = _BRAND / "layouts"

# The layout families that have real HTML/CSS skeletons (GROUND phase verified).
# `editorial-text` added 2026-06-13: a text-only prose family for non-hero slides
# (smart-hero decision) — full antracite canvas, no photo, heading+sub+body.
RENDERABLE_FAMILIES = {
    "cover-photo",
    "photo-headline-yellow-sub",
    "photo-fullbleed",
    "photo-fullbleed-top",
    "photo-fullbleed-split",
    "editorial-text",
    "qa-dialogue",
    "timeline-pinboard",
    "dark-status-list",
    "evidence-carved",
    "statement-bomb",
    "elegant-close",
    "source-citation",
}

# Families named in tokens.json layout_defaults but with NO skeleton yet
# (GROUND gap #1). The composer must NEVER silently emit one of these — it would
# produce a blank/broken slide. If a mapping would pick one, fall back + warn.
UNDEFINED_FAMILIES = {
    "swiss-grid-asymmetry",
    "stat-card-hero",
    "thin-red-rule-divider",
    "monospace-evidence-block",
    "three-verdicts",
}


# B1 (micro, deterministic composition swap — 2026-07-02):
# statement-bomb is a 3-15-word punch layout. A CTA/statement/closing-typed MID
# slide whose body exceeds this budget crams the same way the "35-word take" did
# (E2E 2026-06-13, see map_slide_to_family). B1 catches that pre-render — a
# deterministic swap to editorial-text (which reads a long prose body cleanly) —
# so the scarred designer_loop taxonomy (W82) never has to salvage a crammed
# statement-bomb with font-shrink whack-a-mole. Budget is generous (the layout
# tolerates a short 2-line statement) so the swap only fires on real overflow.
_STATEMENT_BOMB_MAX_WORDS = 18


def _slide_body_word_count(slide: dict[str, Any]) -> int:
    """Words in the text a statement-bomb would actually render (statement/headline/body,
    same precedence as the {{statement}} fill at composition time)."""
    text = (slide.get("statement") or slide.get("headline") or slide.get("body") or "")
    return len(str(text).split())


@dataclass
class SlidePlan:
    index: int  # 1-based
    family: str
    slide: dict[str, Any]
    expect_hero: bool


def map_slide_to_family(slide: dict[str, Any], index: int, total: int) -> str:
    """Derive a brand layout family from a slides_json slide.

    slides_json fields (from wr2_draft_generator normalizer):
      slide_number, slide_type, is_cover, is_hero_image, headline, subhead,
      body, image_prompt, image_url.

    Mapping rules (smart-hero, 2026-06-13 — only RENDERABLE families):
      - slide 1 / is_cover            -> cover-photo            (Art 9.3 hard rule)
      - last slide / cta/closing/stmt -> statement-bomb         (Art 9.5 hard rule)
      - is_hero_image (mid)           -> photo-headline-yellow-sub (hero photo + text)
      - non-hero "take"               -> statement-bomb         (punchy text-only)
      - non-hero default              -> editorial-text         (text-only prose)

    A NON-hero slide NEVER routes to photo-headline-yellow-sub: that layout has a
    full-bleed hero photo, so an empty/missing image would leave a visual void
    (the "void-trap"). Non-hero slides go to a TEXT-ONLY family instead.

    We deliberately do NOT auto-route to dark-status-list / evidence-carved /
    source-citation: those need structured items/facts/citations the generator
    does not produce, so a blind mapping would break their fill.

    Returns a family in RENDERABLE_FAMILIES. Never returns an UNDEFINED one.
    """
    # Per-slide explicit override (manual full-bleed-photo carousels, 2026-06-13):
    # a slides.json may pin `layout_family` directly to opt a slide into a
    # specific renderable family (e.g. "photo-fullbleed" for the foto-a-tutta-slide
    # treatment). Honoured ONLY when it names a RENDERABLE family — a typo or an
    # UNDEFINED value falls through to auto-routing so we never emit a blank
    # skeleton. This intentionally lets a manual author bypass the Art 9.3/9.5
    # cover/CTA hard rules for a fully-photographic carousel.
    explicit = (slide.get("layout_family") or "").strip()
    if explicit in RENDERABLE_FAMILIES:
        return explicit
    if index == 1 or slide.get("is_cover"):
        return "cover-photo"
    st = (slide.get("slide_type") or "").lower()
    if index == total or st in {"cta", "closing", "statement"}:
        # B1 deterministic composition swap: a MID CTA/statement slide whose body
        # overflows the statement-bomb budget goes to editorial-text instead of
        # cramming. The TRUE last slide (index == total) is ALWAYS statement-bomb
        # — Art 9.5 hard rule (statement-bomb closer). Over-length there is the
        # drafter's job (A4 closer-guard regen), NOT a layout swap: swapping the
        # closer would break the constitution's mandatory closing statement-bomb.
        if index != total and _slide_body_word_count(slide) > _STATEMENT_BOMB_MAX_WORDS:
            logger.info(
                "B1 composition swap: slide %d/%d (type=%s, %d words) "
                "statement-bomb -> editorial-text (over %d-word budget)",
                index, total, st or "?", _slide_body_word_count(slide),
                _STATEMENT_BOMB_MAX_WORDS,
            )
            return "editorial-text"
        return "statement-bomb"
    if slide.get("is_hero_image"):
        return "photo-headline-yellow-sub"
    # non-hero: route to a TEXT-ONLY family (never the photo layout with an empty
    # image → void-trap). All non-hero prose — including an editorial "take" —
    # goes to editorial-text: statement-bomb is for a 3-15 word punch, NOT a
    # 35-word take (E2E 2026-06-13: a take routed to statement-bomb crammed; on
    # editorial-text the same copy reads cleanly, like the other prose slides).
    return "editorial-text"  # text-only prose family


def _extract_skeleton(family: str) -> str:
    """Pull the HTML skeleton out of a layout family .md file (first ```html block)."""
    md_path = _LAYOUTS / f"{family}.md"
    if not md_path.is_file():
        raise FileNotFoundError(f"layout family not found: {md_path}")
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"```html\s*(.*?)```", text, re.DOTALL)
    if not m:
        raise ValueError(f"no ```html block in {md_path}")
    return m.group(1).strip()


def _normalize_skeleton(html: str) -> str:
    """Make a brand skeleton renderer-ready.

    - strip Google-Fonts @import (fonts vendored locally via _fonts.css)
    - inject <link _fonts.css> in <head>
    - rewrite _base.css href ../_base.css -> _base.css (co-located)
    """
    # strip @import url('...fonts.googleapis...');
    html = re.sub(r"@import\s+url\(['\"]https://fonts\.googleapis[^)]*\)\s*;", "", html)
    # point base css to co-located file
    html = html.replace('href="../_base.css"', 'href="_base.css"')
    html = html.replace("href='../_base.css'", "href='_base.css'")
    html = html.replace('href="./_base.css"', 'href="_base.css"')
    # inject _fonts.css link right after the _base.css link (or in head)
    if "_fonts.css" not in html:
        if 'href="_base.css"' in html:
            html = html.replace(
                'href="_base.css">',
                'href="_base.css">\n<link rel="stylesheet" href="_fonts.css">',
                1,
            )
        else:
            html = html.replace("<head>", '<head>\n<link rel="stylesheet" href="_fonts.css">', 1)
    return html


def _hero_bg_to_img(html: str, hero_filename: str) -> str:
    """Rewrite a CSS background-image hero into a real <img> for decode-gating.

    The brand cover/photo skeletons render the hero as:
        <div class="hero" ...></div>   with CSS .hero{background-image:url('{{image_url}}')}

    The fix (verified against the cover-photo bug 2026-06-07 where a separate
    <img> got covered by the .hero div's background-color): we CONVERT the .hero
    div ITSELF into an <img class="hero"> in place — same element, same position,
    same stacking — rather than adding a second overlapping element. We:
      1. turn the `.hero` CSS rule into an image-styled rule (object-fit:cover,
         drop the now-useless background-image; keep position/inset so it sits
         exactly where the div sat),
      2. replace the empty `<div class="hero" ...></div>` with
         `<img class="hero" src="hero.jpg" ...>` so img.decode() applies to the
         actual hero element and nothing paints over it.

    If the skeleton has NO `<div class="hero">` (some layouts use a different
    hero container), we fall back to injecting a positioned <img> after <body>.
    """
    # 1. In the .hero CSS rule, drop the background-image:url('{{image_url}}')
    #    (the div becomes an <img>, so background-image is irrelevant) and ensure
    #    object-fit:cover is present so the image fills like background-size:cover.
    html = re.sub(
        r"background-image:\s*url\(['\"]?\{\{image_url\}\}['\"]?\)\s*;?",
        "object-fit: cover;",
        html,
    )

    # 2. Convert <div class="hero" ...></div> → <img class="hero" src=... >.
    div_pattern = re.compile(r'<div\s+class="hero"([^>]*)>\s*</div>')
    if div_pattern.search(html):
        html = div_pattern.sub(
            lambda m: f'<img class="hero" src="{hero_filename}"{m.group(1)}>',
            html,
            count=1,
        )
        return html

    # Fallback: no <div class="hero"> — inject a positioned <img> after <body>.
    # The image must NOT paint OVER the slide text (statement-bomb etc.): the
    # existing content is raised above the img (z-index:1) and a legibility
    # scrim (.hero-scrim) sits between image and text.
    hero_img_css = (
        "\n.hero-img{position:absolute;inset:0;width:100%;height:100%;"
        "object-fit:cover;z-index:0;}\n"
        ".hero-scrim{position:absolute;inset:0;"
        "background:rgba(10,10,10,0.55);z-index:0;}\n"
        # :where(...) wraps the WHOLE selector so it carries 0 specificity and
        # NEVER overrides a child's own `position` declaration (e.g.
        # evidence-carved's `.content{position:absolute;left:...;right:...}`,
        # which sets the slide's text-box width). Before this fix, the blanket
        # `position:relative` here beat `.content`'s `position:absolute` on
        # specificity+cascade order, silently dropping the left/right width
        # constraint and letting long fact/body text overflow off-canvas
        # (found 2026-07-11, evidence-carved slide overflow). NOTE: :where(*)
        # alone (zeroing only the `*`) does NOT work — the :not() clauses
        # outside :where() still count; the fix is to wrap the entire
        # selector, verified via Playwright computed-style probe.
        ":where(body > *:not(.hero-img):not(.hero-scrim)){position:relative;z-index:1;}\n"
    )
    html = html.replace("</style>", hero_img_css + "</style>", 1)
    img_tag = (
        f'<img class="hero-img" src="{hero_filename}" alt="" data-zone-type="hero-photo">'
        '<div class="hero-scrim"></div>'
    )
    html = re.sub(r"(<body[^>]*>)", r"\1\n  " + img_tag, html, count=1)
    return html


# Lever → CSS. The designer loop accumulates levers in slide["_levers"]; this
# turns them into a small <style> block appended last so it overrides the
# skeleton. Kept INTENTIONALLY narrow + brand-safe: a darkening scrim, a text
# outline, and a font down-step. These can NOT change palette / font-family /
# add colors / reposition blocks — so a lever can never drift the brand NOR
# break the template's composition (the autonomy guardrail is structural).
#
# REMOVED 2026-06-07 after E2E: `text_anchor` (absolute-repositioning the text
# block to a "calm band"). On the cover layout it fought the template, jammed the
# title against the top edge (clipped, overlapping the wordmark) and the cheap
# legibility score then read a FALSE-HIGH 0.924 because it measured the now-empty
# bottom box. Repositioning is a COMPOSITION decision (which layout family) — not
# a safe runtime CSS override. The remaining levers only ever IMPROVE legibility
# in place; none can move or clip text.


# grow_font clamps: (legible-min px, anti-overflow-cap px) per element on the
# 1080x1350 render canvas. Declared + parametrizable — the final judge is the
# vision critic in the E2E (it asks for a thumbnail-legible sub-headline).
#
# Sizing rationale (pixel-measured 2026-06-10): an IG thumbnail is ~150px wide,
# so the canvas (1080px) downscales ~7.2x. The _base.css bases are subhead 36px,
# body 28-32px, headline 60-84px — at thumbnail the subhead collapses to ~5px,
# unreadable. The vision critic asks for ~18-22px-equivalent at thumbnail
# ("collapses to ~7px tall, unreadable … increase to ~20-22px"), i.e. ~130-160px
# absolute on the canvas. Floors are set to clear ~17px-at-thumbnail and the cap
# to ~22px-at-thumbnail. Every MIN is ABOVE the element's own 1em base so the
# progressive step (below) is never pinned by the floor (the old (52,64) bug).
#
# BUG #2 (hierarchy inversion, pixel-measured 2026-06-10): a sub-headline grown
# to a 120-160px "thumbnail-legible" size is LARGER than the 84px cover title
# (--font-size-headline-cover) → the kicker dominates the title (the vision
# correctly rejects "HIERARCHY INVERSION — the date dominates"). The kicker is an
# accessory tag/category by the template contract; it must stay subordinate to
# the title. So the sub-headline grow is now CAPPED relative to the title
# (max = title * _SUBHEAD_MAX_FRACTION_OF_TITLE), NOT at a thumbnail-legible
# floor. If the cover title itself reads too small at thumbnail, the right fix is
# to grow the TITLE (grow_font target=heading), whose clamp stays the largest.
_HEADING_BASE_PX = 84  # --font-size-headline-cover in the brand _base.css
_SUBHEAD_MAX_FRACTION_OF_TITLE = 0.55  # kicker stays <= ~55% of the title size
_GROW_CLAMP_PX = {
    # subhead capped under the title: (40, 46) with 46 = round(84 * 0.55) < 84.
    "subhead": (40, round(_HEADING_BASE_PX * _SUBHEAD_MAX_FRACTION_OF_TITLE)),
    "body": (104, 140),     # ~14.4px..19px at thumbnail (base 28-32px)
    "heading": (100, 150),  # title grows ABOVE its 84px base, stays the largest
}
# Per grow step the target steps up FROM the legible floor (not from 1em). Each
# step adds this fraction of the floor; min() with the cap guards overflow.
_GROW_STEP = 0.15


def _levers_to_css(levers: dict[str, Any]) -> str:
    """Build a brand-safe, composition-safe <style> override block from levers.

    Targets common brand text containers (.body, .subhead, .headline, .text,
    [data-zone-type='text']) and the scrim layer. Selectors are defensive
    (multiple class names) because skeletons differ; an unused selector is inert.
    Only legibility-in-place knobs — never position/size-of-box/color/font.
    """
    if not levers:
        return ""
    rules: list[str] = []

    # scrim_opacity: darken behind the text. The renderable families place the
    # hero as an absolutely-positioned element at z-index 0 and a .gradient/
    # .content stack above it. We STRENGTHEN the existing .gradient overlay in
    # place — we do NOT add a new positioned layer and we NEVER touch `position`
    # on any text element (E2E 2026-06-07: setting position:relative on the
    # [data-zone-type='text'] container — which matches the cover's absolutely-
    # positioned `.content` — knocked it out of its bottom anchor and slammed the
    # title to the top edge, clipped. The scrim must be positioning-inert.)
    scrim = levers.get("scrim_opacity")
    if scrim is not None:
        a = max(0.0, min(0.95, float(scrim)))
        # Deepen the brand gradient overlay (.gradient / .legibility-armor /
        # .scrim / .overlay) — these are already correctly positioned by the
        # skeleton; we only change their paint, not their box.
        rules.append(
            ".gradient,.legibility-armor,.scrim,.overlay,[data-zone-type='overlay']{"
            f"background:linear-gradient(180deg, rgba(0,0,0,0.0) 30%, rgba(13,13,13,{a:.2f}) 70%, rgba(13,13,13,{min(0.98, a + 0.1):.2f}) 100%) !important;"
            "}"
        )

    # text_stroke: stronger outline for crispness over residual highlights.
    # Paint-only (text-shadow + webkit stroke) — does NOT touch position/layout.
    if levers.get("text_stroke"):
        rules.append(
            ".headline,.heading,.subhead,.subheading,.body,.text,"
            ".cover-text,.slide-text,h1{"
            "text-shadow:0 1px 3px rgba(0,0,0,0.85),0 0 1px rgba(0,0,0,0.9);"
            "paint-order:stroke fill;-webkit-text-stroke:0.4px rgba(0,0,0,0.55);"
            "}"
        )

    # shrink_font: down-step a too-dense element. Each accumulated step = -8%.
    for elem in ("body", "heading", "subhead"):
        steps = levers.get(f"shrink_{elem}", 0)
        if steps:
            factor = max(0.6, 1.0 - 0.08 * int(steps))
            sel = {
                "body": ".body,.text,[data-zone-type='text']",
                "heading": ".headline,.heading,h1",
                "subhead": ".subhead,.subheading",
            }[elem]
            rules.append(f"{sel}{{font-size:calc(1em * {factor:.2f});line-height:1.25;}}")

    # grow_font: symmetric to shrink_font. Step UP a too-small element toward a
    # thumbnail-legible minimum. We clamp(min_legible, grown, cap): the MIN floor
    # guarantees one grow lever already clears the legibility threshold, the cap
    # prevents a long element from overflowing its box. Paint/size-only on the
    # text — never palette/font-family/position.
    for elem in ("subhead", "body", "heading"):
        steps = levers.get(f"grow_{elem}", 0)
        if steps:
            min_px, cap_px = _GROW_CLAMP_PX[elem]
            # progress FROM the legible floor: step 1 == floor, each extra step
            # adds _GROW_STEP*floor; the cap (min) guards overflow. Absolute px
            # (NOT calc(1em*…)) so it never gets pinned by a floor above 1em.
            target_px = min(cap_px, round(min_px * (1.0 + _GROW_STEP * (int(steps) - 1))))
            sel = {
                "body": ".body,.text,[data-zone-type='text']",
                "heading": ".headline,.heading,h1",
                "subhead": ".subhead,.subheading",
            }[elem]
            rules.append(
                f"{sel}{{font-size:{target_px}px !important;line-height:1.15;}}"
            )

    # rebalance_wrap: the headline already carries explicit <br>s placed by
    # _balance_headline (each line capped to a safe width). Make the browser
    # HONOR them — text-wrap:balance keeps lines tidy, overflow-wrap:normal +
    # white-space:normal stop it from breaking words or collapsing/ignoring the
    # <br>s. Flow-only on the headline text; never position/color/font-family.
    if levers.get("_rebalance_wrap"):
        rules.append(
            ".headline,.heading,.statement,.cover-text,.slide-text,h1{"
            "text-wrap:balance;overflow-wrap:normal;white-space:normal;"
            "word-break:keep-all;"
            "}"
        )

    # NOTE: text_anchor_band is intentionally NOT honored here (see module note).

    if not rules:
        return ""
    return "\n<style data-levers=\"1\">\n" + "\n".join(rules) + "\n</style>\n"


def _apply_levers_to_html(html: str, slide: dict[str, Any]) -> str:
    """Append the lever override <style> just before </head> (or </body>)."""
    css = _levers_to_css(slide.get("_levers") or {})
    if not css:
        return html
    if "</head>" in html:
        return html.replace("</head>", css + "</head>", 1)
    if "</body>" in html:
        return html.replace("</body>", css + "</body>", 1)
    return html + css


# Default safe line width for the big cover headline. The cover heading uses
# var(--font-size-headline-cover) (84px on the 1080px canvas): ~22 chars is the
# single-line capacity at that size AND it matches what the Claude vision critic
# asks for — it judges 2 balanced lines as better than 3 lines with a short tail
# (the iter-2/3 "THE TOP sits alone on line 3" critique fired at the old cap=16,
# which over-wrapped into 3 lines with a 2-word tail). 22 lets the greedy wrap
# settle on those 2 even lines. Parametrizable so a smaller headline font can
# pass a larger budget.
# Per-character advance width, in ems, for UPPERCASE Montserrat-bold (the cover
# .heading is text-transform:uppercase, font-weight:800). MEASURED empirically
# (playwright, getBoundingClientRect at 84px, staged brand _fonts.css) — the
# sum-of-chars estimate reproduces real rendered string widths to within ~0.7%.
# This is the font-aware width model (approach (a)) used by _balance_headline to
# wrap by RENDERED PIXEL WIDTH, not by character count (the char-count model
# over-/under-shot because W/M are ~3x wider than I, so an 18-char "INDONESIA
# VISA FEE" is 937px while an 18-char all-I string would be ~half that).
_UPPER_EM_WIDTH = {
    "A": 0.786, "B": 0.769, "C": 0.730, "D": 0.826, "E": 0.672, "F": 0.642,
    "G": 0.770, "H": 0.806, "I": 0.339, "J": 0.557, "K": 0.752, "L": 0.610,
    "M": 0.954, "N": 0.806, "O": 0.846, "P": 0.737, "Q": 0.846, "R": 0.740,
    "S": 0.647, "T": 0.635, "U": 0.786, "V": 0.766, "W": 1.184, "X": 0.737,
    "Y": 0.693, "Z": 0.679,
    "0": 0.685, "1": 0.405, "2": 0.599, "3": 0.603, "4": 0.700, "5": 0.607,
    "6": 0.649, "7": 0.632, "8": 0.669, "9": 0.649,
    " ": 0.291, ".": 0.283, ",": 0.283, "-": 0.388, "&": 0.752, "$": 0.647,
    "/": 0.415, "%": 0.897, "+": 0.609, "'": 0.242,
}
_EM_WIDTH_DEFAULT = 0.74  # avg uppercase letter (A-Z mean ≈ 0.74em)

# Cover headline box + font (read from the brand layout, kept parametrizable):
#   --canvas-width 1080px − 2×--spacing-edge-margin 60px = 960px content box
#   --font-size-headline-cover 84px
_COVER_BOX_WIDTH_PX = 960
_COVER_HEADLINE_FONT_PX = 84
# Safety margin: the sum-of-chars estimate slightly OVER-estimates (ignores
# negative kerning), which is the safe direction; this extra haircut leaves
# headroom so the browser never re-wraps a line we sized to fit.
_WRAP_SAFETY = 0.96
# Back-compat: a coarse char budget kept for callers/tests that referenced it,
# derived from the pixel box (≈ box / avg-char-px). NOT the wrap driver anymore.
_COVER_MAX_CHARS_PER_LINE = int(
    _COVER_BOX_WIDTH_PX / (_COVER_HEADLINE_FONT_PX * _EM_WIDTH_DEFAULT)
)


def _estimate_text_width_px(text: str, font_px: int = _COVER_HEADLINE_FONT_PX) -> float:
    """Estimate the RENDERED width (px) of `text` as UPPERCASE Montserrat-bold at
    `font_px`, via the measured per-character em-width table. Uppercase because
    the cover .heading applies text-transform:uppercase. Accurate to ~1% vs the
    real browser render (see _UPPER_EM_WIDTH provenance).

    Markup-normalized: a literal `&nbsp;` entity counts as ONE space (it renders
    as a single non-breaking space, not 6 visible chars — without this the
    de-orphan glue would inflate the estimate ~40% and mis-trip the fit logic);
    a `<br>` is a zero-width line break and is dropped before measuring (callers
    that care about per-line width split on `<br>` first)."""
    measured = text.replace("&nbsp;", " ").replace("<br>", "")
    return sum(_UPPER_EM_WIDTH.get(c, _EM_WIDTH_DEFAULT) for c in measured.upper()) * font_px


def _balance_headline(
    text: str,
    *,
    box_width_px: int = _COVER_BOX_WIDTH_PX,
    font_px: int = _COVER_HEADLINE_FONT_PX,
    safety: float = _WRAP_SAFETY,
) -> str:
    """Re-wrap a headline into MULTIPLE lines (explicit <br>s) sized by the
    ESTIMATED RENDERED PIXEL WIDTH of each line, so NO line overflows the cover
    box (the browser never gets to re-wrap) and NO line is a single orphan word.

    Root-cause fix (2026-06-10): the previous versions wrapped by CHARACTER COUNT
    (_COVER_MAX_CHARS_PER_LINE). But at 84px uppercase Montserrat-bold, char
    count is a poor proxy for width — "INDONESIA VISA FEE" (18 chars) renders
    937px while the 960px box fits only ~that, and a char-budget of 22 let a
    too-wide line through, which the browser then re-split, RE-creating the
    "TOP"/"FEE" orphans + unexpected 3rd lines. We now greedily fill each line up
    to `box_width_px * safety` measured by `_estimate_text_width_px`.

    Text-only — only inserts <br> between whole words; never splits a word and
    never touches position/color/font/box (so it cannot drift the brand).

    Rules:
      - ≤3 words: leave unchanged (too short to wrap; one line is fine).
      - greedy-fill each line up to the pixel budget (whole words only); a single
        word wider than the budget gets its own line (never split mid-word).
      - if everything fits on one line, leave it flat (no <br>).
      - no single-word orphan line: borrow the previous line's last word when the
        merged line still fits the budget (front-to-back, any line not just last).
      - if the text already contains a <br>, assume it's pre-wrapped → no-op.
    """
    text = text.strip()
    if not text or "<br>" in text.lower():
        return text
    words = text.split()
    if len(words) <= 3:
        return text

    budget_px = max(1.0, float(box_width_px) * float(safety))

    def width(seg: list[str]) -> float:
        return _estimate_text_width_px(" ".join(seg), font_px)

    # Greedy fill by pixel width: add words while the line stays within budget.
    lines: list[list[str]] = []
    cur: list[str] = []
    for w in words:
        if not cur:
            cur = [w]
            continue
        if width(cur + [w]) <= budget_px:
            cur.append(w)
        else:
            lines.append(cur)
            cur = [w]
    if cur:
        lines.append(cur)

    # Everything fit on one line → nothing to wrap.
    if len(lines) <= 1:
        return text

    # Kill ANY single-word orphan line: borrow the PREVIOUS line's last word and
    # prepend it, only when the previous line keeps ≥2 words AND the merged orphan
    # line still fits the pixel budget (never create an over-wide line to fix an
    # orphan; a word with no legal companion is left on its own line). Front-to-
    # back so a fix on line i can still be helped by line i-1.
    for i in range(1, len(lines)):
        while (
            len(lines[i]) == 1
            and len(lines[i - 1]) >= 2
            and width([lines[i - 1][-1]] + lines[i]) <= budget_px
        ):
            lines[i].insert(0, lines[i - 1].pop())

    # Number-orphan pass: a line MUST NOT end on a bare numeral token (e.g. "3",
    # "10") when there is a following line -- the number belongs to the clause
    # that starts the next line ("3 RULES CHANGED" must not be split as "3" /
    # "RULES CHANGED"). Move the trailing numeral DOWN to start the next line,
    # provided the resulting lines still fit the budget. Conservative: only bare
    # integers (digits only, optional trailing period); never creates an over-wide
    # line; never moves if the donor line would lose its last remaining word.
    _bare_numeral_re = re.compile(r"^\d+\.?$")
    for i in range(len(lines) - 1):
        if (
            lines[i]
            and _bare_numeral_re.match(lines[i][-1])
            and len(lines[i]) >= 2  # keep >=1 word on the donor line after moving
            and width([lines[i][-1]] + lines[i + 1]) <= budget_px
        ):
            moved = lines[i].pop()
            lines[i + 1].insert(0, moved)

    return "<br>".join(" ".join(line) for line in lines)


def _emphasize_key_numbers(body: str) -> str:
    """Wrap KEY regulatory numbers in the body in <span class="emphasis"> so they
    render in the brand accent yellow (Article 6.9 anchor-highlight: yellow is the
    family color for verifiable facts — numbers, codes, regulations).

    Why: the Claude vision critic explicitly checks "do key numbers stand out?"
    (claude_vision.py) and was failing fresh drafts on slides where the crux
    number ("183 days", "Day 184") rendered in the same weight/color as the
    surrounding body — a missed-hierarchy reject. Yellowing the number is the
    brand-sanctioned way to make it pop (operator decision 2026-06-24, option C).

    Conservative + deterministic + brand-drift-safe:
      - matches a numeral (optionally with a thousands sep / decimal / %) that is
        either a standalone quantity or immediately followed by a unit noun
        (days, day, months, %, IDR/USD/Rp amounts, year forms) — i.e. the kind of
        number that carries regulatory weight, NOT every stray digit.
      - matches at most the first 2 such numbers per body (avoids a christmas-tree
        of yellow that would itself flatten hierarchy).
      - NEVER touches a body that already contains markup (`<span`, `<`), so it is
        a strict no-op on facts-block / pre-emphasized bodies and cannot produce
        nested or broken spans.
      - operates on the verbatim body BEFORE it is substituted into the skeleton
        (the composer fills via plain .replace, so the literal span renders).
    """
    if not body or "<" in body:
        return body
    # numeral core: 183 | 1,000 | 12.5 | 30% ; optionally a currency prefix or a
    # unit-noun suffix gives it "regulatory" weight worth highlighting.
    num = r"\d[\d,.]*"
    pattern = re.compile(
        r"(?<![\w>])"                                  # not mid-word / not inside a tag
        r"("
        r"(?:(?:Rp|IDR|USD|\$|€|£)\s?" + num + r")"    # currency amounts
        r"|(?:" + num + r"\s?%)"                        # percentages
        r"|(?:" + num + r"\s?(?:days?|months?|years?|hari|bulan|tahun|hours?|jam))"  # durations
        r"|(?:Day\s?" + num + r")"                      # "Day 184"
        r")",
        re.IGNORECASE,
    )
    count = 0

    def _wrap(m: "re.Match[str]") -> str:
        nonlocal count
        if count >= 2:
            return m.group(0)
        count += 1
        return f'<span class="emphasis">{m.group(0)}</span>'

    return pattern.sub(_wrap, body)


def _deorphan_numbers_in_headline(text: str) -> str:
    """ALWAYS-ON, deterministic, PIXEL-INDEPENDENT number-orphan correction.

    Distinct from `_balance_headline` (a FULL pixel-rebalance gated behind the
    designer-loop `_rebalance_wrap` lever): this pass enforces ONLY the safe,
    text-only typographic rule "a bare numeral must never be stranded at a line
    end, split from the noun it quantifies" — the load-bearing "3 RULES CHANGED"
    must never wrap as "...VALID. 3" / "RULES CHANGED".

    It runs ALWAYS at compose time (not gated behind the non-deterministic vision
    critic) and is PIXEL-INDEPENDENT: instead of guessing where the browser will
    wrap (the F10 re-shadow proved our pixel estimate disagrees with the real
    browser wrap, so a pixel-based de-orphan missed the orphan), it GLUES every
    bare numeral to its immediately-following word with a non-breaking space
    (&nbsp;). The browser then physically cannot break between them, so the
    numeral always carries its noun onto whatever line it lands on, regardless of
    box width or font metrics. The composer substitutes the headline via plain
    string .replace (no HTML escaping — see _fill_placeholders), so the literal
    "&nbsp;" entity renders as a real non-breaking space, not as visible text.

    Brand-drift-safe: it ONLY inserts &nbsp; between a numeral and its next word;
    it changes no other spacing, never reorders/drops words, and is a no-op when
    the headline contains no bare-numeral-followed-by-word pattern.

    Handles a headline whether flat or already lever-wrapped (with <br>): the
    glue applies to the textual word sequence either way.
    """
    text = text.strip()
    if not text:
        return text
    # Glue a bare integer (optionally with a trailing period, e.g. "3" / "10")
    # to its IMMEDIATELY FOLLOWING word via &nbsp;. Word boundaries on both sides
    # so we never touch a number embedded in a token (e.g. "IDR3" or "22/2023"),
    # and we require a following word so a trailing numeral at the very end is
    # left alone (nothing to glue it to). A literal regular space (not a <br>)
    # must separate them — never glue across an existing <br>.
    return re.sub(
        r"(?<![\w&;])(\d+\.?)[ ](?=\w)",
        lambda m: m.group(1) + "&nbsp;",
        text,
    )


# Headline shrink-to-fit floor: 60px = the brand `headline-slide` token (the
# "regular slide title" size in tokens.json). A principled lower bound — a cover
# title may shrink toward the regular-slide title size to keep a load-bearing
# sentence intact on one line, but never below it. Well above the shrink_font
# lever's absolute 50px (84*0.6) hard minimum.
_HEADLINE_FIT_FLOOR_PX = 60

# Sentence-boundary splitter: a terminal . ! or ? followed by whitespace (or the
# end of string), keeping the punctuation attached to the sentence it closes.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_into_sentences(text: str) -> list[str]:
    """Split a headline into sentence/clause units at terminal . ! ? boundaries,
    keeping the punctuation with its sentence. A headline with no internal
    boundary returns a single-element list."""
    parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]
    return parts or [text.strip()]


def _max_fit_font(
    line: str,
    *,
    box_width_px: int = _COVER_BOX_WIDTH_PX,
    base_font_px: int = _COVER_HEADLINE_FONT_PX,
    safety: float = _WRAP_SAFETY,
    floor_px: int = _HEADLINE_FIT_FLOOR_PX,
) -> int | None:
    """Largest integer font (base..floor) at which `line` fits the box budget on
    ONE line. Returns None if it does not fit even at the floor."""
    budget = box_width_px * safety
    for f in range(base_font_px, floor_px - 1, -1):
        if _estimate_text_width_px(line, f) <= budget:
            return f
    return None


def _wrap_headline_sentence_aware(
    text: str,
    *,
    box_width_px: int = _COVER_BOX_WIDTH_PX,
    base_font_px: int = _COVER_HEADLINE_FONT_PX,
    safety: float = _WRAP_SAFETY,
    floor_px: int = _HEADLINE_FIT_FLOOR_PX,
) -> tuple[str, int | None]:
    """ALWAYS-ON, deterministic, MEASURED sentence-aware cover-headline wrap.

    Contract (the ordering is the whole point):
      1. SENTENCE-BREAK FIRST: split the headline at . ! ? boundaries so each
         sentence/clause gets its own line(s). The load-bearing sentence
         ("3 RULES CHANGED.") stays intact instead of the browser re-splitting it.
      2. BOUNDED FONT-SHRINK SECOND: pick the LARGEST single font (one size for
         the whole headline — CSS .heading is one element) at which EVERY sentence
         fits on its own line, shrinking from the 84px base only as far as needed,
         never below `floor_px` (the brand `headline-slide` 60px floor).
      3. PIXEL-WRAP FALLBACK LAST: any single sentence that still cannot fit on
         one line at the floor is wrapped across lines by the existing pixel-greedy
         `_balance_headline` at the floor font — graceful degradation, never an
         overflow and never a sub-floor font.

    Returns (headline_html_with_<br>s, font_px). font_px is None when the wrap is
    a pure no-op at the base size (so the caller injects no font override and the
    cover renders exactly as today). When font_px is not None the caller must
    inject `.heading{font-size:<font_px>px}` so the measured fit actually holds.

    Brand-drift-safe: text-only (<br> insertion + a bounded font size); never
    touches palette/font-family/position/box. A short headline (<=3 words AND no
    sentence boundary) is returned verbatim with font_px=None.
    """
    text = text.strip()
    if not text or "<br>" in text.lower():
        # already wrapped upstream (e.g. lever ran) — don't second-guess it
        return text, None

    sentences = _split_into_sentences(text)
    single_sentence = len(sentences) == 1

    # No-op for short single-sentence headlines (<=3 words) that ALREADY FIT at
    # the base font: leave them verbatim+flat (zero brand drift, the common
    # legacy behavior). A short title that OVERFLOWS at base still falls through
    # to the fit logic below (bounded shrink / pixel-wrap) — "short" is not a
    # license to overflow.
    budget = box_width_px * safety
    if (
        single_sentence
        and len(text.split()) <= 3
        and _estimate_text_width_px(text, base_font_px) <= budget
    ):
        return text, None

    # 1+2: try to keep every sentence on its own line at one shared font >= floor.
    per_sentence_fonts = [_max_fit_font(s, box_width_px=box_width_px,
                                        base_font_px=base_font_px, safety=safety,
                                        floor_px=floor_px) for s in sentences]

    if all(f is not None for f in per_sentence_fonts):
        # Every sentence fits as a single line at >= floor. Use the SMALLEST
        # per-sentence max-fit font so all share one size and all fit.
        chosen = min(f for f in per_sentence_fonts if f is not None)
        if chosen >= base_font_px:
            # Everything already fits at the base size.
            if single_sentence:
                # A single sentence that fits at base on one line: leave it FLAT
                # (no <br>, no font override) — zero brand drift, common case.
                return text, None
            # Multi-sentence at base: just break between sentences, no shrink.
            return "<br>".join(sentences), None
        # A bounded shrink (< base, >= floor) makes all sentences fit one-per-line.
        return "<br>".join(sentences), chosen

    # 3: at least one sentence cannot fit on one line even at the floor → pixel-
    # wrap THAT sentence across lines at the floor font; keep the others intact.
    out_lines: list[str] = []
    for s, f in zip(sentences, per_sentence_fonts):
        if f is not None:
            out_lines.append(s)  # fits as a single line at the shared floor font
        else:
            # graceful degradation: pixel-greedy wrap this sentence at the floor.
            wrapped = _balance_headline(s, box_width_px=box_width_px,
                                        font_px=floor_px, safety=safety)
            out_lines.append(wrapped)  # may itself contain <br>s
    return "<br>".join(out_lines), floor_px


# ── facts-block body structurer (designer-loop convergence, 2026-06-12) ─────
# Diagnosis (draft 3e2c2923 slide 2, HARD-reject history 2026-06-11): a "facts"
# body like "NEW FEE: IDR 3,500,000. OLD FEE: IDR 2,000,000. REGULATION: PMK
# 47/2026. EFFECTIVE: 1 JUNE 2026. [SOURCE: KEMENKEU, 24 APR 2026]" rendered as
# ONE monolithic uppercase-bold paragraph. The vision critic HARD-rejects it
# every iteration (no internal hierarchy, the key number doesn't pop, the
# [SOURCE:…] attribution glued into the paragraph, the text block floats in
# dead voids) and its only proposed lever is `rerender` — a structural
# recomposition that no CSS lever can perform, so the designer loop can NEVER
# converge on these slides. The fix lives HERE in the composer: detect the
# label/value structure at compose time and render it as a proper stack.
# CONSERVATIVE by contract (W68/W72/W73 discipline — never clobber a correct
# rendering): a body that does not parse as fact pairs renders byte-identical
# to the legacy paragraph path, and cover slides are completely untouched.

# Trailing `[SOURCE: …]` / `[FONTE: …]` attribution (case-insensitive). Only a
# TRAILING bracket segment is attribution — a mid-body bracket is content.
_SOURCE_LINE_RE = re.compile(
    r"\s*\[\s*((?:SOURCE|FONTE)\s*:\s*[^\]]+?)\s*\]\s*\.?\s*$",
    re.IGNORECASE,
)

# A fact segment is `LABEL: value` — label 1-4 words with no internal period
# (the [^.:] class enforces it), value non-empty.
_FACT_SEGMENT_RE = re.compile(r"^([^.:]+):\s*(.+)$")
_FACT_LABEL_MAX_WORDS = 4

# Stack styling, brand-token-pure: label = small muted uppercase, value =
# larger high-contrast extrabold, lead value (the key number) = the existing
# brand yellow accent token, source line = subordinate (smaller, reduced
# opacity, NOT uppercase-bold). `.text-panel{justify-content:center}` centers
# the whole text stack vertically in its zone (the dead-void critique) — the
# skeleton's .text-panel is already a flex column, so this is positioning-inert
# for every other element. Selectors are defensive descendants of the
# skeleton's .body slot; unused selectors are inert (same approach as levers).
_FACTS_BLOCK_CSS = (
    "\n<style data-facts-block=\"1\">\n"
    ".text-panel{justify-content:center;}\n"
    ".fact-row{margin-bottom:var(--spacing-list-gap);}\n"
    ".fact-label{font-size:var(--font-size-body-md);color:var(--color-text-muted);"
    "font-weight:var(--font-weight-bold);letter-spacing:var(--letter-spacing-title);"
    "line-height:var(--line-height-snug);}\n"
    ".fact-value{font-size:var(--font-size-subheadline);color:var(--color-text-white);"
    "font-weight:var(--font-weight-extrabold);line-height:var(--line-height-snug);}\n"
    ".fact-value-lead{color:var(--color-accent-yellow);}\n"
    ".fact-source{margin-top:var(--spacing-section-gap);"
    "font-size:calc(var(--font-size-body-md) * 0.8);color:var(--color-text-muted);"
    "font-weight:400;text-transform:none;opacity:0.7;}\n"
    "</style>\n"
)


def _split_source_line(body: str) -> tuple[str, str | None]:
    """Extract a trailing `[SOURCE: …]` / `[FONTE: …]` attribution from a body.

    Returns (body_without_source, source_text). source_text keeps the label +
    citation verbatim (brackets stripped) — e.g. "SOURCE: KEMENKEU, 24 APR
    2026" — so the attribution renders untouched on its own subordinate line.
    A body with no trailing source returns (body, None).
    """
    m = _SOURCE_LINE_RE.search(body)
    if not m:
        return body, None
    return body[: m.start()].rstrip(), m.group(1).strip()


def _parse_fact_pairs(body: str) -> list[tuple[str, str]] | None:
    """Heuristic LABEL/value parser for "facts" slide bodies.

    Returns the ordered pairs ONLY when the whole (source-stripped) body is a
    chain of ≥2 `LABEL: value` segments separated by `. ` — label 1-4 words
    with no internal period, value non-empty. ANY segment that doesn't fit the
    shape (narrative prose, a single colon-clause, a >4-word label) returns
    None and the caller falls back to the legacy paragraph rendering
    UNCHANGED. When in doubt: None — this MUST stay conservative.
    """
    text = (body or "").strip()
    if not text:
        return None
    # Split AFTER a period followed by whitespace; each segment keeps its
    # terminal period (stripped from the value below). Periods inside tokens
    # (e.g. Indonesian "3.500.000") are not followed by a space → safe.
    segments = [s.strip() for s in re.split(r"(?<=\.)\s+", text) if s.strip()]
    if len(segments) < 2:
        return None
    pairs: list[tuple[str, str]] = []
    for seg in segments:
        m = _FACT_SEGMENT_RE.match(seg)
        if not m:
            return None
        label = m.group(1).strip()
        value = m.group(2).strip()
        if value.endswith("."):
            value = value[:-1].rstrip()  # the segment terminator, not content
        if not label or not value:
            return None
        if len(label.split()) > _FACT_LABEL_MAX_WORDS:
            return None
        pairs.append((label, value))
    return pairs


def _facts_block_html(pairs: list[tuple[str, str]], source_text: str | None) -> str:
    """Render parsed fact pairs as a label/value stack + optional source line.

    Each row = small muted uppercase label + larger high-contrast value; the
    FIRST row's value (the lead fact, e.g. the new fee) carries the brand
    yellow accent so the key number pops. The source line sits OUTSIDE the
    rows, at the bottom of the stack, as a subordinate attribution. Plain
    string markup (no escaping) — consistent with _fill_placeholders, which
    substitutes via str.replace.
    """
    rows: list[str] = []
    for i, (label, value) in enumerate(pairs):
        lead = " fact-value-lead" if i == 0 else ""
        rows.append(
            '<div class="fact-row">'
            f'<div class="fact-label">{label}</div>'
            f'<div class="fact-value{lead}">{value}</div>'
            "</div>"
        )
    if source_text:
        rows.append(f'<div class="fact-source">{source_text}</div>')
    return "\n".join(rows)


# Storyboarder→template field aliases for {{#each}} loops. The layout templates
# iterate a canonical variable (`items`, `facts`, `citations`, `events`) but the
# storyboarder emits domain-named arrays (`list_items`, …). Map the alias to the
# template's variable so the loop binds instead of shipping raw {{#each items}}.
_EACH_ALIASES: dict[str, tuple[str, ...]] = {
    "items": ("list_items", "items"),          # dark-status-list
    "facts": ("facts", "fact_items"),          # evidence-carved
    "citations": ("citations", "sources"),     # source-citation
    "events": ("events", "timeline", "list_items"),  # timeline-pinboard
}


def _resolve_each_rows(var: str, slide: dict[str, Any]) -> list[Any] | None:
    """Find the array a {{#each <var>}} loop should iterate, honoring aliases."""
    for key in _EACH_ALIASES.get(var, (var,)):
        rows = slide.get(key)
        if isinstance(rows, list) and rows:
            return rows
    return None


def _expand_each_blocks(html: str, slide: dict[str, Any]) -> str:
    """Expand Handlebars-style ``{{#each <var>}}…{{/each}}`` blocks.

    For each row, the inner template's ``{{field}}`` placeholders are filled from
    that row dict (``{{this}}`` → the row itself when it is a scalar), and a nested
    ``{{#if field}}…{{/if}}`` keeps its body only when the row has a truthy field.
    Field values are HTML-escaped (rows carry user copy). A block whose array is
    missing/empty is removed entirely (no raw mustache shipped) — this is the bug
    fix: previously the whole ``{{#each}}`` block reached the renderer verbatim.
    """
    each_re = re.compile(r"\{\{#each\s+([a-z_]+)\}\}(.*?)\{\{/each\}\}", re.DOTALL)

    def _render_block(m: re.Match[str]) -> str:
        var, inner = m.group(1), m.group(2)
        rows = _resolve_each_rows(var, slide)
        if not rows:
            return ""  # no data → drop the block (never ship raw {{#each}})
        out: list[str] = []
        for row in rows:
            chunk = inner
            if isinstance(row, dict):
                # nested {{#if field}}…{{/if}} per row
                def _if_sub(mi: re.Match[str], _row: dict[str, Any] = row) -> str:
                    return mi.group(2) if _row.get(mi.group(1)) else ""
                chunk = re.sub(
                    r"\{\{#if\s+([a-z_]+)\}\}(.*?)\{\{/if\}\}", _if_sub, chunk,
                    flags=re.DOTALL,
                )
                for fk, fv in row.items():
                    chunk = chunk.replace("{{%s}}" % fk, _html_escape(str(fv)))
                chunk = chunk.replace("{{this}}", _html_escape(str(row)))
            else:
                # scalar row: {{this}} is the value
                chunk = chunk.replace("{{this}}", _html_escape(str(row)))
            # strip any leftover {{field}} the row didn't supply (no raw mustache)
            chunk = re.sub(r"\{\{[a-z_]+\}\}", "", chunk)
            out.append(chunk)
        return "".join(out)

    return each_re.sub(_render_block, html)


def _qa_dialogue_fields(slide: dict[str, Any]) -> dict[str, str]:
    """Adapt the storyboarder's ``qa_pairs`` array to qa-dialogue's flat fields.

    The qa-dialogue template wants ``voice_a_label/voice_a_quote/voice_b_*`` but
    the storyboarder emits ``qa_pairs: [{voice, line}, …]``. Map the first two
    pairs onto the two voices. Returns {} when qa_pairs is absent (template then
    falls back to whatever flat fields the slide already carries).
    """
    pairs = slide.get("qa_pairs")
    if not isinstance(pairs, list) or len(pairs) < 1:
        return {}
    out: dict[str, str] = {}
    for idx, key in ((0, "a"), (1, "b")):
        if idx < len(pairs) and isinstance(pairs[idx], dict):
            p = pairs[idx]
            out["voice_%s_label" % key] = str(p.get("voice") or p.get("label") or "")
            out["voice_%s_quote" % key] = str(p.get("line") or p.get("quote") or "")
    return out


def _fill_placeholders(
    html: str,
    slide: dict[str, Any],
    *,
    hero_filename: str | None,
    cover_family: bool = False,
) -> str:
    """Fill {{placeholders}} + simple {{#if}} blocks from a slide dict.

    Supported fields map to common skeleton placeholders:
      heading, subheading, body, image_url, regulation_code, statement.
    {{#if regulation_code}}...{{/if}} renders only if present.
    """
    # Schema-field fallback (BUG #3): newer drafts use headline/subhead, older
    # (Canva) drafts use heading/subheading. Read BOTH so an old-schema draft does
    # not render a blank cover (vision: "no editorial text").
    headline = (slide.get("headline") or slide.get("heading") or "").strip()
    # rebalance_wrap lever (designer loop): re-wrap the headline into balanced
    # lines via a <br>. Text-only — applied here BEFORE placeholder substitution
    # so the skeleton's {{heading}}/{{statement}} carry the <br> verbatim (the
    # composer uses plain string .replace, no HTML-escaping → <br> renders as a
    # tag, not literal text). The FULL pixel-rebalance stays lever-gated (it is a
    # heavier composition change). The number-orphan de-wrap, by contrast, is a
    # safe, pixel-budget-bounded, text-only typographic rule and runs ALWAYS so a
    # load-bearing "3 RULES CHANGED" never splits even when the non-deterministic
    # critic does not request the lever (the F10 re-shadow orphan). Order: full
    # rebalance first (if levered), then the deterministic number de-orphan over
    # whatever line structure resulted.
    headline_font_px: int | None = None
    if (slide.get("_levers") or {}).get("_rebalance_wrap"):
        # designer-loop lever: full pixel-rebalance (heavier composition change).
        headline = _balance_headline(headline)
    elif cover_family:
        # ALWAYS-ON sentence-aware wrap (deterministic, measured): break at
        # sentence boundaries so a load-bearing clause ("3 RULES CHANGED.") stays
        # on one line; bounded font-shrink to fit; pixel-wrap fallback at the
        # floor. Returns the single font size (if a shrink was needed) to inject.
        headline, headline_font_px = _wrap_headline_sentence_aware(headline)
    # Deterministic number de-orphan (belt-and-suspenders): glue any remaining
    # bare numeral to its noun so the browser can never strand it.
    headline = _deorphan_numbers_in_headline(headline)
    subhead = (slide.get("subhead") or slide.get("subheading") or "").strip()
    body = (slide.get("body") or slide.get("body_text") or "").strip()
    reg = (slide.get("regulation_code") or slide.get("primary_regulation_code") or "").strip()

    # Facts-block body structurer (NON-cover slides only): when the body parses
    # as a chain of LABEL: value facts, render it as a label/value stack with a
    # separated subordinate source line instead of one monolithic paragraph.
    # When it does NOT parse (or on a cover), body_html stays the verbatim body
    # and NO facts CSS is injected → byte-identical to the legacy rendering.
    body_html = body
    facts_block = False
    if body and not cover_family:
        body_wo_source, source_text = _split_source_line(body)
        pairs = _parse_fact_pairs(body_wo_source)
        if pairs:
            body_html = _facts_block_html(pairs, source_text)
            facts_block = True
        else:
            # Plain-paragraph body: yellow the crux regulatory number(s) so the
            # key fact pops (Art 6.9 anchor-highlight; option C 2026-06-24). The
            # facts-block path above already emphasizes its lead value, so this is
            # the non-facts branch only. No-op if the body has no key number.
            body_html = _emphasize_key_numbers(body_html)

    # {{#if regulation_code}} ... {{/if}}
    if reg:
        html = re.sub(r"\{\{#if regulation_code\}\}(.*?)\{\{/if\}\}", r"\1", html, flags=re.DOTALL)
    else:
        html = re.sub(r"\{\{#if regulation_code\}\}.*?\{\{/if\}\}", "", html, flags=re.DOTALL)

    # statement-bomb uses {{statement}}; map from headline/body
    statement = (slide.get("statement") or headline or body).strip()

    # statement-bomb's richer placeholder {{statement_html_with_emphasis_span}}
    # was previously NEVER filled — the raw mustache shipped to the renderer on
    # every CTA slide. Build it from the statement: HTML-escape the text, then
    # wrap the LAST word in <span class="emphasis"> (the skeleton's accent).
    statement_emphasis_html = ""
    if statement:
        words = _html_escape(statement).split()
        if len(words) > 1:
            statement_emphasis_html = (
                " ".join(words[:-1])
                + f' <span class="emphasis">{words[-1]}</span>'
            )
        else:
            statement_emphasis_html = f'<span class="emphasis">{words[0]}</span>'

    # Expand {{#each <var>}} list blocks FIRST (dark-status-list / evidence-carved /
    # source-citation / timeline-pinboard) so the loop rows are materialized before
    # the scalar placeholder pass. Previously unhandled → raw mustache shipped.
    html = _expand_each_blocks(html, slide)

    replacements = {
        "{{heading}}": headline,
        "{{subheading}}": subhead,
        "{{subhead}}": subhead,
        "{{body}}": body_html,
        "{{regulation_code}}": reg,
        "{{statement}}": statement,
        "{{statement_html_with_emphasis_span}}": statement_emphasis_html,
        # evidence-carved "take" block scalars. Previously UNBOUND → the raw
        # mustache ({{take_label}}/{{take_line}}) shipped to the renderer and
        # leaked as literal text at the bottom of every evidence-carved slide
        # that supplied a take (critic FAIL, 2026-07-11 revise-run S7). Default
        # to empty so a slide with no take never leaks a placeholder either.
        "{{take_label}}": _html_escape((slide.get("take_label") or "").strip()),
        "{{take_line}}": _html_escape((slide.get("take_line") or "").strip()),
    }
    # qa-dialogue: map qa_pairs → the template's flat voice_a/voice_b fields.
    for fk, fv in _qa_dialogue_fields(slide).items():
        replacements["{{%s}}" % fk] = _html_escape(fv)
    for k, v in replacements.items():
        html = html.replace(k, v)

    # image_url: if we moved hero to <img>, the {{image_url}} in CSS is already
    # neutralized; any remaining {{image_url}} (e.g. unconverted) -> local file
    if hero_filename:
        html = html.replace("{{image_url}}", hero_filename)
    else:
        html = html.replace("{{image_url}}", "")

    # Inject the sentence-aware bounded font-shrink (if any). The cover .heading
    # is one element, so one font size governs all its lines; the wrap above
    # MEASURED that this size lets every sentence fit. Paint/size-only on the
    # title — never palette/font-family/position/box. line-height tightened to
    # match the brand cover tight leading at the smaller size.
    if headline_font_px is not None:
        font_css = (
            "\n<style data-headline-fit=\"1\">\n"
            f".heading,.headline,.statement,h1{{font-size:{headline_font_px}px !important;"
            "line-height:1.05;}}\n</style>\n"
        )
        if "</head>" in html:
            html = html.replace("</head>", font_css + "</head>", 1)
        elif "</body>" in html:
            html = html.replace("</body>", font_css + "</body>", 1)
        else:
            html = html + font_css

    # Inject the facts-block styles ONLY when the stack was rendered, so a
    # non-parsing body stays byte-identical to the legacy paragraph output.
    if facts_block:
        if "</head>" in html:
            html = html.replace("</head>", _FACTS_BLOCK_CSS + "</head>", 1)
        elif "</body>" in html:
            html = html.replace("</body>", _FACTS_BLOCK_CSS + "</body>", 1)
        else:
            html = html + _FACTS_BLOCK_CSS

    return html


async def compose_carousel(
    slides_json: list[dict[str, Any]] | dict[str, Any],
    output_dir: Path,
    *,
    topic: str = "",
    timeout_ms: int = 30000,
) -> RenderResult:
    """Compose + render a full carousel from a slides_json into output_dir.

    Accepts either a list of slide dicts or the full carousel object
    {"slides": [...], ...}. Returns the RenderResult (whose .ok enforces that
    every hero image was actually placed).
    """
    import httpx  # async, Golden Rule #4

    if isinstance(slides_json, dict):
        slides = slides_json.get("slides", [])
    else:
        slides = slides_json
    if not slides:
        raise ValueError("slides_json has no slides")

    total = len(slides)
    output_dir = Path(output_dir)
    _stage_assets(output_dir)
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    _stage_assets(slides_dir)  # fonts/logo/_base.css co-located with the HTML

    # Build plans
    plans: list[SlidePlan] = []
    for i, slide in enumerate(slides, start=1):
        family = map_slide_to_family(slide, i, total)
        if family in UNDEFINED_FAMILIES:
            logger.warning("slide %d mapped to undefined family %s — falling back", i, family)
            family = "photo-headline-yellow-sub"
        expect_hero = bool(slide.get("is_hero_image")) or i == 1
        plans.append(SlidePlan(index=i, family=family, slide=slide, expect_hero=expect_hero))

    # Download heroes + materialize HTML per slide
    html_specs: list[tuple[Path, bool, str]] = []
    async with httpx.AsyncClient() as client:
        for plan in plans:
            hero_filename: str | None = None
            if plan.expect_hero:
                url = (plan.slide.get("image_url") or "").strip()
                if url:
                    hero_filename = f"slide-{plan.index:02d}-hero.jpg"
                    dest = slides_dir / hero_filename
                    ok = await _download_hero(client, url, dest)
                    if not ok:
                        # leave hero_filename pointing at a missing file → the
                        # renderer gate will FAIL this slide (correct: we must
                        # NOT ship a hero slide without its image)
                        logger.warning("slide %d hero download failed url=%s", plan.index, url)

            skeleton = _extract_skeleton(plan.family)
            html = _normalize_skeleton(skeleton)
            if plan.expect_hero and hero_filename:
                html = _hero_bg_to_img(html, hero_filename)
            html = _fill_placeholders(
                html, plan.slide, hero_filename=hero_filename,
                cover_family=(plan.family == "cover-photo"),
            )
            html = _apply_levers_to_html(html, plan.slide)  # designer-loop levers

            html_path = slides_dir / f"{plan.index:02d}.html"
            html_path.write_text(html, encoding="utf-8")
            # 3-tuple: thread the layout family so the renderer's hero-visibility
            # gate samples where THIS family exposes the photo (top/lower/middle).
            html_specs.append((html_path, plan.expect_hero, plan.family))

    result = await render_html_files(html_specs, output_dir, timeout_ms=timeout_ms, make_pdf=True)

    # write a manifest
    manifest = {
        "topic": topic,
        "total_slides": total,
        "families": [p.family for p in plans],
        "heroes_expected": result.heroes_expected,
        "heroes_placed": result.heroes_placed,
        "slides_rendered": result.slides_rendered,
        "ok": result.ok,
        "failures": result.failures,
        "png_paths": [str(p) for p in result.png_paths],
        "pdf_path": str(result.pdf_path) if result.pdf_path else None,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


async def materialize_slide_html(
    slide: dict[str, Any],
    slides_dir: Path,
    *,
    index: int,
    total: int,
    hero_filename: str | None = None,
) -> tuple[Path, bool]:
    """Materialize ONE slide to HTML (honoring slide['_levers']) in slides_dir.

    Returns (html_path, expect_hero). Assets must already be staged in slides_dir
    (fonts/logo/_base.css) and the hero (if any) already downloaded to
    slides_dir/hero_filename. This is the per-slide half of compose_carousel,
    factored out so the designer loop can re-materialize a single slide with new
    levers between iterations without touching the others.
    """
    family = map_slide_to_family(slide, index, total)
    if family in UNDEFINED_FAMILIES:
        logger.warning("slide %d mapped to undefined family %s — falling back", index, family)
        family = "photo-headline-yellow-sub"
    expect_hero = bool(slide.get("is_hero_image")) or index == 1

    skeleton = _extract_skeleton(family)
    html = _normalize_skeleton(skeleton)
    if expect_hero and hero_filename:
        html = _hero_bg_to_img(html, hero_filename)
    # Cover-photo family already shows the regulation via the yellow subheading
    # kicker (the {{subheading}} slot). The skeleton also has a top-right corner
    # badge ({{#if regulation_code}}...{{/if}}). Rendering both is redundant and
    # the tiny badge is illegible at thumbnail size. Strip the badge block so the
    # cover renders the regulation exactly once (in the kicker).
    if family == "cover-photo":
        html = re.sub(
            r"\{\{#if regulation_code\}\}.*?\{\{/if\}\}",
            "",
            html,
            flags=re.DOTALL,
        )
    html = _fill_placeholders(
        html, slide, hero_filename=hero_filename, cover_family=(family == "cover-photo")
    )
    html = _apply_levers_to_html(html, slide)

    html_path = slides_dir / f"{index:02d}.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path, expect_hero


def make_slide_render_fn(
    *,
    slides_dir: Path,
    index: int,
    total: int,
    hero_filename: str | None,
    timeout_ms: int = 30000,
):
    """Build a render_fn(slide_with_levers, png_path) for run_designer_loop.

    The returned async callable re-materializes THIS slide's HTML with whatever
    levers the loop has accumulated (slide['_levers']) and renders it to png_path,
    enforcing the hero-placement gate. slides_dir must already have staged assets
    + the downloaded hero. This is the bridge between designer_loop (which owns
    the lever STATE) and the composer (which owns lever→CSS + rendering).
    """
    from .renderer import render_html_files

    async def _render_fn(slide_with_levers: dict[str, Any], png_path: Path) -> None:
        # SLIDE-PRIVATE RENDER NAMESPACE (cover-drop fix 2026-06-30, superscar #5/#9):
        # render_html_files names its output by the 1-based position in the spec
        # list, which is ALWAYS 1 here (single-element list) → it writes "01.png".
        # If that landed in the shared slides_dir, EVERY slide would transiently
        # write slides_dir/01.png — clobbering slide 1's already-placed cover
        # before the upload glob runs (observed: Drive got 02..08, no cover).
        # Cure: render each slide into its OWN private scratch dir, then move the
        # PNG to its canonical slot. The transient "01.png" can never collide with
        # another slide's canonical home because it lives under .render-NN/slides/.
        render_root = slides_dir / f".render-{index:02d}"
        scratch_slides = render_root / "slides"
        scratch_slides.mkdir(parents=True, exist_ok=True)
        # Stage assets (fonts/logo/_base.css) into the scratch slides dir so the
        # co-located HTML resolves them under one file:// origin, and copy the
        # downloaded hero (if any) alongside — materialize/render expect both.
        _stage_assets(scratch_slides)
        if hero_filename:
            hero_src = slides_dir / hero_filename
            if hero_src.is_file():
                shutil.copy2(hero_src, scratch_slides / hero_filename)
        # Re-materialize THIS slide's HTML with the loop's accumulated levers into
        # the private scratch dir.
        await materialize_slide_html(
            slide_with_levers, scratch_slides, index=index, total=total, hero_filename=hero_filename
        )
        html_path = scratch_slides / f"{index:02d}.html"
        # Thread the layout family (same derivation materialize_slide_html used)
        # so the hero-visibility gate samples the right band for this layout.
        family = map_slide_to_family(slide_with_levers, index, total)
        if family in UNDEFINED_FAMILIES:
            family = "photo-headline-yellow-sub"
        # render_html_files writes PNG to (render_root/"slides")/f"{enum_idx:02d}.png"
        # with enum_idx always 1 (single-element list) → render_root/slides/01.png,
        # which is now PRIVATE to this slide.
        res = await render_html_files(
            [(html_path, expect_hero_for_index(slide_with_levers, index), family)],
            render_root,
            timeout_ms=timeout_ms,
            make_pdf=False,
        )
        produced: Path | None = None
        if res.png_paths:
            produced = Path(res.png_paths[0])
        else:
            cand = scratch_slides / "01.png"
            if cand.is_file():
                produced = cand
        if produced and produced.is_file() and produced.resolve() != png_path.resolve():
            png_path.parent.mkdir(parents=True, exist_ok=True)
            produced.replace(png_path)
        # Best-effort cleanup of the scratch dir so it never pollutes the upload
        # glob (which scans slides_dir/*.png — .render-NN/ is a subdir so its PNGs
        # are NOT globbed, but we remove it to keep the workspace clean).
        shutil.rmtree(render_root, ignore_errors=True)

    return _render_fn


def expect_hero_for_index(slide: dict[str, Any], index: int) -> bool:
    """Whether this slide must carry a hero image (cover or explicit hero)."""
    return bool(slide.get("is_hero_image")) or index == 1


async def _download_hero(client: Any, url: str, dest: Path) -> bool:
    # Retry with backoff: the hero lives on Fly/Tigris storage and a single transient
    # network flap ("No route to host" / ConnectTimeout) on the Pro would otherwise burn
    # an html_render_attempt and fail the whole carousel render. Superscar #8 (network
    # flap / proxy fragility): wrap the point download in a retry-loop with backoff.
    attempts = 3
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30.0)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "hero GET failed url=%s err=%s (attempt %d/%d)", url, exc, attempt, attempts
            )
            if attempt < attempts:
                await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s
            continue
        if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
            logger.warning(
                "hero bad response url=%s status=%s ctype=%s (attempt %d/%d)",
                url, resp.status_code, resp.headers.get("content-type"), attempt, attempts,
            )
            if attempt < attempts:
                await asyncio.sleep(2 ** (attempt - 1))
            continue
        if not resp.content:
            logger.warning("hero empty body url=%s (attempt %d/%d)", url, attempt, attempts)
            if attempt < attempts:
                await asyncio.sleep(2 ** (attempt - 1))
            continue
        dest.write_bytes(resp.content)
        return True
    logger.error("hero download exhausted %d attempts url=%s last_err=%s", attempts, url, last_exc)
    return False
