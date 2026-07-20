# GARUDA OS — Unified Surface Concept & Adoption Plan

|                          |                                                                                                                                                                                                                                                                                                      |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Status**               | PROPOSED — awaiting verifier review (external-agent contract: author never merges)                                                                                                                                                                                                                   |
| **Date**                 | 2026-07-19                                                                                                                                                                                                                                                                                           |
| **Author**               | Kimi (external agent, Air-M5)                                                                                                                                                                                                                                                                        |
| **Scope owner decision** | kita. (operational workspace) + my. (client portal) only                                                                                                                                                                                                                                             |
| **Artifacts**            | `concepts/concept-v1-copper-anthracite.html` (open in browser; sample data, no PII). Concepts v2/v3 were removed from this diff on 2026-07-19 to fit the tri-LLM `--max-diff-chars 80000` review budget (see §7); they survive as local iteration artifacts and can be re-added on verifier request. |

---

## 1. Decision

1. **Adopt the copper/anthracite shell (Concept v1) as the single design language** for operational surfaces. It is not a new invention: it consolidates what `apps/mouth` already does well (GARUDA tokens, liquid glass, funnel accents, grain, motion 150/250/400ms).
2. **Adopt the Day/warm-paper variant (Concept v3) as the native light theme of the same token system** — `operative-light` reconciled (paper `#f6f2e9`, ink navy `#16213a`, daylight copper family). One system, two themes; not two designs.
3. **Import two disciplines from `skills/bali-zero-brand` into the product tokens:**
   - **Yellow = verifiable facts** — a `fact-badge` component (bg `#F4C430`, black IBM Plex Mono text, 4px radius, per the brand's `regulation_badge` WCAG spec) used for KBLI codes, citations, regulation codes across all product surfaces.
   - **Red `#C8102E` = criticals only** — never decorative.
4. **`bali-zero-brand` tokens remain the language of editorial/carousel surfaces only** (WR2/IG content). Its closed-namespace constraints (no green/blue/purple, single weight, serif ban) are correct for scroll-stopping content and hostile to 8-hour operational UI. The brand constitution already scopes enforcement to carousel text-zones; this plan respects that boundary.

## 2. Scope

**IN**

- `kita.balizero.com` workspace — `(workspace)` route group in `apps/mouth` (~60 pages: dashboard, clients, process, inbox, intelligence, revenue, hr, admin, settings…)
- `my.balizero.com` client portal — `/portal/*` routes

**OUT (explicit)**

- `apps/admin-dashboard` — owner does not use it (2026-07-19). Recommend a separate retirement/archival decision; zero redesign investment.
- `apps/web` (zantara chat satellite) — parked; revisit after WS1–WS3 land.
- `/prime` (3D maps), `/visa-oracle` (scoped `oracle.css` by design), marketing/editorial (already on brand), WR2 carousel pipeline.
- **No deploy.** Canonical flow only: PR → CI → verifier review → merge by verifier.

## 3. Audit evidence (2026-07-19)

- `apps/mouth` has the real design system: 3-tier tokens in `packages/core` (primitives → semantic → 5 themes), hostname-persona theming (`kita`→operative-dark, `my`→operative-light, else→editorial), 18+ tested components, effects (grain/shimmer).
- **Two competing token SSOTs exist**: `packages/core/tokens` and `packages/design-system/tokens/bz-tokens.css` (anthracite scale, chart series, layout constants). The latter is consumed by no app.
- **Two ThemeProviders coexist** in mouth (`packages/core/components/ThemeProvider.tsx` + legacy `next-themes` provider in `src/components/providers/`), and **the persisted theme key is split**: the pre-paint inline script in `src/app/layout.tsx` reads `localStorage('bz-theme')`, while the core provider and the appearance-settings page read/write `localStorage('theme')` — user theme selection is therefore applied inconsistently depending on which writer ran last.
- `semantic.css` comments note **~600+ hardcoded hex drift** across the app.
- `admin-dashboard` (shadcn slate, light-default) and `apps/web` (starter-kit blue, system-ui) share **zero** brand tokens — recorded for completeness; out of scope per §2.
- CRM analytics MCP tools are role-gated (`tax_consultant`); concept KPI numbers are placeholders, not real figures.

## 4. Work streams

### WS1 — Token reconciliation (foundation, do first)

- Merge `packages/design-system/tokens/bz-tokens.css` into `packages/core` (anthracite scale, `--bz-chart-*` series with WCAG annotations, layout constants); then deprecate the duplicate package.
- Add semantic `fact-badge` tokens (yellow/black spec from bali-zero-brand `regulation_badge`) and a `critical` status alias (`#C8102E`).
- Collapse to a single ThemeProvider; remove the `next-themes` legacy path.
- Acceptance: one token SSOT; `packages/design-system` marked deprecated in its README.

### WS2 — kita. workspace shell (Concept v1)

- New tested components in `packages/core/components`: `SystemPulse`, `PracticePipeline`, `ComplianceRadar`, `ZantaraDock` (with `FactBadge` citations), KPI card with count-up.
- **Governance gate:** adding components to `packages/core` requires the Phase 4 waiver / governance update mandated by `packages/core/README.md`; the WS2 implementation PR must obtain that waiver (or amend the README governance) before the components land — this is now an explicit WS2 prerequisite, not an afterthought.
- Align `(workspace)` group pages to the concept shell (sidebar/topbar already close — mostly token cleanup).
- Token-lint pass: purge hardcoded brand hexes in the `(workspace)` group (target: 0 outside tokens).
- Acceptance: `(workspace)` renders from semantic tokens only; new components have unit tests; visual baseline captured.

### WS3 — my. portal day theme (Concept v3)

- Apply `operative-light` across `/portal/*` with the v3 reconciliations (warm paper, ink navy, daylight copper, sage/amber state set).
- AA contrast pass on light theme (state colors on tint backgrounds). **Known correction from tri-LLM review:** `#b5633a` on `#f6f2e9` measures ≈ 3.91:1 — acceptable for large text/UI accents only; small text in the copper family must use a darker step (target ≥ 4.5:1, e.g. `#9d5230`, to be verified with computed ratios during the AA pass).
- Cormorant headlines only on editorial blocks (mastheads), Inter for UI.
- Acceptance: Lighthouse accessibility ≥ 95 on portal home/billing/matters; visual baseline captured.

### WS4 — Governance

- Visual regression snapshots for 5 key screens (kita dashboard, clients, process; my portal home, matters) as CI gate.
- Token-lint CI rule for `(workspace)` + `/portal` groups blocking new hardcoded brand hexes.
- Hostname defaults unchanged. **Theme-key reconciliation (replaces the earlier "keep `bz-theme` override" note):** standardize on the single key `bz-theme` — pre-paint script, core ThemeProvider and appearance-settings page all read/write it; migrate the `theme` key readers/writers and one-time-copy any existing `theme` value into `bz-theme` on first load so no user loses a saved preference.

## 5. Suggested PR sequence after this plan

1. WS1: token merge + `FactBadge` component + tests (small, high leverage).
2. Token-lint CI rule (locks the win).
3. WS2 components: `SystemPulse` + `ComplianceRadar` first (highest daily-use value) — after the Phase 4 waiver.
4. WS3 portal light pass, page by page (portal home → matters → billing).

## 6. Contract compliance notes

- Docs + static HTML artifacts only; **no code changes**, no off-limits files touched, no PII (all rows use fictional names / CLI-#### IDs).
- Worktree discipline followed: `agent_start.py --lane docs --task-id garuda-os-unified-surfaces --base-branch origin/main` (worktree HEAD `8ccdddf2e2`).
- Local checkouts lag origin at authoring time (Air-M5 main 10 behind, Pro at #2813) — flagged to operator; this branch forks from fresh `origin/main`.
- Verification, testing and merge are reserved for the Claude verifier session.

## 7. Amendments after tri-LLM review (2026-07-19, `INCONCLUSIVE` round 1)

Addressed all five codex P1 findings:

1. **Legal doctrine (v1 concept):** corrected the Zantara mock answer — BKPM 5/2025 Art. 26 distinguishes total investment > IDR 10B from minimum paid-up capital **IDR 2.5B** (was incorrectly "minimum paid-up capital IDR 10B"). Same fix applied to the local v2/v3 artifacts.
2. **Currency (v1 concept):** replaced the Vietnamese đồng glyph `₫` with `Rp`/IDR everywhere including chart tooltips (7 occurrences). Same fix in local v2/v3.
3. **Theme persistence:** §3 now records the `bz-theme` vs `theme` split; WS4 reconciles on `bz-theme` with a one-time migration of saved `theme` values.
4. **WCAG AA (v3 note):** the `#b5633a` on `#f6f2e9` ≈ 3.91:1 claim corrected — copper family restricted to large text/UI; darker step for small text, verified in the WS3 AA pass.
5. **`packages/core` governance:** WS2 now makes the Phase 4 waiver / README governance update an explicit prerequisite for the four new components.

Plus two process fixes:

6. **Diff-size cure:** the round-1 diff (~128 KB) exceeded `--max-diff-chars 80000` and forced `diff_complete=False`. Concepts v2/v3 were removed from the PR (they remain local iteration artifacts; v2 is out-of-scope editorial study, v3's tokens are fully specified in §WS3). Diff is now ~48 KB → fully reviewable.
7. **inventory-check:** registered `PLAN.md` in `docs/DOCS_INVENTORY.md` (the row the gate's regen-diff expected).
