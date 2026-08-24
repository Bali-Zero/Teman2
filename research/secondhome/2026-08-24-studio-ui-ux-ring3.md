---
date: 2026-08-24
domain: visa
client_case: none (product/UX work on the E33 Second Home Studio)
sources:
  - research/secondhome/2026-08-24-studio-ui-ux-ring2.md (this capture's predecessor — same conventions)
  - twelve PRs on Bali-Zero/Teman2 merged this pass: #4811, #4812, #4814, #4816, #4817, #4818, #4821, #4823, #4824, #4825, #4828, #4831
  - painted-pixel contrast and rendered-DOM measurements taken directly on production and on branch, 2026-08-24 — not a lane's self-report
  - e33-fact-registry.json query this session (dependent_spouse_code_e31b, dependent_codes_confirmation, e33f_family_inclusion)
  - nuzantara-rag /health consumer-side check, 2026-08-24
---

# Second Home Studio — Ring-3 UI/UX research capture

This capture records the 2026-08-24 pass that followed ring-2: twelve PRs shipped against the Second Home Studio. Every number below is a painted-pixel or DOM measurement taken directly on production or on the branch — none is a lane's self-report.

## 1. What shipped, and the measurement behind each

| PR | What it does | Measurement |
|---|---|---|
| #4811 | Two-step confirm on "Clear saved plan" | One activation used to destroy the plan — fatal on touch, where no hover warns first. Now arms, then confirms; disarms on Escape, on blur, after 5s. Proved live on production across all four scenarios. |
| #4812 | Pins the three disarm paths with tests | Three mutations, each kills its own test. The proposed `console.error` assertion was found **vacuous** (React 18+ no longer warns on setState after unmount) and was replaced with a direct `clearTimeout` spy — flagged instead of shipping a test that could not fail. |
| #4814 | Wizard nav row, present on all six steps | CTA contrast **3.62:1 → 4.82:1** (painted `rgb(217,43,58)`, 16px/600); Back button border **~1.2:1 → 3.74:1**, measured ENABLED at step 2. |
| #4816 | Both Second Home WhatsApp CTAs | Contrast **1.98:1 → 6.45:1**, brand green `#25D366` byte-identical, icon follows the ink. |
| #4817 | Route-aware readiness checklist | Proved live on four routes: **0-of-8** (deposit), **0-of-8** (property), **0-of-9** (senior), **0-of-10** on the "I'm not sure" fail-safe — the unresolved route widens the list, never narrows it. |
| #4818 | Commits the block `next dev` writes into `apps/mouth/CLAUDE.md` | Stops worktrees going dirty. |
| #4821 | Corner doc §4bis | Four rows plus two measurement traps. |
| #4823 | Printed plan's money-path section | Each step card **222px → 1022px**. Before, the body wrapped one word per line and "application" was clipped mid-word. Proved live: the PDF was rendered from production and page 2 read directly. |
| #4824 | WhatsApp ink cure promoted from a comment to a token plus a sweeping guard | The sweep visits **1219 files** and found **seven more defective surfaces** beyond the three found by hand-grepping — including `packages/core/components/apps/AppWhatsAppCTA.tsx`, a shared core component. Proved live: `/book` **1.98:1 → 6.45:1**; `/services` **2.28:1 → 5.61:1** (5.61 not 6.45 because its green is `#22c55e`, not `#25d366`). |
| #4828 | The armed destructive control | The most instructive PR of the twelve — see §2. |
| #4831 | Money-path headings on screen | Before/after, measured by injecting the branch's rules onto the live DOM (see table below). Root cause: `.custody-layout` was `minmax(0,1fr) minmax(12rem,0.3fr)` — the aside's own 12rem floor claimed the row at every width up to the 1120px cap. |
| #4825 | Fly watcher named a count, not a machine | Six consecutive red runs, 09:25→13:13 UTC, whose entire payload was `unhealthy_svc=1` with no machine id and no check name. Now emits capped `svc_detail=`/`vm_detail=` fields that declare it when they truncate. |

#4831 heading rows, before → after (columns per row at each width):

| Width | Before | After |
|---|---|---|
| 360px | 2/3/3 | 2/2/2 |
| 390px | 2/3/2 | 2/2/2 |
| 860px | 7/7/4 (heading box 38px) | 1/1/1 |
| 1024px | 5/5/4 | 1/1/1 |
| 1180px | 4/4/3 | 2/2/2 |
| 1440px | 4/4/3 | 2/2/2 |
| 1920px | 4/4/3 | 2/2/2 |

## 2. The collision that moved twice (the centrepiece)

The armed "Clear saved plan" control painted `rgb(255,51,68)` — **byte-identical** to the border of the "Your all-inclusive figure — 35.000.000 IDR" panel. One means "here is your price, relax"; the other means "you are one press from destroying your plan".

Round 1 moved it to `--state-warning` (amber): 43° hue separation, 6.18:1 text, 6.24:1 border — every acceptance criterion met. **The PR was disarmed anyway**, because `VerdictPanel.tsx:105-109` already uses `--state-warning` as the `edge_case` band border, and `rules.ts` makes `edge_case` the outcome for the ENTIRE property route and for every applicant aged 55-59. The fix had moved the same defect one hue over.

Reading the whole `BAND_STYLES` table showed why hue was a dead end: `--state-success` = strong_fit, `--state-info` = likely_fit, `--state-warning` = edge_case, `--text-secondary` = not_eligible, `--accent-funnel` = price panel and CTA and custody icons. **Every hue on the page already means something.**

Round 2 changed the **channel**: a solid opaque fill instead of a tinted outline. All four bands paint a light tint (6-8%) behind a thin outline, so a solid fill is a shape none of them can produce — that is a structural proof, not four screenshots.

And this round found something the brief had not: the two acceptance criteria were **jointly unsatisfiable with one colour** — a fill dark enough to hold text at 4.5:1 measures ~2.78:1 against the page surface, under the 3:1 non-text floor, and lightening it flips the failure the other way. The requirement was split across two tokens rather than quietly missing one of them. The lesson: *a brief that cannot be satisfied as written is a finding, not an obstacle to route around.*

## 3. Meta-pattern: six instruments lied before the product did

Every one has the same shape — **reading state through a proxy instead of through the thing itself:**

1. A CSS marker that did not discriminate: `custody-arrow{display:none}` and `minmax(0` already existed in the pre-#4823 mobile breakpoint, so finding them proved nothing. Only the genuinely new class `bz-shs-back-to-answers` discriminates.
2. The CDN blamed: `x-vercel-cache: HIT`, `age: 4716`. Disproved by fetching with and without a cache-buster — byte-identical HTML, same sha1, same chunk URLs.
3. A grep on the served HTML for `0d3a1f`, a value that lives in a CSS bundle.
4. `:hover` read as "armed", because the pointer came to rest on the button after a Playwright click. Cured by focusing and pressing Enter instead.
5. A hydration probe that clicked an option and left the plan in `localStorage`, so all four checklist scenarios resumed mid-flow and returned identical answers.
6. The root `evidence/brief.yml` read instead of the per-branch `evidence/2026-08/<slug>/brief.yml` — for a moment it looked as though a lane had declared someone else's work as its own.

Three more of the same family, worth naming:

- `npm --prefix <dir> exec -- vitest` does not change vitest's cwd: a run launched from a worktree silently tests the MAIN checkout, so every mutation appears caught by tests that never saw it.
- A **disabled** control measured as a contrast FAIL (Back at step 1, 1.97:1). WCAG exempts disabled controls; the honest reading is at step 2, enabled: 3.74:1.
- A probe that failed to reach the page read as **absence of a defect**: the first sweep did not reach the custody map at 1440px and 1920px, so the disease was reported as confined to the laptop band. It was 4/4/3 at both.

Also worth recording is the near-miss that measurement refuted: `scrollIntoView({block:'start'})` put "Back to your answers" 100% under the sticky nav and the hit test returned the NAV — it looked like a serious focus-obscured defect. Walking the real tab order with 45 Tab presses found exactly one obscured control, "Close menu", inside the menu system itself. Browsers account for sticky headers when they move focus. **Not a defect.**

## 4. Left deliberately undone, with the reason

- **The article corpus.** An independent sweep found roughly eight more articles plus their `id`/`ru` translations carrying the same loose E33 shape: "proof of funds … in an Indonesian bank account", "$130K proof of funds", an Rp 5 billion property threshold, and the E33A/E33B codes. **Three of the four sampled are NOT noindexed**, so they are live. Rewriting them is the tracked F7 editorial task — a different concern with different risk, and an owner decision on volume.
- **Household Plan stays blocked, and the 2026-08-20 pricing ruling does NOT unblock it.** Verified in the fact registry this session: `dependent_spouse_code_e31b` **pending**, `dependent_codes_confirmation` **pending**, `e33f_family_inclusion` **unknown** — awaiting letter 006 Q6. The ruling settled which PricingTool rows apply; it did not confirm which permit code applies to whom. This is exactly the misreading the next session would make.
- **The `@media (max-width: Npx)` blocks lack a `screen` scope**, so Chromium's print layout also matches them. Pre-existing and inert today, because print and mobile want the same stacked shape. It becomes a trap only if the two are ever made to diverge. A note, not a PR.
- **The fly-watcher red itself.** Naming which of three `nuzantara-postgres` machines is unhealthy needs a Fly token this host does not have. Consumer-side truth, measured the same turn: `nuzantara-rag/health` returned `healthy` with `database: connected`, so it was never a client-facing outage.
