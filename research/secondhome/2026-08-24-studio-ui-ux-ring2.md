---
date: 2026-08-24
domain: visa
client_case: none (product/UX work on the E33 Second Home Studio)
adversarial_review: codex
sources:
  - research/secondhome/2026-08-19-e33-sticky-funnel-research.md (the 5-seat product research this pass executes against)
  - .agents/skills/secondhome/SKILL.md (corner: verified facts, owner decisions, live state)
  - production probe of https://balizero.com/visa/second-home and /studio, headless Chromium, 2026-08-24 (reported by the original capture; screenshot artifacts are not retained in this worktree)
  - live PricingTool via search_service_pricing, 2026-08-24 (reported by the original capture)
  - apps/mouth/data/bali-zero-prices.json (Codex cross-check of all six cited E33/E33E/E33F rows, 2026-08-24)
  - Kimi K3 cross-family refutation of the ring-2 spec, 2026-08-24
  - gh pr view (original capture's title/state check for #4743/4745/4747/4748/4751/4752/4753/4755), 2026-08-24; Codex's re-run could not reach api.github.com, so local origin/main first-parent history was used as the fallback
  - reported prove-live walk on promoted production (post-#4751), full-page screenshots + direct fetch of the served JS chunk, 2026-08-24; artifacts not retained in this worktree and not independently reproduced by Codex
  - origin/main source read of SavePlanBar.tsx, CustodyMap.tsx, VerdictPanel.tsx, and packages/core/tokens/{primitives,semantic,themes/editorial}.css, 2026-08-24
---

# Second Home Studio — Ring-2 UI/UX research capture

This capture records the 2026-08-24 pass that turned the Second Home Studio from a functionally correct wizard into a studio worth returning to, and the defects found while doing so.

## 1. What was measured

The Phase-B delivery record reported that the core loop was already built: 8 modules, all wired, 256 vitest tests green. The pass measured how *alive* the surface felt and how honestly it reflected the underlying product rules. Codex could not independently repeat that historical test tally in this worktree because local `vitest` dependencies are absent and the sandbox cannot reach the npm registry.

The `file:line` citations in this section describe the pre-ring-2 source snapshot at `33377a032`. Most still match this worktree byte-for-byte; `MemoPreview.tsx:118-153` and `VerdictPanel.tsx:30` subsequently drifted because PRs #4745 and #4748 intentionally changed those exact sections. Their historical content was re-opened at `33377a032` and still supports the claims below.

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
- Landing page: 652 lines (`SecondHomeLanding.tsx`) + 10 source files in `studio/components/`, exporting 11 component functions (`QuestionCard.tsx` also exports `OptionButton`).
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

**Why the reported 256 tests could still be green.** The PricingTool-only rule was obeyed at the **value** level — the figure always came from `usePricingData`, never a hardcoded literal — and violated at the **key** level. A test asserting "the price renders" passes; only a test asserting *which row was resolved, per branch* can fail. There was none.

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

The original pass recorded these as verified with `gh pr view` on 2026-08-24. Codex re-ran all eight exact `gh pr view <n> --json title,state,mergedAt` commands, but this sandbox returned `error connecting to api.github.com` for every call; the API `state` fields therefore were not independently observed in the adversarial pass. As a fallback, all eight GitHub-authored squash commits were found in the first-parent history of local `origin/main`; their commit subjects match the titles below (the #4748 row is a fair shortening of the full subject, which ends “with semantic state tokens”).

| PR | Title | State | What it does |
|---|---|---|---|
| #4743 | docs(secondhome): align base E33 price in §4 with live 35M rate | merged | Fixed a self-contradiction in `.agents/skills/secondhome/SKILL.md`: §4 still listed `base 39M` while §3 and §4bis already had 35M. |
| #4745 | feat(mouth): animate MemoPreview rows and add growing receipt spine | merged | `MemoPreview.tsx` rows fade/rise in (180ms) when they first become known; unanswered rows render as lighter placeholders; a left spine grows as rows populate. |
| #4747 | fix(mouth): the Studio quoted one price for three different products | merged | The pricing-key fix: `resolveSecondHomePriceKey(product, location)` maps each verdict product to the correct PricingTool row. |
| #4748 | feat(mouth): differentiate VerdictPanel by fit band | merged | `VerdictPanel.tsx` renders a distinct border/icon/color treatment per band (`strong_fit` green, `likely_fit` blue, `edge_case` amber, `not_eligible` grey). |
| #4751 | feat(mouth): let the plan leave the screen — print / save as PDF | merged | `window.print()` action in the save bar; `@media print` redefines tokens to a light document; hides nav/buttons; keeps verdict, custody, route comparison, timeline, checklist, price, and WhatsApp href. |
| #4752 | feat(mouth): add minimal stroke-icon vocabulary to Second Home Studio | merged | Adds `lucide-react` stroke icons to TimelineView owner chips, RouteComparator column headers, and an optional icon prop on `OptionButton`. |
| #4753 | feat(mouth): draw the money's path instead of describing it | merged | Rewrites `CustodyMap.tsx` as an interactive node diagram: your money → your own BUMN bank account → Imigrasi evidence, with Bali Zero outside the chain. |
| #4755 | docs(pending-arms): SHS ledger maintenance — retire, close, extend, open | merged | Ledger maintenance in `.claude/skills/modus/PENDING-ARMS.md`: retires the radiogroup-accessible-name finding (refuted), closes the E33E/E33F pricing-parity item (Zero's ruling), extends the `E33_CLAIM_GUARD_ENFORCE` item with a cache-bypass finding, and opens a new item for the not-yet-proven-live Studio price fix from PR #4747. |

## 4bis. Prove-live on promoted production (2026-08-24)

The original production pass reported that production had been promoted and then re-verified. Codex could not independently reproduce that prove-live evidence in this worktree: the three named screenshots are absent, and the exact required chunk request returned HTTP code `000` (network failure), not a response that can confirm or refute the capture's reported HTTP 200. The claims below are therefore retained as attributed original-pass observations, not upgraded into a second independent attestation.

1. **The original pass reported the price defect (§2) cured on the served page — both halves.** Its browser walk on promoted production — path: age 55–59 → deposit route → USD 50k deposit + USD 3k/month income → no family → ASAP → in Indonesia — reportedly rendered, under the label "YOUR ALL-INCLUSIVE FIGURE", the figure **45.000.000 IDR** for the `E33E` match, the correct E33E price. Before PR #4747 the same walk rendered 35.000.000 IDR, understating the real product price by 10.000.000 IDR. The unavailable full-page screenshot `after-E33E-verdict-desktop.png` was reported as 2880×6958 and as showing "Matching product: **E33E**" and "YOUR ALL-INCLUSIVE FIGURE / 45.000.000 IDR". The base-E33 half — deposit route, USD 130k, no senior disclosure — was likewise reported from the unavailable `after-base-verdict-desktop.png` (2880×6870): a green `strong_fit` border with a check icon, "Matching product: **E33**", and **35.000.000 IDR**. The original pass treated this evidence as closing the PENDING-ARMS item opened by PR #4755; Codex verified the resolver and price rows in source but did not independently prove their served-production behavior.
2. **Bundle-level proof reported by the original pass.** It recorded `curl https://balizero.com/_next/static/chunks/app/visa/second-home/studio/page-8450b87e629710e7.js` → HTTP 200 and the strings `E33E Second Home Senior`, `custody-outside`, and `Save as PDF`. Codex's exact status command returned `000`; the follow-up `grep -o` emitted no substrings because no response body was received, so this pass cannot use that result as evidence that the strings are absent. All three strings do exist in the corresponding `origin/main` source, which proves they were built and merged, not that this exact chunk was served.
3. **The other four visual changes were reported live in the same original capture**: the verdict panel carried an amber border + warning-triangle icon for the `edge_case` band and a green border + check icon for `strong_fit`, plus a neutral `rgba(255,255,255,0.68)` border + X icon for `not_eligible` in the unavailable `after-lowcapital-verdict-desktop.png` — no longer the one undifferentiated accent border across all four bands that §1 flagged at `VerdictPanel.tsx:30`; the custody section rendered as a 3-node money-path diagram — "Open an account in your own name" → "Use the bank evidence for your application" → "Maintain the qualifying position" — captioned "The deposit is evidence of your financial capacity. It is not a payment to Bali Zero," i.e. Bali Zero drawn outside the money chain; the timeline attributed each step to `YOU` / `BALI ZERO` / `IMIGRASI`; the save bar offered `Print / Save as PDF` alongside `Save on this device` / `Copy plan link` / `Clear saved plan`. Codex confirmed the corresponding implementations in source, but not their rendered production appearance.

## 5. What remains open and why

Blocked by an external fact:
- **Grounded AI Concierge.** Blocked until `E33_CLAIM_GUARD_ENFORCE` is armed in production and independently re-verified live. The guard currently only logs/appends a fallback note; cached FAQ/semantic answers are intentionally not re-checked, which is the path a concierge would serve most often. This is a production-behavior-changing decision on the RAG orchestrator lane, not a Studio UI concern.
- **Evidence Strip.** Blocked because `e33_cases` is empty. Building it now would require either fabricating representative numbers or shipping an empty shell. Revisit only after the visa-oracle/secondhome case-lifecycle lane has real rows.

Waiting for a Zero decision:
- **Regulatory Radar.** The data exists (`e33-fact-registry.json`: 34 facts, 7 confirmed / 18 pending / 8 unknown / 1 disputed), but publishing a curated list of what Bali Zero has asked Imigrasi in writing is positioning, not just engineering. Zero must decide which subset is safe to show and whether the transparency is worth the upkeep.
- **Bookable human advisor.** The WhatsApp handoff exists as a plain CTA, but offering a named consultant with a response-time promise activates a real-client flow. That is an operations/owner decision, not a UI-only change.

Built and merged after the original capture; production not re-probed in this review:
- **Scenario Toggle.** Current `origin/main` imports `ScenarioToggle` in `StudioApp.tsx` and renders it on the verdict page. It is no longer an open build item.

Not yet built, no external blocker:
- **Target-Date Planner.** Demoted by the refuter; can be revisited if/when step durations are verified against real cases.
- **Household Plan.** Demoted by the refuter; can be revisited when the dependent-product mapping for E33 is confirmed.

Confirmed regression in the captured post-#4753 source, subsequently fixed in `origin/main`:
- **Printing the plan hid the custody diagram's three nodes.** Confirmed by reading both files in the post-#4753 source snapshot. #4751's print stylesheet (`SavePlanBar.tsx`'s `PRINT_STYLES`, inside `@media print`) hid every button on the page with a bare, unscoped selector: `nav, button, .fixed.bottom-0.left-0.right-0.z-50, .bz-shs-save-plan-bar { display: none !important; }`. #4753 — this same wave — rewrote each of `CustodyMap.tsx`'s three chain nodes as `<button type="button" aria-expanded={isExpanded}>`, wrapping the icon, title, and chevron; the step description sat outside the button but was `hidden` unless the node was expanded, and only the connecting `custody-arrow` SVGs and the `custody-outside` aside ("not a payment to Bali Zero") sat outside a `<button>` entirely. Net effect in that snapshot: on a printed plan the three custody nodes vanished completely — only arrows pointing at empty space and the outside-box survived. The printed plan is the artefact a prospect carries to their bank, so this was client-facing. A blanket selector written for the save bar's own controls silently swallowed content the moment a sibling PR turned that content into a control — the mechanism generalises beyond this page. Current `origin/main` has removed the bare `button` selector and keeps the custody detail text in the DOM with `data-collapsed`; the source-level regression is closed, although production was not re-probed in this review.

Also observed, not yet fixed:
- **The reassurance figure and the destructive control read as the same red.** Confirmed by tracing both tokens to source this session: the all-inclusive price panel's border resolves to `--accent-funnel: #ff3344` (`packages/core/tokens/themes/editorial.css:57`, the visa-funnel override on the editorial theme); the "Clear saved plan" button's border resolves to `--color-error` → `--state-danger` → `--color-state-danger: #ef4444` (`packages/core/tokens/primitives.css:57`, applicable outside the light-theme override). The two hex values differ by only 16/17/0 in RGB — practically the same red on a reassurance box and a destructive action. The pass that walked the page measured the two elements ~321px apart, close enough to appear on screen together without scrolling.

## 6. Meta-pattern

The repeated failure mode is reading the system through a **proxy** instead of through the thing itself:
- A test verified "the price renders" instead of "which PricingTool row was resolved", so the wrong product price reached clients while tests stayed green.
- A two-point diff accused a lane of deleting PRs that were actually just extra commits on `main`.
- The repeated card-style object made every module look equally important, so the custody reassurance — the #1 trust lever — carried the same visual weight as a utility button.
- `VerdictPanel.tsx:30` fixed one border color for every band, so the most important payoff moment looked identical whether the user was strongly eligible or not eligible at all.

The fix, in each case, was to measure closer to the source: the actual PricingTool key, the actual git graph, the actual DOM and token usage, the actual user-facing consequence of a design choice.

## Adversarial review

Reviewed by Codex (GPT-5), generator != grader, against the worktree at commit `14f750fe8`.

- PR titles/states: re-scanned the document and ran `gh pr view <n> --json title,state,mergedAt` separately for #4743, #4745, #4747, #4748, #4751, #4752, #4753, and #4755. All eight commands failed with `error connecting to api.github.com`; no API `state` or `mergedAt` value was available to this reviewer. The fallback first-parent read of local `origin/main` found GitHub-authored squash commits `214dff8eb`, `5a0e355fb`, `e53a5d089`, `e1bb9f05f`, `b958e83a5`, `ec6d7b5e0`, `27c917d8c`, and `dac28e301` respectively. All eight are landed on `origin/main`; their subjects match the table, with #4748 fairly shortened from “differentiate VerdictPanel by fit band with semantic state tokens”. The table remains accurate, but this pass does not falsely present the unavailable GitHub API fields as observed.
- `file:line` citations: opened all 25 unique citations (27 occurrences), plus the load-bearing pricing resolver, backend WhatsApp contract, `PRINT_STYLES`, custody-node implementation, and semantic-token chain. Twenty-three citations still match this worktree directly. `MemoPreview.tsx:118-153` and `VerdictPanel.tsx:30` drifted because #4745 and #4748 changed those sections; both historical claims were confirmed at the pre-ring-2 snapshot `33377a032`, so they were marked as historical drift rather than defects.
- Prices: cross-checked every cited row against `apps/mouth/data/bali-zero-prices.json`. Exact matches: E33 5-year 35.000.000 IDR; E33E 5-year 45.000.000 IDR; E33E extend 10.000.000 IDR; E33F offshore 14.000.000 IDR; E33F Altus/onshore 16.000.000 IDR; E33F extend 10.000.000 IDR. No price mismatch was found.
- Live/production claims: ran the exact chunk status command; it returned `000`, not a server status. The requested `curl -s ... | grep -o 'E33E Second Home Senior\|custody-outside\|Save as PDF'` then emitted no substrings because the fetch produced no response body (exit 1), so that result does not establish absence. The three screenshot files are not present anywhere in this worktree. §4bis and the frontmatter now distinguish the original pass's reported production evidence from what Codex independently re-verified; local `origin/main` contains all three strings, which proves built/merged source only.
- Historical test tally: attempted `npx vitest --run src/lib/secondhome-studio src/app/visa/second-home/studio`; it failed with npm `ENOTFOUND` because `vitest` is not installed locally and the sandbox cannot reach `registry.npmjs.org`. The 256-test number is now explicitly attributed to the Phase-B delivery record rather than to this review.
- Internal consistency and sources: §4's print feature and §5's post-#4753 print regression are sequential, not contradictory. Two stale “remains open” statements were corrected from current `origin/main`: `ScenarioToggle` is now imported/rendered, and the print selector regression is fixed in source. The frontmatter now includes the price JSON used by this review and labels unavailable production artifacts as reported; the legitimate Kimi K3 spec-review sources remain intact.

Six defects or attestation gaps were corrected: the wrong frontmatter reviewer, the 12-versus-10 component-file count, the unqualified 256-test attestation, the independently-unverifiable prove-live wording, the stale Scenario Toggle status, and the stale print-fix status. No PR-title or price defect survived the checks above.
