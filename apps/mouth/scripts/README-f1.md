# F1 — workspace a11y + perf scripts

Dev tooling used during the F1 workspace a11y + perf sweep
(branch `frontend/workspace-a11y-perf`).

Outputs land in `.artifacts/f1-baseline/` (git-ignored).

## Scripts

- `f1-baseline.mjs`
  - `@axe-core/playwright` + Lighthouse + screenshots over the 18
    `(workspace)` routes.
  - Env: `PLAYWRIGHT_BASE_URL` (default `http://127.0.0.1:3000`),
    `SKIP_LIGHTHOUSE=1`, `SKIP_WARMUP=1`.
- `f1-perf.mjs`
  - Measure JS transfer/decoded size + chunk count + LCP per route via
    Playwright Resource Timing.
  - Env: `PLAYWRIGHT_BASE_URL`, `LABEL=before|after`.
- `f1-summary.mjs`
  - Aggregate `axe-before-dev/` vs `axe/` and `perf/before.json` vs
    `perf/after.json`, print a delta table.
- `f1-shot.mjs`
  - Quick visual QA: 4 workspace routes via dev server (DEV BYPASS).

## Typical workflow

```bash
# 1. Baseline BEFORE (git checkout main, prod start at :3001):
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 LABEL=before node scripts/f1-perf.mjs
mv .artifacts/f1-baseline/axe .artifacts/f1-baseline/axe-before-dev

# 2. Apply fixes, rebuild, restart prod, baseline AFTER:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 LABEL=after node scripts/f1-perf.mjs
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 SKIP_LIGHTHOUSE=1 node scripts/f1-baseline.mjs

# 3. Compare:
node scripts/f1-summary.mjs
```

## Notes

- The Playwright runs use a fake admin profile (`localStorage.user_profile`)
  to skip the workspace login redirect on prod builds. Routes whose API
  loaders 401 will still bounce to `/login` — those are excluded from the
  apples-to-apples comparison in `f1-summary.mjs` (see `OK_ROUTES`).
- `axe-before-dev/` is the BEFORE snapshot; the AFTER snapshot lives in
  `axe/`.
- Dev-only; no runtime/import dependency from `src/`.
