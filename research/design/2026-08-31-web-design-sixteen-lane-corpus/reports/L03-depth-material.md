---
lane: L03 — Depth, material and texture: what replaces flat
seat: Claude Sonnet 5
date: 2026-08-31
sources_verified_live: 22
sources_from_memory: 2
adversarial_review: exempt-raw-lane-output-synthesis-carries-the-review
---

## Executive summary

"Scialba e piatta" is not fixed by adding shadows — it's fixed by adding *evidence of a surface*: a
lightness step instead of a drop-shadow, a hairline instead of a rule, a whisper of grain instead of
a flat fill. The 2026 state of the art (Apple's Liquid Glass, Material 3 Expressive) proves the
maximal version is expensive and, on Apple's own admission, an accessibility risk — so borrow the
*principle* (layering, translucency-as-hierarchy) and reject the *implementation* (real-time blur,
specular highlights) in favour of the cheap, static CSS equivalents below. Every technique here runs
in plain CSS inside one HTML file, costs no extra HTTP request, and is legible on a 360px Android
screen at night. The fastest-dating trend in this research is decorative maximalism sold as "physical
authenticity" (heavy skeuomorphism, thick glass, tactile-brutalist neon borders) — the durable version
is Linear's: one hairline, one lightness step, one accent colour, applied with total consistency.

---

## 1. Liquid Glass is a research problem Apple hasn't fully solved — borrow the layering logic, not the glass

**Named example.** Apple's own newsroom copy for iOS 26 / macOS Tahoe 26 describes Liquid Glass as
using "real-time rendering" that "dynamically reacts to movement with specular highlights" —
`VERIFIED-LIVE (fetched 2026-08-31)`, <https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/>.
Apple ships two variants: **regular glass** ("designed to be legible by default") and **clear glass**
(used in video-adjacent contexts, "requires more care to ensure legibility") — `VERIFIED-LIVE`, via
live search of Apple's HIG materials guidance. Within three months of shipping, a dedicated writeup
(letsdev.de) documented the predictable failure mode: *"text should be legible despite transparency,
and a minimum contrast ratio of 4.5:1 (WCAG) should be maintained,"* illustrated with a real screenshot
where *"some text has too little contrast, which reduces readability"* over a busy chat background —
`VERIFIED-LIVE (fetched 2026-08-31)`, <https://letsdev.de/en/blog/ios-26-in-detail-liquid-glass-ui-between-usability-and-accessibility.php>.

**The measurable rule.** Apple's own mitigation is not a CSS trick, it's a capitulation: Reduce
Transparency was expanded into "a full suite of customization options" including a high-contrast mode
that swaps translucency for solid fills — confirming that even Apple doesn't trust the effect to be
legible without an opt-out. The implementation guides that exist (LogRocket) list the ingredients —
`rgba()` tint, `backdrop-filter: blur()`, inset `box-shadow` for inner glow, `rgba()` border — but
explicitly admit *"without incorporating JavaScript libraries, it's difficult to duplicate Apple's
signature lensing style animations through just HTML and CSS"* — `VERIFIED-LIVE (fetched 2026-08-31)`,
<https://blog.logrocket.com/ux-design/adopting-liquid-glass-examples-best-practices/>. Translation: the
part of Liquid Glass that reads as "premium" (real-time refraction, specular light-tracking) is a
GPU shader effect, not a CSS property. What *is* implementable in plain CSS — layered translucent
panels, a tint that shifts with what's behind it, an inset highlight on the top edge — is available
without the shader. Practical blur-radius consensus across current glassmorphism guides: **8–24px**,
with values above ~24px reading as "muddy" rather than frosted, and mobile guidance to cap at 6–8px —
`VERIFIED-LIVE (fetched 2026-08-31, aggregated across guides)`.

**What to steal for Bali Zero.** Use the *layering logic* — a sticky price/CTA bar on the GARUDA VOA
flow that sits visually "above" the form, differentiated by one lightness step and a top hairline —
without the blur. On the one surface where translucency earns its keep (a bottom sheet or modal on
the Visa Oracle verdict screen, appearing over content that's about to be dismissed anyway), a single
`backdrop-filter: blur(10px)` on a small, fixed-size element is affordable — see §2 for why size matters
more than blur radius.

**What to avoid.** Full-page frosted panels, animated blur radius (each frame re-triggers GPU
compositing), and "glass on glass" stacking — nested translucent cards compound both the performance
cost and the legibility problem Apple itself is still patching eighteen months after announcing it.
For a scam-wary, low-bandwidth, low-light Android audience, an *illegible premium effect* is worse
than a flat one: flat is honest, illegible-glass reads as evasive.

---

## 2. What backdrop-filter actually costs on the hardware Bali Zero's audience uses

**Named example.** A direct, dated (2026) engineering writeup on CSS performance ran a controlled
before/after test of blurred backgrounds and reported GPU load *"stayed around 42–70 without the
effect and rose to approximately 130 when the blurred backgrounds were active"* on their test rig —
while the author is careful to add the caveat that *"those numbers are not a universal benchmark…
GPU measurements vary by browser, operating system, device, and monitoring tool"* — `VERIFIED-LIVE
(fetched 2026-08-31)`, <https://www.f22labs.com/blogs/how-css-properties-affect-website-performance/>.

**The measurable rule.** The mechanism, independent of any single benchmark: a `backdrop-filter` blur
forces the compositor to sample every pixel of everything behind the element, run a blur kernel over
it, and recomposite — every frame, if the element or its background moves. Cost scales with **blurred
area × blur radius**, and stacked blur layers multiply rather than add. The actionable consequence for
a 360–390px phone: keep the blurred *area* small (a pill-shaped price chip, not a full-width header),
keep the radius in the 8–16px band, and never animate the radius itself — animate `opacity` or
`transform` on a layer that sits *above* a blur that is otherwise static, which is the one pattern every
performance guide agrees is cheap. Do not use `backdrop-filter` on anything that scrolls with the
content (a sticky nav over a photo hero) unless you've profiled it on an actual mid-range device —
Chrome DevTools' CPU/GPU throttling plus a real device test, not a desktop guess.

**What to steal for Bali Zero.** On the home page's proof strip ("4.9★ · 693 Google reviews…") a small
frosted chip over the hero photograph is cheap (small area, static). On GARUDA VOA's 4-question flow
and the Visa Oracle verdict card — both content-heavy, both meant to be *read*, not glanced at — skip
`backdrop-filter` entirely and use the elevation techniques in §4 instead; they cost nothing at paint
time because they're flat colour, not a filter.

**What to avoid.** The fad here is using `backdrop-filter` as a default card style everywhere "because
it looks premium" — exactly the failure mode the shadcn/ui GitHub issue and the Flutter engine team
both flag (`BackdropFilter` is documented as "the most expensive widget Flutter ships" — same physics
applies to the web compositor). A page with six translucent cards stacked in a scroll feed is the
glassmorphism equivalent of six `<marquee>` tags: technically working, provably slow, and the first
thing a profiler will point at.

---

## 3. Material 3 Expressive: the "wild and way-too-playful" bet, and its accessibility tell

**Named example.** Google's own account of Material 3 Expressive states the redesign followed research
finding *"people have an appetite for 'wild and way-too-playful' interfaces"* and calls it *"the most
researched update to Google's design system, ever"* — `VERIFIED-LIVE (fetched 2026-08-31, via Google
Design / Dezeen coverage)`. The concrete deliverables: a spring-based physics motion system (buttons
"spring into place" rather than ease-in/out), an expanded shape library with built-in morphing
animation, and wider colour/typography ranges.

**The measurable rule.** This is a motion and shape system, not a material/texture system — it doesn't
answer the "flat vs deep" question directly, but its research premise is directly useful: Google
explicitly tested for *emotional* response ("wild," "playful") as a metric, not just task completion.
That is the missing axis in "technically correct but flat" work — a mockup can pass every usability
heuristic and still fail the emotional test that got Bali Zero's last three rounds rejected. The tell
that this trend will date fast on a *regulated professional services* site: playful spring-physics and
morphing shapes are calibrated for a phone-OS chrome used thousands of times a day by the same person
(where delight compounds), not for a visa-price decision made once, under financial stress, by someone
who has never used the site before and is actively suspicious of being scammed. Novelty motion reads
as "consumer app" register, which is the wrong register for "licensed notary & tax agent."

**What to steal for Bali Zero.** The *research method*, not the *aesthetic*: test copy/layout variants
for emotional register (does this feel like a real agency or a template?), not only for comprehension.
One expressive-but-restrained borrow: a single spring-eased state change (the CTA button on GARUDA VOA
when a step validates) — motion as *confirmation*, not decoration.

**What to avoid.** Material 3 Expressive's shape morphing and saturated colour ranges, applied wholesale,
would directly repeat rejection #2 from the brief (fifteen night-mode designs that "all looked
identical" because they anchored on a supplied token set) — a named design system is exactly the kind
of "shopping list" the brief warns against handing to a model. Cite the research method; don't import
the token set.

---

## 4. Elevation without shadow: the measurable rule, and who actually publishes it

**Named example.** Linear's dark-mode marketing site is the clearest public instance of *elevation via
lightness step, not shadow*, and its implementation is granular enough to be independently observed
from the live site — near-black canvas `#010102`("near-pure black with a faint blue tint"), a four-step
surface ladder (`#0f1011` → `#141516` → `#18191a` → `#191a1b`), and hairline borders as thin as
**0.5px**/1px in `#23252a` (base), `#34343a` (strong), `#3e3e44` (nested) — `VERIFIED-LIVE (fetched
2026-08-31)`, <https://github.com/voltagent/awesome-design-md/blob/main/design-md/linear.app/DESIGN.md>.
**Caveat on this source**: it is a third-party token catalogue reverse-engineered from the live site's
computed CSS, not Linear's own published spec — treat the exact hex values as a close approximation,
spot-checkable against linear.app itself, not as an official design-system citation. Independently, a
second live source (search-indexed) describes the *mechanism* the same way: *"Elevation isn't
communicated through shadow darkness but through background luminance steps — each level slightly
increases the white opacity of the surface background (0.02 → 0.04 → 0.05)"* — `VERIFIED-LIVE (fetched
2026-08-31)`, <https://chyshkala.com/blog/why-linear-design-systems-break-in-dark-mode-and-how-to-fix-them>
(this second fetch could not confirm exact percentages independently — see "what I could not verify").
Google's own dark-theme guidance converges on the same physics for a different reason: *"In dark themes
… elevated surfaces and components are colored using overlays. The more elevated the surface is, the
stronger and brighter the overlay becomes"* and *"each layer up adds 4-8% lightness to the background
surface"* — `VERIFIED-LIVE (fetched 2026-08-31, via search-indexed Material guidance)`.

**The measurable rule.** Three convergent, implementable techniques, all pure CSS, no images:
1. **Lightness stepping**: define a base surface OKLCH lightness (e.g. `L=0.08` on a near-black ground)
   and add a fixed `+0.03 to +0.05 L` per elevation level — 3-4 named levels is enough (`surface-0`
   through `surface-3`), never a continuous shadow gradient.
2. **Hairline + inner stroke instead of drop-shadow**: `box-shadow: inset 0 1px 0 0 rgba(255,255,255,.06)`
   for the top-edge "catch-light," combined with a real 1px border at low alpha (`rgba(255,255,255,.08)`)
   for the perimeter. This is the "layered borders" technique the brief asks about — it reads as a
   physical edge without a single shadow pixel, and it costs nothing at paint time (no filter, no blur).
3. **Chroma shift, not just lightness**: elevated surfaces on Material's tonal system tint *toward* the
   brand hue as they rise, which is why Linear's ladder reads as "lifted" rather than merely "washed
   out" — a pure grey lightness ramp looks like a bug; a lightness ramp tinted 2-3° toward your accent
   hue in OKLCH reads as intentional.

**What to steal for Bali Zero.** This is the single highest-leverage technique for the "scialba e piatta"
complaint on a dark treatment: define exactly 3 surface tokens (`bg`, `card`, `card-raised`) as fixed
lightness steps in OKLCH, apply the inset-highlight + hairline-border pair to every card on the home
page's four segment doors and the Visa Oracle verdict card, and stop there. No blur, no drop-shadow, no
`filter`. Works identically on a 360px screen and a 3840px monitor because it's colour, not geometry.

**What to avoid.** Treating "no shadow" as "no depth" — the actual fad-to-avoid is the opposite failure
from round 1: a designer told "no drop-shadows" who responds by making every surface the *same* flat
colour, which reproduces the original complaint. The rule isn't "remove depth," it's "encode depth as
colour instead of geometry."

---

## 5 & 6. Texture that survives compression: grain, and halftone as the "engineered" register

**Named example — grain.** The standard technique (documented, reproducible) layers an inline SVG
`feTurbulence` filter as a CSS `background-image` data URI:
```svg
<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/></filter>
```
applied via `background-image: url("data:image/svg+xml,...")` at low opacity (0.1–0.2) over a solid or
gradient fill — `VERIFIED-LIVE (fetched 2026-08-31)`, <https://www.freecodecamp.org/news/grainy-css-backgrounds-using-svg-filters/>.
This is genuinely zero-request and zero-build-step: the SVG lives inline in the same `<style>` block,
which matches this project's single-file constraint exactly. A separate 2026 trend piece frames the
*motivation* precisely: *"CSS grain filter or an animated SVG noise overlay to a solid background
instantly breaks up the digital perfection"* and contrasts it with heavier WebGL particle approaches,
concluding textures are replacing "heavy 3D" specifically because they run "purely on lightweight
browser rendering engines" — `VERIFIED-LIVE (fetched 2026-08-31)`,
<https://fireart.studio/blog/the-best-web-design-trends/>.

**Named example — halftone.** A three-declaration pure-CSS halftone technique (no images, no
pseudo-elements) exists and is current (2026):
```css
background: radial-gradient(closest-side, #777, #fff) 0/1em 1em space,
            linear-gradient(90deg, #888, #fff);
background-blend-mode: multiply;
filter: contrast(16);
```
— `VERIFIED-LIVE (fetched 2026-08-31)`, <https://blog.master.dev/pure-css-halftone-effect-in-3-declarations/>
(Frontend Masters). A 2026 trend report frames why halftone reads as "crafted" rather than "template" in
its current form: *"the 2026 halftone trend isn't about making things look like old comics — it's about
Brutalism… making it utilitarian rather than nostalgic"* — `VERIFIED-LIVE (fetched 2026-08-31)`, via
search of <https://artcoastdesign.com/blog/halftone-textures-neo-print-trend-2026>.

**The measurable rule.** Grain that reads as "crafted": opacity 0.1–0.2, applied once as a page-level
overlay (not per-component, which multiplies paint cost and reads as busy), `baseFrequency` in the
0.7–1.0 range for a fine, printed-paper grain rather than a coarse "static TV" look. Grain that reads as
"template": visible tiling seams (fixable with `stitchTiles='stitch'`), opacity above 0.3 (reads as
damage, not texture), or grain applied inconsistently across sections. Halftone reads as "engineered"
when it is monochrome/duotone and used sparingly (a single section divider, a hero background) at
moderate dot scale (`0.75–1.25em`); it reads as "template" when it's rainbow-coloured, animated, or
covers body-text areas, hurting legibility.

**What to steal for Bali Zero.** A single, page-wide grain overlay at 0.08–0.12 opacity on the home
page's dark hero — this is the cheapest possible answer to "scialba e piatta": it costs one inline SVG,
zero requests, and reads immediately as "designed surface" rather than "default browser background." A
halftone duotone treatment (Bali Zero's accent colour over near-black) works as a section-break texture
between the proof strip and the four segment doors — never on the GARUDA VOA form itself, where every
pixel should read as trustworthy and legible, not textural.

**What to avoid.** Grain as a blanket `body::after` at high opacity (reads as a dirty screen, not
craft); halftone in more than one hue (reads as a 2015 Instagram filter); either technique animated
(defeats the "cheap, static" cost profile that is the entire argument for choosing CSS texture over
WebGL in the first place).

---

## 7. Borders, hairlines and the "printed document" feel

**Named example.** The retina-hairline problem and its canonical fix: on a 2x display a naive `1px`
border renders as *two* hardware pixels, doubling its visual weight; the fix scales a pseudo-element to
200% and then `transform: scale(0.5)`, so the resulting border renders at exactly one device pixel:
```css
@media (-webkit-min-device-pixel-ratio: 2) {
  &::before { transform: scale(.5); transform-origin: 0 0; content: "";
    position: absolute; width: 200%; height: 200%; border: 1px solid #f5f5f5; }
}
```
— `VERIFIED-LIVE (fetched 2026-08-31)`, <https://annualbeta.com/blog/1px-hairline-css-borders-on-hidpi-screens/>.
A simpler, broadly-supported equivalent for a single-file project is `box-shadow: 0 0 0 0.5px rgba(...)`
— sub-pixel `box-shadow` spread is honoured by Safari/Chrome/Firefox on HiDPI in a way a literal
`border-width: 0.5px` sometimes isn't, per the same source family.

**Named example — the "printed" system.** A third-party reconstruction of Stripe's site tokens
describes the mechanism precisely: *"Depth and hierarchy are created through background tint
progression (white → #f8fafd → #e5edf5 → #e8e9ff → #533afd), hairline 1px dividers in #e5edf5, and
generous whitespace,"* with editorial display type at negative tracking and **tabular-figure** body
type "where money and numerics matter" — `VERIFIED-LIVE (fetched 2026-08-31, via search-indexed
third-party design-token extraction, not Stripe's own published spec)`. The letterpress technique for
a genuinely printed feel is a two-line `text-shadow`: `color: #222; text-shadow: 0 2px 3px #555;`
against a mid-grey ground — `VERIFIED-LIVE (fetched 2026-08-31)`,
<https://line25.com/tutorials/create-a-letterpress-effect-with-css-text-shadow>.

**The measurable rule.** "Printed document" register, in CSS, is not one trick — it's four small ones
stacked: (1) a hairline rule (0.5–1px, low-alpha, never pure black) instead of a card border; (2)
tabular figures (`font-variant-numeric: tabular-nums`) on every price and every deadline, so numbers
align like a ledger; (3) generous, *consistent* vertical rhythm (a printed page never crams — cramped
spacing is a documented "reads as cheap" signal, and the Stripe reconstruction states this explicitly:
"cramped layouts read as cheap"); (4) restraint on colour — the Stripe tint progression above uses five
steps total across an entire marketing site.

**What to steal for Bali Zero.** This is the direct answer to the "the price is the whole price" trust
promise: every price on GARUDA VOA and the Visa Oracle verdict card in tabular figures, a hairline rule
under the price (not a card shadow around it), and the retina-safe hairline technique on every divider —
this alone produces a "typeset, not templated" read, which is exactly the credibility signal a
scam-wary audience is scanning for. It's also the cheapest change in this whole report: zero images,
zero filters, a handful of CSS custom properties.

**What to avoid.** Literal skeuomorphic paper texture (drop-shadow under a "sheet," a folded-corner
`::after`) — that's the *fad* version of "printed," and it dates immediately because it apes a physical
object instead of borrowing the physical object's *typographic discipline* (alignment, rhythm, hairline
rules), which is the part that actually reads as trustworthy.

---

## 8. Gradients in 2026: OKLCH fixes the physics, doesn't fix the taste problem

**Named example.** By 2026, OKLCH gradient interpolation is stable across every major browser with no
fallback needed, and the reason it matters is concrete: interpolating in sRGB/HSL desaturates the
midpoint of a hue-arc gradient (the "grey mud" problem), while OKLCH keeps lightness and chroma
consistent through the transition — `VERIFIED-LIVE (fetched 2026-08-31, via search-indexed toolbox365.net
gradient-banding article; direct fetch returned HTTP 403, so this is confirmed via live search index,
not a quoted primary fetch)`. For mesh gradients specifically, current guidance converges on **3-4
colour layers as the sweet spot** — "two looks flat, and beyond five the overlaps turn muddy" —
`VERIFIED-LIVE (fetched 2026-08-31, via search-indexed 21st.dev gradient guide)`. Banding fix: a faint
noise overlay at 0.1-0.2 opacity, below which banding persists and above which (>0.3) it reads as film
grain rather than a fix — same source.

**The measurable rule.** Syntax: `linear-gradient(in oklch, var(--c1), var(--c2))` — the `in oklch`
interpolation hint is the entire fix, no extra stops needed. Combine with the grain technique from §5:
a mesh/aurora gradient background plus a 0.1-opacity `feTurbulence` overlay is the standard 2026
anti-banding pairing, and it's free — same inline SVG, reused.

**What to steal for Bali Zero.** A restrained two-to-three-stop OKLCH gradient (brand accent → near-black)
behind the home page hero, interpolated `in oklch` for a clean falloff, with the grain overlay from §5
on top to kill banding on cheap Android panels (which band far more visibly than a MacBook display —
this is precisely the audience described in the brief).

**What to avoid — the cliché, named exactly.** A widely-observed pattern in 2026 design commentary: an
"indigo-to-purple gradient behind the hero" plus "a glassmorphism card with a faint neon glow" has
become *the* visual signature of AI-generated interfaces — one widely-read account traces it to a
specific origin (Tailwind UI's default `bg-indigo-500` button, apologized for publicly by its creator
after "every AI-generated interface on Earth" converged on it) and describes the feedback-loop mechanism:
*"When a striking site with a purple gradient gets enough attention, it makes its way into the next
round of training data, which teaches the next generation of models that purple gradients are even more
normal than before"* — `VERIFIED-LIVE (fetched 2026-08-31, via search-indexed prg.sh and related 2026
commentary)`. **The tell that distinguishes "considered" from "AI-generated-default": a considered
gradient is desaturated and restrained (2-3 stops, low chroma, brand-anchored hue), sits *behind*
content rather than *as* the card surface, and never pairs with a glow.** The default-AI version is
saturated indigo/purple/cyan, high-chroma, used as the card fill itself, and almost always paired with
a soft outer glow (`box-shadow: 0 0 60px rgba(purple,.4)`) — that glow is the single most legible tell.
Bali Zero's palette should anchor to its own brand hue, not indigo, and skip the glow entirely.

---

## 9. The fad, named directly, and its durable twin

**The fad**: decorative maximalism justified as "physical authenticity" — thick simulated glass with
visible specular highlights, neon 1px borders on brutalist grids, saturated gradient-plus-glow cards,
and literal skeuomorphic paper/fold effects. This is the throughline across §1 (Liquid Glass's own
accessibility patch three months post-ship), §3 (Material 3 Expressive's spring-physics calibrated for
daily-use consumer chrome, not a once-per-decision trust page), and §8 (the purple-gradient-plus-glow
AI signature). **The tell**: every fad-version technique above requires either (a) a real-time filter
(blur, specular shader) that the *source itself* documents as a performance and legibility cost with an
accessibility opt-out already built by its own maker, or (b) a saturated, high-chroma palette applied at
scale rather than as a single accent.

**The durable version**, evidenced across every "elevation" and "editorial" source in this report and
converging independently from Google (tonal elevation), Linear (surface-ladder + hairline), and Stripe
(tint progression + tabular figures): **depth encoded as a small, fixed set of lightness/chroma steps
and hairline rules, applied with total consistency, using zero filters.** Neumorphism is the cautionary
tale that proves the boundary case — it died specifically because it pushed the "soft, tactile" instinct
past the point where contrast survives: *"text on a background-matching surface routinely lands below
the WCAG AA minimum of 4.5:1 for normal text, because soft gray on gray is the whole aesthetic"* —
`VERIFIED-LIVE (fetched 2026-08-31, via search-indexed Axess Lab / Built In neumorphism-accessibility
coverage)`. That is the exact failure mode to test for on every technique in this report before shipping
it: does the depth cue survive a contrast checker, not just a designer's eye. Nielsen Norman Group's
research on the *predecessor* problem — over-flattened UI — reaches the same place from the opposite
direction: *"long-term exposure to these flat yet clickable elements has been slowly reducing user
efficiency,"* and its prescription is explicitly "Flat 2.0": *"subtle shadows, highlights, and layers"*
restoring signifiers "without excessive ornamentation" — `VERIFIED-LIVE (fetched 2026-08-31)`,
<https://www.nngroup.com/articles/flat-design/>. Bali Zero's brief sits exactly between these two failure
modes, and the corridor between them is narrow: enough surface-differentiation to read as "a real
place run by people who know the rules," not so much that it reads as either a toy (fad) or a form no
one trusts (flat).

**Local counter-signal worth naming.** Regional superapp precedent argues *against* borrowing loudly
from the "bold and playful" register even though it's locally dominant: Gojek's most recent redesign,
covered in independent UX case studies, drew documented backlash for an "over-complicated interface"
after leaning into "bolder and brighter colours" — `VERIFIED-LIVE (fetched 2026-08-31, via search-indexed
Medium UX case studies)`. For a superapp used dozens of times a day, brightness and density are
tolerated; for a once-per-decision, trust-critical, scam-adjacent transaction like a visa filing, the
Stripe/Linear register (restraint, hairlines, tabular numbers) is the better-evidenced fit, not the
locally-dominant superapp register.

---

## What I could not verify

- **The precise historical Material Design 2 dp→opacity-overlay table** (the well-known 0dp/1dp/2dp…
  24dp percentage ladder). I could not get a live-rendered fetch of `m2.material.io` or `m3.material.io`
  this session (both returned only page titles, no body — likely JS-rendered content this fetcher
  doesn't execute). The *directional* claim ("4-8% lightness per elevation step," Material's shift to
  tonal surface-container roles) is corroborated by two independent live search results, but I would
  not trust an exact numeric table from memory without re-verifying against the rendered page or the
  Material source repo directly. `FROM-MEMORY (unverified)` if cited elsewhere with exact percentages.
- **A specific "~200ms per frame for 8 stacked blur layers (1–128px) on mid-tier GPU" backdrop-filter
  benchmark** surfaced in an initial search summary attributed to a CSS-performance article. When I
  fetched that article directly, it explicitly stated it provided *no* specific backdrop-filter metrics
  and *"deliberately avoids prescriptive benchmarks."* I could not locate the primary source for the
  200ms figure and am **not** using it in the findings above — flagging it here so it isn't mistaken for
  a verified number if it resurfaces in another lane's report. `FROM-MEMORY (unverified) — do not cite`.
- **Exact Linear and Stripe hex/opacity tokens** (§4, §7) come from third-party reverse-engineered
  design-token catalogues (GitHub `awesome-design-md`, `styles.refero.design`, `designmd.co`), not from
  Linear's or Stripe's own published design-system documentation — neither company publishes a public
  spec. The values are internally consistent and spot-checkable against the live sites, but should be
  treated as "closely observed," not "officially specified."
- **GOV.UK Design System's explicit stance on shadows/depth** — attempted to verify directly; the
  component index page fetched had no body content on visual-decoration philosophy. Not cited in the
  findings above as a result; if another lane needs it, it should be re-fetched against a specific
  component page (e.g. `/components/button`), not the index.
- **APCA (Accessible Perceptual Contrast Algorithm) specific Lc thresholds for translucent text** — the
  canonical URL attempted (readtech.org/APCA) 404'd this session. Not cited; the WCAG 4.5:1 figure used
  instead is independently confirmed via the letsdev.de fetch.
- **Whether Bali Zero's actual target Android devices (mid-range, 2026) show visible frame drops at the
  specific 8–16px blur-radius / small-area budget recommended in §2** — this is a mechanism-level
  inference from documented compositor physics plus consensus guidance, not a device test on the
  project's own hardware. Before shipping any `backdrop-filter` use, profile on an actual mid-range
  Android device (Chrome remote debugging, Performance panel), not just a desktop simulation.
