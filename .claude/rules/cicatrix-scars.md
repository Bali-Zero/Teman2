# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

### ⚠️ SCAR: Dockerfile cell-core missing (PR #56 CI-only fix)

_Discovered: 2026-04-15 · Fixed: 2026-04-16 via PR #62_

**TRAUMA:** PR #56 (commit `31ec067b8`) fixed the `from cell_core import ...`
ImportError in CI (`tests.yml`, `fly-deploy.yml` pre-deploy gate) by adding
`pip install -e ../../packages/cell-core`. It did NOT touch
`apps/backend-rag/Dockerfile`. Consequence: the deployed image still lacked
`cell-core`, making `/api/skill/*`, `/api/experience/*`, and `/api/metabolic/*`
run in degraded mode (fake empty responses, or 503 for metabolic).

**ANTIBODY:** The Fly build context is now the monorepo root (set via
`flyctl deploy --dockerfile apps/backend-rag/Dockerfile --config apps/backend-rag/fly.toml`
in `.github/workflows/fly-deploy.yml`). The Dockerfile copies
`packages/cell-core/` into the image and `pip install -e`s it, mirroring the
CI pattern. Root `.dockerignore` scopes the context to
`apps/backend-rag/` + `packages/cell-core/`.

**GOTCHA:** Local `docker build` must now run from the repo root, not from
`apps/backend-rag/`. See `apps/backend-rag/CLAUDE.md` → "Docker Build Context —
Monorepo Root".
