# Surface: Web (public)

> **Inheritance**: governed by `constitution.md` Articles 2 (palette), 3 (typography family),
> 6.3-6.7 (numbers / regulatory verbatim / bilingual lexicon / no-emoji), 7 (forbidden phrases),
> 8 (spelling & accuracy). Everything below is a deviation or an addition specific to the three
> public web surfaces.
>
> **Scope**: `balizero.com` home page · **GARUDA VOA** landing · **Visa Oracle** verdict. This is the
> spec the `web-mouth` row of the surface table pointed at and did not have. It does not govern the
> internal CRM surfaces (`kita` / `my` / `prime`).
>
> **Provenance**: derived from a sixteen-lane research corpus (12 web-grounded lanes + 4 cross-family
> seats), 2026-08-31. Evidence, per-lane sourcing and the full 116-gate floor live in
> `research/design/2026-08-31-web-design-sixteen-lane-corpus/`. This file carries the part a designer
> or an agent acts from; it does not duplicate the evidence.
>
> **Unresolved inheritance**: the colour generator in W3 derives a _warm near-black_ ground that is
> not one of Article 2's carousel tokens. Article 12.3 forbids a surface from overriding palette
> tokens. Reconciling the two is an Article 12.4 amendment and an owner decision — draft it in
> `_proposed-amendments/`, do not resolve it by shipping.
>
> Created 2026-08-31. Owner: Antonello Siano.

---

## W0 — The one thing this file exists to prevent

Three rounds of design were rejected. Round 1 was technically correct and emotionally flat
("_la UI è scialba e piatta_"). Round 2 produced fifteen night modes that all looked identical,
because the brief handed out reference colour tokens and every model anchored on them. Round 3
diverged in colour once the tokens were banned — and then three of five models took their _names and
metaphors_ from the list of suggestions the brief offered.

**Whatever the brief supplies, the models return.** The failure was never the models' taste. The brief
shipped **values** where it should have shipped **equations, envelopes and an acceptance test**.

The governing principle, and it is the whole file in five words:

> **Ship the generator, not the palette.**
>
> "…the answer to 'the last three rounds all looked the same' is a **parameter sweep**, not a prompt."

Supplying _nothing_ is the same failure by another route — a model given nothing returns the median of
its training data. So: supply the generator and the envelope (W2, W3), require the designer to state
**which input was varied and why**, and gate the output on tests that do not care about taste (W1).

---

## W1 — The two acceptance tests that gate every output

Both are run in review, out loud, by pointing at things. Neither needs tooling.

**W1.1 — Test A, derivability.** For every colour, effect, spacing value and duration in the mockup:

> _what input produced this, and would a different input produce something different?_
> **Anything that cannot name its input is the fad.**

An indigo→purple gradient has no input — it is a constant. A glass panel's opacity has no input — it
is a taste. A surface at `oklch(21.3% κ·1.3 H_base)` has two inputs, both defensible, both variable.

**W1.2 — Test B, falsifiability.** For every claim on the page:

> _name the external record that would falsify it._
> **Who renders the artifact?** Your own server → decoration. A registrar, regulator or platform → evidence.

No record → it is decoration sitting where a checkable fact should be. The operational corollary,
which decides most proof-strip arguments: _could this element still render if the underlying fact
vanished tomorrow?_ **Prefer the one that breaks.**

**W1.3 — The reason Test B is not optional here.** Discriminating power is inversely proportional to
adoption cost: any signal you can add for free this afternoon, a scammer added this morning. The
corpus's strongest single finding is a live autopsy of a fake e-VOA site that has adopted the entire
honest-intermediary playbook — disclaimer, outbound link to the government site, twelve languages,
"more than 50 specialized employees" — and whose About page still reads, verbatim, _"www.<fake>.com
belongs to ."_ and _"Our headquarters are located at , phone , email …"_. Three unfilled template
variables. **A copycat can generate every trust signal in existence except a name, an address and a
registration number that resolves in someone else's database.** Design toward the things it cannot fill.

---

## W2 — The eleven knobs

Each of these, **varied alone**, produces visibly different and equally defensible work. This is the
machinery. A design review that cannot say which knob was moved has not reviewed anything.

**W2.1 — `κ` (kappa): the chroma of the neutral.** Envelope **0.000 → 0.018** OKLCH, measured across
three shipped systems (IBM Carbon 0.0000; Radix `slateDark` 0.0041→0.0155; Material 3 0.0124 at hue
300° `[M]`). κ=0.000 is a Carbon-like industrial neutral; κ=0.006 is a surface that whispers the brand
hue. _Two values of κ produce two visibly different products from the same brand colour_ — the exact
divergence the previous rounds could not manufacture. **Highest-yield knob in the corpus; it costs one
number.**

**W2.2 — `H_ground − H_accent`: hue distance, ground to accent.** Measured from `#C8102E` (H = 22.3°):
warm near-black `#0F0D0C` = **26.1°**; M3's `#141218` = **81.9°**; blue-black `#0B1020` = **112.8°**.
Varying this changes the entire character of the dark mode **and** its chromostereopsis behaviour by
~4×. Constraint: stay in **26–46°** (W4 gate 12).

**W2.3 — Polarity: is red the ink, or the field?** Binary, and the most radically different outputs of
any knob here. All fifteen rejected night modes chose the same polarity. The alternative — _invert the
flag_: red as the **field** (deep oxblood/maroon ground) with warm off-white as the light — is the one
proposal no other seat reached. Its hex ranges are reasoned proposals, **not measured values**
(`FROM-MEMORY`): a starting point for the sweep, not an answer.

**W2.4 — `dark_travel_multiplier`.** Range **1.2–1.6** (measured: Radix `gray` 1.56×, `slate` 1.57×,
`red` 1.43×, `grass` 1.21×). This decides whether a dark mode reads as _layered_ or _flat_: M3 packs
seven dark tiers into 16 L-points, which is precisely why M3 dark reads flat unless you also use its
tint.

**W2.5 — The spacing ratio.** Not the spacing — the **ratio** between inside-section gaps (16–24px)
and between-section gaps (64–96px), i.e. **3–4×**. The best one-line diagnosis of _scialba e piatta_
in the corpus: **the ratio between small and large gaps is what creates rhythm; uniform 24px
everywhere is what creates _scialba_.** Uniformity is the single most common cause of the flatness
the owner rejected.

**W2.6 — The intensity budget: _which_ element gets the one peak.** Exactly **one** element per
viewport may sit at maximum contrast / size / saturation, and the promoted element must be the thing
the user came to decide. Allocation for these three surfaces:

| Surface             | The one peak                         | The first thing the scroll earns |
| ------------------- | ------------------------------------ | -------------------------------- |
| Home page           | the H1                               | the proof strip                  |
| GARUDA VOA          | the price                            | the passport step                |
| Visa Oracle verdict | the verdict **plus** the named human | the four editable answers        |

The failure this explains: _every round distributed emphasis evenly, because distributing evenly is
what "clean" means to a model without an allocation decision. The eye completes its sweep in one pass,
finds no peak, and files the page as **unfinished** rather than **serene**._

Consequence for the home hero, resolving a contradiction three seats had with each other: the hero
holds **the dateline, the H1 and one affordance** — not four doors, which do not fit above the fold at
any readable type size (geometry, not taste). **The proof strip is the first thing the scroll earns.**

**W2.7 — Type ratio, base size, tier count.** Ratio (Polaris 1.2, Gojek 1.3), base size (Gojek
deliberately raised its base to 12pt for legibility; 18px on transactional surfaces), tier count
(**three sizes, two weights, one family** — two families is the ceiling). All three vary
independently; all three round to **4px multiples** so long Indonesian strings do not break the
vertical rhythm.

**W2.8 — Easing family: "productive" vs "expressive".** Carbon ships two complete curve families from
one system for exactly this reason — `standard.productive cubic-bezier(0.2, 0, 0.38, 0.9)` vs
`standard.expressive cubic-bezier(0.4, 0.14, 0.3, 1)`. One token swap, two feels, both defensible.

**W2.9 — Grain and texture, as bounded parameters not effects.** `feTurbulence baseFrequency`
**0.7–1.0**, opacity **0.08–0.20**, `stitchTiles='stitch'`; halftone dot scale **0.75–1.25em**,
monochrome/duotone only. Grain reads as _crafted_ inside those bands and as _damage_ above **0.3**.
Zero HTTP requests — inline in the same `<style>` block.

**W2.10 — Awareness stage, per surface.** PAS (problem-first) for **problem-aware** cold traffic (home
page); benefit/certainty framing for **solution-aware** traffic (verdict, GARUDA VOA). A Copyhackers
home-page A/B of a PAS opener returned **+49% and +46% paid lift at 99% confidence**; the mechanism is
stage-of-awareness matching, and a first-time visa buyer is problem-aware by definition. Same product,
different copy machinery, chosen by funnel position rather than taste.

**W2.11 — The verify/act classifier.** Tag **every** screen `verify` or `act`. _Verify_ screens show
everything at once and hide nothing behind an accordion. _Act_ screens carry exactly one primary CTA,
zero promotional modules, zero carousels. One boolean per screen generates a whole information
architecture — and it is derived from precedent, not preference: Gojek's home is dense, its
ride-booking task screen is sparse. Same users, same day, both modes.

> **How to use this section**: a mockup arrives with a one-line statement — _"κ = 0.006, polarity =
> red-as-field, dark_travel = 1.45, peak = the price"_. Two mockups that differ in one knob are a
> sweep. Two mockups that differ in vibe are round four of the same failure.

---

## W3 — The generator arithmetic

Four equations, from a published generator, confirmed empirically against Radix's shipped values.
`n` is the normalised ramp position.

- **Lightness**: `L(n) = 1 − n`, with the branch flipping when background luminance crosses
  `Y_b = 0.18`. _That branch **is** the light/dark sibling rule, stated as arithmetic._
- **Chroma envelope**: `S(n) = −4n² + 4n` — a parabola, zero at both ends, peak at mid-ramp. Verified
  shipped: Radix `slateDark` runs **0.0041 → 0.0155 → 0.0029** across steps 1 → 8 → 12.
- **Hue drift compensation**: `H(n) = H_base + 5·(1 − n)` — 5° counteracting the Bezold–Brücke effect.
  Radix `redDark` shows the same drift: **12.7° at step 3 → 23.0° at step 9**.
- **The contract is contrast, not colour**: Radix guarantees **Lc 60 and Lc 90 (APCA)** for steps 11
  and 12 against a step-2 background, and holds that in both modes _at different hex values_.

**The fixed point — the rule that makes two themes siblings rather than inversions.** Radix holds
**step 9, and only step 9, byte-identical across light and dark** for every chromatic scale, and
re-derives all eleven others per mode against the Lc contract. **The brand identity is one fixed
point; everything else is derived.**

The discriminator, usable in review: **siblings have matched Lc and different L; inversions have
matched L-complement and unpredictable Lc.**

Applied here: the accent is defined not as a hex but as **"the step whose Lc against the current
surface is ≥ 60"** — which resolves to a different value in each mode, automatically. `#C8102E` is the
step-9 fixed point, not the value you paint with.

---

## W4 — The hard floor

Checkable gates. A mockup that fails one of these is not a taste disagreement. Gate numbers are the
research capture's numbering — **116 gates exist; the ones below are the ones that bite on these three
surfaces**, and the rest (form autofill tokens, keyboard hygiene, VA/QRIS/card screen detail, EAA
dates and per-country penalties, secondary type rules) live in the capture.

> ⚠️ **Standing caveat on every APCA (`Lc`) figure below.** They were computed with a _locally
> reimplemented_ APCA-W3 0.1.9 that reproduces two canonical reference values exactly but was not
> independently validated. **Re-run every Lc gate through `apcacontrast.com` before wiring it into
> CI.** OKLCH conversions and WCAG 2.x ratios are unambiguous published maths and are solid.
>
> `[M]` marks a number the source lane itself marked `FROM-MEMORY (unverified)`. It is the best number
> the corpus has; it must **never** be quoted to a client as measured. Every Material 3 and Apple HIG
> number here is `[M]` by construction — both sites are JS-rendered SPAs that defeated four lanes.

### W4.1 Contrast and colour

| #   | Gate                                                                                                                                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Body text: WCAG **≥ 4.5:1** _and_ APCA **\|Lc\| ≥ 75** — both, not either                                                                                                                                          |
| 2   | Large text (≥18px, or ≥14px bold) and UI text: **≥ 3:1** _and_ **\|Lc\| ≥ 60**                                                                                                                                     |
| 3   | Any border/rule that carries meaning (`--border-strong`): **≥ 3:1** (SC 1.4.11) _and_ **\|Lc\| ≥ 26**                                                                                                              |
| 4   | Decorative separator (`--border-subtle`): **\|Lc\| ≤ 14** — deliberately below the non-text threshold, and it may carry no obligation                                                                              |
| 5   | Focus indicator: **≥ 3:1** against the unfocused state of the same pixels, covering **≥ a 2px perimeter** (SC 2.4.13)                                                                                              |
| 6   | Neutral surface chroma: OKLCH **C peak ≤ 0.018** across the whole ramp. Above it, a surface stops being a surface and becomes a colour                                                                             |
| 7   | Any two semantic state colours that can co-occur: **≥ 12 OKLCH L-points** apart, _plus_ a glyph, _plus_ a word                                                                                                     |
| 8   | Dark-mode elevation step: **≥ +7 L** per level (dark ladder needs 1.2–1.6× the travel of the light ladder)                                                                                                         |
| 9   | Light-mode elevation step: **≥ −3.5 L** per level                                                                                                                                                                  |
| 10  | Brand red as **ink** on a dark ground: **forbidden.** `#C8102E` on `#141218` measures **Lc −24**, and no lightness of that hue clears Lc 60 on both a near-black and a near-white ground (max achievable **50.6**) |
| 11  | Brand red as **fill**: permitted. White on `#C8102E` = **Lc −82.4**                                                                                                                                                |
| 12  | Hue distance, ground to accent: **26–46°** (warm near-black). Never the ~113° of a blue-black — that is the maximum-span chromostereopsis pair                                                                     |

**The red CTA, decided.** Red fill, on a **warm near-black** ground (26–46° from the accent hue), and
the control must **additionally** carry a non-tonal affordance — a 1px system-colour border plus a
size/weight step. Reason: in shaded ~10,000-lux daylight, white on `#C8102E` falls to **2.79:1**, below
the 3:1 non-text threshold — the label washes out in the exact environment where someone stands
outside an immigration office. The button must still be findable when its label is gone. **The flare
model behind that 2.79:1 is the source lane's own engineering estimate (`[M]`: ρ = 4.5%, 400 nits,
10,000 lux) — measure it on a real phone in Kerobokan at midday before quoting it.**

**Tone may never be load-bearing.** Tone-based elevation (a Linear-style surface ladder) is _permitted
as an enhancement that carries no information_. **Every hierarchy relation a user must read to complete
a task must additionally be encoded in at least one of: scale, weight, position, glyph/word, or a 1px
rule using a system colour.** Two mechanical reasons, not preferences: under `forced-colors: active`
`box-shadow` is force-stripped to `none` and author colours are overridden (an inset-highlight
technique simply evaporates); and at ~10,000 lux a Material-3 elevation step reaches **1.05:1** and a
dark hairline **1.15:1** — both invisible `[M]`. The only forced-colors-safe border primitive in the
whole corpus is **`1px solid CanvasText`**.

### W4.2 The three tests, run on every mockup — no tooling beyond a browser

- **Greyscale test** — desaturate the screenshot and hand it to someone. If they cannot read the
  verdict, it fails. _(This test fails Radix's own step-9 palette, which is why "we used a good design
  system" is not a substitute for running it.)_
- **Daylight test** — apply `filter: contrast(0.35) brightness(1.4)`. If the only thing left is a grey
  rectangle, the hierarchy was tonal and must be re-encoded in scale / weight / position / rule.
- **Forced-colors test** — render under `@media (forced-colors: active)`. Every affordance must still
  be findable.

### W4.3 Targets, motor and reach

| #   | Gate                                                                                                       |
| --- | ---------------------------------------------------------------------------------------------------------- |
| 13  | Tap target, legal floor: **≥ 24 × 24 CSS px** (WCAG 2.2 SC 2.5.8)                                          |
| 14  | Tap target, design target: **44 × 44px (Apple) / 48 × 48dp (Material)** ≈ 9mm physical `[M]`               |
| 18  | Input field height **≥ 44px**, with a label that stays visible on focus — never placeholder-as-label `[M]` |
| 19  | Primary CTA **and** price in the bottom third of the viewport (thumb zone) on **every** mobile step        |

> 48dp is Material's _recommendation_, not the WCAG criterion. One cross-family seat asserted that
> 48×48dp "aligns with SC 2.5.8" — **it does not**; the criterion is 24×24 CSS px. Cite gate 13 for
> the floor and gate 14 for the target, never the other way round.

### W4.4 Motion

| #   | Gate                                                                                                                                                                                                                   |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 24  | Token scale for _this_ client (biased fast: phone, night, anxious): instant **80ms** / fast **150ms** / base **220ms** / slow **320ms**. **Nothing on any surface exceeds 320ms**                                      |
| 26  | INP **≤ 200ms** at p75                                                                                                                                                                                                 |
| 27  | Wait < 1s: **no indicator at all** — the flash reads as a glitch                                                                                                                                                       |
| 28  | Wait 1–10s: spinner for a single module; **named-step skeleton** for a page. A skeleton with no content placeholders is worse than nothing                                                                             |
| 29  | Wait > 10s: percent-done **and** a way to interrupt                                                                                                                                                                    |
| 30  | **Artificial delay: zero.** No `setTimeout` on any success path; every animated duration bound to a real promise. **Greppable — make it a lint rule**                                                                  |
| 31  | `prefers-reduced-motion: reduce`: kill decorative classes **by name**, then compress everything else to **0.001ms** — do not delete the transition property (a component depending on `transitionend` breaks silently) |
| 32  | `backdrop-filter`, if used at all: radius **8–16px**, small static area only, never animated, never over scrolling content. Cost scales with blurred area × radius; stacked blurs multiply                             |

**Why gate 30 is the one that cannot be traded.** The dividing line eight independent lanes reached is
identical: _legitimate motion happens before first meaningful paint or in response to the user's own
input; illegitimate motion happens **to a settled number**._ The "analysing your case…" delay may
genuinely buy a few points of perceived value — and it does not matter, because **one caught lie on the
verdict screen correctly re-prices every other claim on the page, including the true ones.** The
asymmetry is not close. (Note the equivocation the fad depends on: the "false front" literature is
about showing a real page _sooner than it is ready_ — a **speed** illusion. The labour illusion slows a
_finished_ result down — a **cost** illusion. They point in opposite directions.)

### W4.5 Performance and payload

Performance is a **trust signal** on these surfaces, not an SEO concern: a slow VOA payment page does
not just lose a sale, it _confirms the suspicion_ that this is not a legitimate operation.

| #   | Gate                                                                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 33  | LCP **≤ 2.5s** at p75, on a **throttled mid-tier Android / 4G profile** — not desktop wifi                                                                                                                            |
| 34  | CLS **≤ 0.1** at p75                                                                                                                                                                                                  |
| 35  | First-viewport total weight **≤ 500KB compressed**                                                                                                                                                                    |
| 36  | Hero image **≤ 150–200KB**, WebP/AVIF, sized for 390px — not a scaled-down desktop asset                                                                                                                              |
| 37  | Critical JS **≤ 150KB compressed**                                                                                                                                                                                    |
| 38  | Hero video / WebGL / canvas: **zero**                                                                                                                                                                                 |
| 40  | Fonts: one **static instance per weight actually used**, subset to Latin, plus a metric-matched fallback `@font-face` (`size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`) targeting **CLS 0** |

**The diagnosis has moved, the budget has not.** Indonesia's median mobile download was **45.01 Mbps,
+53.1% YoY** — the "slow Bali connection" premise is not the binding constraint at the national median.
**The binding constraint is CPU at p75** (mid-range Android parsing JS, decoding images, painting
layout). That changes the fix: _reduce main-thread work and defer everything non-critical until after
the LCP element paints_, rather than only compressing assets. It does **not** license relaxing the
budget — Core Web Vitals is a **75th-percentile** measure, and a national median is not the p75 of a
roaming tourist on a throttled eSIM in a Kerobokan backstreet at 11pm. Baseline for context: only
**55.9% of origins pass all three Core Web Vitals; mobile 48% vs desktop 56%** (May 2026 CrUX,
18.4M origins).

### W4.6 Type

| #   | Gate                                                                                                                                                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 42  | A **discrete step table**, pixel-checked at exactly **360px and 1440px**. `clamp()` permitted only on display/hero type nobody QAs at in-between widths — **never** on a price, a verdict, or body copy |
| 43  | Mobile line length **30–50 characters**, min **14–15px**, line-height **≥ 1.3**                                                                                                                         |
| 44  | Desktop line length **≤ 80 characters** (WCAG 1.4.8); copy set wider was **skipped 41% more often** than copy at 60–70                                                                                  |
| 45  | Base body size **≥ 16px**; **18px** on the transactional surfaces                                                                                                                                       |
| 46  | **Three sizes, two weights, one family.** Two families is the ceiling                                                                                                                                   |
| 48  | Every price, deadline and reference number: `font-variant-numeric: tabular-nums lining-nums` (**five lanes independently**)                                                                             |
| 49  | Currency token **~0.55× numeral height, baseline-aligned. Never superscript** — superscript currency is the airline/SaaS tell                                                                           |
| 50  | Total vs components: total's type size **≥ 2.5×** any component or caveat line; no component line bolder than the total. At 360px ≈ **40px/600** against **14px/400**                                   |

**Family choice, decided: system-font-first on both transactional surfaces; at most one licensed text
face on the home page; zero display serifs anywhere.** A second family costs a font file _and_ a
rendering risk on the primary device class — there is a live, unresolved report against Google's own
font repo of visible **variable-font rendering corruption specifically on Chrome for Android**, and
360–390px Android _is_ this audience. On the one screen where a glyph glitch is a trust event, a
rendering risk is not worth literary gravitas. GOV.UK proves the document-like, serious register is
achievable with **no serif at all**; the gazette's load-bearing devices are the dateline, the column
rules, the tabular figures and the single loud headline — none of which requires a serif. Also: no
`hyphens: auto` for Indonesian (no `id` dictionary confirmed in any engine), `text-wrap: balance` on
headings, non-breaking space between currency and figure.

### W4.7 The money moment — binary gates

| #   | Gate                                                                                                                                                                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 85  | **The stranger test.** Can a stranger on a 360px phone learn the **total price without typing anything**? If no, the surface fails. Binary                                                                                                                                                                            |
| 86  | Price block and primary CTA in **one card**, **≤ 24px** vertical gap, no divider, reachable without scroll after the last question. If the page scrolls it away, a sticky bar carries **price + CTA together** — never a lone sticky CTA, which is the drip-pricing shape                                             |
| 87  | **Monotonicity**: the number the user first sees never goes up. No "from IDR 790.000"                                                                                                                                                                                                                                 |
| 88  | **Asterisks: zero.** `IDR 790.000*` destroys in one glyph everything above it                                                                                                                                                                                                                                         |
| 89  | Inclusion line: same card, **≤ 48px** below the price, **≤ 8 words**, contains _included_ / _sudah termasuk_                                                                                                                                                                                                          |
| 90  | Zero-state line, explicit and almost always omitted: **"Nothing is added at the end." / "Tidak ada biaya tambahan."**                                                                                                                                                                                                 |
| 91  | The inclusion claim may **not** live only in a tooltip — a disclosure must be _unavoidable_, and a tooltip is by definition avoidable                                                                                                                                                                                 |
| 92  | **Accordions forbidden** on any surface carrying a price, a fee or a licence term — hidden content reads as concealment to this audience                                                                                                                                                                              |
| 93  | **Comprehension test — ship gate.** Five-second exposure of the price card to 10 people, then _"How much will you pay in total?"_ and _"Is there anything else to pay later?"_ **Ship only at ≥ 90% correct on both**                                                                                                 |
| 94  | Two prices (790.000 / 850.000) render as a **timeline, never a tier menu**: `Today — IDR 790.000 — 30 days` → `Day ~25, if you want to stay — IDR 850.000 — 30 more days`, with the **sum stated plainly** underneath. Same type size for both (they are equally real), no default selection, no "most popular" badge |
| 95  | **Payment control on an uncertain verdict: zero.** A borderline state gets its own colour token (not a tint of "supported"), its own verb ("Needs a check" / "Perlu dicek"), a named person, a clock, **no price and no payment control**                                                                             |
| 96  | FX line, if shown: **0.5× size**, low emphasis, directly beneath — `≈ €44 · mid-market rate, 31 Aug — your bank sets the final amount`. Subordinate, and it names who decides                                                                                                                                         |

**The money boundary, decided.** Keep gate 86's adjacency; **change the verb**. The control next to the
price reads **"Continue — we check your passport before you pay"**, not "Pay". That satisfies adjacency,
keeps the price before the passport upload, and stops the system charging on a verdict computed from
four unverified self-reported answers. Cost, stated honestly: Bali Zero absorbs review time on people
who never buy.

**Cost side, for anyone arguing the gates down**: 70.22% average cart abandonment across 50 studies,
with **40% citing extra costs revealed too late** as the top non-browsing reason, and **33% of
benchmarked mobile sites fail to display total order cost at any point before asking for card data**.

### W4.8 The verdict screen

| #   | Gate                                                                                                                                                                                                                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 97  | H1: second person, indicative, **< 10 words**, no conditional clause, no adverb of degree. **Pronoun test: if the largest text on screen contains no "you", it is a badge and it fails**                                                                                                                        |
| 98  | Split anything over **25 words**; paragraphs **≤ 5 sentences**                                                                                                                                                                                                                                                  |
| 99  | Component types on screen **≤ 7**                                                                                                                                                                                                                                                                               |
| 100 | **Nothing interactive inside the verdict panel** — GOV.UK states plainly that interactive elements in the panel "will not be accessible"                                                                                                                                                                        |
| 101 | Block order: verdict → price → "what happens next" _with a `when` on every step_ → the four answers with Change links → the named human → contact → save-a-record                                                                                                                                               |
| 102 | Answers: four rows, each _key · value · Change_, with visually-hidden text so a screen reader hears "Change name", not "Change". Editing costs **two taps and one return**, never restarts the flow, and **if the edit flips the verdict, the page says so explicitly**                                         |
| 103 | Save-a-record: one-tap PDF/permalink carrying a **reference code, the price, the named handler and the date**. Highest-value item on the screen and almost always omitted                                                                                                                                       |
| 104 | **Must not ship**: a confidence score, a probability, a decision-tree visualisation, or a "how we calculated this" expander containing pseudo-reasoning                                                                                                                                                         |
| 105 | The caveat: a complete sentence naming a **real actor** ("Indonesian Immigration makes the decision"), placed once, after the verdict and after the price, never in the H1, never as an asterisk. **Deletion test**: delete it — if the verdict is now false it stays; if still true it was decoration and goes |
| 106 | A refusal has four obligatory parts: the determination in one sentence; **the specific reason naming the answer that caused it**, with a Change link on that exact answer; **the route that does work, priced, on the same screen**; and a named human — _do not downgrade the human on bad news_               |
| 107 | If a language model touches this page, **one line saying so** — EU AI Act Art. 50 applies from **2 August 2026**                                                                                                                                                                                                |

**Why gate 104 is absolute.** `AI-powered eligibility score: 94%` is a fabrication with a decimal
point, and it is precisely how a confident scam beats an honest agency. A 2025 study (12 retired Dutch
police officers + 180 lay users, four explanation conditions) found **no form of explanation helped in
fostering appropriate trust** — and where hybrid explanations _did_ raise subjective trust among
experts, the authors call it "worrisome, as it does not lead to better decisions."

**The named human is a mechanism, not a decoration**, and it has one falsifier: **the same face answers
on WhatsApp after payment.** A named human on the verdict with a bot behind it is _worse than no face
at all_ — it converts a trust asset into a caught lie.

### W4.9 Payment rails and copy/legal

| #   | Gate                                                                                                                                                                                                                                                                                                |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 71  | **Single column**, one field group visible at a time, at 360–390px. Not a style choice — it is what the screen physically allows                                                                                                                                                                    |
| 72  | Guest checkout labelled **explicitly and equally weighted**. 60% of test subjects could not _locate_ it when it was not a clearly separate choice; forced account creation is 18% of abandonment                                                                                                    |
| 81  | QRIS **never pre-selected** for a buyer paying from abroad. Cross-border QRIS covers **only** MY / TH / SG / JP domestic apps (+KR, CN in progress). The QRIS **mark** may sit in the pre-commitment rail row — showing a mark is not pre-selecting a rail                                          |
| 82  | **MDR is never passed to the buyer.** Bank Indonesia, verbatim: _"Biaya MDR ini ditanggung oleh merchant dan tidak boleh dibebankan kepada konsumen"_                                                                                                                                               |
| 84  | Payment truth is derived from the **provider's server notification**, never from the browser returning to a success URL. Idempotency on payment creation, document submission and refund                                                                                                            |
| 108 | **String blocklist, failing the build on a hit**: `official partner` · `official` / `approved` (affiliation sense) · `resmi` · `guaranteed` / `dijamin` · `100%` · `no risk` / `tanpa risiko` · `#1` · `first reseller`                                                                             |
| 109 | Statutory hooks (not house style): **UU 8/1999 Pasal 9(1)(c)(d)(j)(k)** and **Pasal 10**; penalties **Pasal 62(1)** up to **5 years or Rp 2.000.000.000**; **Pasal 63** includes **revocation of the business licence**                                                                             |
| 110 | The compliant form of a strong claim is the claim **with its conditions attached**, not a weakened claim. Pasal 9(1)(j)'s escape hatch is _"tanpa keterangan yang lengkap"_: "We filed 47 KITAS this month" is fine **with the period, definition and date stated**; "#1" is not fine at any length |
| 111 | Urgency devices: **zero** countdowns, "X people viewing", "N slots left" — unless wired to a real, checkable deadline (a VA expiry is real; a marketing timer is not)                                                                                                                               |
| 112 | Success states: **no confetti.** A drawn checkmark (300–400ms, no bounce), the amount, a reference ID, the next step                                                                                                                                                                                |
| 113 | Accessibility overlays: **zero, on any surface, ever.** Over 1,030 signatories: "full compliance cannot be achieved with an overlay" — and overlays are now cited **against** defendants                                                                                                            |
| 114 | No self-issued Bali Zero "verified"/"licensed" badge graphic. **Test: who serves the asset, and where does the click land?**                                                                                                                                                                        |
| 115 | All four preference media queries implemented and tested: `prefers-reduced-motion`, `prefers-contrast`, `forced-colors`, `prefers-color-scheme`. All Baseline widely available — there is no excuse in 2026                                                                                         |
| 116 | Honour the OS `prefers-color-scheme` on **first load** — never require a toggle click to respect a preference the OS already announced                                                                                                                                                              |

**Standing dates**: WCAG 2.2 is a **W3C Recommendation of 12 December 2024** and is the enforceable
floor. WCAG 3.0 is "an incomplete draft," not expected before ~2028, and **its contrast algorithm is
undecided** (APCA was removed from the draft in July 2023) — do not design to Bronze/Silver/Gold. EAA
obligations for services applied from **28 June 2025** via EN 301 549 → WCAG 2.2 AA, with a
microenterprise exemption at **<10 employees and ≤ €2M turnover**.

---

## W5 — What must never ship

### W5.1 Dead technique (taste has nothing to do with it)

- **Any number that animates.** Count-up odometers, "was" prices fading in, "you saved…" lines, a
  price pulse on re-render. **Eight lanes.** A number that changes state after the user has read it is
  theatre, and theatre reads as sleight of hand to someone afraid of being scammed. State the number
  once, tabular, static.
- **The artificial "analysing your case…" delay** and any progress animation not bound to a real
  promise. Compute client-side and render in <300ms; if a server call is genuinely pending, render what
  is already known while it resolves.
- **`#121212` and blue-black as the dark ground.** Every reference system measured lands at
  **L ≈ 18–20% with C ≤ 0.018**; none is `#000000`, none is `#121212`. A blue-black is κ≈0.03 at
  H≈265° — outside that envelope, and the exact hue that maximises chromostereopsis span against a red
  accent. **Tell: if you can name the colour of the background ("navy", "midnight blue"), κ is too high.**
- **Indigo→purple gradient with a glow; a bento grid for the four segment doors; the floating pill
  navbar; unmodified Inter at default weights.** The blue-to-purple gradient is the loudest AI tell of
  2026 and **two lanes independently traced it to the same 2019 origin** — Tailwind's `indigo-500`
  default — from two unrelated source families. The single most legible sub-tell is the glow:
  `box-shadow: 0 0 60px rgba(purple,.4)`.
- **Padlock / SSL-seal / "100% secure" iconography.** Chrome retired the padlock because "nearly all
  phishing sites use HTTPS, and therefore also display the lock icon" — only **11%** of study
  participants understood its precise meaning. Worse: Indonesia's own government authenticity banner
  teaches the public a padlock test **that the named fake passes**. Any Bali Zero content repeating
  "look for the padlock" arms the scam.
- **Full-page `backdrop-filter`, glass-on-glass stacking, animated blur radius.** The part of Liquid
  Glass that reads as premium is a GPU shader, not a CSS property — and Apple shipped a legibility
  slider twelve months later. **A trend that ships with an off-switch twelve months later is a trend
  with a known expiry date.** For this audience an _illegible_ premium effect is worse than a flat one:
  flat is honest, illegible-glass reads as evasive.
- **Hero video, WebGL heroes, scroll-jacking, parallax, kinetic/scroll-scrubbed headline type,
  magnetic-hover and gooey-blob cursors.** Cursor effects are inapplicable to **100% of this audience
  by construction** — there is no cursor on a 360px touchscreen.
- **Auto-advancing banner carousels** — they persist because they serve ad operations, not users `[M]`.
- **`text-overflow: ellipsis`** as the silent fix for overflow; **`clamp()`** on a price, a verdict or
  body copy; **one `Intl.NumberFormat` for both locales**; `notation:'compact'` on a payable price;
  **`parseFloat` on an `id-ID` string**. See W6.4.
- **Flags as the language switcher** — settled UX doctrine, and Indonesia is the textbook case that
  breaks it. Use text: **"EN · ID"**.
- **Placeholder-as-label**; multi-column checkout at 360–390px; a decorative micro-icon as the _only_
  tap target for a critical action.
- **Batik / wayang / Garuda as decoration.** And the second-order instruction: **name this as an
  explicit exclusion in any image-generation brief**, because those motifs dominate stock-photo and
  tourism-brand training data and a generator will reach for them unprompted.

### W5.2 Legal risk, not taste (each cites a real instrument)

- **A comparison table naming a competitor with an asserted number.** Defamation and unfair-competition
  exposure under Indonesian practice — and it makes Bali Zero sound like the agents it is
  differentiating from. You may state a competitor's **structure** truthfully; never their **amount**.
  Note the "Us vs Government" grid is the _copycat's own signature device_.
- **Composite testimonials** ("Sarah from Perth", blended from several real clients) — the single
  highest-risk pattern for this client. The FTC rule (effective **21 Oct 2024**, **$51,744 per
  violation**) treats an undisclosed composite or fictional testimonial as fake. Initial-only
  attribution (`— Marco R. · Italy`) is the canonical fake-testimonial format.
- **AI-voice or AI-avatar video testimonials** — the FTC's 2024 consent order against Rytr put this on
  notice as a live enforcement target.
- **Fake / incentivised reviews and unfalsifiable rating strips.** A banned practice under the UK
  **DMCC Act** since April 2025; the CMA opened five ratings investigations on **27 March 2026**, with
  fines to **10% of global turnover**. Keep 4.9 and 693 _numerically_ — they sit in the empirically
  optimal band (purchase likelihood peaks 4.0–4.7 and _falls_ toward 5.0) — but make the string a
  **live link to the Google Business Profile**, i.e. an artifact that breaks if the reviews vanish.
- **A confidence percentage on a binary legal question**, plus the GDPR Art. 22 / EU AI Act Art. 86
  surface. If an LLM touches the verdict page, **Art. 50 requires a disclosure line from 2 August
  2026**, with fines to **€15m or 3% of turnover**, and Bali Zero serves EU nationals.
- **Any fabricated urgency device** — for this audience it _actively confirms_ the exact fear the
  redesign exists to dispel.
- **DCC-adjacent card routing** offering "pay in your home currency" — it directly contradicts the
  "the price is the whole price" promise.
- **QRIS advertised as universal.** Accurate only for six named nationalities' domestic apps plus
  anyone holding a local e-wallet.
- **An employee photograph without written, per-surface consent and a documented takedown SLA.**
  **UU 27/2022 (PDP) Pasal 4** covers an identifiable facial image on a public page. A face still live
  after someone leaves is both a compliance failure and a trust liability — and weigh harassment risk
  soberly, since this same face also delivers refusals.
- **Passing MDR to the buyer** — Bank Indonesia forbids it outright, which is why "IDR 790.000,
  all-inclusive" is not just marketing language but the legally accurate description of what BI
  enforces.
- **Licence adjectives instead of licence numbers.** "Licensed konsultan pajak" is a copycat-grade
  claim — a _claim_, not a _credential_. Ship the **izin praktik number**, the **NPPPJK**, the **NIB**,
  plus the lookups that resolve them in someone else's database (`ahu.go.id/pencarian/profil-pt`,
  `oss.go.id`, and SIKOP's public `carikonsultan` search at `sikop.kemenkeu.go.id`). Same rule kills
  "Office in Kerobokan" — it has the same information content as "offices in Europe and the United
  States", which is what the named fake says. Ship the **full street address and a map**.

> **On the live site today**: several strings on `balizero.com` are caught by the rules above (the
> twice-run marquee proof strip, the initial-only testimonial, the `#1` in the `<title>`, the licence
> adjectives, "Office in Kerobokan", the stale April 2026 dateline). Those readings came from
> _summarising fetchers, not raw HTML_, from two independent lanes. **`curl` the page before acting on
> any of them.** The list, with replacements, is in the research capture §4.1. Two are explicitly
> **not** defects: the H1 ("Most people moving to Bali pick the wrong visa in the first month") — do
> not let a stakeholder's discomfort with a "negative" headline talk it back into "Your visa, handled";
> and "Filed this month: 47 KITAS, 9 PT PMAs", which is the rarest asset in the corpus — strengthen it
> by stating the methodology and the as-of date, **and by letting it dip**. A month where the number
> dips slightly and stays visible is worth more, credibility-wise, than a month silently swapped out.
> Never merge it with the lifetime "5,000+ clients" figure.

---

## W6 — Copy and register

**W6.1 — The register is `Anda`, never `kamu`,** on any surface touching money or legal status. Short
declarative clauses, benefit named first, no exclamation marks (the BCA / OSS pattern, verified live).
`kamu` "reads as a downgrade in institutional seriousness to an Indonesian reader exactly the way an
immigration lawyer texting 'hey bestie' would read to an English one."

**W6.2 — Copy the government/bank register, not the marketplace register.** This is not a
West-versus-Asia call: the split is _within_ Indonesia. Traveloka, BCA, `imigrasi.go.id` and
`oss.go.id` all run navy/white, card-based service categories, generous whitespace, and state
regulatory facts **in full sentences, not badges** — while **29.2% of study participants** named
clutter (icons, banners, ads stacked without hierarchy) as their explicit usability complaint about the
marketplace apps. Density here is a **category signal, not a cultural universal**: "Asian users like
density" is false; **they like density that pays**.

**W6.3 — Three tests that need no tooling.**

- **Pronoun test** (verdict): _if the largest text on screen contains no "you", it is a badge._ GOV.UK's
  live visa checker terminates on "**You'll need a visa to come to the UK**" — not a badge, not a card,
  not a celebration.
- **Deletion test** (caveat): delete it; if the verdict is now false it was load-bearing and stays; if
  still true it was decoration and goes.
- **Actor test** (certainty): state the limit of certainty by **naming the actor**, not by hedging the
  outcome. "Immigration decides" is a sentence about who holds the pen. "*subject to approval" is an
  asterisk — and asterisks are what scam sites use.

**W6.4 — The two price formatters. Two, keyed to page language. Never one.**

| Locale | Form              | Rule                                                                                                                |
| ------ | ----------------- | ------------------------------------------------------------------------------------------------------------------- |
| `id`   | **`Rp790.000`**   | dot thousands, **no space** — strip the U+00A0 that ICU inserts                                                     |
| `en`   | **`IDR 790,000`** | `currencyDisplay:'code'`, en-US grouping. `IDR` beats `Rp` because a suspicious buyer can paste it into a converter |

Never `notation:'compact'` on a payable price — it emits `Rp 790 rb`, which is a rounding, not a price.

**The `parseFloat` trap, and it is the reason this is a spec clause and not a style note**: never
`parseFloat` an `id-ID` price string. **`parseFloat("790.000")` returns `790`** — a two-order-of-magnitude
error that throws nothing, logs nothing, and renders a plausible number.

**W6.5 — Indonesian expansion is real and unmeasured.** The one hard data point in the whole corpus is
Canva's own localization guidance: translating the button label "Generate an image" into Indonesian
increases the string by about **40%**, enough to overflow its container — and Canva's own fix is to
design the _shorter English_ label so the Indonesian expansion still fits. **No vendor publishes an
Indonesian-specific percentage** (two lanes searched independently and both failed to find one). The
**+35–50%** working budget is an engineering margin, **not a measurement** — never quote it as one.
The response is structural, not a multiplier:

- No fixed pixel/rem width on buttons, chips, badges, pills — min-width + wrap + a min-height that
  tolerates two lines.
- **Never** `text-overflow: ellipsis` on a price, a verdict word, or "all-inclusive" / "sudah termasuk".
  A truncated Indonesian string reads as _broken_, not tidy, to an audience already primed to suspect.
- The one genuinely dangerous term is **"all-inclusive"** on the GARUDA VOA price card: English fits a
  badge in one word-pair, Indonesian needs a clause — _"Sudah termasuk semua"_. Design the badge for
  the clause.

**W6.6 — Bilingual plumbing.** Language switcher as text **"EN · ID"**, never flags; persistent,
top-right, same position on every surface; auto-detect from `Accept-Language` on first load with a
one-tap override; **never a geo-IP redirect the user cannot undo**; and it **must not lose form state
mid-flow**. One **"Full name (as in passport)"** field — never a first/last split, which silently
rejects valid single-name Indonesian passports. WhatsApp/phone pre-formatted **`+62 8xx-xxxx-xxxx`**
(trunk 0 dropped) so it dials from a local and a foreign handset. Timestamps suffixed **WITA**, always.

**W6.7 — Restraint is the design target here, not an accessibility concession.** A first-time visitor
afraid of being scammed, on a phone, at night, is under real cognitive load even without a vestibular
condition — and the same restraint that serves a vestibular-disorder user (less unsolicited motion,
clear step-by-step confirmation, nothing that starts moving on its own) reads to an anxious buyer as
**calm competence** rather than compliance. **For this brief the design target and the accessibility
target are close to the same target.** Say that in the review; it settles most arguments about "making
it feel premium".

---

## W7 — What is NOT decided

**Nothing in this section may be built on without being re-checked first.** A session that resolves one
of these in prose has invented an answer, not found one.

### W7.1 Facts that are settled — carry these forward exactly

- **The e-VOA government fee is `IDR 500.000`**, verified **2026-08-31** against **PP 45/2024
  §III.B.1.c** and `evisa.imigrasi.go.id/front/info/evoa`. This closes the corpus's single most
  dangerous unverified item (three lanes tried and failed; one verified a _different_ figure — IDR
  1.500.000 for a 60-day extendable visit visa — and wrote "I believe it is IDR 500.000 — **do not
  publish on my word**"). **It closes it as of that date and no longer.** A **DGI announcement of
  2026-08-12 proposes 750.000 / 1.000.000, and no enacting regulation has been found** — so the figure
  is live-but-contested, and the staleness stamp in W7.2 is not optional.
- **The brand red is `#C8102E`.** Verified in this repo: `skills/bali-zero-brand/tokens.json` (line 45,
  `color.status.red`) and `packages/core/tokens/semantic.css` (`--status-critical`). The corpus
  contained a second, unsourced hex (`#CE1126`) used by one seat for a contrast claim; **it appears in
  no brand-token file** — its only two occurrences in this repo are hardcoded one-offs in
  `apps/backend-rag/scripts/templates/kbli_magazine.html` and `kbli_presentation.html`, which are not
  brand surfaces. All of W3 and W4.1 assume `#C8102E`. Corroboration from inside the repo, which is
  _not_ a corpus figure: `semantic.css`'s own comment records `#c8102e` on operative anthracite at
  **~2.54:1**, i.e. the codebase had already measured what gate 10 forbids.
- **The government-fee split, decided (with a condition).** Print the **total dominant at ≥ 2.5×**
  (gate 50) **and** the split as two checkable lines, with the government line linked to a live
  `.go.id` URL — because against an agent who charges "above and beyond what should be paid", the split
  is the one move they cannot copy without exposing their margin. **A slogan asserts; a breakdown
  invites verification.**

### W7.2 The condition attached to the split — build it or drop the split

Stamp both lines with **"Government fee verified against [URL] on [date]"**, wired to a **recurring
check**. **If the check goes stale or the URL dies, the surface must fall back automatically to a
non-numeric inclusion list — three or four ticked lines, no figures — never to a stale number.** A
split with an unverified government figure is not an anti-scam device; it is a falsifiable claim on the
one screen where being caught once re-prices every other claim on the page. Note the corpus's own
cautionary find: the government's anti-scam page still names `molina.imigrasi.go.id` as the sole
official site, and that hostname **resolves NXDOMAIN**. _The only thing worse than no warning page is
one pointing at a dead domain._

### W7.3 Owner decisions — a session must not make these

| Q   | Question                                                                             | Standing recommendation                                                                                                                                                                                                                                                                                           |
| --- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | Split the government/service fee, or total only?                                     | Print the split, gated as W7.2                                                                                                                                                                                                                                                                                    |
| Q2  | Publish employee photographs and full names?                                         | Name + role + licence number + a **measured** response time, yes. Photograph only with written, per-surface, revocable consent and a takedown SLA. **Never print a response time you cannot compute from your own outbox**                                                                                        |
| Q3  | Where does the payment boundary sit?                                                 | After passport preflight — verdict CTA reads "Continue — we check your passport before you pay"                                                                                                                                                                                                                   |
| Q4  | The refund matrix, case by case                                                      | **No recommendation. The interface cannot ship without it.** Six cases the UI must render: customer cancellation, failed document check, duplicate charge, Bali Zero error, government-system outage, Immigration refusal. "May be non-refundable" is placeholder copy — a vague legal footnote is not acceptable |
| Q5  | Does the EU-facing entity fall under the EAA microenterprise exemption?              | Design to WCAG 2.2 AA regardless, **but establish the fact** — it is a headcount/turnover question, not a research question                                                                                                                                                                                       |
| Q6  | Publish a "how to check any Bali visa agent — including us" page?                    | Yes, dated, versioned, wired to a real recurring check. **No controlled study exists** on what this costs in conversion; nobody invented one                                                                                                                                                                      |
| Q7  | Ship the WhatsApp exit ramp at the verdict?                                          | Yes. In a chat-first, scam-saturated market the exit _is_ the trust ritual. Guardrail, non-negotiable: the handoff carries a **case ID and a summary — never the passport file, never personal data into chat**. Its "20% return" threshold is **invented as a testing target, not a benchmark**                  |
| Q8  | Does a language model touch the verdict page?                                        | If yes, ship the disclosure line — EU AI Act Art. 50, from 2 August 2026. Not optional                                                                                                                                                                                                                            |
| Q9  | Red as the primary CTA fill, and do we A/B it?                                       | Yes to red, yes to the A/B. The case for red is **identity and local reading, not lift** — no study shows red CTAs convert better anywhere. Cost: red must then never _also_ carry error states                                                                                                                   |
| Q10 | Night-mode polarity: dark neutral ground + red accent, or the inverted maroon field? | **Do not decide this in prose. Build both from the same generator and choose from two rendered outputs.** Choosing between two artefacts is a brand decision the owner is entitled to make on sight; choosing between two arguments is not                                                                        |

### W7.4 Unverified — do not build on these

- **Every APCA (`Lc`) figure in W4.1** — locally reimplemented algorithm, validated against two
  canonical reference values only. Re-run through `apcacontrast.com` before any of them becomes a CI
  gate.
- **The entire ambient-flare model** behind the daylight numbers (the 1.05:1 elevation step, the
  1.15:1 hairline, the 2.79:1 red-CTA collapse). The structure is sound; ρ = 4.5%, 400 nits and the
  10,000 / 20,000 lux figures are one lane's engineering estimates. Replace with a photometer reading
  on an actual target device before quoting any ratio.
- **Every Material 3 and Apple HIG number** in this file (`[M]`): `m3.material.io` and
  `developer.apple.com/design/human-interface-guidelines` are JS-rendered SPAs that defeated four lanes
  independently. Well-corroborated by secondary sources; not quoted from a primary page. If one becomes
  load-bearing, open a browser.
- **Linear's and Stripe's token values** — no public spec; the circulating hexes come from
  reverse-engineered third-party catalogues. Do not cite them.
- **The dateline's status.** The gazette direction (dateline + edition rhythm as _provenance_) is right
  **and conditional on a fact nobody has checked**: is the "Filed this month: 47 KITAS" counter
  auto-generated or hand-edited? **Ship the dateline only if it is server-rendered from the same query
  that generates the counter. If those two lines can have different truth values, delete the dateline
  and keep the counter.** If the counter is hand-edited, the gazette direction is unavailable and the
  stale-dateline liability finding stands unopposed.
- **`indonesia-evoa.com`'s current legal status.** What is verified: the 2022 Immigration statement
  naming it, and that the site is live today with the quoted content. What is **not**: whether it has
  since been sanctioned or become a lawfully-disclosed intermediary. In any published copy call it
  _"the site Immigration named in 2022, still live today, with these characteristics"_ — **never "a
  scam site."**
- **Whether Indonesian text expansion has a published figure** (it does not — W6.5), whether any
  browser ships an `id` hyphenation dictionary, **Display-P3 coverage on budget Indonesian Android**
  (flagged by two seats independently — measure on the actual devices in the Kerobokan office before P3
  affects any decision), and whether the October 2026 expansion of 0% QRIS MDR to all merchants up to
  Rp 100,000 is real (found in search, **failed to corroborate on direct fetch — do not build pricing
  copy on it**).
- **Directional-only numbers that must never be quoted to a client as measured** — countdown-timer lift
  figures, per-badge trust percentages, "53% abandon past 3 seconds", the jam-study percentages, the
  57%/43% above-the-fold split, video-testimonial statistics, vendor payment-conversion claims. The
  full list is in the research capture §7.2.
- **The methodological caveat that outranks all of the above.** The canonical citable web-credibility
  work is _old_ (Stanford/Fogg ~2002; Nielsen 1999; NN/g 2016) and no 2020–2026 replication of
  comparable authority could be surfaced. **Do not let anyone present "the research says X about trust
  signals" as settled 2026 knowledge.** What _is_ defensible: the mechanism (signal death), the
  regulator rules (ASA, CMA, FTC, UU 8/1999), and the live autopsy.
- **The right posture for version one**, from the best design system in government, on exactly this
  screen: GOV.UK's own confirmation-pages pattern states _"Research is needed on the best way to confirm
  transactions that are part of a wider user task."_ **Assume version one is wrong, and instrument it.**

### W7.5 The thing that is not a knob: the state machine

The five-screen funnel is not the product. **The case ledger is, and the number of screens is an output
of the state inventory, not an input to it.** Thirty-plus states exist that no mockup in this project
has ever depicted: _upload unreadable · passport contradicts answers · quote expired before payment ·
payment pending (the bank may have completed this — do not pay again) · duplicate payment · paid but
application cannot be assembled · submission attempted, provider unavailable · disputed or charged back
· opened on a second device · shared link opened by another person._ Each needs what the screen says,
what the system owes the user, and **who is out of pocket right now**.

And the failure it names: **avoid the fashionable single progress bar — "Step 4 of 5" — when the
underlying process contains waiting, correction and refusal.** A progress bar describes page position,
not legal or financial state. It becomes deceptive when "90% complete" remains unchanged for three days.

**Caveat, stated because its own author states it**: that state table has **zero live sources** — it is
a **design artefact, not evidence**. Use it as a checklist; never cite it as precedent.

---

## W8 — Hard fail conditions (specific to the web surface)

W8.1 A mockup shipped **without a knob statement** (which of W2's eleven inputs was varied, and to
what) → **hard fail**. This is the rule the three rejected rounds existed to produce.
W8.2 Any value, effect or duration that **cannot name its input** under W1.1 → **hard fail**.
W8.3 Any claim on the page with **no external record that could falsify it** (W1.2), or a "verified"
artifact served from Bali Zero's own origin → **hard fail**.
W8.4 Brand red used as **ink on a dark ground** (gate 10) → **hard fail**.
W8.5 A hierarchy relation a user must read to complete a task carried by **tone alone** — i.e. the
screenshot fails the greyscale, daylight or forced-colors test (W4.2) → **hard fail**.
W8.6 A `setTimeout` / `DELAY_MS` / unbound progress animation on any success path (gate 30) → **hard
fail**, and it is greppable.
W8.7 A **payment control on an uncertain or borderline verdict** (gate 95), or a payment control
adjacent to a verdict computed from unverified self-reported answers (W4.7) → **hard fail**.
W8.8 A **confidence score, probability or pseudo-reasoning expander** on the verdict (gate 104) →
**hard fail**.
W8.9 A string from the blocklist (gate 108) present anywhere in the built output → **hard fail**, and
it fails the build.
W8.10 The **stranger test** (gate 85) failed on any surface carrying a price → **hard fail**.
W8.11 A **numeric government-fee split shipped without the live-verification stamp and the automatic
fallback** (W7.2) → **hard fail**.
W8.12 A single `Intl.NumberFormat` for both locales, or `parseFloat` applied to an `id-ID` price string
(W6.4) → **hard fail**.
W8.13 A price card that has not passed the **≥ 90% comprehension gate** (gate 93) → **soft fail**
(route back: the test costs ten strangers and one week).
W8.14 An accessibility overlay widget on any surface (gate 113) → **hard fail**.

---

## W9 — Where the evidence lives

This file is the **actionable layer**. It deliberately does not carry the evidence, the per-lane
sourcing, the nine unresolved contradictions with their rulings, or the 31 gates that did not make the
cut above.

- **Research capture** — `research/design/2026-08-31-web-design-sixteen-lane-corpus/`. The corpus
  (twelve web-grounded lanes + four cross-family seats; **254 `VERIFIED-LIVE`, 111 `FROM-MEMORY`**
  source declarations), the eleven convergences, the nine contradictions and how each was ruled, the
  complete 116-gate floor, and the full "could not verify" ledger. **Anything in this file that reads
  like an assertion has an argument there. Read it before overruling one.**
- **Lint** — `scripts/lint_web_surface.py`. The machine-checkable subset: gate 30 (artificial delay),
  gate 108 (string blocklist), gate 88 (asterisk on a price), the `parseFloat`/`id-ID` trap, the single
  formatter, `text-overflow: ellipsis` on a protected string, `clamp()` on a price or verdict, and
  overlay-vendor script hosts. A gate that can be grepped belongs there, not in a reviewer's memory.
- **Cross-surface** — `constitution.md` Articles 2 / 3 / 6.3-6.7 / 7 / 8 apply unchanged, and
  `voice/forbidden-phrases.md` is a superset the blocklist in gate 108 does **not** replace.
