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

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .renderer import RenderResult, _stage_assets, render_html_files

logger = logging.getLogger("wr2.composer")

_BRAND = Path.home() / ".claude" / "skills" / "bali-zero-brand"
_LAYOUTS = _BRAND / "layouts"

# The 9 layout families that have real HTML/CSS skeletons (GROUND phase verified).
RENDERABLE_FAMILIES = {
    "cover-photo",
    "photo-headline-yellow-sub",
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

    Mapping rules (conservative — only the 9 renderable families):
      - slide 1 / is_cover            -> cover-photo            (Art 9.3 hard rule)
      - last slide / slide_type cta   -> statement-bomb         (Art 9.5 hard rule)
      - is_hero_image (mid)           -> photo-headline-yellow-sub (hero + text)
      - has explicit list structure   -> evidence-carved        (facts) [future]
      - default body                  -> photo-headline-yellow-sub if image_url
                                         else dark-status-list-ish text slide

    Returns a family in RENDERABLE_FAMILIES. Never returns an UNDEFINED one.
    """
    st = (slide.get("slide_type") or "").lower()

    if index == 1 or slide.get("is_cover"):
        return "cover-photo"
    if index == total or st in {"cta", "closing", "statement"}:
        return "statement-bomb"
    if slide.get("is_hero_image"):
        return "photo-headline-yellow-sub"
    # text-forward body slide: if it has an image use the photo layout, else a
    # text layout. (dark-status-list expects label/value items; without that
    # structure we keep it on the photo layout with image, or a plain text
    # variant. For now, default to photo-headline if image present.)
    if slide.get("image_url"):
        return "photo-headline-yellow-sub"
    return "photo-headline-yellow-sub"  # safe default (renders heading+sub+body)


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
    hero_img_css = (
        "\n.hero-img{position:absolute;inset:0;width:100%;height:100%;"
        "object-fit:cover;z-index:0;}\n"
    )
    html = html.replace("</style>", hero_img_css + "</style>", 1)
    img_tag = f'<img class="hero-img" src="{hero_filename}" alt="" data-zone-type="hero-photo">'
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
# var(--font-size-headline-cover) (84px on the 1080px canvas), where roughly this
# many characters fit on one line before the browser re-wraps. Parametrizable so
# a smaller headline font can pass a larger budget.
_COVER_MAX_CHARS_PER_LINE = 16


def _balance_headline(text: str, *, max_chars_per_line: int = _COVER_MAX_CHARS_PER_LINE) -> str:
    """Re-wrap a headline into MULTIPLE balanced lines (explicit <br>s) so that
    NO line is wide enough for the browser to re-wrap and NO line is a single
    orphan word.

    The `rebalance_wrap` lever's renderer side (FIX#2b 2026-06-10). The earlier
    single-<br> split (2026-06-09) failed on long titles: it produced two
    segments, but the long segment ("Trail Reaches the Top") still exceeded the
    cover font's line width and the browser re-wrapped it on its own, RE-creating
    the very "TOP" orphan we were fixing. This greedy word-wrap caps every line
    at `max_chars_per_line` (≈ the cover font's single-line capacity) so the
    browser never gets to re-wrap, then rebalances to kill any single-word last
    line.

    Text-only — it only inserts <br> tags between whole words; it never splits a
    word and never touches position/color/font/box (so it cannot drift the brand).

    Rules:
      - ≤3 words: leave unchanged (too short to wrap; one line is fine).
      - greedy-fill each line up to `max_chars_per_line` (whole words only); if a
        single word is longer than the budget it gets its own line (never split).
      - if the result is a single line (everything fit), leave it flat.
      - no single-word orphan line: if the last line has 1 word, pull the last
        word of the previous line down onto it (when that keeps the previous line
        non-empty); applied to whichever line ends up the lone orphan.
      - if the text already contains a <br>, assume it's pre-wrapped → no-op.
    """
    text = text.strip()
    if not text or "<br>" in text.lower():
        return text
    words = text.split()
    if len(words) <= 3:
        return text

    budget = max(1, int(max_chars_per_line))

    # Greedy fill: start each line, add words while the line stays within budget.
    lines: list[list[str]] = []
    cur: list[str] = []
    for w in words:
        if not cur:
            cur = [w]
            continue
        candidate = " ".join(cur + [w])
        if len(candidate) <= budget:
            cur.append(w)
        else:
            lines.append(cur)
            cur = [w]
    if cur:
        lines.append(cur)

    # Everything fit on one line → nothing to wrap.
    if len(lines) <= 1:
        return text

    # Kill a single-word orphan on the LAST line by borrowing the previous line's
    # last word (only if the previous line keeps ≥1 word). Repeat once is enough
    # for headline-length text, but loop defensively while it stays an orphan and
    # the move is legal.
    while len(lines) >= 2 and len(lines[-1]) == 1 and len(lines[-2]) >= 2:
        lines[-1].insert(0, lines[-2].pop())

    return "<br>".join(" ".join(line) for line in lines)


def _fill_placeholders(html: str, slide: dict[str, Any], *, hero_filename: str | None) -> str:
    """Fill {{placeholders}} + simple {{#if}} blocks from a slide dict.

    Supported fields map to common skeleton placeholders:
      heading, subheading, body, image_url, regulation_code, statement.
    {{#if regulation_code}}...{{/if}} renders only if present.
    """
    headline = (slide.get("headline") or "").strip()
    # rebalance_wrap lever (designer loop): re-wrap the headline into balanced
    # lines via a <br>. Text-only — applied here BEFORE placeholder substitution
    # so the skeleton's {{heading}}/{{statement}} carry the <br> verbatim (the
    # composer uses plain string .replace, no HTML-escaping → <br> renders as a
    # tag, not literal text). Only when the lever is set in slide["_levers"].
    if (slide.get("_levers") or {}).get("_rebalance_wrap"):
        headline = _balance_headline(headline)
    subhead = (slide.get("subhead") or "").strip()
    body = (slide.get("body") or "").strip()
    reg = (slide.get("regulation_code") or slide.get("primary_regulation_code") or "").strip()

    # {{#if regulation_code}} ... {{/if}}
    if reg:
        html = re.sub(r"\{\{#if regulation_code\}\}(.*?)\{\{/if\}\}", r"\1", html, flags=re.DOTALL)
    else:
        html = re.sub(r"\{\{#if regulation_code\}\}.*?\{\{/if\}\}", "", html, flags=re.DOTALL)

    # statement-bomb uses {{statement}}; map from headline/body
    statement = (slide.get("statement") or headline or body).strip()

    replacements = {
        "{{heading}}": headline,
        "{{subheading}}": subhead,
        "{{subhead}}": subhead,
        "{{body}}": body,
        "{{regulation_code}}": reg,
        "{{statement}}": statement,
    }
    for k, v in replacements.items():
        html = html.replace(k, v)

    # image_url: if we moved hero to <img>, the {{image_url}} in CSS is already
    # neutralized; any remaining {{image_url}} (e.g. unconverted) -> local file
    if hero_filename:
        html = html.replace("{{image_url}}", hero_filename)
    else:
        html = html.replace("{{image_url}}", "")

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
    html_specs: list[tuple[Path, bool]] = []
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
            html = _fill_placeholders(html, plan.slide, hero_filename=hero_filename)
            html = _apply_levers_to_html(html, plan.slide)  # designer-loop levers

            html_path = slides_dir / f"{plan.index:02d}.html"
            html_path.write_text(html, encoding="utf-8")
            html_specs.append((html_path, plan.expect_hero))

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
    html = _fill_placeholders(html, slide, hero_filename=hero_filename)
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
        # Re-materialize THIS slide's HTML with the loop's accumulated levers.
        # materialize writes into slides_dir; the renderer expects assets +
        # the HTML under output_dir/"slides", so we render with
        # output_dir = slides_dir.parent and let it use slides_dir.
        render_root = slides_dir.parent
        await materialize_slide_html(
            slide_with_levers, slides_dir, index=index, total=total, hero_filename=hero_filename
        )
        html_path = slides_dir / f"{index:02d}.html"
        # render_html_files writes PNG to (render_root/"slides")/f"{enum_idx:02d}.png"
        # where enum_idx is the 1-based position in the list → always "01" here.
        res = await render_html_files(
            [(html_path, expect_hero_for_index(slide_with_levers, index))],
            render_root,
            timeout_ms=timeout_ms,
            make_pdf=False,
        )
        produced: Path | None = None
        if res.png_paths:
            produced = Path(res.png_paths[0])
        else:
            cand = render_root / "slides" / "01.png"
            if cand.is_file():
                produced = cand
        if produced and produced.is_file() and produced.resolve() != png_path.resolve():
            png_path.parent.mkdir(parents=True, exist_ok=True)
            produced.replace(png_path)

    return _render_fn


def expect_hero_for_index(slide: dict[str, Any], index: int) -> bool:
    """Whether this slide must carry a hero image (cover or explicit hero)."""
    return bool(slide.get("is_hero_image")) or index == 1


async def _download_hero(client: Any, url: str, dest: Path) -> bool:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=30.0)
    except Exception as exc:
        logger.warning("hero GET failed url=%s err=%s", url, exc)
        return False
    if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
        logger.warning("hero bad response url=%s status=%s ctype=%s", url, resp.status_code, resp.headers.get("content-type"))
        return False
    if not resp.content:
        return False
    dest.write_bytes(resp.content)
    return True
