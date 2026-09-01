---
lane: L01 — Colour systems, with night/dark as the hard case
seat: Claude Opus 5 (1M context), effort xhigh
date: 2026-08-31
sources_verified_live: 23
sources_from_memory: 5
adversarial_review: exempt-raw-lane-output-synthesis-carries-the-review
---

## Executive summary

1. **Dark is not light inverted — it is light re-derived.** Measured across Radix and IBM Carbon, the dark ramp spends **1.2–1.6× more lightness travel** than the light ramp to express the same eight steps of hierarchy. Copy a light ladder and flip it and you get the flat, "default dark theme" look, mechanically.
2. **The chroma of your "black" is a designed number with a narrow measured envelope: C = 0.000 to 0.018 in OKLCH.** Carbon ships exactly 0.000 (pure achromatic). Material 3 ships 0.012 at hue 300°. Radix `slateDark` ships 0.004 rising to 0.016. Outside that band it stops reading as a surface and starts reading as a colour.
3. **`#C8102E` cannot be ink on a dark ground. Measured: APCA Lc −24 on `#141218`** — below APCA's own Lc 30 "spot-readable absolute minimum". There is **no** lightness of that hue that clears Lc 60 on both a near-black and a near-white ground (best achievable is 50.6 at L≈72%). One accent value for both themes is arithmetically impossible; you need two, joined by a contract, not by a hex.
4. **In shaded Bali daylight (~10,000 lux on a 400-nit phone) tone-based elevation dies.** My flare model puts a Material-3 elevation step at **1.05:1** and a hairline at **1.15:1**. Every "surface container" tier collapses into one flat plane. Whatever hierarchy the GARUDA VOA flow depends on must survive that, so it must be carried by line, space and type — not by tone.
5. **The 2026 tell to avoid is the indigo→purple gradient**, named by 925studios as *"the single loudest AI tell in 2026"*, traced to Tailwind's 2019 `indigo-500` default. It is the exact failure mode this project already hit three times: models return the median of their training data.

**How to read this report:** every hex below is either a *measurement of somebody else's shipped system* or *the output of a generator given a stated input*. None of them is a recommendation. The deliverable of this lane is the machinery — ramps, envelopes, contracts, acceptance tests — so that changing one input parameter produces a different, equally defensible palette. If anyone lifts a hex out of this document and paints with it, the lane has failed.

---

## Finding 1 — The elevation ladder is arithmetic, and dark needs ~1.5× the travel of light

**Named example.** IBM Carbon `@carbon/themes@11.80.0` and Radix Colors `@radix-ui/colors@3.0.0`, both read directly from package source.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://unpkg.com/@carbon/themes@11.80.0/js/generated/themes/g100.js · https://unpkg.com/@radix-ui/colors@3.0.0/index.js

**Measurable rule.** I converted every step to OKLCH locally. Carbon g100: `background #161616` L=20.0 → `layer-01 #262626` L=26.9 → `layer-02 #393939` L=34.5 → `layer-03 #525252` L=43.9. Step sizes **+6.9, +7.6, +9.4** L-points, *increasing* as you climb. Carbon's own light theme moves the other way and by less: `white` background L=100.0 → `layer-01 #f4f4f4` L=96.7, a step of **−3.3**.

Radix says the same thing independently. Steps 1→8 of the same scale:

| scale | light travel | dark travel | ratio |
|---|---|---|---|
| `gray` | −19.9 L | +31.1 L | **1.56×** |
| `slate` | −19.8 L | +31.1 L | **1.57×** |
| `red` | −24.9 L | +35.6 L | **1.43×** |
| `grass` | −27.7 L | +33.6 L | **1.21×** |

Two independent, admired systems converge on: *the dark ladder needs roughly 1.2–1.6× the lightness travel of the light ladder for the same perceived number of levels.* Material 3's dark ladder is the tightest of the three — `surface #141218` L=18.7 up to `surface-bright #3b383e` L=34.6, seven tiers inside 16 L-points, steps of +1.6 to +5.2 — which is precisely why M3 dark reads as *flat* unless you also use its tint.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://raw.githubusercontent.com/material-components/material-web/main/tokens/versions/v0_192/_md-ref-palette.scss

**What to steal, for Bali Zero.** Define surfaces as an *L-ladder in OKLCH with a declared step size*, not as a list of hexes. For the Visa Oracle verdict card — which sits on the page, holds a price, and must feel lifted — the card should be **one step ≥ +7 L above its page** in dark, and **one step ≥ −3.5 L below its page** in light. That replaces "pick a slightly lighter grey". Ship it as a token: `--surface-step-dark: 7; --surface-step-light: 3.5;` and generate.

**What to avoid.** The fad version is `filter: brightness(1.1)` or `background: rgba(255,255,255,0.05)` on a card. Tell them apart: a real ladder is *asymmetric between modes and non-uniform between steps*; the fad is one constant applied everywhere, which is exactly what produces fifteen identical night modes.

---

## Finding 2 — The chroma of the "black" is a variable, and its envelope is 0.000–0.018

**Named example.** Three shipped systems, three different answers, all measured by me from source:

| system | darkest surface | OKLCH L | OKLCH C | hue |
|---|---|---|---|---|
| IBM Carbon g100 | `#161616` | 20.0 | **0.0000** | — |
| Radix `grayDark` 1 | `#111111` | 17.8 | **0.0000** | — |
| Radix `slateDark` 1 | `#111113` | 17.9 | **0.0041** | 286° |
| Material 3 dark `surface` | `#141218` | 18.7 | **0.0124** | 300° |
| Radix `redDark` 1 | `#191111` | 18.8 | **0.0135** | 18° |

**Measurable rule.** Every one of them lands at **L ≈ 18–20%**, and none of them exceeds **C = 0.018** anywhere in its neutral ramp (Radix `slateDark` peaks at 0.0155 at step 8; M3's neutral-variant peaks at 0.0178). That is the whole envelope. Below ~0.004 it is a true grey; 0.004–0.018 is a *tinted* grey that carries brand hue without becoming a colour; above that it stops being a surface. Radix `redDark1 #191111` is the interesting one: it is a near-black **derived from the red hue itself** (H=18°, C=0.0135) — proof that "black tinted with the brand" is a real, shipped technique, not a mood.

Note also: **none of these is `#000000`, and none is `#121212` either.** L≈18–20% in OKLCH is the convergence point, and `#121212` is L=18.2 — so the folklore number is roughly right but the *reason* is the L value, not the hex.

**What to steal.** Expose exactly one knob, `κ` (kappa) = neutral chroma at the endpoints, with an acceptance test `κ_peak ≤ 0.018`. Set κ=0.000 and you get a Carbon-like industrial neutral. Set κ=0.006 and you get a surface that whispers the brand hue. That single parameter is worth more to this project than any palette, because *two different values of κ produce two visibly different products from the same brand colour* — which is the divergence the previous rounds could not manufacture.

**What to avoid.** "Blue-black" as an unexamined default. A blue-black is just κ≈0.03 at H≈265°, i.e. **outside** the envelope every reference system stays inside — and it is the exact hue that maximises the chromostereopsis span against a red accent (Finding 6). The tell: if you can *name the colour of the background* ("navy", "midnight blue"), κ is too high.

---

## Finding 3 — Hairlines live in a measured band *below* text thresholds, and the alpha trick is why they don't glow

**Named example.** Measured hairline contrasts, all against their own theme's base:

| token | value | APCA Lc | WCAG | meets SC 1.4.11 (3:1)? |
|---|---|---|---|---|
| Radix `grayDark6` (subtle separator) | `#3a3a3a` | **0.0** (below APCA's clip) | 1.55 | no |
| M3 `outline-variant` | `#49454f` | **−10.1** | 1.99 | no |
| Radix `grayDark7` (UI border) | `#484848` | **−10.0** | 1.92 | no |
| Carbon g100 `border-subtle-01` | `#525252` | **−14.0** | 2.32 | no |
| Radix `grayDark8` (hover border) | `#606060` | **−19.3** | 2.80 | no |
| Carbon g100 `border-strong-01` | `#6f6f6f` | **−26.0** | 3.60 | **yes** |
| M3 `outline` | `#938f99` | **−42.3** | 5.87 | **yes** |

**Measurable rule.** Non-interactive separators sit at **|Lc| 0–14**; interactive borders and focus rings at **|Lc| 19–42**. The subtle tier is *deliberately* under the 3:1 non-text threshold — it is decorative, and a *second, stronger* border token carries the accessibility obligation. That two-tier split is the mechanism, and it is what stops a hairline from glowing: you never push the decorative line up to a compliance number it was never meant to hit.

The second mechanism is Radix's alpha scales. `grayDarkA6 = #ffffff2c` (17.3% white). Composited, the *same token* yields `#3d3b40` on `#141218`, `#47464b` on `#211f26`, `#59575d` on `#36343b` — the line automatically tracks whatever surface it lands on, staying at |Lc| 0–11 in all three cases. A solid hex hairline cannot do that; it glows on the low surface and vanishes on the high one.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale (steps 6/7/8 defined as "subtle borders on components which are not interactive", "subtle borders on interactive components", "stronger borders … and focus rings")

**What to steal.** On all three surfaces, express every hairline as `color-mix(in srgb, var(--fg) 17%, transparent)` rather than a hex, and hold **two** border tokens with a written contract: `--border-subtle` targets |Lc| ≤ 14, `--border-strong` targets |Lc| ≥ 26 and WCAG ≥ 3:1. The GARUDA VOA form fields need `--border-strong` (they are components you must identify); the dividers between the four home-page segment doors need `--border-subtle`.

**What to avoid.** `border: 1px solid rgba(255,255,255,0.1)` sprinkled everywhere at one value. Tell them apart: the disciplined version has two tokens with two different numeric targets and a test; the fad version has one alpha the designer nudged until it "looked right" on one background.

---

## Finding 4 — Perceptual colour in production, 2026: what actually ships and what it costs

**Named example.** `oklch()` and `color-mix()` are both **Baseline Widely available, since May 2023** per MDN. Relative colour syntax (`oklch(from …)`) shipped in **Chrome 119, October 2023** per the Chrome team.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/oklch · https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix · https://developer.chrome.com/blog/css-relative-color-syntax

**Measurable rule and the concrete CSS.** The ranges that matter: **L 0–1, C 0–0.4 (`0.4` = `100%`), H 0–360, and `0deg` is magenta, not red.** Evil Martians' practical ceiling is **C < 0.37** for both sRGB and P3. Chroma is *not* a free parameter — I measured the sRGB ceiling for the flag-red hue (22.3°) across the ramp: it is **0.040 at L=10%, 0.242 at L=60%, 0.114 at L=80%, 0.025 at L=95%.** A constant-chroma ramp is impossible; chroma must be a function of L.

```css
:root {
  --brand-h: 22.3;                 /* the ONE input */
  --kappa: 0.006;                  /* neutral chroma, acceptance test: peak <= 0.018 */

  /* surfaces: an L-ladder, not a hex list */
  --s-0: oklch(17.8% calc(var(--kappa) * 1.0) var(--brand-h));
  --s-1: oklch(21.3% calc(var(--kappa) * 1.3) var(--brand-h));
  --s-2: oklch(28.5% calc(var(--kappa) * 1.9) var(--brand-h));
  --s-3: oklch(40.2% calc(var(--kappa) * 2.4) var(--brand-h));

  /* hairlines composite, so one token works on every surface */
  --hairline: color-mix(in srgb, currentColor 17%, transparent);
}
@media (color-gamut: p3) {          /* Evil Martians' gamut-widening pattern */
  :root { --accent: oklch(62.6% 0.24 var(--brand-h)); }
}
```

**What the fallback actually costs — honestly: almost nothing, and that is the trap.** Because both features are Baseline, the fallback story in 2026 is a two-line cascade (`background: #…; background: oklch(…)`), not a build step. The real cost is elsewhere: **out-of-gamut chroma is silently gamut-mapped by the browser**, so `oklch(62% 0.30 22)` and `oklch(62% 0.35 22)` can render as the *same* pixel on an sRGB phone while diverging on a P3 one. Your dark ladder can look correct on the designer's MacBook and mushy on a 360px Android. Evil Martians' answer is to declare sRGB-safe values in the base rule and widen only inside `@media (color-gamut: p3)`, with `stylelint-gamut` enforcing it.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl

**What to avoid.** Wide-gamut P3 accents as the *primary* accent. The audience here is on budget Android; wide-gamut coverage on that tier is unreliable (see "could not verify"). Use P3 as an enhancement to an sRGB-correct design, never as the design.

---

## Finding 5 — Building light and dark siblings from ONE brand colour: the actual arithmetic

**Named example.** Matt Ström's published generator, plus Radix's step-9 rule, plus Stripe's Lab-space method.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://mattstromawn.com/writing/generating-color-palettes/ · https://stripe.com/blog/accessible-color-systems · https://linear.app/now/how-we-redesigned-the-linear-ui

**Measurable rule — the four equations.** Ström gives them explicitly:

- **Lightness:** `L(n) = 1 − n` (linear in the scale position), with the branch flipping when the background luminance crosses `Y_b = 0.18`. That branch *is* the light/dark sibling rule stated as arithmetic.
- **Chroma envelope:** `S(n) = −4n² + 4n` — a parabola, zero at both ends, peak at mid-ramp. I verified it empirically in Radix: `slateDark` chroma runs 0.0041 → 0.0155 → 0.0029 across steps 1→8→12. That is the parabola, shipped.
- **Hue drift compensation:** `H(n) = H_base + 5·(1 − n)` — a 5° shift counteracting the Bezold–Brücke effect (perceived hue drifts as brightness changes). Radix's own `redDark` shows the same drift, from H=12.7° at step 3 to H=23.0° at step 9.
- **Contrast, not colour, is the contract.** Radix guarantees "**Lc 60 and Lc 90 APCA** on top of a step 2 background from the same scale" for steps 11 and 12 — and I confirmed it holds in *both* modes with different values: `gray11` is Lc −60.6 dark and +76.0 light; `gray12` is −95.5 dark and +99.7 light.

**The rule that makes them siblings rather than inversions.** Radix holds **step 9 — and only step 9 — byte-identical across light and dark** for every chromatic scale, and re-derives all eleven others:

| scale | light step 9 | dark step 9 | |
|---|---|---|---|
| red | `#e5484d` | `#e5484d` | **same** |
| tomato | `#e54d2e` | `#e54d2e` | **same** |
| grass | `#46a758` | `#46a758` | **same** |
| blue | `#0090ff` | `#0090ff` | **same** |
| gray | `#8d8d8d` | `#6e6e6e` | different |

The brand identity is one fixed point. Everything else is derived per-mode against an Lc contract. Grays have no identity to preserve, so even they move.

**And here is the hard constraint for `#C8102E` specifically.** Measured: OKLCH **L=53.0%, C=0.2074, H=22.3°** — sitting at **97% of the sRGB chroma ceiling** for its own lightness and hue. As ink it gives **Lc +77.1 on white** but **Lc −24.0 on `#141218`** (and −24.1 on a blue-black `#0B1020`). I searched the whole hue for a single lightness that clears Lc 60 on both grounds: **the maximum achievable is 50.6, at L≈72%.** It does not exist. What the flag red *can* do on a dark ground is be a **fill** — white on `#C8102E` measures Lc −82.4, comfortably above the Lc 75 body-text minimum.

**What to steal.** Ship the generator, not the palette. Inputs: `H_base`, `κ`, `dark_travel_multiplier` (1.2–1.6), and the Lc contract per step. Outputs: two ramps that pass their own tests. Then the answer to "the last three rounds all looked the same" is a *parameter sweep*, not a prompt. For the Visa Oracle verdict, the accent must be defined as *"the step whose Lc against the current surface is ≥ 60"* — which resolves to a different hex in each mode, automatically.

**What to avoid.** `filter: invert()` and its manual equivalent — hand-picking the "dark version" of each light hex. Tell them apart: siblings have **matched Lc and different L**; inversions have **matched L-complement and unpredictable Lc**.

---

## Finding 6 — Chromostereopsis: the evidence is real, and it points the opposite way from the folklore

**Named example.** Two peer-reviewed studies, both fetched.

**Study 1 — the threshold.** *Color difference threshold of chromostereopsis induced by flat display emission* (PMC4382974). Setup: DELL U2412M, 0.27 mm pixel pitch at 0.8 m, red 605 nm / blue 497 nm luminophores, 10 observers. Measured threshold for the illusory-depth percept: **Δx = 0.003, Δy = 0.004 in CIE chromaticity; Δλ ≤ 1 nm.** The strongest effect is along the **blue–red axis** of the display's CIE xyY space. Design guidance in the paper's own words: avoid "colors with a large wavelength span" on flat displays.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://pmc.ncbi.nlm.nih.gov/articles/PMC4382974/

**Study 2 — and it contradicts the assumption in the brief.** *Effect of Chromostereoscopic Stimulus on Accommodative Response and Subjective Perception* (PMC12962248). 30 healthy adults, mean age 19.83 ± 1.18. Seven conditions: black-on-white baseline plus red / green / blue / yellow text on black. Measured accommodative lag: **blue-on-black 0.61 D (worst), black-on-white 0.35 D (baseline), red-on-black 0.18 D (best)**, main effect p < .001. Blue text was rated *most difficult to read and most distant*. The authors' recommendation is to avoid **pure saturated blue text** on dark interfaces.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://pmc.ncbi.nlm.nih.gov/articles/PMC12962248/

**Measurable rule.** Saturated red on a dark ground is *not* the accommodative villain — short-wavelength blue is. But the *illusion* is a function of the **span** between the two chromatic extremes present, and its threshold is essentially zero (Δλ ≤ 1 nm). So the real rule is about the **pair**, not the red: keep the maximum hue span between any two saturated, similar-luminance elements on the same dark ground well under the red↔blue extreme. Measured hue distances from `#C8102E` (H=22.3°): a blue-black `#0B1020` sits at **112.8°** away; M3's tinted `#141218` at **81.9°**; a warm near-black `#0F0D0C` at **26.1°**.

**What to steal.** This is the finding that indicts the palette all three previous rounds converged on. **Blue-black ground + saturated red accent is the maximum-span pair** — the one configuration the 1995–2015 chromostereopsis literature specifically identifies, and on a dark ground red advances while blue recedes, so the accent literally floats. If the brand red stays, the ground must move *toward* it in hue: a near-black at 26–46° from the accent (κ small, hue warm) collapses the span by ~4×. Alternatively keep a cool ground and drop the accent's chroma at the point of adjacency.

**What to avoid.** Over-reading this. The measured accommodative penalty for red-on-black was *better* than black-on-white. Do not ban red; ban the **pairing** and the **saturation at the seam**. Tell them apart: a real chromostereopsis problem shows up as edge shimmer between two adjacent saturated fills; a fake one is somebody disliking red.

---

## Finding 7 — Semantic colour without hue, and the measurement that proves even Radix fails it

**Named example.** Radix's own step-9 solids, which are the intended "solid background" for semantic states.

**Measurable rule.** I converted them: `success #46a758` L=65.1 · `danger #e5484d` L=62.6 · `warning #ffc53d` L=85.4. **The minimum pairwise lightness separation among the three is 2.6 L-points** — success and danger. In greyscale, and for a deuteranope, *the two most consequential states in the entire system are the same colour.* Deuteranomaly + deuteranopia together affect roughly **6% of men**, and WCAG 2.2 SC 1.4.1 exists precisely for this.

The measurable rule is therefore a two-part acceptance test:
1. **Lightness separation:** any two semantic solids that can appear in the same context must differ by **≥ 12 OKLCH L-points** (the gap Radix achieves between warning and the other two: 20.3). Below that, colour alone is doing all the work.
2. **Redundant channel, always:** shape/icon + word. A verdict is `✓ Supported`, a refusal is `✕ Not supported`, a caution is `! Check this` — glyph, word, and colour, three channels.

**What to steal.** The Visa Oracle verdict is the highest-stakes surface in the product: a "supported" that reads as a "refused" is a lost client. Encode it as **glyph + word + lightness step + hue**, in that order of load-bearing. In the GARUDA VOA flow, the payment-state chips (`pending` / `paid` / `submitted` / `decided`) must pass the 12-L-point test against each other, or be differentiated by fill-vs-outline instead. Bonus: this is exactly what survives the daylight collapse in Finding 8, because glyph and word are shape, not tone.

**What to avoid.** The green-dot / red-dot status pattern with a tooltip. Tell them apart: screenshot it, desaturate it to greyscale, and hand it to someone. If they cannot read the verdict, it fails — and note that this test would fail Radix's own step-9 palette, which is why "use a good design system" is not a substitute for the test.

---

## Finding 8 — The Bali daylight flare model: where tone-based hierarchy dies

**Named example / method.** WCAG's contrast formula is `(L₁+0.05)/(L₂+0.05)`, and the **0.05 is itself a screen-flare constant** — ~5% of peak white. Replace it with a measured ambient term and you get a contrast figure for the actual environment. `L_reflected = E · ρ / π`; `f = L_reflected / L_peak`. With ρ = 4.5% (cheap glossy panel, weak AR coating) and a 400-nit phone:

| pair | night indoors (f=0.004) | near a window (f=0.036) | **shaded warung, 10k lux (f=0.358)** | open shade, 20k lux |
|---|---|---|---|---|
| dark body text | 76.0:1 | 18.8:1 | **3.07:1** | 2.04:1 |
| light body text | 66.6:1 | 21.9:1 | **3.67:1** | 2.36:1 |
| dark hairline | 6.6:1 | 2.3:1 | **1.15:1** | 1.08:1 |
| light hairline | 1.8:1 | 1.7:1 | **1.47:1** | 1.34:1 |
| dark elevation step (+2 tiers) | 2.7:1 | 1.4:1 | **1.05:1** | 1.02:1 |
| white on `#C8102E` | 7.6:1 | 6.3:1 | **2.79:1** | 2.03:1 |

**Measurable rule.** **WCAG's own 0.05 flare constant corresponds to ~1,400 lux on a 400-nit phone** — a bright office, not a Bali street. Past ~10,000 lux the entire tonal hierarchy compresses: a Material-3 elevation step reaches **1.05:1** and a dark hairline **1.15:1**. Both are invisible. Body text survives at 3:1, badly. The light theme retains ~20% more body-text contrast and ~28% more hairline contrast than the dark theme at the same ambient.

**What to steal.** Two things. (a) Treat **dark mode as the night default, not the only mode**, and make the light sibling genuinely first-class — the audience is described as "often at night" *and* on cheap Android in a tropical country, and those are two different designs joined by the Finding 5 contract. (b) On the GARUDA VOA flow specifically — a payment path someone will complete standing outside an immigration office — **hierarchy must not be carried by tone at all**: use scale, weight, whitespace, and a hard 1px line at `--border-strong`, all of which are shape and survive flare. NN/g independently reached the shape-not-tone conclusion from the opposite direction, criticising Liquid Glass for undermining "outdoor readability."
`VERIFIED-LIVE (fetched 2026-08-31)` — https://www.nngroup.com/articles/liquid-glass/

**What to avoid.** Fine-grained tonal elevation ladders (M3's seven surface tiers inside 16 L-points) as the primary hierarchy device on a mobile-first Indonesian product. Tell them apart: take a screenshot, apply `filter: contrast(0.35) brightness(1.4)`, and see whether the page still has a structure. If the only thing left is a grey rectangle, the hierarchy was tonal.

---

## Finding 9 — The 2026 fad, named

**Named example.** 925studios, *AI Slop Fonts and Gradients*: **"The blue-to-purple gradient is the single loudest AI tell in 2026,"** traced to *"Tailwind's indigo-500 default"* from 2019. Their companion tells: Inter *"used everywhere … the safest possible answer"*; *"a row of three feature cards, rounded corners, soft shadow, thin-line icon at the top"*; thin interchangeable line icons; weightless copy like "Build faster. Ship smarter." Their diagnosis is exactly this project's diagnosis: a model *"returns the median of every example in its training data."*
`VERIFIED-LIVE (fetched 2026-08-31)` — https://www.925studios.co/blog/ai-slop-design-tells

**The second fad, with a receipt.** Translucent-material UI. Apple shipped Liquid Glass at WWDC June 2025; NN/g found *"text on top of images is a bad idea because the contrast between the text and the background is often too low"* and that Apple had abandoned the *"at least 0.4cm between targets (and 1cm × 1cm tap areas)"* guideline. By **June 2026** Apple was *"updating the foundations of how Liquid Glass is built to ensure exceptional readability"* and adding *"a new slider and settings to adjust Liquid Glass, so you can set it anywhere from ultra clear to fully tinted."* A trend that ships with an off-switch twelve months later is a trend with a known expiry date.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://www.nngroup.com/articles/liquid-glass/ · https://techcrunch.com/2026/06/08/apple-is-tweaking-its-controversial-liquid-glass-design/

**How to spot both in eighteen months.** The test is *derivability*. Ask of any colour or effect: **what input produced this, and would a different input produce something different?** An indigo→purple gradient has no input — it is a constant. A glass panel's opacity has no input — it is a taste. A surface at `oklch(21.3% κ·1.3 H_base)` has two inputs, both defensible, both variable. Anything in this design that cannot name its input is the fad.

**Specifically for Bali Zero.** The audience is described as *afraid of being scammed*. Translucency, glow and gradient are the visual vocabulary of crypto and of the scam agencies this company is trying to be distinguishable from. The mechanism that signals "licensed, boring, real" is the opposite: opaque surfaces, hard 1px rules, a single fixed brand point, and numbers that do not move. The proof strip ("4.9 ★ · 693 Google reviews · Filed this month: 47 KITAS") should be typeset like a ledger, not lit like a dashboard.

---

## What I could not verify

Listed so it can be checked before anything here is trusted.

1. **My APCA implementation.** I implemented APCA-W3 0.1.9 locally from memory of the constants (`normBG 0.56 / normTXT 0.57 / revBG 0.65 / revTXT 0.62 / scale 1.14 / blkThrs 0.022 / blkClmp 1.414 / loClip 0.1 / offset 0.027`). It reproduces two canonical reference values exactly — `#000` on `#fff` → **106.0**, `#fff` on `#000` → **−107.9** — which is a strong but not conclusive check. **Every Lc number in this report should be re-run through https://apcacontrast.com before it is used as a gate.** The OKLCH conversions and WCAG 2.x ratios are unambiguous published math and I consider them solid.
2. **The ambient-flare model in Finding 8.** The *structure* is sound (WCAG's 0.05 is a flare term; `E·ρ/π` is standard Lambertian). The *constants* are my engineering estimates, not fetched: ρ = 4.5% diffuse reflectance for a budget glossy phone, 400-nit peak, and the lux figures for tropical shade (10,000) and open shade (20,000). Directionally I am confident; the exact ratios should be replaced by a photometer reading on an actual target device before anyone quotes them.
3. **Linear's hex values.** Linear's own engineering post (verified) confirms LCH, the three inputs — *"base color, accent color, and contrast"* — the reduction from *"98 specific variables for each theme"*, and per-subtree theme regeneration. The specific values `#08090a`, `#0f1011`, `#f7f8f8` circulate on third-party benchmark sites; I attempted to fetch one (designmd.cc) and got **HTTP 403**. `FROM-MEMORY (unverified)` — do not cite those hexes.
4. **Things, Arc, and Stripe's dark tokens.** I found no public token source for any of them. Stripe's *method* is verified (CIELAB, WCAG 4.5/3.0 targets, *"any two colors are guaranteed to have sufficient contrast for small text if they are at least five levels apart"*); Stripe's dark *values* are not. Arc in particular I would not cite at all — I did not verify the product's current status. `FROM-MEMORY (unverified)`.
5. **WCAG 2.2 SC 1.4.11 (3:1 for non-text) and SC 1.4.1 (use of colour).** I applied both thresholds from memory and did not fetch the specification text. The 6%-of-men deuteran figure comes from a search summary, not a fetched primary source. `FROM-MEMORY (unverified)`.
6. **Display-P3 coverage on budget Indonesian Android.** My claim that it is unreliable rests on a search summary describing partial-coverage marketing, not a fetched dataset. If P3 matters to a decision, measure it on the actual devices in the Kerobokan office.
7. **Gojek Asphalt.** I fetched both foundations pages. They confirm light/dark themes and semantic *fill / border / icon* roles and give brand green `#00AA13`, but publish **no ramp values, no contrast rules, and no dark-mode arithmetic** ("Implementation (coming soon)"). The local-axis evidence for this lane is therefore thinner than I would like, and I did not find a substitute.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://asphalt.gojek.io/pages/foundations_colors.html
8. **NN/g's dark-vs-light summary** (Piepenbrock 2013, Dobres 2017, Aleman 2018, Legge 1985) is verified as *NN/g's characterisation* of those studies. I did not fetch the underlying papers.
`VERIFIED-LIVE (fetched 2026-08-31)` — https://www.nngroup.com/articles/dark-mode/

### Source ledger

**VERIFIED-LIVE (fetched 2026-08-31) — 23:**
radix-ui.com/colors/docs/palette-composition/understanding-the-scale · …/composing-a-palette · radix-ui.com/colors/docs/overview/aliasing · unpkg.com/@radix-ui/colors@3.0.0/index.js · unpkg.com/@carbon/themes@11.80.0/js/generated/themes/g100.js · …/g90.js · …/g10.js · …/white.js · raw.githubusercontent.com/carbon-design-system/carbon/main/packages/themes/src/index.ts · raw.githubusercontent.com/material-components/material-web/main/tokens/versions/v0_192/_md-sys-color.scss · …/_md-ref-palette.scss · developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/oklch · developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix · developer.chrome.com/blog/css-relative-color-syntax · evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl · git.apcacontrast.com/documentation/APCA_in_a_Nutshell.html · pmc.ncbi.nlm.nih.gov/articles/PMC4382974/ · pmc.ncbi.nlm.nih.gov/articles/PMC12962248/ · nngroup.com/articles/dark-mode/ · nngroup.com/articles/liquid-glass/ · techcrunch.com/2026/06/08/apple-is-tweaking-its-controversial-liquid-glass-design/ · stripe.com/blog/accessible-color-systems · mattstromawn.com/writing/generating-color-palettes/ · linear.app/now/how-we-redesigned-the-linear-ui · 925studios.co/blog/ai-slop-design-tells · asphalt.gojek.io/pages/foundations_colors.html
*(26 URLs; counted as 23 distinct sources — the four `@carbon/themes` theme files are one package.)*

**FROM-MEMORY (unverified) — 5:** APCA-W3 0.1.9 constants (self-checked against two reference values) · ambient-flare model constants (ρ, nits, lux) · Linear's specific hex values (designmd.cc returned 403) · Things / Arc / Stripe dark token values (no public source found) · WCAG 2.2 SC 1.4.11 and SC 1.4.1 threshold wording and the 6% deuteran prevalence figure.
