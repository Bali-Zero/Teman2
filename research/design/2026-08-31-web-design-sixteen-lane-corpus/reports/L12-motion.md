---
lane: L12 — Motion and micro-interaction
seat: Claude Sonnet 5
date: 2026-08-31
sources_verified_live: 17
sources_from_memory: 6
---

## Executive summary

Every serious motion system converges on the same shape, not the same numbers: **micro-feedback ≈50–150ms, transitions ≈150–400ms, nothing habitual over ~500ms** — Bali Zero's dark, phone-first, anxious-at-midnight surfaces should sit at the fast end of that band (120–250ms) because slow motion reads as *hesitation*, and hesitation is exactly what a scam-wary visitor is scanning for. The 2026 responsiveness metric that actually gates Google/Core Web Vitals is **INP ≤200ms**, not the 1968-era 100ms/1s/10s ladder — but that ladder still correctly tells you *when* to show feedback at all (nothing under ~1s, a percent-done indicator only past ~10s). Skeleton screens beat spinners only above roughly a 1-second wait and only when they preview real structure, not a blank frame — for GARUDA's passport-upload and payment-confirmation steps this argues for a **named-step skeleton** ("Verifying passport… Checking availability… Confirming payment"), not a spinning wheel. The whole system is achievable in plain CSS today: `transition`, `@starting-style` + `transition-behavior: allow-discrete`, and `animation-timeline: scroll()` cover entrance/exit/progress with no JavaScript, at 85–90%+ global browser support, degrading silently (not brokenly) on the rest. The one fad to kill on sight is scroll-jacking / hijacked-scroll storytelling — NN/g's own usability testing found it disorients most users and only survives when it serves a real explanatory purpose (which none of Bali Zero's three transactional flows have).

---

## 1. Durations and easing, with numbers

### Finding 1.1 — The named example
**IBM Carbon Design System**, `@carbon/motion` package — `https://github.com/carbon-design-system/carbon/blob/main/packages/motion/src/dtcg/motion.json` — **VERIFIED-LIVE (fetched 2026-08-31)**.

**The measurable rule.** Carbon ships six duration tokens and six easing curves, in two "modes":

```
duration.fast.01      70ms
duration.fast.02      110ms
duration.moderate.01  150ms
duration.moderate.02  240ms
duration.slow.01      400ms
duration.slow.02      700ms

easing.standard.productive  cubic-bezier(0.2, 0, 0.38, 0.9)
easing.standard.expressive  cubic-bezier(0.4, 0.14, 0.3, 1)
easing.entrance.productive  cubic-bezier(0, 0, 0.38, 0.9)
easing.entrance.expressive  cubic-bezier(0, 0, 0.3, 1)
easing.exit.productive      cubic-bezier(0.2, 0, 1, 0.9)
easing.exit.expressive      cubic-bezier(0.4, 0.14, 1, 1)
```
"Productive" curves are steeper/faster (enterprise data tables, dense forms — get out of the way); "expressive" curves have more visible deceleration (consumer-facing surfaces — feel considered). The split exists because Carbon serves both IBM's own SaaS dashboards and public-facing product pages from one system, and a single curve family tested badly on one or the other.

**Atlassian Design System** — `https://atlassian.design/foundations/motion` — **VERIFIED-LIVE (fetched 2026-08-31)**:
- Hover/press feedback: **50–150ms**
- Panels/modals entering or exiting: **150–400ms** (dropdown 150ms, modal 250ms, named exactly)
- Four curves, purpose-tagged: `ease-out-bold cubic-bezier(0, 0.4, 0, 1)` for things arriving and stopping (panels, flags); `ease-in-out-bold cubic-bezier(0.4, 0, 0, 1)` for scaling/repositioning; `ease-in-practical cubic-bezier(0.6, 0, 0.8, 0.6)` for exits; `ease-out-practical cubic-bezier(0.4, 1, 0.6, 1)` for subtle everyday entrances (popups, hover fades).

**Material 3** — `https://m3.material.io/styles/motion/easing-and-duration/tokens-specs` — direct fetch of the page returned only its title (client-rendered; MDN/caniuse-style static export was not reachable by the fetch tool). The following numbers are corroborated across two independent live search snippets pulled from the current indexed page and a third-party summary of it, but **not independently page-fetched and quoted** — treat as a notch below the other two: `short1 50ms / short2 100ms / short3 150ms / short4 200ms`, `medium1 250ms … medium4 400ms`, `long1 450ms … long4 600ms`, emphasized easing `cubic-bezier(0.2, 0, 0, 1)`. Material's own framing: Emphasized easing "for most transitions", Standard easing only when speed matters more than naturalness (a system list scrolling past, not a hero element arriving).

**Apple HIG** — `https://developer.apple.com/design/human-interface-guidelines/foundations/motion` — fetch attempted twice, both returned only the page title (client-rendered app-shell). **FROM-MEMORY (unverified)**: HIG's long-standing guidance is 0.2–0.5s for interface animation with a system ease-in-ease-out curve, spring-based (not cubic-bezier) for anything the user can interrupt with a touch — this should be confirmed against the live page before it is quoted to Zero as a number.

**What to steal for Bali Zero.** Adopt a five-token scale modeled on Carbon+Atlassian's convergence, biased fast because the brief is phone/night/anxious:
```css
:root {
  --dur-instant: 80ms;   /* checkbox, toggle, button press */
  --dur-fast:    150ms;  /* hover, small state change */
  --dur-base:    220ms;  /* card/panel enter */
  --dur-slow:    320ms;  /* modal, page-section reveal */
  --ease-out:    cubic-bezier(0.2, 0, 0, 1);   /* arrivals */
  --ease-in:     cubic-bezier(0.4, 0, 1, 1);   /* exits */
}
```
Use `--dur-instant`/`--dur-fast` for anything on the Visa Oracle answer-toggle (an editable answer changing state) and GARUDA's 4-question flow; `--dur-base` for the price card appearing; nothing on any of the three surfaces should exceed `--dur-slow`.

**What to avoid.** Copying a system's full 12-token duration ladder (short1…extra-long4) wholesale into a 3-page marketing/transaction site. That granularity exists because Carbon and Material serve hundreds of component states across a whole enterprise product; a single-flow site with five states doesn't need it, and over-tokenizing motion is how "technically correct and emotionally flat" (the exact failure the brief names) happens — five deliberate values chosen for a reason beat twelve inherited ones.

---

## 2. Perceived responsiveness

### Finding 2.1 — The named example
**Nielsen Norman Group**, "Response Times: The 3 Important Limits" — `https://www.nngroup.com/articles/response-times-3-important-limits/` — **VERIFIED-LIVE (fetched 2026-08-31)**, and "Executing UX Animations: Duration and Motion Characteristics" — `https://www.nngroup.com/articles/animation-duration/` — **VERIFIED-LIVE**.

**The measurable rule.** The three limits, quoted directly:
- **0.1s** — feels instantaneous; no feedback needed beyond the result itself.
- **1.0s** — the user notices the delay but stays in flow; still no special feedback required.
- **10s** — the outer edge of attention; past this, show a **percent-done indicator** and a way to interrupt, or the user assumes the system is broken.

Confirmed directly: this article's citations run 1968–1991 (Miller, Card/Newell) with only a 2014 web-context update — **no skeleton-screen or spinner research is cited in it at all**. It is a threshold model for *when to intervene*, not a design-pattern guide, and treating it as the latter (as several blog posts do) overstates what NN/g actually published.

For animation *duration itself*, the companion NN/g piece gives its own numbers: **~100ms** for basic feedback (checkbox, toggle — "feels immediate... illusion of physically manipulating the object"), **200–300ms** for moderate transitions (modal entering), up to **500ms** only for large-object motion across a big screen — and explicitly, over 500ms "starts to feel like a real drag... cumbersome and annoying." Exit animations should generally run shorter than the matching entrance (a 300ms entrance can exit in 200–250ms) because the user's attention has already moved on.

**INP** — `https://web.dev/articles/inp` — **VERIFIED-LIVE (fetched 2026-08-31)**. Thresholds: **good ≤200ms**, needs-improvement 200–500ms, poor >500ms, measured from the moment of interaction to the next painted frame, worst-typical interaction across the page's life (not just first input, which is what FID measured before INP replaced it as a Core Web Vital). This is the number Google actually scores the site on in 2026 — Nielsen's 0.1/1/10s ladder is the *design* rule; INP is the *measurement* that proves you followed it. They agree almost exactly at the fast end (0.1s ≈ 100ms vs. INP's 200ms "good" ceiling), which is not a coincidence — INP effectively codifies Nielsen's instantaneous threshold into a shippable metric.

**Skeleton screens vs. spinners vs. nothing** — `https://www.nngroup.com/articles/skeleton-screens/` — **VERIFIED-LIVE**. Under ~1 second, neither is worth building — the flash reads as a glitch, not a load. Between roughly 1 and 10 seconds: a spinner is right for a single, self-contained module (one card, one video); a skeleton screen is right for a *full-page* load because it previews the coming layout and reduces the "is it broken?" read. The article's specific warning: a skeleton that shows only header/footer chrome with no content placeholders is worse than nothing — users conclude the page is stuck rather than loading.

**Optimistic UI and defensible artificial delay.** Not independently verified live this session (Linear's own writing on it — `linear.app/method` — returned only its table of contents on fetch); documented pattern **FROM-MEMORY**: an action is shown as succeeded the instant the user commits it (message sent, item checked off, block reordered), with the network call reconciling silently behind it and a rollback+toast only on the rare failure. This is defensible when the failure rate is low and the cost of a wrong-looking success is low (reordering a list). It is **not** defensible for GARUDA's payment step — showing "Payment confirmed" before the payment gateway has actually confirmed is not a UX nicety, it is a false statement to someone paying real money for a government service, and directly collides with the brief's core promise ("the price is the whole price," an honest professional who does not overclaim). An artificial delay is a dark pattern specifically when it invents wait time to *simulate effort that isn't happening* (the classic fake "searching 500 airlines…" loader) — it is legitimate when it *smooths a real but jittery process* (holding a genuinely-fast API response for ~400ms so a status step doesn't flicker past unreadably). The dividing line is whether the delay communicates real state or manufactures a fictional one.

**What to steal.** GARUDA's payment step: a named-step progress list ("Verifying passport → Checking availability → Confirming payment"), each step's checkmark landing only when its real network call resolves, INP-safe (button press registers instantly via `:active`/focus styling even while a real network wait is running behind it). Visa Oracle's editable-answer toggle: `--dur-instant` state change is optimistic-safe because there's no server round-trip to fake.

**What to avoid.** A generic spinner on the payment-confirming screen for more than ~2s with no step text — this is precisely the shape NN/g flags as producing "is it broken?" anxiety, and this audience is already primed to suspect a scam.

---

## 3. Modern CSS-only motion, 2026

All four items below ship with **zero JavaScript** — directly usable in the single self-contained HTML mockups this project produces.

### Finding 3.1 — `@starting-style` + `transition-behavior: allow-discrete`
`https://developer.mozilla.org/en-US/docs/Web/CSS/@starting-style` and `.../transition-behavior` — **VERIFIED-LIVE (fetched 2026-08-31)**. Baseline 2024 ("newly available"); caniuse puts `@starting-style` at **90.65% global support** — **VERIFIED-LIVE, `https://caniuse.com/mdn-css_at-rules_starting-style`**, fetched 2026-08-31.

**The mechanism.** `display: none` and other discrete properties normally cannot transition — they flip instantly. `transition-behavior: allow-discrete` makes them transition-eligible, and the browser is smart about *when* the flip happens: entering (`none → block`) flips at 0% of the duration so the element is visible for the whole animation; exiting flips at 100% so it stays visible until the exit finishes. `@starting-style` supplies the "from" values for an element's very first paint, which is what makes a toast/panel animate *in* rather than simply appearing.

```css
.toast {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
  transition: opacity var(--dur-base) var(--ease-out),
              transform var(--dur-base) var(--ease-out),
              display var(--dur-base) allow-discrete,
              overlay var(--dur-base) allow-discrete;
}
.toast.is-open {
  display: block;
  opacity: 1;
  transform: translateY(0) scale(1);
}
@starting-style {
  .toast.is-open { opacity: 0; transform: translateY(8px) scale(0.98); }
}
```
This is real for GARUDA's "your document was accepted" confirmation card and Visa Oracle's verdict reveal — no JS needed if the state toggle itself comes from a `<details>`/`:checked`/`:target` trick in the static mockup, or from the one line of production JS that flips a class.

### Finding 3.2 — Scroll-driven animations (`animation-timeline`)
`https://developer.chrome.com/docs/css-ui/scroll-driven-animations` — **VERIFIED-LIVE (fetched 2026-08-31)**; caniuse `animation-timeline` **85.43% global**, gap is mainly Safari <26 and Firefox <157 — **VERIFIED-LIVE, `https://caniuse.com/mdn-css_properties_animation-timeline`**.

**The mechanism.** The animation's progress is driven by scroll position instead of a clock, and — critically — it runs on the **compositor thread**, so it doesn't jank on a slow Android phone the way a `scroll` event listener rewriting styles on the main thread does. Two flavors: `scroll()` ties progress to a scrollport (a reading-progress bar), `view()` ties it to an element crossing the viewport (fade a card in as it enters).

```css
@keyframes progress { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.reading-bar {
  transform-origin: left;
  animation: progress linear;
  animation-timeline: scroll(root block);
}
```

**What to steal.** A slim progress indicator on the Visa Oracle decision tree (how far through the question sequence) that fills as the page/answer-list scrolls, with zero JS and zero main-thread cost — the exact opposite of the janky parallax this same API is usually (mis)used for.

**What to avoid.** Do not gate any *content visibility* on this — always pair with a `@supports (animation-timeline: scroll()) { }` block, and give the un-supported browser the finished state by default, never a stuck-at-0% bar. Progressive enhancement, not a hard dependency.

### Finding 3.3 — View Transitions API
`https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API` (spec) and `https://caniuse.com/mdn-css_at-rules_view-transition` — **VERIFIED-LIVE (fetched 2026-08-31)**: cross-document (MPA) view transitions via the `@view-transition` at-rule are at **84.8% global support** as of July 2026 — Chrome/Edge 126+, Safari 18.2+ (desktop and iOS), Opera 112+, Samsung Internet 28+. **Firefox does not support it at all**, at any version.

**The mechanism.** For a genuinely multi-page site (three real pages here: home → Oracle → GARUDA), one CSS rule turns on smooth cross-fades between navigations, with no JavaScript:
```css
@view-transition { navigation: auto; }
```
Named transitions on shared elements (`view-transition-name: hero-price`) let a specific element — e.g. the price figure — visually morph from the home page's proof strip into the Oracle's verdict price, instead of a hard cut.

**What to steal.** This is the single highest-leverage "feels considered, costs nothing" move available for three separate HTML pages, and it degrades **silently** — a Firefox visitor just gets an ordinary navigation, never a broken one.

**What to avoid.** Relying on it for anything load-bearing (a step the user must see to understand state) — it is decoration on top of a working page, never the mechanism itself.

---

## 4. Micro-interactions that earn their place

Four of the five examples below are **FROM-MEMORY (unverified this session)** — the WebSearch budget for this lane was exhausted mid-research and the specific product blog posts were not independently re-fetched; each is a widely documented, named pattern, not an invented one, but should be spot-checked before being cited to Zero as gospel.

1. **Question answered (Visa Oracle).** *Stripe Elements* form-field validation — inline checkmark morphs in on the field border the instant a card number passes Luhn-check, not on blur. **Mechanism**: state-driven border-color + a small SVG check `stroke-dashoffset` animation, ~150–200ms. **Steal**: apply the same idea to Oracle's editable-answer chips — a small check-pulse when an answer is accepted, using the `--dur-fast` token, pure CSS via a `:checked` sibling selector. **Avoid**: validating too early (as-you-type shame before the field is even complete) — Baymard's forms research (not fetched this session, cite with care) consistently finds premature error states increase abandonment.
2. **Price appearing (GARUDA / Oracle verdict).** The pattern common to airline/hotel search results (Traveloka, Google Flights): the number doesn't just appear, it **counts up or settles** from a placeholder skeleton digit to the final figure over ~200–300ms, signaling "this was computed for you, not hardcoded." **Steal**: IDR 790.000 settling in on GARUDA, `@starting-style` opacity+scale, no counting animation (counting requires JS and adds nothing an honest flat price needs). **Avoid**: any animation that makes the price look negotiable or provisional after it lands — a re-triggered pulse every time the page re-renders reads as "the price just changed," which is corrosive on a brief whose entire premise is "the price is the whole price."
3. **File uploading (GARUDA passport upload).** WhatsApp/Telegram-style upload chip: a static thumbnail with a **radial progress ring** drawn via `conic-gradient` (pure CSS, no JS, updates only need custom-property writes) rather than an indeterminate spinner, because a determinate ring answers "how much longer" without text. **Steal**: same conic-gradient ring around the passport-photo thumbnail. **Avoid**: an indeterminate spinner on a step with a knowable byte count — determinate feedback is strictly more informative and costs nothing extra in pure CSS.
4. **Payment confirming (GARUDA).** *GoPay/QRIS confirmation pattern* (Indonesian mobile payment UX, widely copied across GoTo/Tokopedia/Traveloka checkout flows): a single, calm checkmark draws in (stroke-path animation, ~300–400ms, no bounce, no confetti) accompanied by an amount and a reference ID, not by a celebratory animation. **Steal**: this register is exactly right for Bali Zero's "real thing, not a party" voice — a drawn checkmark, IDR amount, reference number, next-step text. **Avoid**: Duolingo/Robinhood-style confetti-burst success states — reads as consumer-app cheerfulness on a government-fee transaction and undercuts the "licensed professional" register the brief demands.
5. **Status advancing (all three, but especially post-payment tracking).** Step-tracker with the *current* step subtly breathing (a 2–3% opacity pulse, ~1.5s ease-in-out loop, `prefers-reduced-motion`-gated to a static state) so the page visibly communicates "still working" without a spinner anywhere. **Steal**: exactly matches the brief's "elegant and restful" language — motion as reassurance, not decoration. **Avoid**: pulsing every step simultaneously — only the active one should move, or the eye can't find what changed (this is the same "guide attention, don't decorate" principle Atlassian states directly in its motion foundations, verified above).

---

## 5. Restraint and reduced motion

### Finding 5.1 — The named example
`https://web.dev/articles/prefers-reduced-motion` — **VERIFIED-LIVE (fetched 2026-08-31)** — and The A11y Project, "Understanding Vestibular Disorders" — `https://www.a11yproject.com/posts/understanding-vestibular-disorders/` — **VERIFIED-LIVE (fetched 2026-08-31)**.

**The measurable rule.** Doing `prefers-reduced-motion` "properly" is not `* { animation: none !important; }`. The web.dev guidance draws a line between **decorative** motion to cut entirely — parallax scroll, auto-playing background video, scroll-triggered reveal animations, entrance "vibrate"/attention effects, app-launch-style zoom transitions — and **functional** feedback to keep, just de-intensified: loading indicators, form-validation responses, state-change confirmation. The A11y Project's specific triggers for vestibular symptoms: large-scale parallax, auto-play, anything that starts moving without the user's own action; its core mitigation, stated directly, is to **never auto-start** motion, to signal what a given action will trigger before it happens, and — when full removal would break a transition's function — to compress the duration toward the imperceptible (it cites 0.001s) rather than delete it outright, so a component that logically depends on a `transitionend` event doesn't silently break.

```css
@media (prefers-reduced-motion: reduce) {
  .parallax-hero, .scroll-reveal, .autoplay-video { animation: none; }
  * {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
```
Note the pattern: kill the decorative classes by name (so nothing tries to reference a removed keyframe), then compress everything else near-instant rather than deleting the transition property wholesale.

**What to steal.** On all three surfaces: the status-step breathing pulse (§4.5) and any card-entrance motion respect `prefers-reduced-motion` by collapsing to their end-state instantly; the payment checkmark-draw (§4.4) still *happens* under reduced motion (it's functional confirmation, not decoration) but at near-zero duration.

**What to avoid.** Treating `prefers-reduced-motion: reduce` as an edge case tested once and forgotten — it is not a niche accessibility toggle on this audience. A first-time visitor "often afraid of being scammed," on a slow connection, at night, is under real cognitive load even without a vestibular condition, and the same restraint that serves a vestibular-disorder user (less unsolicited motion, clear step-by-step confirmation, nothing that starts moving on its own) reads to an anxious buyer as *calm competence* rather than *accessibility compliance*. The design target and the accessibility target are, for this specific brief, close to the same target.

---

## 6. The fad

### Finding 6.1 — The named example
Nielsen Norman Group, "Scrolljacking 101" — `https://www.nngroup.com/articles/scrolljacking-101/` — **VERIFIED-LIVE (fetched 2026-08-31)**.

**The measurable rule.** Scrolljacking — hijacking the scrollwheel to change its speed/direction/meaning instead of moving the page normally — was tested directly by NN/g: most participants reported at least mild disorientation, task-oriented users abandoned pages outright, and the effect compounds on mobile (smaller viewport, longer effective scroll distance). NN/g's own dividing line, quoted: scrolljacking survives usability testing only when it has **functional value** — the cited surviving example is BBC's before/after image-reveal scroll, which progressively discloses information the reader actually needs. The named failing example in the same article, Therabody's brand-storytelling scrolljack, disoriented users while adding no information — pure aesthetic signaling.

**Why this is 2025–2026's exhausted convention specifically**: the same mechanism (`animation-timeline: scroll()`/`view()`, now that it's CSS-native and cheap to ship — §3.2) has made scroll-driven *everything* trivially easy to add, which is exactly why the fad version has proliferated on marketing sites this cycle — the barrier to entry dropped from "hire a WebGL engineer" to "one CSS property," and the technique got used because it's now easy, not because it serves the page.

**What to steal for Bali Zero.** The *durable* version of this same API: a reading-progress bar on the Oracle decision tree (§3.2), a single-property fade-in as a proof-strip stat scrolls into view — both disclose real information (how far through the flow you are; that a stat exists) without touching scroll speed or direction at all. The test for "durable vs. fad" on this exact API: **does removing it lose information, or only lose decoration?** A progress bar that vanishes removes the answer to "how much further"; a bouncing hero graphic that vanishes removes nothing.

**What to avoid.** Any full-viewport pinned/hijacked section on the home page or Oracle flow — even one — given this audience is explicitly "at night, on a slow phone, slightly anxious": disorientation is the one guaranteed effect NN/g measured, and disorientation is the opposite of what a scam-wary visitor needs to feel three questions into a decision tree that ends in a payment. The other 2025–2026 fad worth naming for the same reason: cursor-follow "gooey blob" cursors and magnetic-hover buttons — beautiful on a portfolio site with a mouse, meaningless on a 360px touchscreen with no cursor at all, i.e. inapplicable to 100% of this audience by construction, not merely inadvisable.

---

## What I could not verify

- **Material 3's exact duration/easing token table** (`short1 50ms` … `long4 600ms`, emphasized `cubic-bezier(0.2, 0, 0, 1)`) — the primary page (`m3.material.io/styles/motion/easing-and-duration/tokens-specs`) is client-rendered and returned only its title to three separate fetch attempts. The numbers above are corroborated across two independent live-search snippets of the same page, not independently page-fetched and quoted. Recommend a manual browser check before quoting these to Zero as load-bearing.
- **Apple HIG's specific animation-duration numbers** (0.2–0.5s / 200–300ms range) — both fetch attempts against `developer.apple.com/design/human-interface-guidelines/foundations/motion` returned only the page title; this is FROM-MEMORY and unconfirmed this session.
- **Shopify Polaris motion tokens** — could not locate a current, live-fetchable source; the `polaris.shopify.com/design/motion` URL now redirects to a generic app-surfaces index, and the `Shopify/polaris-tokens` GitHub repo's file layout did not match the expected `token-groups/motion.ts` path (repo appears to be a legacy/Ruby-gem-era structure, possibly superseded by the monorepo). Dropped from the report rather than guessed.
- **Named product examples in §4** (Stripe field-validation checkmark, Traveloka/Google-Flights price-settle, WhatsApp/Telegram upload ring, GoPay/QRIS confirmation checkmark) — these are well-documented, widely-cited patterns, but were not re-fetched live this session (WebSearch budget for the lane was exhausted; direct WebFetch attempts at `linear.app/method`, `stripe.com`'s payment-element docs, and Bank Indonesia's QRIS page either returned only tables of contents or 404s). Treat as directionally correct, spot-check before quoting a specific product's exact timing to a client.
- **GOV.UK Design System's loading-time guidance** — the expected URL (`gov.uk/service-manual/design/loading-times-and-loading-pages`) 404'd, and the current Design System's pattern index (fetched live) does not list a loading/progress pattern at all; either the guidance moved, was retired, or never existed as a named pattern. Not cited above as a result.
- **Baymard Institute's forms-validation-timing research**, referenced in passing in §4.1 — not fetched this session; the claim about premature inline-validation errors increasing abandonment is a well-known Baymard finding but should be re-verified with a direct citation before use in client-facing material.
