---
date: 2026-06-07
domain: marketing
client_case: none
topic: WR2 editorial Instagram carousel renderer — HTML/CSS → PNG, SOTA
sources:
  - https://github.com/vercel/satori
  - https://github.com/vercel/satori/blob/main/README.md
  - https://playwright.dev/docs/screenshots
  - https://momentic.ai/blog/playwright-pitfalls
  - https://turntrout.com/playwright-tips
  - https://github.com/microsoft/playwright/issues/20097
  - https://github.com/microsoft/playwright/issues/35200
  - https://www.smashingmagazine.com/2019/10/editorial-design-patterns-css-grid-subgrid-naming/
  - https://www.smashingmagazine.com/understanding-css-grid-template-areas/
  - https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-areas
  - https://webaim.org/articles/contrast/
  - https://testparty.ai/blog/wcag-1-4-6-contrast-enhanced-2025-guide
  - https://instantgradient.com/blog/accessible_gradient_guide
  - https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode
  - https://ray.run/questions/how-do-i-ensure-that-all-images-are-fully-loaded-before-taking-a-screenshot-in-playwright
  - https://restofworld.org/inside/rest-of-worlds-product-team-looks-back-at-2023/
  - https://www.niemanlab.org/2021/07/the-new-york-times-is-using-instagram-slides-and-twitter-cards-to-make-stories-more-digestible/
verified_against_repo:
  - apps/backend-rag/backend/services/layout/playwright_client.py
  - apps/war-room/output/carousel/*/slides/{1,2}.html  (working examples)
  - apps/war-room/output/carousel/*/slides/render.py    (working batch renderer)
  - ~/.claude/skills/bali-zero-brand/tokens.json
  - ~/.claude/skills/bali-zero-brand/layouts/_base.css
  - ~/.claude/skills/bali-zero-brand/layouts/*.md
  - ~/.claude/skills/bali-zero-brand/_render_smoke_test.py
---

# WR2 HTML/CSS → PNG Editorial Carousel Renderer — SOTA Research (2026-06-07)

## TL;DR — the decision, up front

1. **Renderer engine: Playwright-Python (headless Chromium). Do NOT use Satori.** Satori cannot
   render CSS Grid, does not resolve CSS custom properties (`var(--token)`), and does not support
   `radial-gradient` / `backdrop-filter`. The Bali Zero brand is built *entirely* on CSS variables
   (`_base.css :root`), uses `radial-gradient` (the `evidence-carved` "Hammurabi stele" layout), and
   the explicit goal is CSS-Grid-driven layout variety. Satori would force a rewrite of the brand
   system into a flexbox subset and lose the exact features that make the design editorial. Playwright
   is already in the repo and already renders these slides correctly. Reuse it.
2. **Layout-family architecture: ONE fixed 12-column / named-row CSS Grid + `grid-template-areas`,
   swapped per layout-family.** Components (kicker, headline, rule, body, stat, hero, source, logo)
   are brand-locked and identical everywhere; only the *grid placement string* changes per family.
   This is the mechanism that yields "infinite combinations inside a permanent brand."
3. **Font + image determinism are the two things that make HTML→PNG flaky. Both are currently
   UNSOLVED in this repo** (the brand renders Montserrat via a Google-Fonts `@import` network fetch,
   and Montserrat is *not installed locally* — verified). Fix with: vendored local `@font-face`
   (woff2 on disk or base64-inlined) + `await document.fonts.ready`, and per-image
   `await img.decode()` before screenshot — never rely on `networkidle`.

---

## What already exists in the repo (reuse-first baseline — verified this session)

The repo is NOT starting from zero. The working pattern is already proven:

- `apps/backend-rag/backend/services/layout/playwright_client.py` — an async `PlaywrightClient`
  that renders HTML→PNG via a **base64 `data:` URL** (`_html_to_data_url`), with a persistent
  browser, `viewport={width,height}`, `device_scale_factor=1`, and a `clip` to exact dimensions.
  It currently uses `wait_until="networkidle"` (a known flakiness source — see §4/§5).
- `apps/war-room/output/carousel/*/slides/render.py` — a batch renderer that loops `1..N`,
  `page.goto(html.as_uri(), wait_until="networkidle")`, calls `page.evaluate("document.fonts.ready")`
  (note: NOT awaited — bug, see §4), `wait_for_timeout(300)` (a band-aid sleep), then
  `page.screenshot(clip=...)` at 1080×1350. **This produces correct PNGs today.**
- `~/.claude/skills/bali-zero-brand/surfaces/internal-print-a4/_render.py` — a Playwright→PDF
  renderer for A4 briefs. Same engine, different output. Precedent for "one Playwright service,
  multiple output surfaces."
- `~/.claude/skills/bali-zero-brand/layouts/_base.css` — the canonical `:root` token block
  (auto-injected from `tokens.json`) + shared components (`.logo`, `.swipe-indicator`,
  `.regulation-badge`, `.qr-closing`, `.source-citation-footer`). **This is the brand contract.**
- `~/.claude/skills/bali-zero-brand/layouts/*.md` — per-family HTML/CSS skeletons (cover-photo,
  dark-status-list, evidence-carved, statement-bomb, qa-dialogue, timeline-pinboard, etc.).
- `tokens.json` — closed-namespace design tokens (palette, type scale, spacing, canvas 1080×1350).

**Decision implication:** build the new renderer as a thin, hardened wrapper around the existing
`PlaywrightClient` + `_base.css` + token system. The job is *consolidation + determinism hardening +
a Grid layout layer*, not a greenfield engine.

---

## Dimension 1 — HTML/CSS → PNG rendering tech (2026 SOTA)

| Capability needed | Playwright (Chromium) | Satori → resvg/sharp | wkhtmltoimage / Puppeteer-legacy |
|---|---|---|---|
| Exact 1080×1350 px | ✅ viewport + `clip`, `device_scale_factor=1` | ✅ width/height args | ⚠️ Puppeteer ✅; wkhtmltoimage uses old WebKit |
| CSS custom properties `var(--token)` | ✅ full | ❌ **not resolved** (per Satori README) | Puppeteer ✅; wkhtml ❌ partial |
| CSS Grid / `grid-template-areas` | ✅ full | ❌ **flexbox only, no grid** | Puppeteer ✅; wkhtml ❌ |
| `radial-gradient`, `backdrop-filter` | ✅ | ❌ no `radial-gradient`, no `backdrop-filter` | wkhtml ❌ |
| Web-font `@font-face` (Montserrat) | ✅ (must await `fonts.ready`) | ✅ but you pass font buffers manually | ⚠️ unreliable |
| Hero image compositing (`object-fit:cover`) | ✅ + `img.decode()` control | ✅ raster | ⚠️ |
| Determinism (same input→same pixels) | ✅ *if* fonts vendored + images decoded + `animations:"disabled"` | ✅✅ (no browser timing) | ❌ font/version drift |
| Batch of 4–11 slides | ✅ one browser, N contexts (~0.5–3 s/slide) | ✅✅ fastest, no binary | ⚠️ |
| Already in this codebase | ✅ **yes** | ❌ (Node/JSX, new stack) | partial |

Sources for the Satori CSS-subset facts: [Satori README](https://github.com/vercel/satori/blob/main/README.md)
states it implements "a subset of CSS" using the Yoga **flexbox** engine — *"`display: grid` is not
supported"*, CSS variables don't resolve, no `radial-gradient`, no `backdrop-filter`. General
Playwright-vs-Satori tradeoff (browser handles "fonts, gradients, flexbox and every other CSS feature"
vs Satori being faster but flexbox-only): [vercel/satori](https://github.com/vercel/satori).

**Recommendation (Dimension 1): Playwright-Python, headless Chromium.**

- Why not Satori: this brand is CSS-variable-native and the *entire premise* of this work order is
  "infinite layout combinations" — which Antonello's own brief and the brand docs implement with CSS
  Grid. Satori's flexbox-only + no-`var()` model would force throwing away `_base.css` and every
  `var(--token)` reference. The speed win (Satori ~tens of ms vs Playwright ~1 s/slide) is irrelevant
  for a 7–11-slide carousel rendered on operator demand, not at web scale.
- Why not wkhtmltoimage: dead/old WebKit, font drift, no modern CSS. Disqualified.
- Why not raw Puppeteer: it would work (it's Chromium too) but it's Node; the repo's renderer, the
  brand A4 renderer, and the war-room batch script are all **Python Playwright**. Stay in one stack.
- **Determinism note:** Chromium *can* be deterministic enough for "anteprima → dimmi cosa cambiare →
  re-render" if you (a) vendor fonts locally, (b) pin `device_scale_factor=1`, (c) decode images
  before shooting, (d) pass `animations="disabled"` to `screenshot()`, and (e) pin the Playwright/
  Chromium version (font rasterization differs across Chromium builds and OSes — see
  [Playwright #20097](https://github.com/microsoft/playwright/issues/20097)). Pixel-identical *across
  machines* is not guaranteed by any browser engine; pixel-identical *on the same machine/version* is
  achievable and is what this workflow needs.

Concrete engine skeleton (adapt the existing `PlaywrightClient.screenshot`):

```python
# one browser per batch; one context per slide for isolation
context = await browser.new_context(
    viewport={"width": 1080, "height": 1350},
    device_scale_factor=1,            # 1080px CSS == 1080px PNG. Use 2 only for @2x export.
)
page = await context.new_page()
await page.set_content(html, wait_until="domcontentloaded")  # NOT networkidle
await page.evaluate(WAIT_FOR_READY_JS)   # fonts.ready + img.decode() — see §4/§5
png = await page.screenshot(
    clip={"x": 0, "y": 0, "width": 1080, "height": 1350},
    type="png",
    animations="disabled",            # freeze any transitions for determinism
)
```

`set_content` (or the existing `data:` URL) is preferred over writing temp HTML files — fewer disk
race conditions (the repo has a documented history of sibling processes touching working dirs).

---

## Dimension 2 — Editorial layout families that compose infinitely inside one brand

The mechanism top editorial brands use is: **one canonical grid, many placement strings.** From
Smashing Magazine's editorial-grid work, the pattern is named grid lines / named areas that all
components reference, with variety produced by swapping which area each component occupies — *"work on
multiple variations of a layout by adding or removing a CSS class"* and *"make a custom layout by just
playing with the value of grid-template-areas"*
([Smashing — editorial patterns](https://www.smashingmagazine.com/2019/10/editorial-design-patterns-css-grid-subgrid-naming/),
[Smashing — grid-template-areas](https://www.smashingmagazine.com/understanding-css-grid-template-areas/),
[MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-areas)).

### Architecture pattern for WR2 (concrete)

**Step A — one fixed canvas grid in `_base.css` (brand-permanent):**

```css
.slide {
  width: var(--canvas-width);    /* 1080 */
  height: var(--canvas-height);  /* 1350 */
  display: grid;
  /* 12 columns inside the edge margin, named rail lines for full-bleed escapes */
  grid-template-columns:
    [bleed-start] var(--spacing-edge-margin)
    [content-start] repeat(12, 1fr)
    [content-end] var(--spacing-edge-margin) [bleed-end];
  grid-template-rows:
    [top] var(--spacing-edge-margin)
    [head-start] auto
    [head-end] 1fr
    [body-end] auto
    [foot] var(--spacing-logo-bottom) [bottom];
  column-gap: 24px;
  background: var(--color-bg-antracite);
}
```

**Step B — brand-locked components reference *named areas*, never raw coordinates:**

```css
.kicker   { grid-area: kicker;   color: var(--color-accent-yellow); /* uppercase, 36px */ }
.headline { grid-area: headline; color: var(--color-text-white);   /* 700/800, uppercase */ }
.rule     { grid-area: rule;     height: 4px; background: var(--color-accent-yellow); }
.body     { grid-area: body; }
.stat     { grid-area: stat;     color: var(--color-accent-yellow); /* 84–120px number */ }
.hero     { grid-area: hero;     /* full-bleed when placed bleed-start/bleed-end */ }
.source   { grid-area: source; }
```

**Step C — each layout-family is JUST a `grid-template-areas` string (the variety machine):**

```css
/* swiss-grid-asymmetry: headline hugs left 7 cols, stat block right 5 cols */
[data-layout="swiss-grid-asymmetry"] {
  grid-template-areas:
    ".       kicker   kicker   kicker   kicker   .        .      ."
    "headline headline headline headline headline stat   stat   stat"
    "headline headline headline headline headline stat   stat   stat"
    "rule    rule     rule     .        .        .        .      ."
    "body    body     body     body     body     body     .      ."
    "source  source   source   .        .        .        logo   logo";
}

/* stat-card-hero: huge number top, supporting copy below */
[data-layout="stat-card-hero"] {
  grid-template-areas:
    "kicker  kicker  kicker  .       .       .       .       ."
    "stat    stat    stat    stat    stat    stat    stat    stat"
    "stat    stat    stat    stat    stat    stat    stat    stat"
    "rule    .       .       .       .       .       .       ."
    "body    body    body    body    body    body    body    body"
    ".       .       .       .       .       .       logo    logo";
}

/* thin-red-rule-divider: classic FT/NYT column with a hairline rule */
[data-layout="thin-red-rule-divider"] {
  grid-template-areas:
    "kicker   kicker   kicker   kicker   .        .        .      ."
    "headline headline headline headline headline headline .     ."
    "rule     rule     rule     rule     rule     rule     rule  rule"  /* red, 1–2px */
    "body     body     body     body     body     .        .     ."
    "body     body     body     body     body     .        .     ."
    "source   source   source   .        .        .        logo  logo";
}
```

(The `.` cells are empty tracks — deliberate negative space, the single most "editorial" move.)

**How this gives "infinite within brand":**

- The *vocabulary* (colors, type scale, components, edge margin, logo position) is frozen in
  `_base.css` from `tokens.json` → identity is structurally guaranteed.
- The *grammar* (which area each component lands in, how many columns it spans, where the whitespace
  is) is one string per family → combinatorially huge variety. Add a new family = add one
  `grid-template-areas` block; nothing else changes.
- **Modular type scale** ties sizes together so variety never breaks rhythm: define a ratio (e.g.
  1.25 "major third") and derive sizes as CSS vars (`--step-0`, `--step-1`, …) so a "big stat"
  layout and a "dense list" layout still share one harmonic scale. The existing `tokens.json` already
  ships a discrete scale (`headline-cover` 84, `headline-slide` 60, `subheadline` 36, `body-lg` 32 …);
  keep it but expose `clamp()`-based variants for auto-fit headlines (see §3 legibility + overflow).
- **Per-slide overrides** stay declarative: the renderer already supports `heading_color: yellow|white`
  per-layout in `tokens.json layout_defaults`. Extend the same idea to `data-layout` + optional
  `data-density` modifiers rather than ad-hoc inline CSS.

This maps the four families Antonello already named (swiss-grid-asymmetry, stat-card-hero,
thin-red-rule-divider, monospace-evidence-block) plus the existing `.md` families (cover-photo,
dark-status-list, evidence-carved, statement-bomb, qa-dialogue, timeline-pinboard, elegant-close)
onto a single grid. **Recommendation:** migrate the per-family `.md` skeletons (which today each
re-declare their own `body{display:flex}` and bespoke CSS) to the single-grid + areas model so that
the renderer composes them, instead of each family being a hand-written one-off.

---

## Dimension 3 — Text-over-image legibility (WCAG AAA, the "Legibility Armor")

WCAG AAA = **7:1** for normal text, **4.5:1** for large text (≥24px bold / ≥18.66px)
([WCAG 1.4.6 guide](https://testparty.ai/blog/wcag-1-4-6-contrast-enhanced-2025-guide),
[WebAIM contrast](https://webaim.org/articles/contrast/)). Over a photo the contrast varies per pixel,
and WCAG gives no formula for images — the accepted rule is **measure against the lightest pixel the
text will sit on; if it passes there, it passes everywhere**
([WebAIM](https://webaim.org/articles/contrast/),
[accessible gradients](https://instantgradient.com/blog/accessible_gradient_guide)).

The robust SOTA technique (and what the brand already half-does) is a **scrim**: a semi-opaque
gradient between photo and text. The brand's `cover-photo` slide uses:

```css
.gradient {            /* existing — keep, but make the floor opaque enough for AAA */
  position: absolute; inset: 0;
  background: linear-gradient(180deg,
    rgba(0,0,0,0.0) 30%,
    var(--color-overlay-darken-60) 70%,   /* rgba(0,0,0,0.6) */
    var(--color-bg-black) 100%);          /* solid black floor where text sits */
}
```

**To guarantee AAA for white text:** the text must sit only where the scrim floor is dark enough.
White `#FFF` on `#000` is 21:1; white on `rgba(0,0,0,0.6)` over a *mid-grey* photo is roughly 4.5–6:1
(borderline). So the rule for the renderer:

1. **Confine text to a "safe band"** (e.g. bottom 40%) where the gradient is ≥0.78 opacity black, OR
   put text on a solid `--color-bg-black` plate. This makes the floor near-black regardless of the
   photo → AAA guaranteed by construction, no per-image math required. This is the cheapest, most
   bulletproof option and is what NYT/Bloomberg covers do (text on a darkened lower third).
2. **Adaptive scrim by image luminance (optional, higher polish):** sample the hero's mean luminance
   in the text zone (Pillow: downscale to the crop, compute relative luminance), then pick scrim
   opacity from a small ladder — bright image → 0.78–0.85, dark image → 0.55–0.65. Compute it
   server-side and inject as `--scrim-opacity`. Do this only if §1's fixed-band approach proves too
   conservative aesthetically.
3. **Belt-and-suspenders:** add `text-shadow: 0 2px 8px rgba(0,0,0,0.6)` (the brand already uses this
   on `evidence-carved` headings). Shadow alone does NOT satisfy WCAG, but on top of a compliant
   scrim it kills residual edge-glare. **Do not rely on `text-shadow` as the contrast mechanism** —
   it's not measurable and AAA tooling ignores it.
4. Avoid `mix-blend-mode`/`backdrop-filter` for the scrim: they're harder to verify and (per §1)
   would block any future Satori fallback. A plain `linear-gradient` + solid floor is deterministic.

**Recommendation:** ship the fixed dark-band scrim as the default Legibility Armor (AAA by
construction), keep `text-shadow` as cosmetic reinforcement, and gate hero text zones so copy can
never land in the transparent top of the gradient. Add an automated check (see §Checklist) that
computes contrast of the declared text color against the *worst-case* (lightest) pixel under the text
box and fails the render if < 7:1.

---

## Dimension 4 — Web-font determinism in headless rendering (THE #1 flake)

**Finding (verified in this repo):** Montserrat is **not installed locally** (no `*.woff2`/`*.ttf` in
`~/.claude/skills/bali-zero-brand/assets/`, none in macOS system font dirs), and every render path —
the layout `.md` skeletons, and even the brand's own `_render_smoke_test.py` — pulls Montserrat via
`@import url('https://fonts.googleapis.com/css2?family=Montserrat...')`. So **today the output font is
hostage to a network fetch at screenshot time.** When Google Fonts is slow/blocked, Chromium falls
back to the next family (`Inter`/`Poppins`/`sans-serif`) and the PNG silently ships in the wrong font.
The `wait_for_timeout(300)` sleep in `render.py` is a band-aid that hides this most of the time.

Why this is the classic failure: by default Playwright waits on font *network requests* before a
screenshot, and that wait can hang or vary; teams ship `PW_TEST_SCREENSHOT_NO_FONTS_READY` precisely
because font loading is the slow/flaky part
([Momentic pitfalls](https://momentic.ai/blog/playwright-pitfalls),
[Playwright #35200](https://github.com/microsoft/playwright/issues/35200)). Font rasterization also
differs machine-to-machine ([Playwright #20097](https://github.com/microsoft/playwright/issues/20097)),
so a *local, pinned* font file removes the largest source of nondeterminism. Base64/`@font-face`
inlining is the standard determinism move because the bytes are inline and depend on no network
(search synthesis from font-embedding sources).

**Recommendation (do all three):**

1. **Vendor the font files.** Download `Montserrat-Bold.woff2` (700) and `Montserrat-ExtraBold.woff2`
   (800) + `IBMPlexMono-Regular.woff2` once, commit them next to `_base.css`, and declare:

   ```css
   @font-face {
     font-family: 'Montserrat';
     font-style: normal; font-weight: 700;
     src: url('fonts/Montserrat-Bold.woff2') format('woff2');
     font-display: block;   /* block, not swap — never show fallback during render */
   }
   @font-face { /* 800 ExtraBold, same pattern */ }
   @font-face { font-family: 'IBM Plex Mono'; font-weight: 400;
     src: url('fonts/IBMPlexMono-Regular.woff2') format('woff2'); font-display: block; }
   ```

   Remove every `@import url('https://fonts.googleapis.com/...')`. `font-display: block` ensures the
   browser uses *no* text rather than fallback text while the (local, instant) font resolves —
   eliminating fallback-flash entirely.
   - When rendering via a `data:` URL or `set_content` (no base dir), either base64-inline the woff2
     into the `@font-face src: url(data:font/woff2;base64,...)`, OR serve the working dir so relative
     `fonts/…` resolves. Base64 inlining is the most hermetic (zero filesystem/URL dependency) and is
     the recommended default for the data-URL path the existing `PlaywrightClient` uses.

2. **Await fonts before shooting (and fix the existing bug).** The war-room `render.py` calls
   `page.evaluate("document.fonts.ready")` **without awaiting the returned promise** — it resolves
   instantly and does nothing. Use:

   ```js
   await document.fonts.ready;                 // inside page.evaluate, properly awaited
   ```

   With local fonts this returns in ~0 ms and is *guaranteed* satisfied (not a timed gamble).

3. **Drop the `wait_for_timeout(300)` sleep** once 1+2 are in place. Replace `wait_until="networkidle"`
   with `domcontentloaded` + the explicit readiness `evaluate` (networkidle is explicitly discouraged
   as flaky — [Playwright pitfalls](https://momentic.ai/blog/playwright-pitfalls),
   [Playwright screenshots docs](https://playwright.dev/docs/screenshots)).

This single change (vendor + `font-display:block` + awaited `fonts.ready`) converts the renderer from
"usually the right font" to "always the right font, no sleep."

---

## Dimension 5 — Hero image placement (the EXACT thing Canva failed at)

Canva's path failed because images silently didn't appear. The HTML path must make "image present and
fully painted" a *gate*, not a hope. `networkidle` is NOT sufficient (it's discouraged and fires on
unrelated activity); the robust primitive is the per-image **`HTMLImageElement.decode()`** promise,
which resolves only when the image is downloaded *and decoded* and safe to paint
([MDN decode()](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode),
[Playwright image-load Q&A](https://ray.run/questions/how-do-i-ensure-that-all-images-are-fully-loaded-before-taking-a-screenshot-in-playwright)).

**Use a real `<img>` for the hero, not a CSS `background-image`.** The current `cover-photo` layout
uses `background-image: url(...)` on a `.hero` div — backgrounds give you **no load event and no
`decode()` handle**, so you can't reliably await them; that is precisely the "image not appearing"
class of bug. Switch to:

```html
<img class="hero" src="{{tigris_url}}"
     style="object-fit: cover; object-position: var(--focal, 50% 38%);">
```
```css
.hero { grid-area: hero; width: 100%; height: 100%;
        object-fit: cover; }   /* fill the cell, crop overflow, no distortion */
```

**Readiness gate (the bulletproof part), run before screenshot:**

```js
async () => {
  await document.fonts.ready;                       // §4
  const imgs = Array.from(document.images);
  await Promise.all(imgs.map(async (img) => {
    if (!img.complete || img.naturalWidth === 0) {
      // force load even if lazy/offscreen
      try { await img.decode(); } catch (e) { /* surface as render error, do not silently pass */ }
    } else {
      try { await img.decode(); } catch (e) {}
    }
  }));
  // double rAF so the decoded pixels are actually committed to the frame buffer
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
}
```

Then in Python: also set a hard navigation timeout and **fail loudly** if a hero never decodes — the
existing `ScreenshotResult(ok=False, error=...)` graceful-degradation shape is ideal; the renderer
must return `ok=False` (not a blank PNG) when the Tigris image 404s, so the pipeline can retry rather
than publish an empty slide. (This is the direct antidote to the Canva failure mode.)

**Robustness add-ons for remote Tigris URLs:**

- Pre-flight the URL server-side (HEAD/GET 200 + content-type image) *before* building HTML; or,
  better, **download the hero to the working dir and reference it locally** (or base64-inline it).
  Local bytes remove network timing from the render entirely — same philosophy as vendored fonts.
  The repo already co-locates `1-hero.jpg` next to `1.html` in working examples; keep that pattern.
- Set `loading="eager"` (or omit `loading` — default is eager) so Chromium doesn't defer offscreen
  heroes; never `loading="lazy"` for render targets.
- **Focal point:** expose `object-position` as a per-slide token (`--focal: 50% 38%`) so the operator
  can nudge the crop ("more sky / show the face") without re-cropping the source — variety knob #2.
- Pin `device_scale_factor=1` for 1080×1350 exact; optionally render a `@2x` (factor 2 → 2160×2700)
  master and downscale with Pillow/sharp for crisper text if IG compression artifacts show.

---

## Dimension 6 — Competitor + editorial reference (actionable steal-list)

**Indonesian visa/company competitors (the foil):** LetsMoveIndonesia (~8k IG followers) and Emerhub
sell *hospitality and reassurance* — bright, friendly, "seamless transition," price-transparency
positioning ([LetsMoveIndonesia IG](https://www.instagram.com/letsmoveindonesia/),
[Emerhub](https://emerhub.com/indonesia/moving-to-indonesia-an-expats-guide/)). The brand cortex
already names them as the explicit anti-pattern: *"they sell hospitality and reassurance; Bali Zero
tells you what's at stake and cites the regulation verbatim."* **Do not imitate them** — the
differentiator IS the dark, investigative, sourced look. Their weakness to exploit: generic
template/infographic aesthetics and no regulatory citations.

**Editorial leaders worth stealing from (for a regulatory/legal carousel):**

- **Rest of World** — dark palette to make images pop; B/W → color on state change; *guides attention
  via restraint* ([RoW product retro](https://restofworld.org/inside/rest-of-worlds-product-team-looks-back-at-2023/)).
  Steal: dark canvas + one decisive accent (already the brand), and let one image dominate per slide.
- **NYT IG slides** — built explicitly to make stories *digestible*: one idea per slide, big type,
  consistent cover treatment so the series is recognizable in-feed
  ([NiemanLab on NYT slides](https://www.niemanlab.org/2021/07/the-new-york-times-is-using-instagram-slides-and-twitter-cards-to-make-stories-more-digestible/)).
  Steal: **cover consistency** (same font pairing + accent + title placement so followers recognize a
  Bali Zero carousel instantly — the brand's mandatory cover-photo + regulation badge already does
  this; enforce it), and **slide-1-is-a-promise** (a claim/stake, not decoration).
- **FT/Bloomberg** — hairline rules, generous column whitespace, restrained 1–2 weight type, data
  emphasized in the accent color. Steal: the **thin red rule divider** (already a named family) and
  ruthless negative space (empty grid cells) as the signal of "serious publication, not a template."

General carousel mechanics worth honoring (from the editorial-carousel synthesis): 8–12 slides is the
sweet spot for breakdowns; slide 1 must promise a payoff; every slide must be screenshot-friendly
(big type, minimal clutter); cluttered slides lose the reader before the payoff. All of this is
already encoded in the brand constitution (7–10 slides, statement-bomb close, 25–50 words/slide) —
the renderer just has to make it *easy to obey and hard to violate*.

---

## TECH-STACK RECOMMENDATION (build exactly this)

1. **Engine:** Python + Playwright (async), headless Chromium. Reuse and harden
   `apps/backend-rag/backend/services/layout/playwright_client.py`. **Pin the Playwright version**
   (and thus the Chromium build) in the venv so rasterization is stable run-to-run.
2. **Input contract:** a slide dict / Pydantic model →
   `{ layout_family, kicker, headline, subhead, body[], stat?, hero_url?, focal?, source?,
   regulation_code? }`. Renderer maps `layout_family` → a `data-layout` attribute (the
   `grid-template-areas` selector). One model, N families.
3. **Styling:** keep `tokens.json` as the single source of truth; auto-generate the `:root` block of
   `_base.css` from it (already the documented design). Add the **single canonical grid** to
   `_base.css` and one `grid-template-areas` block per family. **Migrate the per-family `.md`
   skeletons onto this grid** (retire their bespoke `flex` CSS).
4. **Fonts:** **vendor `Montserrat-Bold.woff2`, `Montserrat-ExtraBold.woff2`,
   `IBMPlexMono-Regular.woff2`** into `~/.claude/skills/bali-zero-brand/layouts/fonts/`, declare via
   local `@font-face` with `font-display: block`, base64-inline them into the HTML when using the
   `data:`-URL path, and **delete all Google-Fonts `@import`s**. This is the single highest-value fix.
5. **Hero images:** real `<img>` (not CSS background) + `object-fit: cover` + `object-position` from a
   `--focal` token; **download Tigris hero locally (or base64-inline) before render**; gate on
   `Promise.all(images.map(i => i.decode()))` + double-rAF; return `ok=False` on any image failure.
6. **Legibility Armor:** default fixed dark-band gradient scrim (AAA by construction) +
   `text-shadow` cosmetic reinforcement; confine hero text to the dark band; optional luminance-
   adaptive `--scrim-opacity` computed with Pillow for polish.
7. **Screenshot call:** `page.set_content(html, wait_until="domcontentloaded")` → awaited readiness
   `evaluate` (fonts + images) → `page.screenshot(clip={0,0,1080,1350}, type="png",
   animations="disabled")`. **No `networkidle`, no `wait_for_timeout` sleep.**
8. **Output:** 1080×1350 PNG per slide, `device_scale_factor=1` (offer `@2x` master + Pillow
   downscale as an option). Persist with the existing working-dir convention (heroes + html + png
   co-located), which also gives the operator a re-renderable artifact.
9. **Operator loop:** because rendering is ~1 s/slide and deterministic, the
   "anteprima → dimmi cosa cambiare → re-render in 2s" loop Antonello wants is native — expose
   per-slide knobs as tokens/attributes (`data-layout`, `--focal`, `heading_color`, `data-density`)
   so changes are declarative, never hand-edited CSS.
10. **Law 5:** renderer terminates at PNG (status `rendered`); **no Instagram/Graph publish call.**
    Manual publish by Damar stays manual (consistent with the live WR2 pipeline B).

---

## CHECKLIST — must-haves for the renderer (gate before "done")

**Determinism (the flake killers):**
- [ ] Montserrat 700 + 800 and IBM Plex Mono vendored locally (woff2 on disk or base64); **zero**
      `fonts.googleapis.com` references remain (`grep -r googleapis` → empty).
- [ ] `@font-face` uses `font-display: block`.
- [ ] Readiness gate `await document.fonts.ready` is **actually awaited** (fix the existing un-awaited bug).
- [ ] All `<img>` awaited via `Promise.all(images.map(i => i.decode()))` + double `requestAnimationFrame`.
- [ ] `wait_until` is `domcontentloaded`; **no `networkidle`, no fixed `wait_for_timeout` sleep**.
- [ ] `device_scale_factor` pinned (1 for native, 2 only for explicit @2x master).
- [ ] Playwright/Chromium version pinned in the venv.
- [ ] `screenshot(animations="disabled")`.

**Correctness:**
- [ ] Output is exactly 1080×1350 (assert `naturalWidth/Height` on the PNG, as the smoke test does).
- [ ] Hero is a real `<img object-fit:cover>` (not CSS `background-image`); `object-position` from `--focal`.
- [ ] Renderer returns `ok=False` + error (never a blank/wrong PNG) when a hero fails to load/decode.
- [ ] Hero downloaded locally or base64-inlined before render (no live-network dependency at shoot time).

**Brand + layout:**
- [ ] `:root` tokens generated from `tokens.json` (no hardcoded hex outside `_base.css :root`).
- [ ] One canonical CSS Grid in `_base.css`; each family = one `grid-template-areas` block.
- [ ] All families migrated onto the single grid (no per-family bespoke `flex` layouts left).
- [ ] Palette region-aware: banned colors enforced in text/UI zones only, allowed inside hero photo
      (per constitution Art 2.3).
- [ ] Logo, swipe-indicator (slides 2..N-1), regulation badge (cover when code present), source footer
      render from shared `_base.css` components.

**Legibility (WCAG AAA):**
- [ ] Hero text confined to dark-band scrim (≥0.78 black floor) OR on a solid black plate.
- [ ] Automated contrast check: declared text color vs **lightest** pixel under the text box ≥ 7:1
      (normal) / 4.5:1 (large) — fail the render otherwise.
- [ ] `text-shadow` used only as cosmetic reinforcement, never as the contrast mechanism.

**Process:**
- [ ] Renderer stops at `rendered` PNG — no IG publish (Legge 5).
- [ ] Per-slide knobs (`data-layout`, `--focal`, `heading_color`, `data-density`) are declarative for
      the fast operator re-render loop.

---

## Notes / open risks for the implementing agent

- **Cross-machine pixel identity is not guaranteed** by any engine; same-machine/same-version identity
  is. If renders must match across Pro/Mini, render on one designated host or run Chromium in a pinned
  Docker image ([Playwright #20097](https://github.com/microsoft/playwright/issues/20097)).
- **`set_content` vs `data:` URL vs temp file:** prefer `set_content` or `data:` URL (the existing
  client) to avoid the repo's documented sibling-process working-dir races; if you base64-inline fonts
  and hero, the HTML becomes fully hermetic and path-independent.
- **Reuse, don't rebuild:** `PlaywrightClient` (data-URL screenshot), `_base.css` (tokens),
  `_render_smoke_test.py` (1080×1350 + fonts.ready assertions), and the working
  `apps/war-room/output/carousel/*/slides/` examples are the starting material. The new work is
  (1) vendor fonts, (2) the single-grid + `grid-template-areas` family layer, (3) `<img>`+`decode()`
  hero gate, (4) the AAA scrim default + contrast check, (5) consolidate the per-family `.md`s.
- **Verify the autopsy/handoff file:line refs before building on them** (standing repo discipline:
  the WR2 autopsy hallucinated 3 file:line citations — re-`grep`/`Read` each load-bearing path).
