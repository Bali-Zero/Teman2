```css
.glass {
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.08),
    rgba(255, 255, 255, 0.03)
  );
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 20px 60px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(14px) saturate(120%);
  -webkit-backdrop-filter: blur(14px) saturate(120%);
  border-radius: 20px;
}
```

Browser support: Current Chrome/Safari/Firefox support `backdrop-filter`; always keep the translucent background so the card still reads if blur is unavailable.
Performance: Medium.
Use here: floating filters, nav bars, command palettes, KPI overlay cards.

### B2. Liquid Refraction Capsule

Looks like: a pill or chip that feels as if light is bending through it because the highlight and inner shadows are asymmetrical.

Markup: `<button class="liquid-chip">Live sync</button>`

```css
.liquid-chip {
  position: relative;
  padding: 0.85rem 1.2rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(18px);
  overflow: hidden;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    inset 0 -8px 18px rgba(0, 0, 0, 0.2);
}
.liquid-chip::before {
  content: "";
  position: absolute;
  inset: 1px 40% 40% 1px;
  border-radius: inherit;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.22),
    transparent 65%
  );
  filter: blur(10px);
  opacity: 0.9;
}
```

Browser support: Current Chrome/Safari/Firefox are fine; the blur is the only progressive layer.
Performance: Medium.
Use here: status chips, segmented controls, mini buttons in dense toolbars.

### B3. Chromatic Edge Glass With Inner Leak

Looks like: a dark glass card with barely perceptible blue/red edge splitting and a top-left light leak, the kind of subtle polish you notice only after a second look.

Markup: `<div class="glass-edge"></div>`

```css
.glass-edge {
  position: relative;
  border-radius: 22px;
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(16px);
}
.glass-edge::before,
.glass-edge::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
}
.glass-edge::before {
  box-shadow:
    -1px 0 0 rgba(88, 166, 255, 0.22),
    1px 0 0 rgba(255, 45, 76, 0.18);
}
.glass-edge::after {
  inset: 1px;
  border-radius: inherit;
  background: radial-gradient(
    circle at 10% 0,
    rgba(255, 255, 255, 0.16),
    transparent 35%
  );
  mix-blend-mode: screen;
}
```

Browser support: Chrome/Safari/Firefox 2024+ all good.
Performance: Low to medium.
Use here: premium cards, pricing highlights, feature comparison tables.

## C. Text Effects

### C1. Gradient Text With Tight Red Halo

Looks like: sharp white-to-silver lettering with a very restrained red emission hugging the glyph edges.

Markup: `<h1 class="title-glow">Realtime operations.</h1>`

```css
.title-glow {
  color: transparent;
  background: linear-gradient(180deg, #fff 0%, #d9dde7 100%);
  -webkit-background-clip: text;
  background-clip: text;
  text-shadow:
    0 0 18px rgba(255, 45, 76, 0.16),
    0 1px 0 rgba(255, 255, 255, 0.06);
  letter-spacing: -0.04em;
}
```

Browser support: All current browsers support clipped gradient text.
Performance: Low.
Use here: hero headlines, dashboard section titles, modal titles, numeric KPI headings.

### C2. Metallic Sheen Sweep

Looks like: text that catches a moving highlight as if brushed metal is passing under a narrow light source.

Markup: `<h2 class="sheen">Deployment status</h2>`

```css
.sheen {
  color: transparent;
  display: inline-block;
  background: linear-gradient(
    110deg,
    #8f96a3 20%,
    #fff 35%,
    #9aa2af 50%,
    #fff 65%,
    #8f96a3 80%
  );
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  animation: sheen 4.2s linear infinite;
}
@keyframes sheen {
  to {
    background-position: -220% 0;
  }
}
```

Browser support: Chrome/Safari/Firefox 2024+ all good.
Performance: Low.
Use here: logos, launch callouts, plan names, status ribbons.

### C3. Typewriter With Soft Caret

Looks like: controlled terminal-style reveal, but polished enough for SaaS hero copy instead of retro terminal cosplay.

Markup: `<p class="type">Observability, billing, and retries in one surface.</p>`

```css
.type {
  width: 42ch;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  color: #fff;
  border-right: 1px solid rgba(255, 45, 76, 0.7);
  animation:
    typing 3.2s steps(42, end),
    caret 0.9s step-end infinite;
}
@keyframes typing {
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

Browser support: All current evergreen browsers.
Performance: Low.
Use here: hero subheads, product walkthrough intros, command-line style docs sections.

### C4. Split-Letter Rise Reveal

Looks like: individual letters slide into place with a precise stagger, giving titles motion without feeling like a motion-graphics reel.

Markup: `<h2 class="split"><span style="--i:0">S</span><span style="--i:1">y</span><span style="--i:2">n</span><span style="--i:3">c</span></h2>`

```css
.split span {
  display: inline-block;
  color: #fff;
  opacity: 0;
  transform: translateY(0.8em) scale(0.98);
  animation: rise 0.55s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  animation-delay: calc(var(--i) * 60ms);
}
@keyframes rise {
  to {
    opacity: 1;
    transform: none;
  }
}
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Low.
Use here: section headers, onboarding steps, card titles in reveal sequences.

### C5. Variable Font Axis Animation

Looks like: the type subtly shifts in weight across a loop, which feels especially good on a dark interface with a modern grotesk variable font.

Markup: `<h3 class="varfont">Latency</h3>`

```css
.varfont {
  --w: 520;
  font-family: "InterVariable", "SF Pro Display", sans-serif;
  color: #fff;
  font-variation-settings: "wght" var(--w);
  animation: wght 2.8s ease-in-out infinite alternate;
}
@keyframes wght {
  from {
    --w: 430;
  }
  to {
    --w: 720;
  }
}
```

Browser support: Current Chrome/Safari/Firefox support `font-variation-settings`; the visual effect obviously requires a variable font in your stack.
Performance: Low.
Use here: hero headlines, large numeric counters, brand marks, plan labels.

## D. Borders

### D1. Rotating Conic Border

Looks like: a living border where light slowly circulates around the component edge instead of flashing everywhere at once.

Markup: `<div class="orbit-border"></div>`

```css
@property --ang {
  syntax: "<angle>";
  inherits: false;
  initial-value: 0deg;
}
.orbit-border {
  --ang: 0deg;
  border: 1px solid transparent;
  border-radius: 20px;
  padding: 1rem;
  background:
    linear-gradient(#111214, #111214) padding-box,
    conic-gradient(
        from var(--ang),
        rgba(255, 255, 255, 0.12),
        rgba(255, 45, 76, 0.8),
        rgba(39, 211, 195, 0.55),
        rgba(255, 255, 255, 0.12)
      )
      border-box;
  animation: turn 8s linear infinite;
}
@keyframes turn {
  to {
    --ang: 360deg;
  }
}
```

Browser support: Chrome/Safari current versions are strong; current Firefox also supports `@property`, but older ESRs may fall back to a static border.
Performance: Low to medium.
Use here: active cards, upgrade CTA wrappers, selected filters, premium panels.

### D2. Subtle Animated Dash Border

Looks like: an understated “marching ants” perimeter, but tuned to feel like system motion rather than a selection marquee.

Markup: `<div class="ants"></div>`

```css
.ants {
  border-radius: 18px;
  background:
    repeating-linear-gradient(
        90deg,
        rgba(255, 255, 255, 0.24) 0 8px,
        transparent 8px 16px
      )
      top/200% 1px no-repeat,
    repeating-linear-gradient(
        90deg,
        rgba(255, 255, 255, 0.24) 0 8px,
        transparent 8px 16px
      )
      bottom/200% 1px no-repeat,
    repeating-linear-gradient(
        0deg,
        rgba(255, 255, 255, 0.24) 0 8px,
        transparent 8px 16px
      )
      left/1px 200% no-repeat,
    repeating-linear-gradient(
        0deg,
        rgba(255, 255, 255, 0.24) 0 8px,
        transparent 8px 16px
      )
      right/1px 200% no-repeat;
  animation: ants 12s linear infinite;
}
@keyframes ants {
  to {
    background-position:
      100% 0,
      -100% 100%,
      0 -100%,
      100% 100%;
  }
}
```

Browser support: Works in current Chrome/Safari/Firefox without special features.
Performance: Low.
Use here: upload dropzones, pending approval cards, editable zones, drag-and-drop targets.

### D3. Hover Glow With Corner Markers

Looks like: a disciplined card border that stays quiet until hover, then lights up at the corners instead of flooding the whole edge.

Markup: `<article class="corner-frame"></article>`

```css
.corner-frame {
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 20px;
  transition: 0.25s ease;
}
.corner-frame::before,
.corner-frame::after {
  content: "";
  position: absolute;
  width: 14px;
  height: 14px;
  border: 1px solid rgba(255, 45, 76, 0.55);
  transition: 0.25s ease;
}
.corner-frame::before {
  top: -1px;
  left: -1px;
  border-right: 0;
  border-bottom: 0;
}
.corner-frame::after {
  right: -1px;
  bottom: -1px;
  border-left: 0;
  border-top: 0;
}
.corner-frame:hover {
  box-shadow:
    0 0 0 1px rgba(255, 45, 76, 0.22),
    0 18px 42px rgba(255, 45, 76, 0.1);
}
```

Browser support: All current browsers.
Performance: Low.
Use here: feature cards, selected table rows, code blocks, interactive stat tiles.

## E. Cards

### E1. Pointer Tilt Card

Looks like: a card that leans slightly toward the cursor, creating depth without entering gimmick territory.

```html
<div class="tilt-card">P95 latency<br /><strong>82ms</strong></div>
<style>
  .tilt-card {
    --rx: 0deg;
    --ry: 0deg;
    width: 220px;
    padding: 1.2rem;
    border-radius: 20px;
    background: linear-gradient(180deg, #17191d, #101113);
    color: #fff;
    transform-style: preserve-3d;
    transform: perspective(900px) rotateX(var(--rx)) rotateY(var(--ry));
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.38);
    transition: transform 0.12s ease;
  }
</style>
<script>
  const tc = document.querySelector(".tilt-card");
  tc.onmousemove = (e) => {
    const r = tc.getBoundingClientRect(),
      x = e.clientX - r.left - r.width / 2,
      y = e.clientY - r.top - r.height / 2;
    tc.style.setProperty("--ry", `${x / 18}deg`);
    tc.style.setProperty("--rx", `${-y / 18}deg`);
  };
  tc.onmouseleave = () => {
    tc.style.setProperty("--rx", "0deg");
    tc.style.setProperty("--ry", "0deg");
  };
</script>
```

Browser support: Chrome/Safari/Firefox 2024+ all good.
Performance: Medium; great for a few featured cards, not a 50-card grid.
Use here: hero stat cards, pricing highlights, feature callouts.

### E2. Hover Lift + Tight Glow

Looks like: a card rises a few pixels and gains a faint red underglow, similar to the kind of motion SaaS dashboards use to confirm interactivity.

Markup: `<article class="lift-card"></article>`

```css
.lift-card {
  background: linear-gradient(180deg, #17191d, #111214);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    border-color 0.22s ease;
}
.lift-card:hover {
  transform: translateY(-6px);
  border-color: rgba(255, 45, 76, 0.2);
  box-shadow:
    0 20px 50px rgba(0, 0, 0, 0.34),
    0 10px 28px rgba(255, 45, 76, 0.1);
}
```

Browser support: All current browsers.
Performance: Low.
Use here: dashboard cards, pricing tiles, action shortcuts, documentation cards.

### E3. Perspective Stack

Looks like: stacked cards that fan out slightly, which is especially effective for changelog previews, plans, or multiple environment states.

Markup: `<div class="stack"><article></article><article></article><article></article></div>`

```css
.stack {
  position: relative;
  width: 260px;
  height: 180px;
}
.stack article {
  position: absolute;
  inset: 0;
  border-radius: 20px;
  background: #121316;
  border: 1px solid rgba(255, 255, 255, 0.07);
  transition:
    transform 0.28s ease,
    box-shadow 0.28s ease;
}
.stack article:nth-child(1) {
  transform: translateY(18px) scale(0.96);
}
.stack article:nth-child(2) {
  transform: translateY(9px) scale(0.98);
}
.stack:hover article:nth-child(1) {
  transform: translate(-14px, 22px) rotate(-3deg);
}
.stack:hover article:nth-child(2) {
  transform: translate(14px, 10px) rotate(3deg);
}
.stack:hover article:nth-child(3) {
  box-shadow: 0 26px 60px rgba(0, 0, 0, 0.42);
}
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Low.
Use here: plan stacks, changelog cards, browser tabs, workspace switchers.

### E4. Asymmetric Bento Card With Hover Reveal

Looks like: a bento grid with uneven spans and a detail layer that slides up only when the card is intentionally explored.

Markup: `<article class="bento"><span class="meta">Multi-region failover</span></article>`

```css
.bento {
  min-height: 190px;
  border-radius: 24px;
  padding: 1.2rem;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(
      circle at top right,
      rgba(88, 166, 255, 0.12),
      transparent 35%
    ),
    #111214;
  border: 1px solid rgba(255, 255, 255, 0.07);
  grid-column: span 2;
}
.bento .meta {
  position: absolute;
  left: 1.2rem;
  right: 1.2rem;
  bottom: 1rem;
  color: rgba(255, 255, 255, 0.78);
  transform: translateY(18px);
  opacity: 0;
  transition: 0.24s ease;
}
.bento:hover .meta {
  transform: none;
  opacity: 1;
}
```

Browser support: All current browsers.
Performance: Low.
Use here: bento homepages, feature overviews, analytics overview panels.

## F. Buttons

### F1. Shimmer Sweep Button

Looks like: a matte dark button with a diagonal specular sweep moving across it, the sort of motion that feels premium without feeling gamified.

Markup: `<button class="btn-shimmer">Deploy now</button>`

```css
.btn-shimmer {
  position: relative;
  overflow: hidden;
  padding: 0.9rem 1.2rem;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(180deg, #1b1d21, #111214);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.btn-shimmer::before {
  content: "";
  position: absolute;
  inset: -40% auto -40% -30%;
  width: 40%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.24),
    transparent
  );
  transform: skewX(-22deg) translateX(-240%);
  transition: transform 0.7s ease;
}
.btn-shimmer:hover::before {
  transform: skewX(-22deg) translateX(520%);
}
```

Browser support: All current browsers.
Performance: Low.
Use here: primary CTAs, checkout buttons, launch buttons, dialog confirms.

### F2. Magnetic Gradient Outline Button

Looks like: an outlined button whose internal glow follows the pointer slightly, echoing the “magnetic” feel used in polished product marketing sites.

```html
<button class="mag-btn">Open workspace</button>
<style>
  .mag-btn {
    --x: 50%;
    --y: 50%;
    padding: 0.95rem 1.25rem;
    border-radius: 14px;
    color: #fff;
    position: relative;
    background:
      radial-gradient(
        circle at var(--x) var(--y),
        rgba(255, 45, 76, 0.18),
        transparent 38%
      ),
      #101113;
    border: 1px solid rgba(255, 255, 255, 0.12);
    transition:
      transform 0.16s ease,
      border-color 0.16s ease;
  }
  .mag-btn:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 45, 76, 0.24);
  }
</style>
<script>
  const mb = document.querySelector(".mag-btn");
  mb.onmousemove = (e) => {
    const r = mb.getBoundingClientRect();
    mb.style.setProperty("--x", `${e.clientX - r.left}px`);
    mb.style.setProperty("--y", `${e.clientY - r.top}px`);
  };
  mb.onmouseleave = () => {
    mb.style.setProperty("--x", "50%");
    mb.style.setProperty("--y", "50%");
  };
</script>
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Medium.
Use here: hero CTAs, secondary feature buttons, toolbar actions with premium emphasis.

### F3. Pressed Depth + Ripple

Looks like: a button that physically depresses and emits a contained radial ripple from the click point, which makes small interfaces feel far more expensive.

```html
<button class="press">Run check</button>
<style>
  .press {
    position: relative;
    overflow: hidden;
    padding: 0.9rem 1.2rem;
    border-radius: 14px;
    color: #fff;
    border: 0;
    background: linear-gradient(180deg, #ff4864, #d91f3f);
    box-shadow:
      0 8px 0 #8e1027,
      0 18px 32px rgba(255, 45, 76, 0.18);
  }
  .press:active {
    transform: translateY(4px);
    box-shadow:
      0 4px 0 #8e1027,
      0 10px 18px rgba(255, 45, 76, 0.16);
  }
  .press span {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.28);
    transform: translate(-50%, -50%) scale(0);
    animation: r 0.55s ease-out;
  }
  @keyframes r {
    to {
      transform: translate(-50%, -50%) scale(18);
      opacity: 0;
    }
  }
</style>
<script>
  const p = document.querySelector(".press");
  p.onclick = (e) => {
    const s = document.createElement("span"),
      r = p.getBoundingClientRect();
    s.style.left = `${e.clientX - r.left}px`;
    s.style.top = `${e.clientY - r.top}px`;
    p.append(s);
    setTimeout(() => s.remove(), 550);
  };
</script>
```

Browser support: All current evergreen browsers.
Performance: Low to medium.
Use here: primary actions, destructive confirms, command buttons.

## G. Loaders

### G1. Skeleton Shimmer

Looks like: a dark placeholder block with a narrow passing light, closer to Stripe/Vercel loading states than generic gray bars.

Markup: `<div class="skeleton"></div>`

```css
.skeleton {
  height: 18px;
  border-radius: 999px;
  overflow: hidden;
  background: #15171b;
  position: relative;
}
.skeleton::after {
  content: "";
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.14),
    transparent
  );
  animation: sk 1.2s linear infinite;
}
@keyframes sk {
  to {
    transform: translateX(100%);
  }
}
```

Browser support: All current browsers.
Performance: Low.
Use here: table rows, card titles, chart placeholders, command palette loading.

### G2. Gradient Progress Rail

Looks like: a slim progress rail with a multi-hue fill that reads “system status” rather than “gamified progress bar.”

Markup: `<div class="progress" style="--p:72%"></div>`

```css
.progress {
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}
.progress::after {
  content: "";
  display: block;
  height: 100%;
  width: var(--p, 60%);
  background: linear-gradient(90deg, #ff2d4c, #58a6ff, #27d3c3);
  box-shadow: 0 0 20px rgba(255, 45, 76, 0.18);
}
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Low.
Use here: uploads, onboarding completion, sync status, deployment steps.

### G3. Staggered Pulse Dots

Looks like: three clean dots pulsing in sequence, but on a black surface with tighter timing so it feels more product UI than chat bubble loader.

Markup: `<div class="dots"><span></span><span></span><span></span></div>`

```css
.dots {
  display: flex;
  gap: 8px;
}
.dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  opacity: 0.28;
  animation: pulse 0.9s ease-in-out infinite;
}
.dots span:nth-child(2) {
  animation-delay: 0.12s;
}
.dots span:nth-child(3) {
  animation-delay: 0.24s;
}
@keyframes pulse {
  50% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
```

Browser support: All current browsers.
Performance: Low.
Use here: chat loading, async actions, compact list loaders.

### G4. Conic Spinner Ring

Looks like: a thin ring spinner with a bright segment and muted remainder, which reads more like an instrument dial than a generic loader.

Markup: `<div class="ring-spin"></div>`

```css
.ring-spin {
  width: 28px;
  aspect-ratio: 1;
  border-radius: 50%;
  background: conic-gradient(
    from 90deg,
    rgba(255, 255, 255, 0.1),
    rgba(255, 45, 76, 0.95),
    rgba(255, 255, 255, 0.1)
  );
  mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 0);
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(1turn);
  }
}
```

Browser support: Current Chrome/Safari/Firefox support this; Safari prefers simple masks like the one above.
Performance: Low.
Use here: inline loaders, modal submits, search spinners.

### G5. Data-Stream Bars

Looks like: tiny vertical bars rising and falling asynchronously, ideal when you want loading to imply “data arriving” instead of “please wait.”

Markup: `<div class="stream"><span></span><span></span><span></span><span></span></div>`

```css
.stream {
  height: 22px;
  display: flex;
  align-items: end;
  gap: 4px;
}
.stream span {
  width: 4px;
  height: 20%;
  border-radius: 99px;
  background: linear-gradient(180deg, #fff, #ff2d4c);
  animation: bars 0.9s ease-in-out infinite alternate;
}
.stream span:nth-child(2) {
  animation-delay: 0.12s;
}
.stream span:nth-child(3) {
  animation-delay: 0.25s;
}
.stream span:nth-child(4) {
  animation-delay: 0.38s;
}
@keyframes bars {
  to {
    height: 100%;
  }
}
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Low.
Use here: streaming states, log viewers, analytics pending states.

## H. Data Visualization

### H1. Pure CSS Sparkline

Looks like: a small filled sparkline tile that suggests trend direction without needing SVG or canvas.

Markup: `<div class="spark"></div>`

```css
.spark {
  width: 140px;
  height: 44px;
  background:
    linear-gradient(180deg, rgba(88, 166, 255, 0.18), transparent),
    linear-gradient(180deg, transparent 92%, rgba(255, 255, 255, 0.06) 0);
  clip-path: polygon(
    0 78%,
    14% 62%,
    28% 68%,
    44% 36%,
    58% 48%,
    74% 26%,
    100% 8%,
    100% 100%,
    0 100%
  );
  border-radius: 12px;
}
```

Browser support: Current Chrome/Safari/Firefox work with `clip-path`.
Performance: Low.
Use here: dashboard KPIs, compact stat rows, pricing comparisons.

### H2. CSS Variable Bar Chart

Looks like: clean dark bars with per-bar heights driven by inline CSS variables, ideal for dashboard summaries where you do not want a full charting stack.

Markup: `<div class="bars"><span style="--v:42%"></span><span style="--v:68%"></span><span style="--v:88%"></span></div>`

```css
.bars {
  height: 120px;
  display: flex;
  align-items: end;
  gap: 10px;
}
.bars span {
  flex: 1;
  height: var(--v);
  border-radius: 10px 10px 4px 4px;
  background: linear-gradient(
    180deg,
    rgba(88, 166, 255, 0.9),
    rgba(255, 45, 76, 0.9)
  );
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}
```

Browser support: All current browsers.
Performance: Low.
Use here: revenue snapshots, environment usage, response-code distributions.

### H3. Ring Chart With Conic Gradient

Looks like: a compact ring chart with a precise progress cutout, perfect for percentage metrics on dark cards.

Markup: `<div class="ring" style="--val:72"></div>`

```css
.ring {
  --val: 72;
  width: 92px;
  aspect-ratio: 1;
  border-radius: 50%;
  background: conic-gradient(
    #ff2d4c calc(var(--val) * 1%),
    rgba(255, 255, 255, 0.08) 0
  );
  position: relative;
}
.ring::after {
  content: attr(style);
  content: "72%";
  position: absolute;
  inset: 10px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #0f1013;
  color: #fff;
  font: 600 14px/1 sans-serif;
}
```

Browser support: Current Chrome/Safari/Firefox all support `conic-gradient`.
Performance: Low.
Use here: completion, uptime, quota usage, SLA attainment.

### H4. KPI Counter With Trend Arrow

Looks like: a numerical KPI that counts upward on load and pairs with a restrained trend arrow, which makes metrics feel alive without chart noise.

```html
<div class="kpi" data-target="248">0 <em>+12%</em></div>
<style>
  .kpi {
    font:
      700 40px/1 "InterVariable",
      sans-serif;
    color: #fff;
    letter-spacing: -0.04em;
  }
  .kpi em {
    font: 600 14px/1 sans-serif;
    color: #38d39f;
    font-style: normal;
    margin-left: 0.5rem;
  }
  .kpi em::before {
    content: "↗ ";
    display: inline-block;
  }
</style>
<script>
  document.querySelectorAll(".kpi").forEach((el) => {
    let n = 0,
      t = +el.dataset.target,
      s = () => {
        n += Math.ceil((t - n) / 7);
        el.firstChild.textContent = n;
        if (n < t) requestAnimationFrame(s);
      };
    s();
  });
</script>
```

Browser support: All current browsers.
Performance: Low.
Use here: hero stats, dashboard tiles, billing panels, admin summaries.

## I. Navigation

### I1. Morphing Tabs With Sliding Pill

Looks like: a segmented control where a dark pill glides beneath the active label, exactly the kind of navigation micro-motion used in polished dashboards.

```html
<div class="tabs">
  <i class="pill"></i><button class="is-on">Overview</button
  ><button>Usage</button><button>Logs</button>
</div>
<style>
  .tabs {
    position: relative;
    display: inline-flex;
    padding: 4px;
    border-radius: 14px;
    background: #17191d;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .tabs button {
    position: relative;
    z-index: 1;
    padding: 0.7rem 1rem;
    border: 0;
    background: none;
    color: rgba(255, 255, 255, 0.66);
  }
  .tabs .pill {
    position: absolute;
    top: 4px;
    left: 4px;
    height: calc(100% - 8px);
    width: 96px;
    border-radius: 10px;
    background: #0f1013;
    transition: 0.24s ease;
  }
  .tabs .is-on {
    color: #fff;
  }
</style>
<script>
  const t = document.querySelector(".tabs"),
    p = t.querySelector(".pill");
  t.querySelectorAll("button").forEach(
    (b) =>
      (b.onclick = () => {
        t.querySelector(".is-on")?.classList.remove("is-on");
        b.classList.add("is-on");
        p.style.width = `${b.offsetWidth}px`;
        p.style.transform = `translateX(${b.offsetLeft - 4}px)`;
      }),
  );
</script>
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Low.
Use here: dashboards, settings screens, analytics panels, tabbed docs.

### I2. Chevron Breadcrumbs

Looks like: breadcrumb segments cut with angled arrow joins so the trail reads as a single system path instead of separate pills.

Markup: `<nav class="crumbs"><a>Ops</a><a>Deployments</a><a class="is-on">Production</a></nav>`

```css
.crumbs {
  display: flex;
  gap: 10px;
}
.crumbs a {
  padding: 0.65rem 1rem 0.65rem 1.2rem;
  color: rgba(255, 255, 255, 0.72);
  background: #14161a;
  clip-path: polygon(
    0 0,
    calc(100% - 12px) 0,
    100% 50%,
    calc(100% - 12px) 100%,
    0 100%,
    12px 50%
  );
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.crumbs .is-on {
  color: #fff;
  border-color: rgba(255, 45, 76, 0.22);
}
```

Browser support: Current Chrome/Safari/Firefox support `clip-path`.
Performance: Low.
Use here: docs hierarchies, admin paths, workflow breadcrumbs.

### I3. CSS-Only Collapsible Sidebar

Looks like: a dense dark sidebar that snaps between icon-first and expanded states with no framework logic at all.

```html
<input id="nav" type="checkbox" hidden />
<label for="nav" class="toggle">☰</label>
<aside class="side"><a>Dashboard</a><a>Billing</a><a>Logs</a></aside>
<style>
  .toggle {
    display: inline-grid;
    place-items: center;
    width: 42px;
    height: 42px;
    border-radius: 12px;
    background: #15171b;
    color: #fff;
  }
  .side {
    width: 76px;
    overflow: hidden;
    transition: width 0.22s ease;
    background: #101113;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
  }
  .side a {
    display: block;
    padding: 1rem 1.1rem;
    color: #fff;
    white-space: nowrap;
  }
  #nav:checked ~ .side {
    width: 220px;
  }
</style>
```

Browser support: All current browsers.
Performance: Low.
Use here: internal dashboards, admin panels, dense multi-tool products.

## J. Micro-Interactions

### J1. Copy Button Success Flash

Looks like: the button briefly fills with green and swaps label after copying, which gives crisp success feedback without opening a toast.

```html
<button class="copy" data-copy="sk_live_xxx">Copy key</button>
<style>
  .copy {
    padding: 0.8rem 1rem;
    border-radius: 14px;
    background: #15171b;
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: 0.2s ease;
  }
  .copy.ok {
    background: #123326;
    border-color: rgba(56, 211, 159, 0.28);
    box-shadow: 0 0 0 1px rgba(56, 211, 159, 0.18);
  }
</style>
<script>
  const c = document.querySelector(".copy");
  c.onclick = async () => {
    await navigator.clipboard.writeText(c.dataset.copy);
    c.textContent = "Copied";
    c.classList.add("ok");
    setTimeout(() => {
      c.textContent = "Copy key";
      c.classList.remove("ok");
    }, 1200);
  };
</script>
```

Browser support: Current Chrome/Safari/Firefox all support clipboard in secure contexts.
Performance: Low.
Use here: API keys, invite links, token copy actions, share buttons.

### J2. Tooltip Fade and Lift

Looks like: a tooltip that rises 6px and fades in, which feels cleaner and more premium than an instant pop.

Markup: `<button class="tip" data-tip="Only admins can change this">Org role</button>`

```css
.tip {
  position: relative;
}
.tip::after {
  content: attr(data-tip);
  position: absolute;
  left: 50%;
  bottom: calc(100% + 10px);
  transform: translate(-50%, 6px);
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  background: #0f1013;
  color: #fff;
  white-space: nowrap;
  border: 1px solid rgba(255, 255, 255, 0.08);
  opacity: 0;
  pointer-events: none;
  transition: 0.18s ease;
}
.tip:hover::after,
.tip:focus-visible::after {
  opacity: 1;
  transform: translate(-50%, 0);
}
```

Browser support: All current browsers.
Performance: Low.
Use here: icon buttons, forms, metrics, permission labels.

### J3. Badge Pulse With Status Ping

Looks like: a live status badge where the dot emits a faint pulse ring, exactly enough motion to read as “active” and nothing more.

Markup: `<span class="live-badge"><i></i>Live sync</span>`

```css
.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
}
.live-badge i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #38d39f;
  position: relative;
  box-shadow: 0 0 12px rgba(56, 211, 159, 0.45);
}
.live-badge i::after {
  content: "";
  position: absolute;
  inset: -5px;
  border-radius: 50%;
  border: 1px solid rgba(56, 211, 159, 0.35);
  animation: ping 1.8s ease-out infinite;
}
@keyframes ping {
  to {
    transform: scale(1.9);
    opacity: 0;
  }
}
```

Browser support: Chrome/Safari/Firefox 2024+ all good.
Performance: Low.
Use here: environment badges, service health, websocket state, deployment live markers.

## K. Dividers

### K1. Gradient Fade Divider

Looks like: a line that is strongest at the center and disappears at the edges, which feels much more intentional than a full-width rule on a black canvas.

Markup: `<hr class="fade-rule">`

```css
.fade-rule {
  height: 1px;
  border: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.18),
    rgba(255, 45, 76, 0.28),
    rgba(255, 255, 255, 0.18),
    transparent
  );
}
```

Browser support: All current browsers.
Performance: Low.
Use here: between dashboard sections, modal zones, pricing tiers, changelog entries.

### K2. Animated Section Mark Divider

Looks like: a numbered divider with a moving red mark passing across the line, useful when a section transition should feel like progress rather than a break.

Markup: `<div class="section-rule"><span>02</span></div>`

```css
.section-rule {
  position: relative;
  height: 32px;
  display: grid;
  place-items: center;
}
.section-rule::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
}
.section-rule::after {
  content: "";
  position: absolute;
  top: 50%;
  width: 48px;
  height: 2px;
  background: #ff2d4c;
  animation: mark 3.5s ease-in-out infinite;
}
.section-rule span {
  position: relative;
  padding: 0 0.7rem;
  background: #0a0a0a;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
}
@keyframes mark {
  0%,
  100% {
    transform: translateX(-120px);
  }
  50% {
    transform: translateX(120px);
  }
}
```

Browser support: All current browsers.
Performance: Low.
Use here: long-form landing pages, onboarding flows, docs sections, pricing comparisons.

## L. Focus States

### L1. Multi-Layer Focus Ring

Looks like: a focus state with a crisp white inner ring and a soft red outer glow, much better matched to a dark premium interface than the default blue halo.

Markup: `<button class="focus-ring">Focus me</button>`

```css
.focus-ring:focus-visible {
  outline: 0;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.92),
    0 0 0 4px rgba(255, 45, 76, 0.26),
    0 0 18px rgba(255, 45, 76, 0.2);
}
```

Browser support: Chrome/Safari/Firefox 2024+ all support `:focus-visible`.
Performance: Low.
Use here: buttons, links, inputs, tab triggers, menu items.

### L2. Underline Sweep Focus

Looks like: a text link whose underline grows from left to right on focus or hover, which keeps low-density text navigation feeling tactile.

Markup: `<a class="focus-line" href="#">Billing settings</a>`

```css
.focus-line {
  color: #fff;
  text-decoration: none;
  background: linear-gradient(#ff2d4c, #ff2d4c) 0 100%/0 1px no-repeat;
  transition:
    background-size 0.22s ease,
    color 0.22s ease;
}
.focus-line:hover,
.focus-line:focus-visible {
  background-size: 100% 1px;
}
```

Browser support: All current browsers.
Performance: Low.
Use here: nav links, inline actions, docs sidebars, account settings.

## M. Transitions

### M1. View Transitions API Page Swap

Looks like: the old page softly fades and scales while the new page comes forward, which is one of the cleanest possible upgrades for multi-page dark products.

```html
<style>
  ::view-transition-old(root) {
    animation: old 0.24s ease both;
  }
  ::view-transition-new(root) {
    animation: new 0.24s ease both;
  }
  @keyframes old {
    to {
      opacity: 0;
      transform: scale(0.985);
    }
  }
  @keyframes new {
    from {
      opacity: 0;
      transform: scale(1.01);
    }
  }
</style>
<script>
  document.querySelectorAll("a[href]").forEach((a) =>
    a.addEventListener("click", (e) => {
      if (!document.startViewTransition || a.origin !== location.origin) return;
      e.preventDefault();
      document.startViewTransition(() => (location.href = a.href));
    }),
  );
</script>
```

Browser support: Current Chrome is safest; current Safari and Firefox also support View Transitions in modern versions, but this was not universally complete across 2024-era builds, so keep the normal navigation path intact.
Performance: Low.
Use here: app shell page swaps, docs navigation, settings pages, product marketing with multiple routes.

### M2. Scroll-Driven Reveal + Sticky Gradient Band

Looks like: content gently rises and fades in as it enters the viewport while a sticky gradient band keeps the section edge visually alive.

Markup: `<div class="sticky-band"></div><section class="reveal-block"></section>`

```css
.sticky-band {
  position: sticky;
  top: 0;
  height: 96px;
  z-index: -1;
  background: linear-gradient(180deg, rgba(255, 45, 76, 0.18), transparent);
}
.reveal-block {
  animation: reveal both;
  animation-timeline: view();
  animation-range: entry 10% cover 38%;
}
@keyframes reveal {
  from {
    opacity: 0;
    transform: translateY(28px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
```

Browser support: Current Chrome and Safari are good for scroll-driven animation; Firefox still lags or requires fallback, so make sure the block remains fully readable without the animation.
Performance: Low to medium.
Use here: long marketing pages, docs sections, release notes, onboarding sequences.

## N. Cursor Effects

### N1. Custom Cursor With Magnetic Glow

Looks like: the system pointer becomes a soft red-white instrument dot that enlarges around interactive targets.

```html
<div class="cursor-dot"></div>
<style>
  html,
  button,
  a {
    cursor: none;
  }
  .cursor-dot {
    position: fixed;
    top: 0;
    left: 0;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    pointer-events: none;
    background: #fff;
    box-shadow:
      0 0 0 8px rgba(255, 45, 76, 0.12),
      0 0 16px rgba(255, 45, 76, 0.22);
    transform: translate(-50%, -50%);
    z-index: 9999;
    transition:
      width 0.16s,
      height 0.16s,
      box-shadow 0.16s;
  }
  .is-hover .cursor-dot {
    width: 18px;
    height: 18px;
    box-shadow:
      0 0 0 14px rgba(255, 45, 76, 0.14),
      0 0 22px rgba(255, 45, 76, 0.22);
  }
</style>
<script>
  const d = document.querySelector(".cursor-dot");
  addEventListener("mousemove", (e) => {
    d.style.left = e.clientX + "px";
    d.style.top = e.clientY + "px";
  });
  document.querySelectorAll("a,button").forEach((el) => {
    el.onmouseenter = () => document.body.classList.add("is-hover");
    el.onmouseleave = () => document.body.classList.remove("is-hover");
  });
</script>
```

Browser support: Chrome/Safari/Firefox 2024+ all fine on desktop; do not enable on touch devices.
Performance: Medium.
Use here: marketing hero sections, product microsites, premium landing pages.

### N2. Trailing Dot Follower

Looks like: a small trailing point lags behind the main pointer, which adds polish on large dark canvases without becoming a full-blown cursor toy.

```html
<div class="trail"></div>
<style>
  .trail {
    position: fixed;
    top: 0;
    left: 0;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    pointer-events: none;
    background: #ff2d4c;
    box-shadow: 0 0 14px rgba(255, 45, 76, 0.4);
    transform: translate(-50%, -50%);
    z-index: 9998;
  }
</style>
<script>
  const t = document.querySelector(".trail");
  let x = 0,
    y = 0,
    tx = 0,
    ty = 0;
  addEventListener("mousemove", (e) => {
    tx = e.clientX;
    ty = e.clientY;
  });
  (function loop() {
    x += (tx - x) * 0.16;
    y += (ty - y) * 0.16;
    t.style.left = x + "px";
    t.style.top = y + "px";
    requestAnimationFrame(loop);
  })();
</script>
```

Browser support: All current desktop Chrome/Safari/Firefox.
Performance: Medium; still cheap for one follower.
Use here: hero canvases, portfolio-like landing panels, premium showcase sections.

## O. Scroll Effects

### O1. Layered Scroll Parallax

Looks like: background layers move at different rates as you scroll, giving a deep technical stage without resorting to video or WebGL.

```html
<section class="parallax">
  <div class="layer l1"></div>
  <div class="layer l2"></div>
  <div class="layer l3"></div>
</section>
<style>
  .parallax {
    --s: 0;
    height: 320px;
    position: relative;
    overflow: hidden;
    background: #0a0a0a;
  }
  .layer {
    position: absolute;
    inset: -10%;
    transform: translateY(calc(var(--s) * var(--d)));
  }
  .l1 {
    --d: 0.08;
    background: radial-gradient(
      circle at 20% 30%,
      rgba(255, 45, 76, 0.16),
      transparent 30%
    );
  }
  .l2 {
    --d: 0.16;
    background: radial-gradient(
      circle at 70% 40%,
      rgba(88, 166, 255, 0.14),
      transparent 34%
    );
  }
  .l3 {
    --d: 0.24;
    background: radial-gradient(
      circle at 50% 70%,
      rgba(39, 211, 195, 0.1),
      transparent 30%
    );
  }
</style>
<script>
  const px = document.querySelector(".parallax");
  addEventListener(
    "scroll",
    () => px.style.setProperty("--s", scrollY + "px"),
    { passive: true },
  );
</script>
```

Browser support: Chrome/Safari/Firefox 2024+ all fine.
Performance: Medium; keep the number of layers low.
Use here: hero sections, pricing intros, feature transitions.

### O2. Horizontal Snap Panels With Intersection Reveal

Looks like: side-scrolling panels that snap cleanly while each card fades up as it becomes active, great for feature storytelling on dark surfaces.

```html
<div class="snap">
  <section class="panel"></section>
  <section class="panel"></section>
  <section class="panel"></section>
</div>
<style>
  .snap {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 85%;
    gap: 20px;
    overflow: auto;
    scroll-snap-type: x mandatory;
  }
  .panel {
    min-height: 220px;
    scroll-snap-align: start;
    border-radius: 24px;
    background: #121316;
    border: 1px solid rgba(255, 255, 255, 0.08);
    opacity: 0.45;
    transform: translateY(16px);
    transition: 0.28s ease;
  }
  .panel.in {
    opacity: 1;
    transform: none;
  }
</style>
<script>
  const io = new IntersectionObserver(
    (es) =>
      es.forEach((e) => e.target.classList.toggle("in", e.isIntersecting)),
    { threshold: 0.55 },
  );
  document.querySelectorAll(".panel").forEach((p) => io.observe(p));
</script>
```

Browser support: Current Chrome/Safari/Firefox all support `scroll-snap` and Intersection Observer.
Performance: Low to medium.
Use here: feature tours, roadmap timelines, mobile carousels, case-study sequences.

## Practical Notes By Feature Family

`backdrop-filter`: good now in current Chrome/Safari/Firefox, but still best treated as a luxury layer. Keep a readable translucent base without it.

`conic-gradient`: broadly safe in current browsers and ideal for ring charts, spinners, rotating borders, and ambient background sweeps.

`@property`: now useful in current modern browsers, but older enterprise/ESR environments may ignore smooth interpolation. When that happens, the component should still look fine in a static state.

View Transitions API: worth using for app shells and high-polish navigation, but should never be the only way a route change works.

Scroll-driven animation: excellent for marketing surfaces in Chrome/Safari; Firefox still deserves fallback treatment.

Variable font axis animation: visually strong, but only use if the actual font is variable and you are comfortable with slightly more typographic motion.

## Top 10 Immediately Usable

### 1. Perspective Grid Overlay

Why it ranks first: it instantly gives the app a technical stage without touching component logic, and it aligns perfectly with the Linear/Vercel family of restrained futurism.
Best immediate target: hero, dashboard headers, pricing hero.

### 2. Hover Lift + Tight Glow Card

Why it ranks second: it upgrades every grid in minutes and is almost impossible to break. The result feels modern even if the underlying component is plain.
Best immediate target: feature cards, metrics, dashboard tiles.

### 3. Morphing Tabs With Sliding Pill

Why it ranks third: it makes navigation feel product-grade immediately. It is one of the most “SaaS premium” motions in the entire set.
Best immediate target: settings, analytics, docs, workspace switchers.

### 4. Rotating Conic Border

Why it ranks fourth: it is a strong accent for selection and premium states without requiring more layout or more components.
Best immediate target: selected plan, active workspace, premium upsell, focused card.

### 5. Gradient Text With Tight Red Halo

Why it ranks fifth: it gives the brand voice a high-end, dark-product finish while staying far away from neon signage.
Best immediate target: hero headlines, feature titles, KPI numbers.

### 6. Frosted Instrument Panel

Why it ranks sixth: when used sparingly, it immediately adds hierarchy and depth to monochrome interfaces.
Best immediate target: floating nav, filter bars, overlays, command palette.

### 7. Shimmer Sweep Button

Why it ranks seventh: it is cheap, readable, and adds a premium cue to the main CTA without changing information architecture.
Best immediate target: primary CTAs, deploy/run/confirm buttons.

### 8. KPI Counter With Trend Arrow

Why it ranks eighth: it adds motion to data without requiring a charting library and turns otherwise static stats into active instrumentation.
Best immediate target: dashboard hero, admin top row, billing summary.

### 9. Gradient Fade Divider

Why it ranks ninth: it is extremely cheap but disproportionately improves section transitions on dark pages.
Best immediate target: docs, pricing sections, settings groups, modal partitions.

### 10. Conic Spinner Ring

Why it ranks tenth: it is a small detail, but loaders are where product polish leaks fastest. This one feels immediately more expensive than a default spinner.
Best immediate target: async actions, search, modal submits, inline refresh.

## Suggested First Pass for Your Exact Palette

If I were implementing this for your app first, I would start with this stack:

1. `A1` Matte Noise Grain for the overall shell.
2. `A3` Perspective Grid Overlay in the hero or top dashboard zone.
3. `B1` Frosted Instrument Panel for sticky nav or filter rows.
4. `D1` Rotating Conic Border only for the currently selected plan or environment.
5. `E2` Hover Lift + Tight Glow for all dashboard cards.
6. `F1` Shimmer Sweep for the main red CTA.
7. `H4` KPI Counter With Trend Arrow for top-level metrics.
8. `I1` Morphing Tabs With Sliding Pill for analytics/settings navigation.
9. `K1` Gradient Fade Divider for section rhythm.
10. `L1` Multi-Layer Focus Ring everywhere keyboard focus matters.

That combination gives you the right family resemblance to Linear/Vercel/Stripe immediately: monochrome base, precise motion, selective premium accents, no cyberpunk drift.

## Sources Used

Visual direction and current browser-support assumptions were informed by:

- Linear: https://linear.app/
- Vercel: https://vercel.com/
- Stripe: https://stripe.com/
- Anthropic Claude: https://www.anthropic.com/claude
- Cursor: https://www.cursor.com/
- Resend: https://resend.com/
- Supabase: https://supabase.com/
- MDN `backdrop-filter`: https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- MDN `conic-gradient()`: https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/conic-gradient
- MDN `@property`: https://developer.mozilla.org/en-US/docs/Web/CSS/@property
- MDN `font-variation-settings`: https://developer.mozilla.org/en-US/docs/Web/CSS/font-variation-settings
- MDN View Transition API: https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API
- MDN CSS Scroll-Driven Animations: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations

If you want, I can turn this into an actual `design-research-dark-ui.md` file in the repo and then extract a smaller “production shortlist” stylesheet with only the 10 safest patterns.
