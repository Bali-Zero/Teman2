# Track C — Experience (spec)

> Source of truth for scope: `00-product-design.md` §3 "The experience" and §4 "The
> interview". This doc is the 3-PR execution plan for the frontend/experience track only —
> the engine (`visa_engine`, §5) and content/regulatory work (§6) are separate tracks with
> their own PR series.

## Scope

Track C owns the public-facing Visa Oracle v2 experience on `apps/mouth`: design system
(tokens, motion, theming), the living-tree interview UI, microinteractions, mobile-first
layout, and accessibility. It does **not** own: the deterministic engine, the RulePack /
signing pipeline, the regulatory catalog, or any backend wiring. Every PR in this track is
**mock-data-only** until the engine's contracts (`apps/backend-rag/backend/services/
visa_engine/contracts/`) land on main — see "Deferral" below.

## The 3-PR plan

### PR C1 — Foundation (this PR)

- vo2 design tokens (`apps/mouth/src/styles/visa-oracle-v2.css`), scoped under `.vo2`,
  built on the existing core token vocabulary (`packages/core/tokens/`). Tree colors,
  eligibility 4-state colors, Q0 lane-tone colors, motion tokens, light-default /
  dark-override, `prefers-reduced-motion` zeroing.
- Typed mock interview model (`apps/mouth/src/lib/visa-oracle/v2/`): `types.ts` (the
  five-state `DecisionState`, `EligibilityLevel`, language-agnostic `AnswerValue`,
  `InterviewQuestion`, `InterviewState`, `MockOutcome` — one all-inclusive price per
  candidate, owner ruling R1), `mock-tree.ts` (Q0 date-driven lane routing, the 10
  categories, one simplified `remote-worker` behavioral tree, pure `nextQuestion` /
  `answer` / `skip` / `pathsRemaining` / `computeLane` / `resolveOutcome`), colocated
  vitest suite.
- `/visa-v2` prototype route (relocated 2026-07-17 from `/visa/v2`, see "Route location"
  below): `noindex`/`nofollow`, framing card verbatim copy, Begin CTA, Q0 (yes/no),
  date-driven lane display for the onshore branch, 10 category tiles for the offshore
  branch, a quiet "the living tree arrives in the next iteration" placeholder after
  category selection. No deeper navigation, no outcome page, no API calls.

**Route location (Codex sol review F6, 2026-07-17):** the prototype lives at
`apps/mouth/src/app/visa-v2/` — a sibling top-level segment, NOT nested inside
`apps/mouth/src/app/visa/`. It was originally built at `/visa/v2` but that nesting
silently inherited the parent `/visa` route's `VisaLayout` → `<SessionInit funnel="visa">`,
which POSTs `/api/funnel/session/touch` on every visit, violating the "no API calls"
invariant below. `/visa-v2` inherits only the app's root layout.

**Acceptance criteria (C1):**

1. `npx vitest run src/lib/visa-oracle/v2/` green.
2. `npx tsc --noEmit` introduces no new errors on touched files.
3. `/visa-v2` renders with `robots: noindex,nofollow` and does not touch any file under
   `apps/mouth/src/app/visa/` (v1's own tree), nor `research/visa/`, `apps/backend-rag/`, or
   v1 files (`quiz-logic.ts`, `VisaChat.tsx`, etc.).
4. No hardcoded real prices; every mock candidate carries exactly one
   `priceAllInclusive.mock === true` field, never a fee/PNBP/official split.
5. No new npm dependencies.

### PR C2 — Living tree + interview

- The tree visualization itself (design doc §3 "PRIMARY = the living decision tree"):
  branches for the 10 categories, FLIP-based prune animation when a branch becomes
  ineligible, "paths remaining" counter wired to `pathsRemaining()`, branch-aware
  breadcrumb.
- Full behavioral trees for the remaining 9 categories (design doc §4; `remote-worker`
  already modeled in C1) — Work & employment (5q), Invest & golden (6q) including the
  villa-leasehold honesty note, and simplified honest placeholders for the rest until
  their own content passes land (§10.4 "lane-by-lane during build").
  the shared review-gate ★ and family ★ questions (identical across lanes, built once).
- "Why we ask" disclosure glyph wired to every sensitive question.
- Confirmation card ("Here's what you told us", editable, assumptions surfaced) before any
  verdict — the honesty-receipt pattern from §3.
- Constellation atmosphere layer (mood only, low-contrast, never the data structure).

**Acceptance criteria (C2):** tree renders all 10 categories without dead-ending; prune
animation respects `prefers-reduced-motion`; paths-remaining counter never increases as
answers accumulate (mirrors the C1 unit-test invariant, now wired live); confirmation card
lets the user edit any prior answer without losing downstream state; zero backend calls.

### PR C3 — Outcome + accessibility + e2e

- Outcome-page anatomy (design doc §3): verdict headline, 4-state eligibility card
  (icon+text, never color-alone), comparison table for ≥2 candidates, timeline anchored to
  today, the single all-inclusive price reveal, document checklist, "your next 3 steps",
  share/print/PDF, QR→WhatsApp handoff (session pre-loaded), assumptions/caveats footer
  with a dated "regulations verified as of" stamp.
- Five outcome-copy skeletons wired to `DecisionState` (`NEEDS_INPUT` /
  `SUPPORTED_CANDIDATES` / `HUMAN_REVIEW_REQUIRED` / `NO_SUPPORTED_PATH` — three "what
  instead" blocks, never a bare dead end — `TEMPORARILY_UNAVAILABLE`).
- WCAG AA verification pass (keyboard nav, live-region announcements, non-visual tree
  equivalent, plain-language copy pass) + Playwright E2E covering the full mock funnel.

**Acceptance criteria (C3):** axe-core (or equivalent) clean on the full funnel; every
outcome state has a rendered skeleton with no "coming soon" theatre; Playwright E2E green
in CI; still mock-data-only unless the engine deferral (below) has been lifted by then.

## Explicit deferral

Engine wiring (replacing the mock model in `src/lib/visa-oracle/v2/mock-tree.ts` with real
API calls into `visa_engine`) is **out of scope for all three Track C PRs** until PR1's
engine contracts (`apps/backend-rag/backend/services/visa_engine/contracts/`, per the
delivery plan in `00-product-design.md` §9) merge to main. Until then, Track C ships purely
against the typed mock model — every function pure, every price obviously fake and flagged
`mock: true`. This mirrors the design doc's own strangler discipline (§5.6): the frontend
strangler only flips `ENFORCE` once the engine surface it targets is real.
