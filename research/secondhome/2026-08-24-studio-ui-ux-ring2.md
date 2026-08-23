---
date: 2026-08-24
domain: visa
client_case: none (product/UX work on the E33 Second Home Studio)
adversarial_review: kimi-k3
sources:
  - research/secondhome/2026-08-19-e33-sticky-funnel-research.md (the 5-seat product research this pass executes against)
  - .agents/skills/secondhome/SKILL.md (corner: verified facts, owner decisions, live state)
  - production probe of https://balizero.com/visa/second-home and /studio, headless Chromium, 2026-08-24
  - live PricingTool via search_service_pricing, 2026-08-24
  - Kimi K3 cross-family refutation of the ring-2 spec, 2026-08-24
---

# Second Home Studio — Ring-2 UI/UX research capture

This capture records the 2026-08-24 pass that turned the Second Home Studio from a functionally correct wizard into a studio worth returning to, and the defects found while doing so.

## 1. What was measured

The Phase-B core loop was already built: 8 modules, all wired, 256 vitest tests green. The pass measured how *alive* the surface felt and how honestly it reflected the underlying product rules.

| # | Module | State | Evidence |
|---|---|---|---|
| 1 | Adaptive Navigator | Built, solid | `StudioApp.tsx` computes `computeSequence(plan)` fresh every render (`sequence.ts:35-67`); `QuestionCard.tsx` renders a real `role="radiogroup"` (`QuestionCard.tsx:100-108`) with a collapsible "why we ask" `<details>` (`QuestionCard.tsx:66-99`). |
| 2 | Live Fit Memo preview | Built, thin | `MemoPreview.tsx` is a `<dl>` of label/value rows (`MemoPreview.tsx:118-153`) that appeared fully-formed the instant `plan` changed; no transition, no document weight. |
| 3 | "Your money stays yours" custody module | Built, thin | `CustodyMap.tsx`: 3 numbered `<li>` items (`CustodyMap.tsx:5`), each a circled numeral + two lines of plain text (`CustodyMap.tsx:72-90`). No diagram of the money's path; the highest-leverage trust asset wore the same card chrome as the clear-plan button. |
| 4 | Route comparator | Built, thin | `RouteComparator.tsx`: a plain `<table>` wrapped in `overflow-x:auto` (`RouteComparator.tsx:46`). Static, generic, never reflected the user's own answers. |
| 5 | Honest timeline simulator | Built, scoped down | `TimelineView.tsx` renders `buildTimeline()`'s 7 steps as a flat `<ol>` with dashed `border-bottom` (`timeline.ts:88-127`, `TimelineView.tsx:55-123`). The research had asked for "pick a target date, get a week-by-week roadmap"; what shipped was a 3-way horizon band (`asap` / `this_quarter` / `exploring`). |
| 6 | Document readiness checklist | Built, thin | `ReadinessChecklist.tsx`: 10 real checkboxes bound to `plan.checklist` (`checklist.ts`), an "N of 10 prepared" text line (`ReadinessChecklist.tsx:46-58`). `ProgressRail.tsx` already knew how to draw a progress bar (`ProgressRail.tsx:16-38`); the checklist did not reuse it. |
| 7 | Save without account | Built, solid engineering / thin UI | `plan-codec.ts` whitelists every enum field (`isValidPlanShape`, `plan-codec.ts:127-144`) and guards SSR/localStorage (`hasLocalStorage`, `plan-codec.ts:50-64`). `SavePlanBar.tsx` is 3 plain buttons in a bordered box (`SavePlanBar.tsx:67-76`). |
| 8 | WhatsApp handoff | Built, correctly thin | `WhatsAppHandoff.tsx` + `whatsapp-bullets.ts`: branch-aware, ≤6 bullets, verified against the real backend contract (`whatsapp-bullets.ts:1-24`). |

Visual surface measurements:
- Landing page: 652 lines (`SecondHomeLanding.tsx`) + 12 components in `studio/components/`.
- Zero images / SVG / icons across the entire surface except two `lucide-react` glyphs (`ChevronRight`, `Phone`).
- Nine of the eleven components in `studio/components/` open with the same inline style block: `display:"grid", gap:"var(--space-3, 1rem)", background:"var(--surface-raised)", border:"1px solid var(--color-border-subtle)", borderRadius:12, padding:"var(--space-4, 1.5rem)"` (verified in `CustodyMap.tsx:12-20`, `ReadinessChecklist.tsx:22-30`, `RouteComparator.tsx:24-34`, `TimelineView.tsx:35-43`, `SavePlanBar.tsx:68-76`, `WhatsAppHandoff.tsx:35-43`).
- `VerdictPanel.tsx:30` hardcodes `border: "2px solid var(--accent-funnel)"` regardless of `verdict.band`: a `strong_fit` and a `not_eligible` rendered with identical visual weight.

## 2. The correctness defect found

The Studio resolved **one** PricingTool key for **three** different products.

`Verdict.product` is `"E33" | "E33E" | "E33F" | null`. The price panel always called `usePricingData` with the hardcoded identity `E33 Second Home (5 Years)`, no matter which product the verdict matched. Live on a public page since 2026-08-19, under the caption "One figure, everything included for the main applicant":

| Verdict product | Rendered | Real price (PricingTool, 2026-08-24) | Error |
|---|---|---|---|
| `E33` | 35.000.000 IDR | 35.000.000 IDR | correct |
| `E33E` | 35.000.000 IDR | 45.000.000 IDR | understated by 10.000.000 IDR |
| `E33F` | 35.000.000 IDR | 14.000.000 IDR offshore / 16.000.000 IDR onshore | overstated by ~20.000.000 IDR |

A senior matched to E33E read a price ten million rupiah below the real product price.

**Why 256 tests were green.** The PricingTool-only rule was obeyed at the **value** level — the figure always came from `usePricingData`, never a hardcoded literal — and violated at the **key** level. A test asserting "the price renders" passes; only a test asserting *which row was resolved, per branch* can fail. There was none.

**Fix.** PR #4747 introduced `resolveSecondHomePriceKey(product, location)`: it maps the verdict product — and, for `E33F` only, the offshore/onshore split already known from `plan.location` — onto the matching PricingTool row. The figure still comes from the pricing snapshot; only the key selection changed. When `product` is `E33F` and `location` is `null`, the resolver abstains and the price block does not render, because offshore and onshore are genuinely different products.

Prices re-verified live via `search_service_pricing` on 2026-08-24:
- `E33 Second Home (5 Years)`: 35.000.000 IDR
- `E33E Second Home Senior (5 Years)`: 45.000.000 IDR
- `E33F Second Home Senior (1 Year, Offshore)`: 14.000.000 IDR
- `E33F Second Home Senior (1 Year, Altus/Onshore)`: 16.000.000 IDR
- `E33E Second Home Senior (Extend)`: 10.000.000 IDR
- `E33F Second Home Senior (Extend)`: 10.000.000 IDR

## 3. What the refuter said

Kimi K3 reviewed the ring-2 spec cross-family. Conclusions, not softened:

- **Country Comparator should be cut.** It is the only feature whose data "does NOT exist today"; it requires a multi-source research capture before any UI is written; it publishes regulatory-adjacent claims about Malaysia, Thailand, and Portugal — jurisdictions Bali Zero does not practice in; the facts decay without an owner to re-verify; and its stated value is "SEO magnet", a marketing goal, not a 55+ user value.

- **The AI concierge blocker was described imprecisely.** Arming `E33_CLAIM_GUARD_ENFORCE` is not enough because `e33_claim_guard.py` intentionally does not re-check cached FAQ/semantic answers ("pre-vetted and intentionally not re-checked", `e33_claim_guard.py:23-24`). The path a concierge would serve most often — fast cached/KG answers — bypasses the guard by design. The spec's acceptance test did not cover this hole.

- **The gravest omission: no printable plan / PDF.** The research capture itself admitted "No PDF/branded artifact exists yet" and then none of the 11 planned PRs built one. For a 55+ HNW audience deciding on USD 130k/1M, this is the gap between screen and decision. Accepted and shipped as PR #4751.

- **Target-Date Planner should be demoted.** Anchoring calendar months to "typical step durations" manufactures precision when `e33_cases` is empty and 18 of 34 registry facts are still `pending`. The duration ranges themselves are unverified; translating them into month labels is "precision fabricated on nonexistent data".

- **Household Plan should be demoted.** Mapping E33 dependents onto the generic Spouse/Dependent KITAS rows (13.5M IDR onshore / 11M IDR offshore per person) is an assumption: 18 of 34 facts in the registry are still `pending`, and whether E33 dependents actually use that product/price is an unverified regulatory fact.

- **Ship-plan collisions.** Five PRs touch `StudioApp.tsx` (PR1 visual hierarchy, PR4 Scenario Toggle, PR6 Regulatory Radar UI, PR7b Target-Date UI, PR8b Household Plan UI); three touch `copy.ts` (PR4, PR6, PR7b); three touch `VerdictPanel.tsx` (PR1 band border, PR3 arrival transition, PR4 comparing state). Declarations of parallelism were false — sequential landing would produce repeated merge conflicts.

## 4. What shipped

Verified live with `gh pr view` on 2026-08-24:

| PR | Title | State | What it does |
|---|---|---|---|
| #4743 | docs(secondhome): align base E33 price in §4 with live 35M rate | merged | Fixed a self-contradiction in `.agents/skills/secondhome/SKILL.md`: §4 still listed `base 39M` while §3 and §4bis already had 35M. |
| #4745 | feat(mouth): animate MemoPreview rows and add growing receipt spine | merged | `MemoPreview.tsx` rows fade/rise in (180ms) when they first become known; unanswered rows render as lighter placeholders; a left spine grows as rows populate. |
| #4747 | feat(mouth): resolve price key per Second Home product branch | merged | The pricing-key fix: `resolveSecondHomePriceKey(product, location)` maps each verdict product to the correct PricingTool row. |
| #4748 | feat(mouth): differentiate VerdictPanel by fit band | merged | `VerdictPanel.tsx` renders a distinct border/icon/color treatment per band (`strong_fit` green, `likely_fit` blue, `edge_case` amber, `not_eligible` grey). |
| #4751 | feat(mouth): add Print / Save as PDF to Second Home Studio | merged | `window.print()` action in the save bar; `@media print` redefines tokens to a light document; hides nav/buttons; keeps verdict, custody, route comparison, timeline, checklist, price, and WhatsApp href. |
| #4752 | feat(mouth): add minimal stroke-icon vocabulary to Second Home Studio | open | Adds `lucide-react` stroke icons to TimelineView owner chips, RouteComparator column headers, and an optional icon prop on `OptionButton`. |
| #4753 | feat(mouth): custody flow diagram for Second Home Studio | open | Rewrites `CustodyMap.tsx` as an interactive node diagram: your money → your own BUMN bank account → Imigrasi evidence, with Bali Zero outside the chain. |

## 5. What remains open and why

Blocked by an external fact:
- **Grounded AI Concierge.** Blocked until `E33_CLAIM_GUARD_ENFORCE` is armed in production and independently re-verified live. The guard currently only logs/appends a fallback note; cached FAQ/semantic answers are intentionally not re-checked, which is the path a concierge would serve most often. This is a production-behavior-changing decision on the RAG orchestrator lane, not a Studio UI concern.
- **Evidence Strip.** Blocked because `e33_cases` is empty. Building it now would require either fabricating representative numbers or shipping an empty shell. Revisit only after the visa-oracle/secondhome case-lifecycle lane has real rows.

Waiting for a Zero decision:
- **Regulatory Radar.** The data exists (`e33-fact-registry.json`: 34 facts, 7 confirmed / 18 pending / 8 unknown / 1 disputed), but publishing a curated list of what Bali Zero has asked Imigrasi in writing is positioning, not just engineering. Zero must decide which subset is safe to show and whether the transparency is worth the upkeep.
- **Bookable human advisor.** The WhatsApp handoff exists as a plain CTA, but offering a named consultant with a response-time promise activates a real-client flow. That is an operations/owner decision, not a UI-only change.

Not yet built, no external blocker:
- **Scenario Toggle.** Pure client-side, data exists, no backend. Simply not scheduled yet.
- **Target-Date Planner.** Demoted by the refuter; can be revisited if/when step durations are verified against real cases.
- **Household Plan.** Demoted by the refuter; can be revisited when the dependent-product mapping for E33 is confirmed.

## 6. Meta-pattern

The repeated failure mode is reading the system through a **proxy** instead of through the thing itself:
- A test verified "the price renders" instead of "which PricingTool row was resolved", so the wrong product price reached clients while tests stayed green.
- A two-point diff accused a lane of deleting PRs that were actually just extra commits on `main`.
- The repeated card-style object made every module look equally important, so the custody reassurance — the #1 trust lever — carried the same visual weight as a utility button.
- `VerdictPanel.tsx:30` fixed one border color for every band, so the most important payoff moment looked identical whether the user was strongly eligible or not eligible at all.

The fix, in each case, was to measure closer to the source: the actual PricingTool key, the actual git graph, the actual DOM and token usage, the actual user-facing consequence of a design choice.
