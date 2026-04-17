# Air A3 — Ruff Triage (backend/app/)

**Date:** 2026-04-18
**Branch:** `devops/deploy-rollback-hardening`
**Scope:** `apps/backend-rag/backend/app/` (FastAPI app layer — routers, services, deps, setup)
**Ruff version:** 0.15.8

## Before (on `origin/main` @ `e1584d8ef`)

```
ruff check backend/app/ --statistics
→ 22 errors total
   9  I001    [*] unsorted-imports              (auto-fixable, cosmetic)
   7  F401    [*] unused-import                 (auto-fixable, dead code)
   5  E402    [ ] module-import-not-at-top      (manual, often intentional)
   1  ARG001  [ ] unused-function-argument      (manual, FastAPI handler shape)
```

### Per-family breakdown

**F401 — 7 occurrences, all auto-fixable:**
- 5× `asyncio` imported but never used (copy-paste from async router scaffold):
  `auth.py`, `conversations.py`, `crm_clients.py`, `crm_enhanced_documents.py`, `crm_practices.py`
- 1× `can_view_all_clients` in `crm_clients.py` (dead RBAC import — RBAC enforced via `require_crm_admin` instead)
- 1× `TrajectoryOutcome` in `experience.py` (dead model import)

**I001 — 9 occurrences:** import sort/format drift in `deps/services.py`, 5 routers, `health.py`, `hr.py`, `workspace_inbox.py`, `api_key_auth.py`. Deferred — cosmetic, large diff, low signal.

**E402 — 5 occurrences:** all in `api_key_auth.py` (4) + `dynamic_pricing.py` (1). Require case-by-case review (often intentional: `load_dotenv()` before imports, or conditional guards). Deferred.

**ARG001 — 1 occurrence:** `rag_proxy.py:179` `full_path` parameter — FastAPI catch-all mount, param is used by the framework's path routing. **Keep** (false positive from Ruff's perspective).

## Action taken

1. `ruff check --fix --select F401 backend/app/` → 7 fixed, 0 remaining. 6 files touched (`-7 imports`, `+1` reformat blank line).
2. Import-chain gate re-verified: `from backend.app.dependencies import get_current_user` + 6 modified routers load cleanly with dummy JWT/API env vars.
3. Promoted **F401** to the blocking tier in `.github/workflows/fly-deploy.yml`:
   - Old blocking set: `F821,F822,F823`
   - New blocking set: `F401,F821,F822,F823`
   - Rationale: unused imports are cheap to prevent and they surface typo'd
     re-exports before they hit runtime. No false positives encountered on
     the current codebase.

## After

```
ruff check backend/app/ --statistics
→ 15 errors total
   9  I001    [*] unsorted-imports              (deferred — cosmetic)
   5  E402    [ ] module-import-not-at-top      (deferred — per-file review)
   1  ARG001  [ ] unused-function-argument      (keep — FastAPI path param)

ruff check backend/app/ --select F401,F821,F822,F823
→ All checks passed!   ← new blocking tier is green
```

## Follow-ups (out of scope for this PR)

- **I001 sweep** — single commit auto-fix via `ruff check --fix --select I001 backend/app/`, review sort orders (isort-compatible). Estimated diff: ~50 files touched, trivial hunks.
- **E402 in `api_key_auth.py`** — verify whether the pre-import `load_dotenv()` pattern is still needed now that `backend/core/config.py` is the SSOT for env. Likely safe to hoist imports and delete the guard.
- **E402 in `dynamic_pricing.py`** — inspect the singleton-init guard; may be promotable to a module-level `functools.cache`'d factory.
- **Expand blocking scope** once the above land: add `I001` to the blocking tier after the one-off cleanup so sort drift stays caught in PR review.

## Numbers (Legge 7 — "Numeri prima")

| Metric                       | Before | After | Δ   |
| ---------------------------- | ------ | ----- | --- |
| Total ruff errors            | 22     | 15    | −7  |
| F401 count                   | 7      | 0     | −7  |
| Blocking-tier errors         | 0      | 0     | 0   |
| Fixable `--fix` errors       | 16     | 9     | −7  |
| Files modified by auto-fix   | —      | 6     | +6  |
| Lines removed (unused imports)| —     | 7     | −7  |
