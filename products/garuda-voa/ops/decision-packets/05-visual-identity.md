# Owner decision 5 — visual identity

> Prepared for Zero. Pick one of three. No mockups — this is words, not pixels, because a
> rendered screen would be a design decision made ahead of the choice you're being asked to make.
> Costed against what already exists on disk, not against an imagined blank slate.

## What this is actually about

The funnel is four screens: four questions, a verdict (accept or decline), a passport-photo
upload, and a parcel-style tracker. It has to work for someone standing at an airport gate on
weak wifi, on a phone, possibly not reading English as a first language, deciding in under five
minutes whether to hand Bali Zero their money. The three concepts below are three different
answers to "what does that moment feel like", each with a real cost and a real thing it gives up.
None of them is a strawman for the other two — I can argue for each, and I say plainly which one
I'd pick and why.

## Ground: what already exists, so nothing here invents a fiction

**The brand constitution governs four surfaces, and this funnel is not the one it was written
for.** `~/.claude/skills/bali-zero-brand/constitution.md` is the enforced law for Instagram
carousels — 1080×1350 slides, hero photography, layout families. Article 12 says the constitution
also covers a `web-mouth` surface, but its own spec pointer (`packages/core/styles/bz-tokens.css`)
does not exist on disk — verified with `find`, zero hits. That stale pointer is copied a second
time in `.claude/rules/frontend-nextjs.md`. I did not fix either; both are outside this packet's
scope and I'm naming them so the next person doesn't spend time hunting a file that was never
there. What actually governs the web app, verified by reading the files: `packages/core/tokens/`
(three-layer primitives → semantic → theme cascade) plus `apps/mouth/src/app/globals.css`.

That leaves a real question about which constitution rules bind this product. Article 12.2 names
eight cross-surface mandatory rules that apply regardless of which surface pointer is stale:
palette (Art. 2), single type family (Art. 3), concrete numbers (6.3), verbatim regulatory
citations (6.4), untranslated bilingual lexicon (6.5), no hard-sell CTA (6.6), no emoji (6.7), and
spelling/acronym discipline (Art. 8). The carousel-specific articles — aspect ratio, hero image
counts, layout-family taxonomy, archetypes — do not apply; a funnel screen is not a slide.

**One rule I could not honor without breaking something else, and did not try to fix.** Article
2.2 bans green in any TEXT or UI zone, full stop. But the live token system
(`packages/core/tokens/semantic.css:59-66`) has already ruled the opposite for exactly the
element every DECLINE screen in this product needs: "Green is the WhatsApp channel accent (never
a primary)" — a named, comment-documented exception baked into the CTA color system before this
product existed. I'm not relitigating that fight here. All three concepts below keep the existing
WhatsApp-green-as-channel-accent convention untouched and do not introduce any _other_ green,
blue, or purple into UI chrome — that satisfies Article 2.2 everywhere this product actually
touches new surface, without picking a fight with a rule that predates it.

**The reusable component library is bigger than the mandate implied, and reuse is not
symmetric across the three concepts.** `packages/core/components/apps/` already has, read and
confirmed on disk: `AppFrame` (page shell, `data-funnel` scoping), `AppWizard` (the exact
four-question stepper — persisted resume, stacked-context preview, 44px minimum tap targets
already coded into `apps/mouth/src/app/visa/match/page.tsx:59-72`), `AppTrustStrip`,
`AppBranchSelector`, `AppWhatsAppCTA` (decline handoff, already wired for `context`/`utm`
payloads), `AppStampReveal` (an ink-stamp reveal animation built for the Visa Check result page —
serif italic code, red double border, `prefers-reduced-motion` handled), and
`AppResultTimeline` (a checkpoint list built for the Visa Clock result page — this is, almost
verbatim, the "parcel tracker" the mandate asks for). None of these were built for GARUDA VOA.
Whether a concept can adopt them as-is, adapt them, or has to write past them is the real cost
axis between the three — not "hours to build a screen from nothing", because nobody is starting
from nothing.

**The funnel's brand-red is not a free color to spend twice.** `data-funnel="visa"` resolves
`--accent-funnel` to `--color-red-500` (`packages/core/tokens/semantic.css:198-201`), and the CTA
system enforces "brand red is spent on exactly ONE conversion action per page" (semantic.css
comment, MYTHOS P2 decision). That single-primary-red rule is why an ACCEPT verdict screen and a
DECLINE verdict screen cannot simply be "the same card, green vs red" — red is already claimed as
the funnel's own identity color and as the one primary CTA per page. Each concept below has to
solve the accept/decline visual distinction WITHOUT a second red-adjacent hue, because introducing
one risks exactly the "which button is the real one" confusion the single-primary rule exists to
prevent.

---

## Concept A — "The Stamp"

**Feel.** The oldest travel-document metaphor there is: an inspector's ink stamp on a passport
page. ACCEPT is a stamp pressed down — the existing `AppStampReveal` ink-press animation, code in
serif italic, red double border, -4° rotation. DECLINE is the same card shape with no ink: a flat
grey outline where a stamp would go, the shape of an absence rather than a red X. The tracker is a
row of stamps accumulating left to right — Received, In review, Submitted, Approved, Delivered —
each one pressing down as staff advance the practice, which is almost exactly what
`AppResultTimeline` already renders for Visa Clock.

**The four screens.**

- _Questions_: `AppWizard` unmodified. No visual change from what `/visa/match` already ships.
- _Verdict — accept_: `AppStampReveal` given the price and deadline as its "code" field instead
  of a visa type code. One red conversion CTA below it (single-primary-red rule, satisfied by
  construction — the stamp itself is red-bordered chrome, not a button, so it doesn't compete).
- _Verdict — decline_: an un-inked version of the same card — same border weight, same rotation
  geometry, no red, grey outline only — followed immediately by the alternative + WhatsApp
  handoff on the SAME screen, not a second click away. The empty-stamp shape has to be built new;
  nothing in the library renders "the negative space of a stamp."
- _Upload_: no existing component. New build: a camera-first upload card with the three
  documented states from the journeys (`UNREADABLE_DOCUMENT`, low-confidence field-by-field
  confirmation, clean pass) — none of these exist as a component today.
- _Tracker_: `AppResultTimeline` reskinned as a stamp row instead of a checkpoint list. Close
  reuse — the data shape (`label`, `at`, `title`, `body`, `past`) already matches a 5-stage
  practice tracker almost exactly.

**Cost.** Lowest new-build surface of the three: two components adopted near-verbatim
(`AppStampReveal`, `AppResultTimeline`), one adapted (the un-inked decline card), one built from
nothing (upload). L6's lane is genuinely small here.

**What it gives up.** The stamp metaphor is inherently about _authority granting passage_ — and
this product's own state machine is explicit that the preliminary verdict "does not represent or
promise authority approval" (`happy-path.feature`). A stamp reads as official in exactly the place
the product needs to under-promise. It also does the ink-press animation no favors on a decline —
an "un-inked" card is a real design idea but it is untested; nobody has built or looked at one, and
"the shape of an absence" might just read as "broken" on a small phone screen the first time
someone sees it.

**Accessibility.** The red double-border on `AppStampReveal` was built against a black/antracite
background for the Visa Check result page — contrast there is UNCONFIRMED for this product's
context (I did not run a contrast checker; the component's own tokens are the same ones already
in production use, but I have not measured this exact pairing). The rotation (-4°) is decorative,
not load-bearing text, and the component already respects `prefers-reduced-motion` per its own
doc comment. Tap targets: the CTA below the stamp inherits whatever button component carries it
forward — not yet decided by this concept, so the 44px floor is not yet proven here. The
un-inked decline card is new and carries no accessibility history at all.

---

## Concept B — "The Ledger"

**Feel.** Less "you're at the airport", more "you're being handled by someone precise." Numbers
lead. Every fact — price, deadline, decline reason, tracker stage — renders as a labeled data row
in mono numerals, the same visual grammar `FactBadge`, `DeadlineBadge`, `Money`, and `StatChips`
already use across the operator-facing `kita`/`my` surfaces. The accept and decline verdicts are
NOT differentiated by color at all — they're differentiated by which rows are present: an accept
page shows price + deadline + one CTA; a decline page shows the decline reason as a labeled row
plus the alternative as another labeled row plus the WhatsApp handoff. This is the "trust through
precision, not trust through theater" answer.

**The four screens.**

- _Questions_: `AppWizard`, with each answered step re-rendered afterward as a `StatChips` row
  instead of the current free-text "stacked context" summary — a genuine visual change to an
  existing, shipping component, not just a new screen.
- _Verdict — accept_: `Money` for the price, `DeadlineBadge` for the filing window, `FactBadge`
  for "all-inclusive, no PNBP split" (Article 6.3/6.4 discipline literally built into the ledger
  format — a number without a citation looks visibly incomplete in this design, which is a
  feature, not a decoration).
  Read together with the earlier freshness finding (`GROUND.md`/`owner_decisions id:7`): if the
  catalogue's freshness stamp is what makes a number sellable at all, a design that visibly
  starves without a citation is the one concept here that makes a stale price _look_ wrong before
  a human has to notice it.
- _Verdict — decline_: the decline reason is a labeled row (customer-safe copy, not the staff
  reason code — that boundary from `uncertain-ocr.feature` holds regardless of concept), the
  alternative product is a second row, WhatsApp handoff is `AppWhatsAppCTA` styled as a third row
  rather than a button — consistent with the "everything is a row" grammar, but this is the
  concept most likely to make an emotionally difficult moment (you were told no) feel
  administratively cold. A ledger is a strange place to be comforted.
- _Upload_: new build, same as Concept A — nothing existing covers document capture. In this
  register it would read as a form field with a confidence percentage next to each extracted
  value, which is more literally honest about what OCR confidence means than either other concept,
  and also the most exposed to looking like an internal QA tool rather than a consumer product.
- _Tracker_: five `StatChips` in sequence with a fill state, not `AppResultTimeline`'s narrative
  checkpoint copy — a genuinely different data shape, so this is the concept that does NOT reuse
  the closest existing match.

**Cost.** Highest reuse of _individual atoms_ (four separate existing components: `FactBadge`,
`DeadlineBadge`, `Money`, `StatChips`) but the LOWEST reuse of anything shaped like a whole screen
— none of those four were built to compose into a verdict page or a tracker, so assembling them
into these four screens is closer to a new layout than an adaptation. Also the only concept that
pulls in `packages/core`'s `crystal-stat-card` / glass-panel visual family
(`apps/mouth/src/app/globals.css:906-921`), which uses `backdrop-filter: blur()` — a real,
measurable rendering cost on the lower-end Android phones this exact audience is more likely to be
holding at a gate, on the weak wifi the mandate itself calls out. Blur cost is a GPU/paint cost,
not a network cost, so "weak wifi" doesn't make it worse directly — but a five-year-old phone
compositing several blurred panels at once is a real, documented class of jank, and I have not
benchmarked it on this component.

**What it gives up.** Warmth. This is the concept for someone who wants to feel _processed
correctly_, not _taken care of_. For a first-time buyer nervous about a visa refusal, "administrative
precision" is not obviously the more reassuring register than "someone stamped my document."

**Accessibility.** `crystal-stat-card`'s light-theme rewrite (`globals.css:573-585`) exists and is
WCAG-considered per its own comments, but that pass covers the `operative-light` product theme
(kita/my), not a `data-funnel="visa"` public page — UNCONFIRMED whether the same override reaches
this surface. Mono numerals at small sizes are the one typographic risk unique to this concept:
`FactBadge`/`Money`/`StatChips` were sized for dashboard density, not a phone held at arm's length
in daylight; font-size for this context is undecided and unverified.

---

## Concept C — "The Single Card"

**Feel.** One full-viewport card at a time, nothing else. No ambient background video (the kind
`/visa/page.tsx:29-56` layers behind the branch selector today, 12%-opacity screen-blend), no
glass, no gradient scrims, no `crystal-stat-card` blur. Flat surface, one accent flash of color per
state, huge type. The visual reference this is closest to, without borrowing its brand, is a
boarding-pass wallet card or a single-screen payment checkout: content and nothing else. This is
the concept built for the constraint stated hardest in the mandate — a phone, on weak wifi,
someone who is not necessarily comfortable reading English paragraphs.

**The four screens.**

- _Questions_: `AppWizard`, but with every optional visual flourish stripped at the CSS layer —
  no ambient backdrop, no hero-gradient, the plainest possible rendering of a component that
  already supports this because none of its visual chrome is hardcoded into the component itself
  (`AppWizard.tsx` renders bare structure; the surrounding page supplies the atmosphere). This is
  the one concept where "strip it down" is mostly a page-level CSS decision, not a component
  rewrite.
- _Verdict — accept_: one card — price, deadline, one CTA, nothing rotated, nothing animated
  beyond a plain fade-in. No `AppStampReveal`, no ledger rows — those are both adaptations of
  richer existing pieces, and this concept's whole point is declining to use them.
  Consequence: the verdict page ships without the shipped inventory of visual assets the other two
  concepts get for free.
- _Verdict — decline_: identical card shape and weight to accept — same size, same position —
  differentiated only by a single word state ("Not yet eligible") and a muted, non-accent border.
  No un-inked stamp, no extra rows: the alternative and the WhatsApp CTA sit directly below as
  plain text and one button. This is the concept where accept and decline look most alike at a
  glance, which is either the calmest way to deliver bad news or the easiest way for someone
  scrolling fast to misread a decline as a pass — untested either way.
- _Upload_: new build regardless of concept (true for all three), but here it is the cheapest of
  the three to render — a native `<input type="file" capture="environment">` styled as one big
  tap target, no live camera-frame chrome, no preview card treatment. Least visual richness, least
  asset weight, least new CSS.
- _Tracker_: five flat rows, current stage bold, everything else at reduced opacity — closer to a
  plain `<ol>` than to `AppResultTimeline`'s two-column checkpoint layout. Structurally the
  simplest of the three tracker designs, and also the one that communicates the LEAST texture per
  stage (no body copy per checkpoint the way `AppResultTimeline` carries today).

**Cost.** Least reuse of purpose-built app components (skips `AppStampReveal`, `FactBadge`,
`DeadlineBadge`, `StatChips`, `crystal-stat-card` entirely) but also the least NEW code, because
"strip the chrome" is subtraction, not construction — most of what this concept needs is CSS
deletions on top of `AppFrame`/`AppWizard` as they already ship, plus one new upload input and one
new plain tracker list. Fastest to build; also the concept with the fewest existing decisions made
for it, meaning more small typographic/spacing judgment calls land on L6 rather than being
inherited from a component that already made them.

**What it gives up.** Distinctiveness. Every other surface on balizero.com — `kita`, `my`, the
editorial "Rumah Putih" pages, even `/visa` and `/visa/match` today — carries the liquid-glass,
gradient, ambient-video visual language documented across `globals.css`. A funnel this stripped
would be recognizably Bali Zero only through logo and copy, not through its surface treatment.
That is a real brand-consistency cost, not a hypothetical one — it's the one concept a returning
`kita`/`my` user might not immediately place as the same company.

**Accessibility.** This is structurally the strongest of the three, and that is not a coincidence
— it is the direct consequence of having the least chrome for something to hide behind. Flat
surfaces with one accent color are the easiest of the three to hold to a measured contrast ratio
because there is no blur, no gradient-over-photo text, and no glass translucency diluting the
background a text color sits on. Tap targets are the simplest case to hit 44px minimum
consistently because there is nothing else on the card competing for space. I have not run an
actual contrast checker against a real palette for any of the three concepts — that claim is about
relative structural risk, not a measured number, and it stays UNCONFIRMED like the other two until
someone builds and measures it.

---

## Comparison, honestly

|                     | Reuse (whole screens)                        | New build for L6                       | Feel                         | Biggest risk                                            |
| ------------------- | -------------------------------------------- | -------------------------------------- | ---------------------------- | ------------------------------------------------------- |
| A — The Stamp       | High (2 of 4 screens near-verbatim)          | Smallest                               | Travel-document warmth       | Over-promises authority; un-inked decline untested      |
| B — The Ledger      | Low (atoms reused, screens not)              | Largest, plus blur-perf risk           | Administrative precision     | Cold on the one screen (decline) that needs warmth most |
| C — The Single Card | Lowest (skips most purpose-built components) | Smallest, but least inherited judgment | Utility, checkout-grade calm | Breaks visual continuity with the rest of balizero.com  |

**If I had to pick: Concept A, The Stamp.** It is the only one of the three that turns an
existing, already-shipped, already-accessible-reviewed component (`AppStampReveal`,
built and tested for Visa Check) into the emotional center of the accept screen, and reuses
`AppResultTimeline`'s exact data shape for the tracker almost without modification — meaning two
of the four screens carry forward whatever accessibility and cross-browser testing already
happened for Visa Clock and Visa Check, rather than starting cold. Its real risk — over-promising
official authority — is a copy problem I believe is solvable with one line under the stamp
("preliminary check, not a government approval") rather than a structural one, and the state
machine already requires that disclaimer to exist somewhere on the accept screen regardless of
which concept ships. The un-inked decline card is the one genuinely unbuilt, unverified piece of
this concept, and it should be the first thing L6 builds and puts in front of a real phone before
anything else, precisely because it's the one novel visual idea in an otherwise low-novelty
choice.

## What I found but did not fix

- The `web-mouth` surface pointer in `~/.claude/skills/bali-zero-brand/constitution.md` Article
  12.1 (`packages/core/styles/bz-tokens.css`) does not exist. The same wrong path is repeated in
  `.claude/rules/frontend-nextjs.md`. Both are stale references to a file that appears to have
  been renamed/restructured into `packages/core/tokens/` at some point without the pointers being
  updated. Out of scope here (I was told not to touch anything outside this packet), but worth a
  one-line fix commit from whoever owns those two files next.
- Article 2.2's blanket ban on green in UI zones is already, quietly, not the operative rule for
  WhatsApp CTAs — `packages/core/tokens/semantic.css` documents the exception in a comment but the
  constitution itself has never been amended to say so. Not a GARUDA VOA problem to fix, but the
  next brand-constitution audit should reconcile the two documents rather than let the code be the
  only place the real rule lives.

## Your gesture

Pick one:

- [ ] Concept A — The Stamp (recommended)
- [ ] Concept B — The Ledger
- [ ] Concept C — The Single Card
- [ ] None of these — say what's missing and I'll draft a fourth
