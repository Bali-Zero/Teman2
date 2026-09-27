# READY_FOR_REVIEW — ORACLE-PROD-20260927, Phase A (Dux Claude Opus 5.5, BLUE, Gear 3)

## Candidate
- **Code SHA `f38cbf469d7e6de53689b1584bd287afc48ad547`** — branch `agent/air-m5/mouth/oracle-prod-0927`, parent =
  origin/main `f36e245af2` (rebased clean). **Not pushed; no PR, arm, merge or deploy.**
- A docs-only child commit adds this directory's `*.md` and the
  Gear-3 evidence pack `evidence/2026-09/agent-air-m5-mouth-oracle-prod-0927-d995492b/`. The Dux QA harness sources
  (`qa/atlas-qa.local.spec.ts`, `qa/atlas-diag.local.spec.ts`) stay out of git (`*.local.*` is gitignored) — kept on M5 in this
  directory and executed from `apps/mouth/e2e/` on Mini. It touches no byte under
  `apps/`; its SHA is reported with this checkpoint (a tracked file cannot contain its own commit SHA).
- Frozen bytes: `CODE_FROZEN.md` v2, 35 files, aggregate sha256 `af611423607a76e130098faab20c553819d9ced6cbd9cbe4a7f9fa728ee184b9`.

## What changed (35 files, +5055 / −319, all under `apps/mouth`)
- New: `_lib/atlas-scenes.ts` (pure scene projection), `_components/OracleScenery.tsx` (decorative, `aria-hidden`),
  `_components/AtlasRoute.tsx` (native `<dialog>` route history → canonical `onEdit`/`onSelectCategory`), focused tests,
  19 approved WebPs byte-exact in `public/static/visa-oracle/atlas/`.
- Modified: `OracleShell.tsx` (markup/presentational state only), `QuestionScreen.tsx` (presentation props, world/permit
  stages, tile preview), `WhyWeAsk.tsx` (no internal metadata line), `OutcomeSheet.tsx` + `VerdictReveal`-copy (friendly
  ending), `i18n.ts` (listed value edits + additive keys, EN+ID), `oracle.css` (appended atlas section + final print block),
  two existing tests updated for approved copy (listed in the pack).
- Untouched by design: reducer/tree/fact-mapper, `engine-adapter.ts` + `engine-adapter.test.ts` (sibling #7504),
  evaluation/SHADOW/idempotency, consent/resume stores, telemetry, API routes, packages/lockfile, backend.

## Checks on the exact SHA (host Mini, true exit codes; full logs `/tmp/oracle-prod-0927/sha-f38cbf46…-run2/` on Mini)
CI-parity env exported before the build (`apps/mouth/playwright.config.ts:105-113` + `tests.yml` job env).

| Check | Result |
|---|---|
| `npm run build` (canonical: llms gen + `next build --webpack` + 2 bundle asserts) | exit 0, Next.js 16.3.4 (webpack) |
| `npx tsc --noEmit -p tsconfig.json` | exit 0, 0 errors |
| `npx vitest run "src/app/(visa-oracle)"` | exit 0, 50 files / 1324 tests (baseline 45 / 1229) |
| Atlas harness `e2e/atlas-qa.local.spec.ts` (EN/ID × desktop/mobile/narrow, 7 endings, stage geometry 1024/1280/320, dark, reduced motion + Pause, print) | exit 0, 34 passed |
| PR e2e gate (`tests.yml:2523` selection `--grep "page Page\|@offline"`) | exit 0, 134 passed, 1 skipped (existing opt-in `BZ_VISUAL_GALLERY`), 0 failed |
| ESLint on the route | NOT a pass: crashes on the clean baseline too (`eslint-plugin-react` `contextOrFilename.getFilename is not a function`, ESLint 10.11.0) |

Superseded run1 (same bytes) had gate 130/4 fail/1 skip because the verification script set the WhatsApp
`NEXT_PUBLIC_*` var only at `next start` and never `GARUDA_PUBLIC_ENABLED` — environmental, preserved at
`…-run1-env-incomplete`, closed by run2.

## Visual evidence
- Exact-SHA screenshots (126 jpg): Mini `/tmp/oracle-prod-0927/sha-f38cbf46…-run2/atlas/`, copied to `screens/sha-f38cbf46-run2/`
  (M5, not committed). Dux viewed world desktop (pins beside South America / "Indonesia", centred title, clean bottom row)
  and the SUPPORTED ending (friendly headline, closed "Why this fits" / "Legal references", visible empty consent box).
- Round evidence: `screens/qa1`–`qa3` (defects found), coordinator's qaEN/qaEN2 visual review
  (`/tmp/oracle-prod-0927-council/parent-visual-review-qaEN.md`, six findings, all closed with corrected screenshots).

## Reviews and dispositions
- Preliminary (snapshot before fixes): Sol provisional FAIL 1-4 → all ACCEPTED and implemented; Kimi 1-5 ACCEPTED;
  Qwen 2 ACCEPTED (= Kimi 1); Qwen 1 REJECTED (measured `useId()` = `_R_0_`, no colon); Qwen 3 REJECTED (arrival needs
  both readiness flags already true, monotonic while mounted); Qwen 4/5 no change (preserved behaviour). Detail:
  `FIX-ROUND-2.md` §C, `/tmp/oracle-prod-0927-dux-to-coordinator.md`.
- Final on f38cbf46 (v2 manifest af611423…): **Sol PASS, Kimi PASS, Qwen PASS** (`/tmp/oracle-prod-0927-council/final-{sol,kimi,qwen}.md` + receipt JSONs).
- Final on-disk gate: fresh independent Opus 5.5 xhigh, to be commissioned by the coordinator on the docs-commit SHA.

## Integration risks / notes for Phase B
1. origin/main moves: re-check drift and #7504 (still OPEN, touches only `engine-adapter.test.ts`) before push.
2. Merge ≠ live on mouth: production deploy is `scripts/vercel_prod_deploy.py` (promote-first) — prove live with the 19-asset
   byte check and a synthetic-driver journey (`traffic_source=synthetic_driver`, token via stdin only, no client sends).
3. Pro was unusable (swap filled the shared APFS container); all heavy checks ran on Mini. Deviation recorded in PROGRESS.md.
4. Bare `next build` (Turbopack) panics on mirror worktrees with symlinked `node_modules` (baseline too); production uses webpack.

Proposed PR line — `Bites: Visa Oracle visitors at /visa-oracle see the approved branching atlas, finish the canonical
interview, and receive the real production outcome; desktop/mobile screenshots and synthetic journey receipts prove it.`
