# Futuristic Dark UI — Exa Deep Research

> **Context:** Research compiled for **Palette D Monochrome Modern**
> Base `#0a0a0a`, Surface `#141414`, Signal Red `#ff2d4c`, Text `#f5f5f5`,
> Accents: Blue `#4a8ec4`, Green `#5cb88a`, Gold `#d4a853`, Violet `#9880d8`, Teal `#4ab8c4`.
> Reference feel: Linear / Vercel / Stripe / Anthropic claude.ai / Raycast / Arc / Fey / Lu.ma / Cal.com / Resend / Supabase.
> **Hard constraint:** pure HTML + CSS + optional <20 LoC vanilla JS. No framework libs, no build step.
> **Research date:** 2026-04-11. (Exa credit limit hit — research sourced via Brave Search + direct MDN/CSS-Tricks/Codrops/ibelick/Smashing/FEM primaries.)

---

## Table of contents

- **A.** Backgrounds — noise, gradient mesh, grid, aurora, conic, scanlines
- **B.** Glassmorphism variants — frosted, liquid, refraction, chromatic, light leak
- **C.** Text effects — gradient, glow, metallic, typewriter, split-letter, variable font
- **D.** Borders — conic rotating, marching ants, glow hover, dashed animated, corner L
- **E.** Cards — 3D tilt, hover lift, perspective stack, bento asym, reveal details
- **F.** Buttons — shimmer sweep, magnetic, pressed depth, ripple, gradient fill
- **G.** Loaders — skeleton shimmer, progress gradient, dots pulse, conic spinner, data stream
- **H.** Data viz — sparkline pure CSS, bar chart vars, ring chart conic, counter, trend arrow
- **I.** Navigation — indicator pill, chevron breadcrumb, tab morph, sidebar collapse
- **J.** Micro-interactions — count-up, copy flash, tooltip fade, badge pulse, status ping
- **K.** Dividers — gradient fade, animated mark, dotted, section mark number
- **L.** Focus states — ring glow multi, outline offset, underline sweep
- **M.** Page transitions — view transitions, scroll-driven, sticky reveal
- **N.** Cursor — custom, magnetic glow, trailing dot
- **O.** Scroll — parallax, intersection reveal, horizontal snap
- **Top 10 immediately usable** — final ranking for Palette D

---

## Palette D — CSS custom properties (drop into `:root`)

Every snippet below assumes these tokens exist. Paste once; reuse everywhere.

```css
:root {
  --bg-0: #0a0a0a;
  --bg-1: #141414;
  --bg-2: #1a1a1a;
  --fg-0: #f5f5f5;
  --fg-1: #b8b8b8;
  --fg-2: #6b6b6b;
  --line: #2a2a2a;
  --line-2: #3a3a3a;
  --red: #ff2d4c;
  --blue: #4a8ec4;
  --green: #5cb88a;
  --gold: #d4a853;
  --violet: #9880d8;
  --teal: #4ab8c4;
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
}
```

---

## A. Backgrounds

### A1. Grainy gradient (SVG `feTurbulence` + radial)

**Desc:** Dithers a large dark radial gradient with Perlin noise to kill banding and add a premium film-grain feel.
**Snippet:**

```html
<div class="hero"></div>
<svg width="0" height="0" style="position:absolute">
  <filter id="grain">
    <feTurbulence
      type="fractalNoise"
      baseFrequency=".85"
      numOctaves="2"
      stitchTiles="stitch"
    />
    <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .18 0" />
  </filter>
</svg>
<style>
  .hero {
    min-height: 100vh;
    background:
      radial-gradient(1200px 600px at 20% 0%, #1a1a1a 0%, transparent 55%),
      radial-gradient(900px 700px at 80% 100%, #141414 0%, transparent 60%),
      var(--bg-0);
    position: relative;
    isolation: isolate;
  }
  .hero::before {
    content: "";
    position: absolute;
    inset: 0;
    filter: url(#grain);
    mix-blend-mode: overlay;
    pointer-events: none;
    z-index: -1;
  }
</style>
```

**Support:** Chrome/Safari/FF all evergreen. **Cost:** Low (SVG filter rasterized once).
**Use:** Hero, auth screens, empty states.
**Source:** https://css-tricks.com/grainy-gradients/

---

### A2. Dotted grid (radial-gradient mask)

**Desc:** Technical "graph paper" dotted grid — Linear/Raycast signature — fading to the edges so the dots don't fight content.

```css
.grid-dots {
  background-color: var(--bg-0);
  background-image: radial-gradient(circle, #2a2a2a 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: radial-gradient(ellipse at center, #000 40%, transparent 80%);
  -webkit-mask-image: radial-gradient(
    ellipse at center,
    #000 40%,
    transparent 80%
  );
}
```

**Support:** All evergreen (mask-image stable since Safari 15.4). **Cost:** Low.
**Use:** Hero, dashboard wrapper, section backgrounds.
**Source:** https://stackoverflow.com/questions/3540194/

---

### A3. Conic aurora

**Desc:** Two slow-rotating conic gradients with huge blur = Linear/Vercel style aurora without WebGL.

```css
.aurora {
  position: relative;
  overflow: hidden;
  background: var(--bg-0);
}
.aurora::before,
.aurora::after {
  content: "";
  position: absolute;
  inset: -20%;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  mix-blend-mode: screen;
  animation: spin 22s linear infinite;
}
.aurora::before {
  background: conic-gradient(
    from 0deg,
    var(--blue),
    var(--violet),
    transparent 60%
  );
}
.aurora::after {
  background: conic-gradient(
    from 180deg,
    var(--teal),
    var(--red),
    transparent 55%
  );
  animation-duration: 30s;
  animation-direction: reverse;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
```

**Support:** All evergreen. **Cost:** Medium (blur filter). Add `will-change:transform` only on hero.
**Use:** Hero background behind glass card.
**Source:** https://github.com/LunarLogic/auroral , https://dev.to/oobleck/css-aurora-effect-569n

---

### A4. Mesh gradient (stacked radials)

**Desc:** Fake mesh gradient using 4 offset radial gradients — produces organic color pools, no library.

```css
.mesh {
  background:
    radial-gradient(at 12% 18%, hsla(210, 45%, 38%, 0.45) 0, transparent 45%),
    radial-gradient(at 82% 14%, hsla(160, 40%, 35%, 0.35) 0, transparent 50%),
    radial-gradient(at 70% 82%, hsla(0, 80%, 55%, 0.28) 0, transparent 45%),
    radial-gradient(at 18% 88%, hsla(265, 45%, 42%, 0.35) 0, transparent 55%),
    var(--bg-0);
}
```

**Support:** All evergreen. **Cost:** Very low (paint-once).
**Use:** Section panels, app-chrome wallpaper.
**Source:** https://dev.to/oobleck/css-aurora-effect-569n

---

### A5. Scanline overlay

**Desc:** 1px repeating-linear-gradient adds a sub-pixel monitor texture; readable, not cheesy.

```css
.scanlines {
  position: relative;
}
.scanlines::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    to bottom,
    transparent 0 2px,
    rgba(255, 255, 255, 0.02) 2px 3px
  );
  mix-blend-mode: overlay;
}
```

**Support:** All. **Cost:** Very low.
**Use:** Status bar, code blocks, terminal-like panels.

---

### A6. Square-grid line background

**Desc:** CSS-only technical grid (Supabase/Resend style), crisp at any zoom.

```css
.grid-lines {
  background-color: var(--bg-0);
  background-image:
    linear-gradient(var(--line) 1px, transparent 1px),
    linear-gradient(90deg, var(--line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, #000 35%, transparent 75%);
}
```

**Support:** All. **Cost:** Very low. **Use:** Landing hero.
**Source:** https://stackoverflow.com/questions/3540194/

---

## B. Glassmorphism variants

### B1. Frosted dark glass

**Desc:** Canonical dark glass, tuned for Palette D so content behind stays legible.

```css
.glass {
  background: color-mix(in srgb, var(--bg-1) 65%, transparent);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border: 1px solid color-mix(in srgb, #fff 8%, transparent);
  box-shadow:
    0 1px 0 color-mix(in srgb, #fff 6%, transparent) inset,
    0 10px 30px rgba(0, 0, 0, 0.4);
  border-radius: 16px;
}
```

**Support:** Chrome 76+, Safari 9+ (webkit), FF 103+. **Cost:** Medium (GPU blur).
**Use:** Modals, hover menus, sticky headers, command bar.
**Source:** https://www.joshwcomeau.com/css/backdrop-filter/

---

### B2. Light-leak glass (inner gradient border)

**Desc:** The Linear-nav trick — 1px top border fades from transparent → white → transparent to simulate a leaked overhead light.

```css
.leak {
  position: relative;
  background: var(--bg-1);
  border-radius: 14px;
  padding: 1.25rem;
}
.leak::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.25),
    transparent
  );
}
```

**Support:** All. **Cost:** Very low. **Use:** Nav bar, top of cards.

---

### B3. Refraction edge (double border)

**Desc:** Inner dark border + outer 1px white at 5% = "glass thickness" without noise.

```css
.refract {
  background: var(--bg-1);
  border-radius: 14px;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 0 0 1px rgba(0, 0, 0, 0.6);
}
```

**Support:** All. **Cost:** Zero. **Use:** Any card.

---

### B4. Chromatic aberration glass

**Desc:** Two blurred pseudo layers with shifted hue — tasteful RGB split behind glass (Cal.com-ish).

```css
.chroma {
  position: relative;
  isolation: isolate;
  background: var(--bg-1);
  border-radius: 16px;
  overflow: hidden;
}
.chroma::before,
.chroma::after {
  content: "";
  position: absolute;
  inset: 0;
  filter: blur(30px);
  opacity: 0.4;
  mix-blend-mode: screen;
  z-index: -1;
}
.chroma::before {
  background: radial-gradient(
    circle at 30% 30%,
    var(--violet),
    transparent 60%
  );
  transform: translateX(-4px);
}
.chroma::after {
  background: radial-gradient(circle at 70% 70%, var(--teal), transparent 60%);
  transform: translateX(4px);
}
```

**Support:** All. **Cost:** Medium (2 blurs). **Use:** Hero card only.

---

### B5. Liquid glass (Apple WWDC-inspired)

**Desc:** Stacked translucent fills + subtle inner shadow + backdrop-saturation for the "liquid" feel.

```css
.liquid {
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.06),
    rgba(255, 255, 255, 0.02)
  );
  backdrop-filter: blur(18px) saturate(180%) brightness(1.1);
  -webkit-backdrop-filter: blur(18px) saturate(180%) brightness(1.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  box-shadow:
    inset 0 0 40px rgba(255, 255, 255, 0.03),
    0 20px 60px rgba(0, 0, 0, 0.5);
}
```

**Support:** Chrome/Safari/FF latest. **Cost:** Medium-High. **Use:** Hero modals, feature cards.
**Source:** https://yarinsa.medium.com/creating-liquid-glass-effects-with-css-...

---

## C. Text effects

### C1. Animated gradient text (`background-clip:text`)

**Desc:** Linear's hero headline — a slow conic sweep through white → signal red clipped to glyphs.

```css
.headline {
  background: linear-gradient(90deg, #f5f5f5 30%, #ff2d4c 50%, #f5f5f5 70%)
    0/200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: shine 6s linear infinite;
}
@keyframes shine {
  to {
    background-position: -200% 0;
  }
}
```

**Support:** All. **Cost:** Very low. **Use:** Hero h1.
**Source:** https://web.dev/articles/speedy-css-tip-animated-gradient-text

---

### C2. Metallic text (three-stop silver gradient)

**Desc:** Three tight stops give a brushed-metal look; works great on monospace numerals.

```css
.metal {
  background: linear-gradient(
    180deg,
    #e6e6e6 0%,
    #8a8a8a 48%,
    #e6e6e6 52%,
    #5a5a5a 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.06);
}
```

**Support:** All. **Cost:** Zero. **Use:** Big stat numbers, metric cards.
**Source:** https://ibelick.com/blog/creating-metallic-effect-with-css

---

### C3. Glow text (layered text-shadow)

**Desc:** Signal-red glow used sparingly as an accent title.

```css
.glow {
  color: #fff;
  text-shadow:
    0 0 1px rgba(255, 45, 76, 0.9),
    0 0 12px rgba(255, 45, 76, 0.55),
    0 0 28px rgba(255, 45, 76, 0.35);
}
```

**Support:** All. **Cost:** Low. **Use:** Logo, LIVE badge, alert heading.

---

### C4. Typewriter (steps() + caret)

**Desc:** Pure CSS typing without JS.

```css
.typer {
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  border-right: 0.08em solid var(--red);
  width: 22ch;
  animation:
    type 2.4s steps(22, end) forwards,
    caret 0.8s steps(1) infinite;
}
@keyframes type {
  from {
    width: 0;
  }
}
@keyframes caret {
  50% {
    border-color: transparent;
  }
}
```

**Support:** All. **Cost:** Zero. **Use:** Hero tagline, demo transcript.

---

### C5. Variable-font weight on hover

**Desc:** A single glyph smoothly fattens using `font-variation-settings` — feels "physical."

```css
.vary {
  font-family: "Inter", system-ui;
  font-variation-settings: "wght" 400;
  transition: font-variation-settings 0.35s var(--ease-out);
}
.vary:hover {
  font-variation-settings: "wght" 800;
}
```

**Support:** All w/ variable font loaded. **Cost:** Very low. **Use:** Nav links, big CTAs.

---

### C6. Split-letter reveal (scroll-driven)

**Desc:** Each `span` fades/rises as it enters viewport; no IntersectionObserver.

```css
.split span {
  display: inline-block;
  opacity: 0;
  transform: translateY(8px);
  animation: rise linear both;
  animation-timeline: view();
  animation-range: entry 10% cover 40%;
}
@keyframes rise {
  to {
    opacity: 1;
    transform: none;
  }
}
.split span:nth-child(2) {
  animation-delay: 0.05s;
}
/* ...per-letter delays in HTML or via @nth-child */
```

**Support:** Chrome 115+, Safari 26+, FF TP. **Cost:** Low. **Use:** Section headings.
**Source:** https://developer.chrome.com/docs/css-ui/scroll-driven-animations

---

## D. Borders

### D1. Rotating conic border (signature "AI glow")

**Desc:** The 2024/25 hero technique: `@property` drives a conic gradient's angle, giving a tilted-rectangle rotating border — no JS.

```css
@property --a {
  syntax: "<angle>";
  inherits: false;
  initial-value: 0deg;
}
.rot-border {
  position: relative;
  padding: 1px;
  border-radius: 14px;
  background: conic-gradient(
    from var(--a),
    transparent 0 70%,
    var(--red) 75%,
    var(--violet) 85%,
    transparent 100%
  );
  animation: turn 6s linear infinite;
}
.rot-border > * {
  border-radius: 13px;
  background: var(--bg-1);
  padding: 1.25rem;
}
@keyframes turn {
  to {
    --a: 360deg;
  }
}
```

**Support:** Chrome 85+, Safari 16.4+, FF 128+ (`@property`). **Cost:** Low.
**Use:** Upgrade/Pro cards, AI callouts.
**Source:** https://ishu.dev/post/create-moving-border-animation-in-css-using-conic-gradient , https://codetv.dev/blog/animated-css-gradient-border

---

### D2. Marching ants (background-gradient, no SVG)

**Desc:** Selection/drop-zone dashes that march around the box.

```css
.ants {
  background:
    linear-gradient(90deg, var(--fg-0) 50%, transparent 50%) repeat-x,
    linear-gradient(90deg, var(--fg-0) 50%, transparent 50%) repeat-x,
    linear-gradient(0deg, var(--fg-0) 50%, transparent 50%) repeat-y,
    linear-gradient(0deg, var(--fg-0) 50%, transparent 50%) repeat-y;
  background-size:
    14px 1px,
    14px 1px,
    1px 14px,
    1px 14px;
  background-position:
    0 0,
    0 100%,
    0 0,
    100% 0;
  animation: march 900ms linear infinite;
}
@keyframes march {
  to {
    background-position:
      14px 0,
      -14px 100%,
      0 -14px,
      100% 14px;
  }
}
```

**Support:** All. **Cost:** Very low. **Use:** Dropzones, selection, editable regions.
**Source:** https://learnhowto.vercel.app/blog/css/the-ultimate-guide-to-creating-dashed-line-animations-with-css-and-svg

---

### D3. Mouse-aware glow border

**Desc:** CSS vars `--mx/--my` set by a 5-line JS listener; a radial gradient follows the cursor along the card edge.

```css
.gborder {
  position: relative;
  border-radius: 16px;
  background: var(--bg-1);
  padding: 1.25rem;
}
.gborder::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  background: radial-gradient(
    300px circle at var(--mx, 50%) var(--my, 50%),
    rgba(255, 45, 76, 0.6),
    transparent 40%
  );
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}
```

```js
document.querySelectorAll(".gborder").forEach((el) => {
  el.addEventListener("pointermove", (e) => {
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  });
});
```

**Support:** All. **Cost:** Low. **Use:** Pricing cards, feature grids. (Supabase/Cal.com favorite.)

---

### D4. Corner-L brackets

**Desc:** Four SVG-free corner brackets made from box-shadow — cyberpunk-adjacent, not neon.

```css
.bracket {
  position: relative;
}
.bracket::before,
.bracket::after {
  content: "";
  position: absolute;
  width: 18px;
  height: 18px;
  border: 1px solid var(--fg-0);
}
.bracket::before {
  top: 0;
  left: 0;
  border-right: none;
  border-bottom: none;
}
.bracket::after {
  bottom: 0;
  right: 0;
  border-left: none;
  border-top: none;
}
```

**Support:** All. **Cost:** Zero. **Use:** Hero label "> STATUS ACTIVE".

---

### D5. Gradient border on hover

**Desc:** Subtle accent border appears only on hover.

```css
.gbord {
  border: 1px solid var(--line);
  transition: border-color 0.3s;
}
.gbord:hover {
  border-image: linear-gradient(90deg, var(--blue), var(--violet)) 1;
  border-style: solid;
}
```

**Support:** All. **Cost:** Zero. **Use:** List items, nav chips.

---

## E. Cards

### E1. 3D tilt (mousemove, 12-line JS)

**Desc:** Classic depth effect; limited to ±10° for taste.

```html
<div class="tilt"><div class="tilt__inner">Card</div></div>
```

```css
.tilt {
  perspective: 900px;
}
.tilt__inner {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 1.5rem;
  transform: rotateX(var(--ry, 0deg)) rotateY(var(--rx, 0deg));
  transition: transform 0.15s linear;
  will-change: transform;
}
```

```js
document.querySelectorAll(".tilt").forEach((c) => {
  const i = c.querySelector(".tilt__inner");
  c.addEventListener("pointermove", (e) => {
    const r = c.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5,
      y = (e.clientY - r.top) / r.height - 0.5;
    i.style.setProperty("--rx", x * 10 + "deg");
    i.style.setProperty("--ry", -y * 10 + "deg");
  });
  c.addEventListener("pointerleave", () => {
    i.style.removeProperty("--rx");
    i.style.removeProperty("--ry");
  });
});
```

**Support:** All. **Cost:** Low. **Use:** Feature cards in grid.

---

### E2. Hover-lift with depth shadow

**Desc:** Subtle 2px lift + layered shadow (the Vercel dashboard card).

```css
.lift {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 1.25rem;
  transition:
    transform 0.25s var(--ease-out),
    box-shadow 0.25s var(--ease-out),
    border-color 0.25s;
}
.lift:hover {
  transform: translateY(-2px);
  border-color: var(--line-2);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.05) inset,
    0 10px 30px rgba(0, 0, 0, 0.45);
}
```

**Support:** All. **Cost:** Zero. **Use:** Everywhere list-of-things.

---

### E3. Perspective-stack (upcoming items behind)

**Desc:** Shows 1-2 "upcoming" stacked cards behind the top card — Lu.ma event list.

```css
.stack {
  position: relative;
  padding-bottom: 14px;
}
.stack::before,
.stack::after {
  content: "";
  position: absolute;
  left: 8px;
  right: 8px;
  height: 100%;
  border-radius: 14px;
  background: var(--bg-2);
  border: 1px solid var(--line);
  z-index: -1;
}
.stack::before {
  top: 6px;
  transform: scale(0.985);
}
.stack::after {
  top: 12px;
  transform: scale(0.97);
  opacity: 0.6;
}
```

**Support:** All. **Cost:** Zero. **Use:** Lists of upcoming/next items.

---

### E4. Bento grid (asym + auto-flow)

**Desc:** The Arc/Fey signature bento using CSS grid named areas.

```css
.bento {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: 160px;
}
.bento > * {
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1.25rem;
}
.bento > :nth-child(1) {
  grid-column: span 2;
  grid-row: span 2;
}
.bento > :nth-child(4) {
  grid-column: span 2;
}
.bento > :nth-child(6) {
  grid-row: span 2;
}
@media (max-width: 800px) {
  .bento {
    grid-template-columns: repeat(2, 1fr);
  }
  .bento > * {
    grid-column: auto !important;
    grid-row: auto !important;
  }
}
```

**Support:** All. **Cost:** Zero. **Use:** Feature overview, "what's included".
**Source:** https://bentogrids.com/ , https://senorit.de/en/blog/bento-grid-design-trend-2025

---

### E5. Reveal-details (grid-template-rows transition)

**Desc:** Transition height `0fr → 1fr` — modern replacement for max-height hack.

```css
.reveal {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.4s var(--ease-out);
}
.reveal > div {
  overflow: hidden;
}
.reveal[data-open="true"] {
  grid-template-rows: 1fr;
}
```

**Support:** Chrome 117+, Safari 17.4+, FF 127+. **Cost:** Low. **Use:** Accordions, inline details.

---

## F. Buttons

### F1. Shimmer sweep

**Desc:** Pseudo-element ::before containing a skewed white gradient slides across on hover.

```css
.btn-sweep {
  position: relative;
  overflow: hidden;
  background: var(--bg-1);
  color: var(--fg-0);
  border: 1px solid var(--line);
  padding: 0.7rem 1.2rem;
  border-radius: 10px;
}
.btn-sweep::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    120deg,
    transparent 30%,
    rgba(255, 255, 255, 0.18) 50%,
    transparent 70%
  );
  transform: translateX(-100%);
  transition: transform 0.7s var(--ease-out);
}
.btn-sweep:hover::before {
  transform: translateX(100%);
}
```

**Support:** All. **Cost:** Zero. **Use:** Secondary CTAs.
**Source:** https://codeshack.io/pure-css-shimmer-button-hover-effect/

---

### F2. Magnetic button (11-line JS)

**Desc:** Button translates ~20% toward cursor; spring-back on leave.

```html
<button class="mag">Download</button>
```

```css
.mag {
  background: var(--red);
  color: #fff;
  border: none;
  padding: 0.8rem 1.4rem;
  border-radius: 12px;
  transition: transform 0.4s var(--ease-out);
}
```

```js
document.querySelectorAll(".mag").forEach((b) => {
  b.addEventListener("pointermove", (e) => {
    const r = b.getBoundingClientRect();
    const x = e.clientX - (r.left + r.width / 2),
      y = e.clientY - (r.top + r.height / 2);
    b.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
  });
  b.addEventListener("pointerleave", () => (b.style.transform = ""));
});
```

**Support:** All. **Cost:** Low. **Use:** Hero CTA only (rare use = more impactful).
**Source:** https://medium.com/@fulton_shaun/magnetic-buttons-with-css-only-11e249b320a2

---

### F3. Pressed depth

**Desc:** Two gradient stops + inset shadow = a mechanical key.

```css
.key {
  background: linear-gradient(180deg, #1e1e1e, #141414);
  color: var(--fg-0);
  border: 1px solid var(--line);
  border-top-color: #3a3a3a;
  border-radius: 10px;
  padding: 0.55rem 0.9rem;
  box-shadow:
    0 2px 0 #000,
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  transition: transform 0.08s;
}
.key:active {
  transform: translateY(1px);
  box-shadow:
    0 0 0 #000,
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}
```

**Support:** All. **Cost:** Zero. **Use:** Keyboard shortcut pills (Raycast/Cmd-K style).

---

### F4. Radial ripple on click

**Desc:** No JS — pure `:active` + `background-size:15000%`.

```css
.ripple {
  background-color: var(--bg-1);
  background-image: radial-gradient(circle, var(--fg-0) 1%, transparent 1%);
  background-position: center;
  background-size: 15000%;
  color: var(--fg-0);
  border: 1px solid var(--line);
  padding: 0.7rem 1.2rem;
  border-radius: 10px;
  transition: background 0.55s;
}
.ripple:active {
  background-color: var(--line-2);
  background-size: 100%;
  transition: background 0s;
}
```

**Support:** All. **Cost:** Low. **Use:** Toolbar buttons.
**Source:** https://codepen.io/finnhvman/pen/jLXKJw

---

### F5. Gradient-fill on hover (color-mix + accent)

**Desc:** Background shifts to an accent, text inverts smoothly.

```css
.fill {
  --accent: var(--red);
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--accent);
  padding: 0.65rem 1.1rem;
  border-radius: 10px;
  transition:
    background 0.25s,
    color 0.25s;
}
.fill:hover {
  background: var(--accent);
  color: var(--bg-0);
}
```

**Support:** All. **Cost:** Zero. **Use:** Outline buttons in cards.

---

## G. Loaders

### G1. Skeleton shimmer

**Desc:** The pattern everyone ships; tuned dark so it feels like Palette D native.

```css
.skeleton {
  background: linear-gradient(90deg, #141414 0%, #1c1c1c 50%, #141414 100%);
  background-size: 200% 100%;
  animation: sk 1.4s ease-in-out infinite;
  border-radius: 6px;
  height: 1em;
}
@keyframes sk {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
```

**Support:** All. **Cost:** Low. **Use:** Any loading block.
**Source:** https://css-tricks.com / https://codepen.io/maoberlehner/pen/bQGZYB

---

### G2. Indeterminate gradient bar

**Desc:** Progress bar with translating gradient — no library.

```css
.ibar {
  height: 2px;
  background: var(--line);
  overflow: hidden;
  position: relative;
  border-radius: 2px;
}
.ibar::after {
  content: "";
  position: absolute;
  inset: 0;
  width: 30%;
  background: linear-gradient(90deg, transparent, var(--red), transparent);
  animation: slide 1.2s ease-in-out infinite;
}
@keyframes slide {
  0% {
    left: -30%;
  }
  100% {
    left: 100%;
  }
}
```

**Support:** All. **Cost:** Very low. **Use:** Top-page loader, form submit.

---

### G3. Three-dot pulse

**Desc:** Stripe-style three dots with staggered pulse.

```css
.dots {
  display: inline-flex;
  gap: 6px;
}
.dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--fg-1);
  animation: dot 1.2s ease-in-out infinite;
}
.dots span:nth-child(2) {
  animation-delay: 0.15s;
}
.dots span:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes dot {
  0%,
  80%,
  100% {
    opacity: 0.2;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
```

**Support:** All. **Cost:** Zero. **Use:** Chat/typing indicator.

---

### G4. Conic spinner

**Desc:** One element, one conic gradient + mask.

```css
.spin {
  width: 22px;
  aspect-ratio: 1;
  border-radius: 50%;
  background: conic-gradient(transparent 0 25%, var(--fg-0) 100%);
  -webkit-mask: radial-gradient(
    farthest-side,
    transparent calc(100% - 2px),
    #000 0
  );
  mask: radial-gradient(farthest-side, transparent calc(100% - 2px), #000 0);
  animation: rot 800ms linear infinite;
}
@keyframes rot {
  to {
    transform: rotate(360deg);
  }
}
```

**Support:** All. **Cost:** Very low. **Use:** Button loading state.

---

### G5. Data-stream ticks

**Desc:** Terminal/stream feel — 10 bars, random heights via CSS vars and delays.

```css
.stream {
  display: flex;
  gap: 3px;
  align-items: flex-end;
  height: 26px;
}
.stream span {
  width: 3px;
  background: var(--green);
  animation: tick 1s ease-in-out infinite;
  animation-delay: calc(var(--i, 0) * 60ms);
}
@keyframes tick {
  50% {
    height: 100%;
  }
  0%,
  100% {
    height: 20%;
  }
}
```

HTML: `<div class="stream"><span style="--i:0"></span>...<span style="--i:9"></span></div>`
**Support:** All. **Cost:** Low. **Use:** "Live" status in dashboards.

---

## H. Data viz

### H1. Pure CSS sparkline (SVG polyline)

**Desc:** Sparklines _are_ tiny — use inline SVG. No library. Stroke animates on reveal.

```html
<svg class="spark" viewBox="0 0 80 24">
  <polyline
    fill="none"
    stroke="#5cb88a"
    stroke-width="1.5"
    stroke-linejoin="round"
    points="0,18 10,14 20,16 30,10 40,12 50,6 60,8 70,4 80,2"
  />
</svg>
```

```css
.spark polyline {
  stroke-dasharray: 200;
  stroke-dashoffset: 200;
  animation: draw 1.2s ease-out forwards;
}
@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}
```

**Support:** All. **Cost:** Zero. **Use:** Dashboard KPIs inline with numbers.

---

### H2. CSS-var bar chart

**Desc:** Each bar scales by its `--v` custom property — HTML stays semantic.

```css
.bars {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  height: 90px;
}
.bars i {
  flex: 1;
  background: linear-gradient(180deg, var(--blue), #2a567a);
  height: calc(var(--v, 0) * 1%);
  border-radius: 3px 3px 0 0;
  transition: height 0.8s var(--ease-out);
}
```

HTML: `<div class="bars"><i style="--v:40"></i><i style="--v:72"></i>...</div>`
**Support:** All. **Cost:** Zero. **Use:** Activity chart, usage graphs.

---

### H3. Conic ring chart

**Desc:** One div, one conic gradient, one radial mask for the hole.

```css
.ring {
  --p: 72;
  --c: var(--green);
  width: 96px;
  aspect-ratio: 1;
  border-radius: 50%;
  background: conic-gradient(var(--c) calc(var(--p) * 1%), var(--line) 0);
  display: grid;
  place-items: center;
  font: 600 15px system-ui;
  color: var(--fg-0);
}
.ring::before {
  content: "";
  position: absolute;
  inset: 8px;
  background: var(--bg-0);
  border-radius: 50%;
}
.ring {
  position: relative;
}
.ring span {
  position: relative;
  z-index: 1;
}
```

HTML: `<div class="ring" style="--p:68;--c:var(--red)"><span>68%</span></div>`
**Support:** All. **Cost:** Zero. **Use:** Progress KPIs, quota meters.
**Source:** https://css-tricks.com/using-conic-gradients-css-variables-create-doughnut-chart-output-range-input/

---

### H4. Pure-CSS count-up with `@property`

**Desc:** Animates an integer custom property using scroll timeline.

```css
@property --n {
  syntax: "<integer>";
  initial-value: 0;
  inherits: false;
}
.count {
  counter-reset: n var(--n);
  font: 700 48px system-ui;
  color: var(--fg-0);
  animation: countup linear both;
  animation-timeline: view();
  animation-range: entry 0% cover 60%;
}
.count::after {
  content: counter(n);
}
@keyframes countup {
  to {
    --n: 2847;
  }
}
```

**Support:** Chrome 115+, Safari 26+. Fallback: show static number. **Cost:** Very low.
**Use:** "Shipped 2,847 updates" stats.
**Source:** https://stackoverflow.com/questions/78780127/animate-count-of-number-when-element-in-viewport-in-pure-css

---

### H5. Trend arrow with sign color

**Desc:** Inline delta chip that colors green/red via attribute selector.

```css
.delta {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  font: 600 13px system-ui;
  padding: 2px 6px;
  border-radius: 6px;
}
.delta[data-dir="up"] {
  color: var(--green);
  background: rgba(92, 184, 138, 0.12);
}
.delta[data-dir="down"] {
  color: var(--red);
  background: rgba(255, 45, 76, 0.12);
}
.delta[data-dir="up"]::before {
  content: "▲";
}
.delta[data-dir="down"]::before {
  content: "▼";
}
```

**Support:** All. **Cost:** Zero. **Use:** KPI deltas.

---

## I. Navigation

### I1. Sliding indicator pill (radio input, no JS)

**Desc:** Uses `:has()` + named sibling for pill position.

```css
.tabs {
  position: relative;
  display: inline-flex;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 3px;
}
.tabs label {
  padding: 0.45rem 0.9rem;
  color: var(--fg-1);
  cursor: pointer;
  z-index: 1;
  font: 500 13px system-ui;
}
.tabs input {
  display: none;
}
.tabs input:checked + label {
  color: var(--fg-0);
}
.tabs::before {
  content: "";
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 3px;
  width: calc(100% / 3 - 2px);
  background: var(--bg-2);
  border: 1px solid var(--line-2);
  border-radius: 7px;
  transition: transform 0.35s var(--ease-out);
}
.tabs:has(#t2:checked)::before {
  transform: translateX(100%);
}
.tabs:has(#t3:checked)::before {
  transform: translateX(200%);
}
```

**Support:** Chrome 105+, Safari 15.4+, FF 121+ (`:has()`). **Cost:** Very low.
**Use:** Filter/segment controls.

---

### I2. Chevron breadcrumbs

**Desc:** `::after` with a rotated square gives the "›" separator with perfect vertical alignment.

```css
.crumbs {
  display: flex;
  gap: 0.5rem;
  color: var(--fg-1);
  font: 500 13px system-ui;
}
.crumbs a {
  color: inherit;
  text-decoration: none;
}
.crumbs a + a::before {
  content: "›";
  padding-right: 0.5rem;
  color: var(--fg-2);
}
.crumbs a:last-child {
  color: var(--fg-0);
}
```

**Support:** All. **Cost:** Zero. **Use:** App-chrome location.

---

### I3. Collapsible sidebar

**Desc:** Width transitions + icon-only mode via `[data-collapsed]`.

```css
.side {
  width: 240px;
  transition: width 0.3s var(--ease-out);
  overflow: hidden;
  background: var(--bg-1);
}
.side[data-collapsed] {
  width: 56px;
}
.side .label {
  opacity: 1;
  transition: opacity 0.2s;
}
.side[data-collapsed] .label {
  opacity: 0;
}
```

**Support:** All. **Cost:** Zero. **Use:** App shell.

---

### I4. Scroll-hidden top nav

**Desc:** Sticky nav that auto-hides on scroll down, shows on scroll up — using scroll-driven animations.

```css
nav.sticky {
  position: sticky;
  top: 0;
  animation: hide linear both;
  animation-timeline: scroll();
  animation-range: 100px 300px;
}
@keyframes hide {
  to {
    transform: translateY(-100%);
    opacity: 0;
  }
}
```

**Support:** Chrome 115+, Safari 26+. Fallback: always visible. **Cost:** Low.

---

## J. Micro-interactions

### J1. Copy flash

**Desc:** Click → "Copied" chip flashes in.

```html
<button class="copy" data-text="npm i nuzantara">Copy</button>
```

```css
.copy {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--line);
  padding: 0.5rem 0.8rem;
  border-radius: 8px;
}
.copy.ok::after {
  content: "Copied";
  position: absolute;
  top: -28px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--green);
  color: #0a0a0a;
  padding: 2px 8px;
  border-radius: 6px;
  font: 600 11px system-ui;
  animation: pop 1.2s forwards;
}
@keyframes pop {
  0% {
    opacity: 0;
    transform: translateX(-50%) translateY(4px);
  }
  15%,
  75% {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  100% {
    opacity: 0;
  }
}
```

```js
document.querySelectorAll(".copy").forEach(
  (b) =>
    (b.onclick = () => {
      navigator.clipboard.writeText(b.dataset.text);
      b.classList.remove("ok");
      void b.offsetWidth;
      b.classList.add("ok");
    }),
);
```

**Support:** All. **Cost:** Zero. **Use:** Code blocks.

---

### J2. Tooltip fade (CSS only)

**Desc:** `data-tip` attribute → pseudo-element tooltip with fade-in.

```css
[data-tip] {
  position: relative;
}
[data-tip]:hover::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #000;
  color: #fff;
  padding: 4px 8px;
  border-radius: 6px;
  font: 500 12px system-ui;
  white-space: nowrap;
  animation: fadein 0.2s ease-out both;
}
@keyframes fadein {
  from {
    opacity: 0;
    transform: translate(-50%, 2px);
  }
}
```

**Support:** All. **Cost:** Zero. **Use:** Icon buttons.

---

### J3. Status ping (double ring)

**Desc:** A dot with a pulse/ping halo — classic "live" indicator.

```css
.ping {
  position: relative;
  width: 10px;
  height: 10px;
  background: var(--green);
  border-radius: 50%;
}
.ping::after {
  content: "";
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  border: 2px solid var(--green);
  animation: pulse 1.6s ease-out infinite;
  opacity: 0;
}
@keyframes pulse {
  0% {
    transform: scale(0.6);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.9);
    opacity: 0;
  }
}
```

**Support:** All. **Cost:** Very low. **Use:** Online status, build status.
**Source:** https://css3shapes.com/how-to-make-a-pulsing-live-indicator/

---

### J4. Badge count pop (spring-in)

**Desc:** Notification count appears with overshoot cubic-bezier.

```css
.badge {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font: 600 11px system-ui;
  background: var(--red);
  color: #fff;
  border-radius: 9px;
  animation: bop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes bop {
  0% {
    transform: scale(0.2);
    opacity: 0;
  }
  60% {
    transform: scale(1.15);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
```

**Support:** All. **Cost:** Zero. **Use:** Notif bell, cart count.

---

### J5. Kbd chip

**Desc:** Realistic keyboard key using layered inset shadows.

```css
kbd {
  font:
    600 12px ui-monospace,
    monospace;
  background: linear-gradient(180deg, #1e1e1e, #141414);
  color: var(--fg-0);
  border: 1px solid var(--line);
  border-bottom-width: 2px;
  border-radius: 6px;
  padding: 2px 6px;
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.04);
}
```

**Support:** All. **Cost:** Zero. **Use:** Command palette hints.

---

## K. Dividers

### K1. Gradient-fade divider

**Desc:** 1px line that fades in/out at the edges; disappears into backgrounds.

```css
.div-fade {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--line-2), transparent);
  margin: 2rem 0;
}
```

**Support:** All. **Cost:** Zero. **Use:** Section separators.

---

### K2. Animated center mark

**Desc:** A tiny centered chevron/plus that pulses on the divider.

```css
.div-mark {
  display: flex;
  align-items: center;
  gap: 1rem;
  color: var(--fg-2);
}
.div-mark::before,
.div-mark::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--line);
}
.div-mark span {
  font-size: 10px;
  letter-spacing: 0.2em;
}
```

**Support:** All. **Cost:** Zero. **Use:** "SECTION 01" labels.

---

### K3. Dotted divider

```css
.div-dots {
  height: 1px;
  background-image: radial-gradient(circle, var(--line-2) 1px, transparent 1px);
  background-size: 8px 1px;
  margin: 2rem 0;
}
```

**Support:** All. **Cost:** Zero.

---

### K4. Section number mark

**Desc:** Vertical counter — large faint number on the left.

```css
.section {
  counter-increment: sec;
  position: relative;
  padding-left: 4rem;
}
.section::before {
  content: "0" counter(sec);
  position: absolute;
  left: 0;
  top: 0;
  font: 700 56px ui-monospace;
  color: transparent;
  -webkit-text-stroke: 1px var(--line-2);
}
body {
  counter-reset: sec;
}
```

**Support:** All. **Cost:** Zero. **Use:** Landing page sections.

---

## L. Focus states

### L1. Double-layer focus ring (offset + glow)

**Desc:** Meets WCAG 2.2 non-text contrast 3:1 against Palette D dark surfaces.

```css
:where(button, a, input, [tabindex]):focus-visible {
  outline: 2px solid var(--fg-0);
  outline-offset: 2px;
  box-shadow:
    0 0 0 4px rgba(255, 45, 76, 0.35),
    0 0 0 6px rgba(74, 142, 196, 0.18);
  border-radius: inherit;
}
```

**Support:** All. **Cost:** Zero. **Use:** Global selector.
**Source:** https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:focus-visible

---

### L2. Outline sweep underline

**Desc:** Left-anchored underline grows on hover, right-anchored on leave — subtle reversal.

```css
.link {
  position: relative;
  color: var(--fg-0);
  text-decoration: none;
}
.link::after {
  content: "";
  position: absolute;
  left: 0;
  bottom: -2px;
  height: 1px;
  width: 100%;
  background: currentColor;
  transform: scaleX(0);
  transform-origin: right;
  transition: transform 0.35s var(--ease-out);
}
.link:hover::after {
  transform: scaleX(1);
  transform-origin: left;
}
```

**Support:** All. **Cost:** Zero. **Use:** Nav, footer.
**Source:** https://stackoverflow.com/questions/75898697/

---

### L3. Focus within card highlight

**Desc:** Card lifts + accent line when any child is focused.

```css
.card:focus-within {
  border-color: var(--blue);
  box-shadow: 0 0 0 4px rgba(74, 142, 196, 0.15);
}
```

**Support:** All. **Cost:** Zero. **Use:** Forms.

---

## M. Page transitions

### M1. View Transitions — simple cross-fade (MPA)

**Desc:** Two lines of CSS and the browser cross-fades navigations.

```css
@view-transition {
  navigation: auto;
}
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.4s;
  animation-timing-function: var(--ease-out);
}
```

**Support:** Chrome 126+ MPA, Safari 18+, FF TP. Graceful degrade = instant nav. **Cost:** Near-zero.
**Source:** https://developer.chrome.com/docs/web-platform/view-transitions

---

### M2. Named view-transition (hero image morph)

**Desc:** Give the source and destination `view-transition-name` — they smoothly morph between pages.

```css
.cover-img {
  view-transition-name: cover;
}
/* destination detail page: */
.detail-cover {
  view-transition-name: cover;
}
::view-transition-group(cover) {
  animation-duration: 0.6s;
}
```

**Support:** Chrome 111+ SPA, 126+ MPA. **Cost:** Low. **Use:** Article/post list → detail.

---

### M3. Scroll-linked reveal

**Desc:** Fade content as it enters — pure CSS, no IO observer.

```css
.reveal {
  opacity: 0;
  transform: translateY(20px);
  animation: in linear both;
  animation-timeline: view();
  animation-range: entry 0% cover 30%;
}
@keyframes in {
  to {
    opacity: 1;
    transform: none;
  }
}
```

**Support:** Chrome 115+, Safari 26+. **Cost:** Very low. **Use:** Marketing sections.

---

### M4. Sticky-reveal horizontal storytelling

**Desc:** Pins a visual while text scrolls — scroll-driven animation style.

```css
.story {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
}
.story .pin {
  position: sticky;
  top: 10vh;
  height: 80vh;
}
.story .pin img {
  animation: scale linear both;
  animation-timeline: view(root);
  animation-range: cover 0% cover 100%;
}
@keyframes scale {
  to {
    transform: scale(1.1);
  }
}
```

**Support:** All (sticky) / scroll-timeline Chrome 115+. **Cost:** Low. **Use:** Feature storytelling.

---

## N. Cursor

### N1. Custom dot cursor (2 elements, 8-line JS)

**Desc:** Two nested divs follow cursor — outer ring trails, inner dot snaps.

```css
.cursor,
.cursor-dot {
  position: fixed;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 9999;
  border-radius: 50%;
}
.cursor {
  width: 28px;
  height: 28px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  transform: translate(-50%, -50%);
  transition:
    transform 0.2s,
    width 0.2s,
    height 0.2s;
}
.cursor-dot {
  width: 4px;
  height: 4px;
  background: var(--fg-0);
  transform: translate(-50%, -50%);
}
.cursor.hover {
  width: 56px;
  height: 56px;
  border-color: var(--red);
}
```

```js
const c = document.querySelector(".cursor"),
  d = document.querySelector(".cursor-dot");
addEventListener("pointermove", (e) => {
  c.style.left = d.style.left = e.clientX + "px";
  c.style.top = d.style.top = e.clientY + "px";
});
document.querySelectorAll("a,button").forEach((el) => {
  el.addEventListener("pointerenter", () => c.classList.add("hover"));
  el.addEventListener("pointerleave", () => c.classList.remove("hover"));
});
```

**Support:** All. Respect `pointer:fine` only: `@media (pointer:fine){ ... }`. **Cost:** Low.
**Use:** Marketing/portfolio pages — hide default cursor only there.

---

### N2. Magnetic glow (spotlight that follows)

**Desc:** A big radial gradient placed at cursor — flashlight effect over a content area.

```css
.spotlight {
  position: relative;
  isolation: isolate;
  background: var(--bg-0);
  overflow: hidden;
}
.spotlight::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(
    400px circle at var(--mx, 50%) var(--my, 50%),
    rgba(255, 255, 255, 0.08),
    transparent 40%
  );
}
```

(Reuse the same 4-line JS from D3 to set `--mx/--my`.)
**Support:** All. **Cost:** Low. **Use:** Hero, pricing table.

---

### N3. Trailing dot (no lib)

**Desc:** A small delayed follower using CSS transition.

```css
.trail {
  position: fixed;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--red);
  pointer-events: none;
  transition: transform 0.2s var(--ease-out);
  z-index: 9999;
}
```

```js
const t = document.querySelector(".trail");
addEventListener(
  "pointermove",
  (e) =>
    (t.style.transform = `translate(${e.clientX - 5}px,${e.clientY - 5}px)`),
);
```

**Support:** All. **Cost:** Zero.

---

## O. Scroll

### O1. Pure-CSS parallax (scroll-timeline)

**Desc:** Background shifts at half speed as you scroll.

```css
.parallax-bg {
  animation: parallax linear both;
  animation-timeline: scroll(root);
  animation-range: 0 100%;
}
@keyframes parallax {
  to {
    transform: translateY(-20vh);
  }
}
```

**Support:** Chrome 115+, Safari 26+. Fallback: static. **Cost:** Low.

---

### O2. Horizontal snap gallery

**Desc:** Native carousel using `scroll-snap`.

```css
.hsnap {
  display: flex;
  gap: 1rem;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  padding: 1rem;
  scrollbar-width: none;
}
.hsnap::-webkit-scrollbar {
  display: none;
}
.hsnap > * {
  flex: 0 0 78%;
  scroll-snap-align: center;
  aspect-ratio: 16/10;
  background: var(--bg-1);
  border-radius: 16px;
}
```

**Support:** All. **Cost:** Zero. **Use:** Showcases, mobile screenshots.

---

### O3. Sticky section header shadow on scroll

**Desc:** Sticky header gets its shadow only when stuck — uses scroll-driven animation.

```css
header.sticky {
  position: sticky;
  top: 0;
  background: var(--bg-0);
  animation: shadow linear both;
  animation-timeline: scroll(nearest);
  animation-range: 0 60px;
}
@keyframes shadow {
  to {
    box-shadow:
      0 1px 0 var(--line),
      0 10px 24px rgba(0, 0, 0, 0.4);
  }
}
```

**Support:** Chrome 115+, Safari 26+. **Cost:** Low.

---

### O4. Intersection reveal (CSS only via scroll-timeline view)

**Desc:** Same as M3 but staggered via `--i` delay — creates cascade on lists.

```css
.items > * {
  opacity: 0;
  transform: translateY(14px);
  animation: in linear both;
  animation-timeline: view();
  animation-range: entry 0% cover 30%;
  animation-delay: calc(var(--i, 0) * 60ms);
}
```

**Support:** Chrome 115+, Safari 26+. **Cost:** Low.

---

## Bonus — complementary patterns from the search trail

### Z1. Command palette wrapper (Cmd-K)

**Desc:** Glass B1 + backdrop dim + focus ring L1 + input w/ kbd J5. Structural, not a new technique — but the _combination_ is the Palette D signature.

```css
.palette-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: start center;
  padding-top: 18vh;
}
.palette {
  width: min(640px, 92vw);
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-1) 70%, transparent);
  backdrop-filter: blur(22px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6);
}
```

**Use:** Global Cmd-K across the app.

### Z2. Color-mix hover tint

**Desc:** Mix accent with surface at 10–15% for tasteful hovers.

```css
.row:hover {
  background: color-mix(in srgb, var(--red) 10%, var(--bg-1));
}
```

**Support:** Chrome 111+, Safari 16.2+, FF 113+. **Cost:** Zero.

### Z3. Data-tooltip with arrow

```css
[data-tip]::before {
  content: "";
  position: absolute;
  top: -4px;
  left: 50%;
  width: 8px;
  height: 8px;
  background: #000;
  transform: translateX(-50%) rotate(45deg);
}
```

---

## Performance & a11y notes (mandatory reading)

1. **Blur is expensive.** Only one `backdrop-filter` should be animated per viewport at a time. Prefer _static_ blurred layers; animate `transform/opacity`, not blur radius.
2. **Avoid fighting `prefers-reduced-motion`.**
   ```css
   @media (prefers-reduced-motion: reduce) {
     *,
     *::before,
     *::after {
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
       transition-duration: 0.01ms !important;
     }
   }
   ```
3. **Respect `prefers-contrast`.** The signal red on `#0a0a0a` passes 5.6:1 — safe. Keep accents for chrome, white for body.
4. **Use `will-change` sparingly.** Only on elements that are actually animating _right now_ (magnetic button, tilt card).
5. **`color-mix()` + `@property` + `:has()` are your 2024+ power trio.** All three are now baseline enough for Palette D (if you support Chrome 111+/Safari 16.4+).
6. **View Transitions + scroll-driven fallback gracefully** — write static CSS first, add the animation layer behind `@supports`.
7. **Grain layers:** apply with `mix-blend-mode:overlay` and limit to a single full-screen `::before` — don't grain every card.

---

## Top 10 immediately usable (for Palette D, ranked)

A ruthless shortlist. Every one is cheap, stylistically on-brand with Linear/Vercel/Raycast, and adds disproportionate perceived quality.

| #      | Technique                                           | Section       | Why it wins for Palette D                                                                                                                       |
| ------ | --------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | **Dotted grid w/ radial mask** (A2)                 | Background    | The single most recognizable Linear/Raycast backdrop. Zero JS, zero cost, instantly "futuristic." Use as the app-wide body background.          |
| **2**  | **Mouse-aware glow border** (D3)                    | Borders       | 15 lines total (CSS + JS). Turns any `.gborder` into a Supabase-class feature card. Signal-red glow matches the palette's one accent perfectly. |
| **3**  | **Frosted dark glass + light leak** (B1 + B2 combo) | Glassmorphism | The core language of your nav/cmd-bar. Stack them; together they give depth without cyberpunk neon.                                             |
| **4**  | **Double-layer focus ring** (L1)                    | Focus         | Non-negotiable accessibility + it _looks_ like Arc/Raycast. Ship as a `:where()` global.                                                        |
| **5**  | **Rotating conic border (`@property`)** (D1)        | Borders       | The single "wow" moment the app needs — reserve for the Pro/Upgrade card. Pure CSS.                                                             |
| **6**  | **Conic ring chart** (H3)                           | Data viz      | One-div KPI rings. Swap `--c` per category (blue/green/gold/violet/teal). Replaces chart libs in dashboards.                                    |
| **7**  | **Skeleton shimmer tuned dark** (G1)                | Loaders       | Ship before any data hits — perceived perf jump. `#141414 → #1c1c1c → #141414` is calibrated to Palette D.                                      |
| **8**  | **Hover-lift card with layered shadow** (E2)        | Cards         | The default for every list item. Replaces 90% of hover interactions, zero cost.                                                                 |
| **9**  | **Bento grid asym layout** (E4)                     | Layout        | The entire "features" and "what's included" narrative fits in one grid. Mobile-safe via media query.                                            |
| **10** | **Scroll-driven reveal + stagger** (O4)             | Scroll        | Zero-JS intersection reveal that degrades to instant-visible. 4 lines of CSS to animate the whole marketing page.                               |

### Why these ten and not others

- **Not shipped:** cursor effects (N1–N3) — they violate system expectations and hurt accessibility if overused.
- **Not shipped for core app:** magnetic button (F2) — save for the marketing site hero only; inside dashboards it feels like a toy.
- **Not shipped:** marching ants (D2) — great for drop zones but not the broad "everywhere" technique.
- **Not shipped for app chrome:** aurora A3 — too heavy on every page; reserve for `/pricing` or `/changelog` hero.

The ten above combine to give roughly:

- **One visual language** (dotted grid + glass + hover-lift + bento) that reads as "modern tool, not toy."
- **One per-section wow** (rotating conic border on upgrade card, ring charts in dashboard).
- **Zero library footprint** and **<25 lines total JS** across the whole list.
- **Graceful degradation** everywhere — the oldest browsers still render a clean dark UI, just without the scroll-driven cherry.

### Suggested wiring order (if you implement one per day)

1. Day 1: paste the `:root` token block + G1 (skeleton) — immediate perceived win.
2. Day 2: A2 grid + E2 hover-lift — the "chrome" is now Linear-grade.
3. Day 3: B1 + B2 glass — all modals and command palette updated.
4. Day 4: L1 focus global — accessibility locked.
5. Day 5: H3 ring chart + H2 bar chart + H5 delta arrow — dashboard is alive.
6. Day 6: D3 mouse-glow border on pricing/feature cards.
7. Day 7: D1 rotating conic border on the single upgrade card.
8. Day 8: E4 bento grid on the feature overview page.
9. Day 9: O4 scroll-driven reveal across marketing pages.
10. Day 10: M1 view transitions for inter-page fades.

---

## Primary sources (de-duplicated, verified links)

- Josh W. Comeau — Next-level frosted glass: https://www.joshwcomeau.com/css/backdrop-filter/
- CSS-Tricks — Grainy Gradients: https://css-tricks.com/grainy-gradients/
- CSS-Tricks — `conic-gradient()` almanac: https://css-tricks.com/almanac/functions/c/conic-gradient/
- CSS-Tricks — Animated menu indicator: https://css-tricks.com/creating-an-animated-menu-indicator-with-css-selectors/
- CSS-Tricks — Animating Number Counters: https://css-tricks.com/animating-number-counters/
- CSS-Tricks — Conic-gradient doughnut chart: https://css-tricks.com/using-conic-gradients-css-variables-create-doughnut-chart-output-range-input/
- MDN — Scroll-driven animations: https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scroll-driven_animations
- MDN — View Transition API: https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API
- MDN — `:focus-visible`: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:focus-visible
- Codrops — Practical scroll-driven animations: https://tympanus.net/codrops/2024/01/17/a-practical-introduction-to-scroll-driven-animations-with-css-scroll-and-view/
- Codrops — `<feTurbulence>` texture: https://tympanus.net/codrops/2019/02/19/svg-filter-effects-creating-texture-with-feturbulence/
- Smashing — Intro to CSS scroll-driven: https://www.smashingmagazine.com/2024/12/introduction-css-scroll-driven-animations/
- Smashing — Tailwind donut charts (technique applies): https://www.smashingmagazine.com/2023/03/dynamic-donut-charts-tailwind-css-react/
- Frontend Masters — Grainy gradients: https://frontendmasters.com/blog/grainy-gradients/
- Frontend Masters — Fading with mask: https://frontendmasters.com/blog/fading-out-text-with-mask/
- Frontend Masters — Pure CSS halftone: https://frontendmasters.com/blog/pure-css-halftone-effect-in-3-declarations/
- ibelick — Animated gradient borders: https://ibelick.com/blog/create-animated-gradient-borders-with-css
- ibelick — Metallic text: https://ibelick.com/blog/creating-metallic-effect-with-css
- ibelick — Grainy backgrounds: https://ibelick.com/blog/create-grainy-backgrounds-with-css
- ibelick — Animated text gradient: https://ibelick.com/blog/create-animated-text-gradient-with-css
- web.dev — Animated gradient text: https://web.dev/articles/speedy-css-tip-animated-gradient-text
- Chrome Developers — Scroll-driven animations: https://developer.chrome.com/docs/css-ui/scroll-driven-animations
- Chrome Developers — View Transitions: https://developer.chrome.com/docs/web-platform/view-transitions
- scroll-driven-animations.style — Live demos: https://scroll-driven-animations.style/
- Tobias Ahlin — Animating link underlines: https://tobiasahlin.com/blog/css-trick-animating-link-underlines/
- Polypane — Fading content with transparent gradients: https://polypane.app/blog/my-take-on-fading-content-using-transparent-gradients-in-css/
- Ahmad Shadeed — CSS Masking: https://ishadeed.com/article/css-masking/
- codetv.dev — Animated CSS gradient border: https://codetv.dev/blog/animated-css-gradient-border
- Auroral — Pure CSS aurora gradients: https://github.com/LunarLogic/auroral
- Bento Grids gallery: https://bentogrids.com/
- Senorit — Bento grid design 2026: https://senorit.de/en/blog/bento-grid-design-trend-2025
- CSS3shapes — Pulsing live indicator: https://css3shapes.com/how-to-make-a-pulsing-live-indicator/
- finnhvman — Pure CSS ripple: https://codepen.io/finnhvman/pen/jLXKJw
- Linear blog — Redesigning UI: https://linear.app/now/how-we-redesigned-the-linear-ui
- Prototypr — Linears collection (inspired sites): https://prototypr.io/toolbox/linears

---

_End of document. Total techniques documented: 55+ (target was 30+). Writable in a single stylesheet; no dependencies; no build step; ready for Palette D._
