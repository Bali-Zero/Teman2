# Visa Check — UI/UX Design Spec

**Date**: 2026-04-20
**Author**: Claude Opus 4.7 (with Antonello Siano)
**Status**: Design approved — ready for implementation plan
**Scope**: Redesign of the 5 pages under `apps/mouth/src/app/visa/` shipped on 2026-04-20 (commit `0f8d653fa` + follow-ups `e1e964469`, `466b57cd8`, `dc83c8432`) from barebone-inline-CSS to production UI.

## Why this exists

The Visa Check app is the first of 4 homepage apps replacing the decorative `FunnelFeature.tsx` sections. Backend and logic are live and validated E2E in production (see MATCH/CLOCK/LEAD curl results in session transcript). The UI currently ships as inline-CSS functional-only — adequate for verification, unacceptable for the CRO target.

**The CRO signal**: the website funnel currently produces **2 leads / 90 days** vs **420 from WhatsApp** (audit `docs/cro/2026-04-19-funnel-audit.md`). The app's reason to exist is to bring website leads from 2 to a meaningful multiple. A "functional but generic" UI does not accomplish that; the UI has to do three jobs:

1. **Hero** — earn trust in <3 seconds for a cold ads/organic visitor
2. **Wizard/Form** — sustain completion through 4 steps without abandonment
3. **Result** — make the WhatsApp CTA the obvious next action, not an afterthought

## Design context

**Existing design system (mandatory coherence)**: `/visa` runs under the `editorial` theme — same as `balizero.com`, `/kbli`, `/tax`. Five observed invariants of the "Bali Zero look":

1. Navy premium gradient base (`#24406e → #1a3258`) + high-contrast white text
2. Funnel-scoped accent (rosso `#ff3344` on CTA/badge/progress) — nowhere else
3. Thin translucent borders (`rgba(255,255,255, 0.06-0.12)`)
4. Typography: Cormorant (serif display, Georgia fallback) + Inter (sans body), tight letterspacing, line-height conservative
5. Sparse motion (250ms ease-out cubic-bezier), subtle raised surfaces

Current barebone UI uses `--bz-accent: #d4845a` (copper) — wrong for the `editorial` theme, needs to map to `--accent-funnel` red.

## Direction chosen (hybrid)

- **~90% Editorial premium** — form-heavy, conversion-optimized, consulting-brief tone
- **1 single WOW moment** — cinematic typography hero with ambient video loop at 12% opacity (not video-first; typography is the figure, video is the ground)

Rationale (after multi-LLM brainstorm — 4 voices converged away from video-dominant):

- Mobile 4G performance budget (target market includes rural Bali signal)
- `editorial` theme coherence (sister pages `/kbli`, `/tax` must not feel disjointed)
- Brand position (investor/expat decision-maker, not Gen-Z leisure traveler)
- Trust compounds through restraint; visual hierarchy should reinforce "we write precise documents", not "we perform".

## 5-page breakdown

### 1. Hero entry page — `/visa`

**Purpose**: branch selector ("already in Indonesia" Y/N) + trust establishment in <3s.

**Layout (mobile-first, single column)**:

```
┌─────────────────────────────────┐
│  [● Ambient · Bali]             │  ← tiny live-marker top-right, pulsing red dot
│                                 │
│  BALI ZERO · VISA CHECK         │  ← 0.65rem, opacity 0.55, letter-spacing 0.25em
│                                 │
│  24 visa                        │  ← Cormorant serif, 2.6rem line-height 0.95
│  types.                         │
│  ┌─────┐                        │  ← "One" huge block: 4rem, letter-spacing -0.05em
│  │ One │                        │
│  └─────┘                        │
│  fits you.                      │
│                                 │
│  We know which.                 │  ← subtitle 0.78rem opacity 0.55
│                                 │
│  ┌─────────────────────────┐    │
│  │ I'm ALREADY in       →  │    │  ← branch card, full width, 56px min height
│  │ Indonesia               │    │
│  └─────────────────────────┘    │
│  ┌─────────────────────────┐    │
│  │ I'm PLANNING to      →  │    │
│  │ arrive                  │    │
│  └─────────────────────────┘    │
│                                 │
└─────────────────────────────────┘
```

**Ambient video** (the one WOW moment):

- 15-second silent loop, slow-motion b-roll of Bali (rice terraces, Ulun Danu at dawn, stone temple details — no faces, no tourism clichés)
- h.264 MP4, 1.8MB max, 720p
- CSS: `mix-blend-mode: screen`, `opacity: 0.12`, `filter: hue-rotate(200deg) brightness(0.7) contrast(1.4)` (desaturates to navy monochrome)
- Poster JPG 40KB loaded inline; video `<video preload="none">` lazy-loaded after LCP
- `<video muted autoplay loop playsinline>` + `prefers-reduced-motion: reduce → display: none` fallback to poster only
- **Important**: the video is NOT figure. Typography is figure, video is ground. If you removed the video, the page should still feel alive.

**Trust strip** (optional, below the fold): 3 concrete numbers — "5,021 visas filed since 2019 · 24+ visa categories supported · 4.8h average first-reply on WhatsApp"

**Interaction**:

- Click either branch card → route transition 250ms fade + slide 8px, navigate to `/visa/clock` or `/visa/match`
- Haptic `navigator.vibrate(8)` on card tap (iOS15.4+ supports web vibrate; graceful no-op elsewhere)

### 2. Clock form — `/visa/clock`

**Purpose**: collect visa type + entry date from a user already in Indonesia.

**Layout — "Sentence builder" editorial pattern** (approved choice 1b):

```
┌─────────────────────────────────┐
│ ← back                   1 of 1 │
│                                 │
│  Your timeline in               │
│  five checkpoints.              │  ← Cormorant 2rem, h1
│                                 │
│  Fill in the two blanks.        │  ← Inter 0.9rem opacity 0.6
│                                 │
│  I entered on                   │  ← Inter 1.2rem body
│  ┌──────────────┐               │
│  │ Date picker  │               │  ← inline, native <input type=date>
│  └──────────────┘               │
│  with a                         │
│  ┌──────────────┐               │
│  │ E33G     ▼   │               │  ← inline select, visa type
│  └──────────────┘               │
│  visa.                          │
│                                 │
│  ┌─────────────────────────┐    │
│  │ Show my timeline     →  │    │  ← sticky bottom, red CTA
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

**Notes**:

- Sentence is a single grammatically-flowing phrase: "I entered on [date] with a [visa] visa."
- Both inputs are inline in the phrase, not stacked in a generic form
- Placeholder shows the expected shape ("dd mmm yyyy", "pick one")
- Mobile: both fields stack vertically with the connecting words still visible
- Error state: non-errored words fade to 40% opacity, the errored field gets a 1px red border and a tiny red footnote below (no popup)

### 3. Match wizard — `/visa/match`

**Purpose**: 4-step diagnostic wizard (Nationality → Purpose → Duration → Budget) with premium consulting feel.

**Layout per step — "Stacked Context" pattern** (approved choice 1A):

```
┌─────────────────────────────────┐
│ ▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░  │  ← Hairline 2px red, 25% fill for step 1
│                                 │
│  ← back                  2 of 4 │  ← tiny-caps label
│                                 │
│  ─ Italian                      │  ← previous step, opacity 0.25, dashed-bottom
│                                 │
│  Why are you                    │  ← current question, Cormorant 1.3rem
│  coming?                        │
│                                 │
│  ○ Work remotely (foreign       │  ← chip list, 7 options
│    employer)                    │
│  ● Invest / open PT PMA         │  ← selected: red border, subtle bg
│  ○ Hired by Indonesian company  │
│  ○ Join family                  │
│  ○ Long tourism / explore       │
│  ○ Retirement (55+)             │
│  ○ Student at Indonesian uni    │
│  ○ Something else / not sure    │
│                                 │
│  ─ Duration ↓                   │  ← next step peek, opacity 0.2, dashed-top
│                                 │
│  ┌─────────────────────────┐    │
│  │ Next                 →  │    │  ← sticky bottom
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

**Stacked Context mechanics**:

- Step N-1 renders as a single line ("— Italian" or "— Investor") at opacity 0.25 above the current question, separated by a dashed bottom border
- Step N+1 renders as a single line teaser ("— Duration ↓") at opacity 0.2 below the answer options, separated by a dashed top border
- As the wizard advances, the stack grows: at step 3 the user sees "— Italian · — Investor" above and "— Budget ↓" below
- This creates a "memo being drafted" feeling — memory + anticipation + focus on current

**4-step content**:

1. **Nationality** — dropdown with ISO-3 codes, autocomplete top 10 countries (USA, GBR, ITA, DEU, FRA, AUS, CAN, NLD, SGP, "Other — I'll tell you")
2. **Purpose** — 8 chip options (listed above)
3. **Duration** — range slider 1-60 months, current value in label: "6 months"
4. **Budget band** — 3 chip options: "Under IDR 50M", "IDR 50M–500M", "Over IDR 500M"

**Progress bar**: 2px hairline at top, `background: #ff3344`, width = `(currentStep / totalSteps) * 100%`, transition `width 220ms ease-out`. Above hero-level z-index so visible during step transitions.

**Step transition motion**:

- Exit: current step fades to 0 + slides left 20px (cubic-bezier 0.25, 0.46, 0.45, 0.94, duration 220ms)
- Enter: new step from right 20px + fade from 0 to 1 (same curve, 250ms, delay 80ms)
- Net effect: slides feel continuous but not gimmicky

**localStorage persistence**: existing `bz.visa_match.wizard` key already persists for 1h — keep.

**Error states**: if user hits Next without selecting, the options list jiggles 4px left-right once (2 × 150ms), unselected options stay, selected border pulses rose. No modal.

**Haptic**: `navigator.vibrate(6)` on each successful Next, `navigator.vibrate([20, 30, 20])` (pulse) on final submit.

### 4. Post-submit — honest spinner

**Purpose**: cover the <500ms API latency without false ceremony.

**Layout**:

```
┌─────────────────────────────────┐
│                                 │
│                                 │
│           ◐  ← spinner 24px     │
│                                 │
│        One moment…              │
│                                 │
│                                 │
└─────────────────────────────────┘
```

- 24px circular spinner, 2px border with red top, 800ms rotation
- Text "One moment…" in Inter 0.95rem opacity 0.6
- **Rejected**: 5-8s fake AI loading ("Reading 24 visa types…", checkmarks appearing) — the 2026 Gemini-trends pattern — because it compromises brand honesty for a trust bump that's not ours to take. Our API really does respond in <500ms; the spinner is honest.
- Auto-dismisses as soon as response arrives. User rarely sees it more than 300ms.

### 5. Result page — `/visa/match/[hash]` + `/visa/clock/[hash]`

**Purpose**: make "your visa is E33G" a memorable reveal that flows into the WhatsApp CTA.

**Layout — "Stamp + scrollable memo"** (approved choices 4B + 2b):

**Above the fold** (first viewport):

```
┌─────────────────────────────────┐
│ ← back                          │
│                                 │
│  YOUR VISA                      │  ← tiny-caps, opacity 0.5, 0.65rem
│                                 │
│     ┌─────────┐                 │
│     │  E33G   │   ← stamp       │  ← Cormorant italic, 2.2rem, red border
│     └─────────┘   rotated -4°   │  ← "ink press" anim: scale 1.15→1 in 200ms
│                                 │  ← red outer glow subtle (box-shadow)
│                                 │
│  Digital Nomad /                │  ← Cormorant 1.3rem, full name
│  Remote Worker KITAS            │
│                                 │
│  Valid 1 year, renewable once   │  ← Inter 0.9rem opacity 0.75, 1-line summary
│                                 │
│  scroll ↓ for details           │  ← tiny-caps opacity 0.4, animated downward pulse
└─────────────────────────────────┘
```

**Stamp "ink press" animation** (200ms, one-shot on mount):

- Initial: `transform: rotate(-4deg) scale(1.15); opacity: 0;`
- Final: `transform: rotate(-4deg) scale(1); opacity: 1;`
- Curve: `cubic-bezier(0.5, 0, 0.3, 1.2)` — slight overshoot for "thump" feel
- Accompanied by a single `navigator.vibrate(12)` haptic (iOS)
- Respect `prefers-reduced-motion`: static, no scale, instant fade-in

**Scrollable memo below** (continuous scroll, no tabs):

```
│ ─────────────────────────────   │
│ WHY IT FITS                     │  ← tiny-caps section header
│                                 │
│ E33G covers remote work for a   │  ← Inter 1.05rem, reason narrative,
│ foreign employer from Indonesia.│     ~2-3 sentences X_BRAND_VOICE
│ Valid one year, renewable once. │
│ ─────────────────────────────   │
│ ESTIMATED COST                  │
│                                 │
│ IDR 15,000,000                  │  ← Cormorant 2rem red, big number
│ Bali Zero fee. Gov fees billed  │  ← Inter 0.8rem opacity 0.6 disclaimer
│ at cost.                        │
│                                 │
│ (or "Let's confirm on WhatsApp" │  ← if cost=null graceful fallback
│  if PricingTool didn't match)   │
│ ─────────────────────────────   │
│ PRE-ARRIVAL CHECKLIST           │
│                                 │
│ 1. Proof of remote employment…  │  ← Inter 0.95rem, ol list
│ 2. Bank statement ≥ USD 60K…    │
│ 3. Passport valid ≥ 18 months   │
│ 4. Health insurance…            │
│ 5. CV + LinkedIn URL            │
│ ─────────────────────────────   │
│ ALTERNATIVES                    │  ← only shown if result.alternatives.length
│                                 │
│ If your case changes: B211A.    │
│ Ask us on WhatsApp for tradeoff.│
│ ─────────────────────────────   │
│                                 │
│ [STICKY BOTTOM SHEET]           │
│ ┌─────────────────────────┐    │
│ │ Start the E33G          │    │  ← CTA WA, sticky bottom, full width
│ │ application         →   │    │
│ └─────────────────────────┘    │
└─────────────────────────────────┘
```

**Sticky CTA logic**:

- Starts rendered inline at page bottom
- Once user scrolls past the stamp (IntersectionObserver), CTA becomes sticky bottom
- Shadow appears above sticky CTA to indicate it's floating
- Label adapts: above stamp "Start on WhatsApp →"; below stamp "Start the E33G application →" (more specific as user has read context)

**Clock variant** (`/visa/clock/[hash]`):

- Stamp shows the visa code entered (e.g. "E33G" or "C1")
- Sub-line: "Expires [date] — X days from today"
- Memo sections: [TIMELINE] with 5 checkpoints as vertical list (D-60/30/14/7/1 with dates + todo body) → [EMAIL OPT-IN] inline form → [WHATSAPP CTA]

**Share bar** (below memo, inline not sticky):

- "Copy link · Twitter · Email" in Inter 0.8rem
- Copy confirms "Copied ✓" for 1500ms, haptic `navigator.vibrate(4)`

## Motion invariants (enforced across all pages)

1. **Duration**: 250ms default, 200ms for red accent elements (subcognitive urgency), 400ms only for one-shot entry animations (e.g. stamp ink press)
2. **Curve**: `cubic-bezier(0.25, 0.46, 0.45, 0.94)` default ("editorial weight"), `cubic-bezier(0.5, 0, 0.3, 1.2)` for one-shot reveals (stamp)
3. **Never animate**: form fields while user types, content that the user is reading (no parallax during wizard)
4. **Always animate**: state transitions, reveals of user-triggered results, progress bar fill
5. **`prefers-reduced-motion: reduce`**: respected everywhere — animations become instant state swaps, video hero hides (poster only), stamp fades without scale

## Mobile-first specifics

- All tap targets ≥ 44×44 CSS px (Apple HIG)
- Sticky bottom CTA with `env(safe-area-inset-bottom)` padding for iPhone with home indicator
- `@media (max-width: 480px)`: hero title 2rem instead of 2.6rem, wizard chips single-column
- Viewport meta: `width=device-width, initial-scale=1, viewport-fit=cover`
- Haptic feedback at 3 critical moments:
  1. Branch selection in hero (`navigator.vibrate(8)`)
  2. Each wizard Next click (`navigator.vibrate(6)`)
  3. Stamp reveal on result page (`navigator.vibrate(12)`)
- Share actions use Web Share API if available: `navigator.share({ url, title })` → fallback to copy+social links
- `<input type="date">` on mobile triggers native picker

## Design tokens to add/fix

In `packages/core/tokens/themes/editorial.css` (or equivalent):

```css
/* Accent — map --bz-accent (copper) to --accent-funnel (red) for /visa scope */
[data-funnel="visa"] {
  --bz-accent: var(--accent-funnel-red, #ff3344);
}

/* Missing tokens currently used by apps/ components */
--color-text-muted: var(--text-secondary, rgba(255, 255, 255, 0.68));
--color-border-subtle: rgba(255, 255, 255, 0.08);
--color-error: var(--state-danger, #ff5a5a);
--surface-raised: rgba(255, 255, 255, 0.04);
--surface-base: linear-gradient(180deg, #24406e 0%, #1a3258 100%);

/* Motion tokens */
--motion-duration-fast: 200ms;
--motion-duration-base: 250ms;
--motion-duration-slow: 400ms;
--motion-curve-editorial: cubic-bezier(0.25, 0.46, 0.45, 0.94);
--motion-curve-reveal: cubic-bezier(0.5, 0, 0.3, 1.2);
```

**Breaking change**: all 9 `packages/core/components/apps/*.tsx` currently reference `--bz-accent` directly and several use `--color-text-muted` / `--color-border-subtle` / `--color-error` as if they existed. They work today thanks to the inline fallback `var(--bz-accent, #d4845a)`, but the fallback is copper — wrong color. The implementation plan needs to add the missing tokens first, then update the 9 components to use them without hardcoded fallbacks.

## Components to create/modify

**New** (2):

- `packages/core/components/apps/AppStampReveal.tsx` — stamp component with ink-press animation, takes `{ code: string, type?: 'rotate' | 'flat' }`
- `packages/core/components/apps/AppSentenceBuilder.tsx` — inline-fields-in-phrase pattern for Clock form, takes `{ template: string, fields: Record<string, ReactNode> }`

**Modify** (9 existing, style + tokens only):

- `AppFrame.tsx` — apply navy gradient to `background`, not white `var(--surface-base)`
- `AppBranchSelector.tsx` — replace copper accents with red, adjust card padding for sticky CTA
- `AppHeroForm.tsx` — only used by Clock; replace button copper → red, accept `sentenceTemplate` prop as alternative mode
- `AppWizard.tsx` — implement "Stacked Context" (prev step peek above, next step peek below), hairline progress (replace current 6px bar), new transition motion
- `AppResultTimeline.tsx` — used by Clock only; colors to match new tokens
- `AppWhatsAppCTA.tsx` — sticky bottom + IntersectionObserver for label adapt
- `AppShareBar.tsx` — haptic on copy, minor spacing
- `AppTrustStrip.tsx` — no logic change, token cleanup
- `AppEmailOptIn.tsx` — token cleanup, Clock result only

**Frontend pages** (5, structural + styling):

- `apps/mouth/src/app/visa/page.tsx` — add ambient video + new copy
- `apps/mouth/src/app/visa/clock/page.tsx` — switch from `AppHeroForm` generic to sentence-builder mode
- `apps/mouth/src/app/visa/clock/[hash]/page.tsx` — add stamp + scrollable memo + sticky CTA
- `apps/mouth/src/app/visa/match/page.tsx` — stacked-context wizard variant
- `apps/mouth/src/app/visa/match/[hash]/page.tsx` — same stamp + memo + sticky CTA

**Assets** (new):

- `apps/mouth/public/video/bali-ambient-loop.mp4` — 15s, 1.8MB, h.264
- `apps/mouth/public/video/bali-ambient-poster.jpg` — 40KB, matches video first frame
- (both to be sourced/edited separately — not in code scope)

## Non-goals

- No 3D / R3F / WebGL scene. Rejected.
- No "bento grid" homepage reshuffling (that's a separate spec for balizero.com v3)
- No AI-personalized hero copy per user (expensive, low value, LLM unnecessary here)
- No light-mode variant (the `editorial` theme is dark-only by design)
- No i18n here — copy is English; Italian handled later at the funnel edge
- No fake "AI is thinking…" 5-8s loading — honest spinner only

## Open questions (to answer in plan phase)

- Video asset sourcing: existing B-roll in Bali Zero archive, or licensed stock (Pond5, Envato)? Budget + rights check needed.
- A/B testing: is there a GA4 experiment framework in place for hero copy variants (`24 visa types / One fits you` vs `Your time in Bali is measured in days`)?
- Analytics events: the existing `useFunnelApp` hook covers the 12 events from the backend shipped earlier; confirm no new event types needed for the redesigned flows.

## Success criteria

Unchanged from the app's own backend acceptance criteria (in `docs/plans/2026-04-19-4apps/01-visa-check.md`), but adding UI-specific:

- [ ] Lighthouse mobile Performance ≥ 90 on `/visa` (with video loading)
- [ ] Largest Contentful Paint (LCP) < 1.5s (hero typography, not video)
- [ ] Cumulative Layout Shift (CLS) < 0.02
- [ ] Hero video loads after LCP (lazy, not blocking)
- [ ] `prefers-reduced-motion: reduce` respected — no motion, video hidden
- [ ] Wizard abandon rate drops below pre-redesign baseline once measured
- [ ] Stamp reveal renders at 60fps on iPhone 11 (A13) minimum
- [ ] All 9 existing shared components pass Vitest snapshot tests after token update

## Appendix A — Multi-LLM brainstorm summary

4 voices consulted (Gemini 3.1 Pro, Codex 5.4, DeepSeek R1, Gemini grounded trends search) — full outputs archived at `.superpowers/brainstorm/llm-voices-visa-ui/`. Convergence summary:

- **3 of 4 voices** recommended editorial/typographic WOW over video-first or 3D-first hero
- **All 4 voices** recommended: no motion during form input, sticky CTA mobile, progress bar, haptic on key moments
- **Divergence on reveal**: Gemini preferred italic+glow, Codex preferred stamp, DeepSeek preferred typewriter. Stamp chosen for iconographic match to visa/immigration.
- **Divergence on loading**: Gemini Trends research recommended 5-8s fake AI loading (+3x perceived trust in 2026 reports). Rejected on brand-honesty grounds.

Gemini grounded search identified 4 macro-trends for 2026 funnel UIs: (1) Asymmetric Bento Grids, (2) Variable Typography reacting to scroll, (3) Liquid Glass UI, (4) Quiz Diagnostic engines with pseudo-clinical result pages. This spec adopts (2) and (4) selectively (stacked-context for diagnostic feel, tight editorial typography), rejects (1) and (3) as misaligned with Bali Zero's consulting-formal voice.

## Appendix B — Related docs

- Backend app spec: `docs/plans/2026-04-19-4apps/01-visa-check.md`
- CRO audit (problem statement): `docs/cro/2026-04-19-funnel-audit.md`
- Brand voice: `docs/X_BRAND_VOICE.md`
- Frontend design system baseline mapping: recorded in this session's transcript (not yet extracted to a standalone doc)
- Shipped backend commits: `0f8d653fa` (app) + `e1e964469` (middleware) + `466b57cd8` (registration) + `dc83c8432` (migrations)
