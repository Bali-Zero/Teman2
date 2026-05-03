# Dockerfile `cell-core` install fix — PR #62

> **Date:** 2026-04-16
> **Type:** Infrastructure fix (not feature)
> **Branch:** `feature/dockerfile-cellcore-fix-2026-04-16`
> **Closes:** Scar left by PR #56 (CI fixed, Dockerfile not)
> **Approved approach:** Option C — monorepo-root build context via `flyctl deploy --dockerfile ... --config ...`

---

## 1. Problem

The Docker image deployed to `nuzantara-rag` on Fly.io does **not** contain the `cell-core` package. Consequently, three recently-shipped routers run in degraded mode in production:

| Router              | Shipped in   | Runtime status                            |
| ------------------- | ------------ | ----------------------------------------- |
| `/api/skill/*`      | PR #55       | 200 with fake data (`total=0` always)     |
| `/api/experience/*` | PR #54       | 200 with fake data                        |
| `/api/metabolic/*`  | PR #60 / #61 | 503 `"cell_core.metabolic not available"` |

Verified live on 2026-04-16:

```bash
$ flyctl ssh console --app nuzantara-rag -C 'python -c "from cell_core.genome import Genome"'
ModuleNotFoundError: No module named 'cell_core'
```

### Root cause

`apps/backend-rag/Dockerfile` installs only `requirements-prod.txt` (no `cell-core`) and copies only `backend/`, `scripts/`, `training-data/`, `*.py` in the runtime stage. The `packages/cell-core/` directory sits **outside the Fly build context**, which defaults to the `fly.toml` directory (`apps/backend-rag/`).

PR #56 (commit `31ec067b8`) fixed the same issue in **CI only** (`tests.yml`, `fly-deploy.yml` gate) via `pip install -e ../../packages/cell-core`. It did not touch the Dockerfile. This design closes the loop.

## 2. Goal

Make `cell_core` importable inside the deployed container, without:

- touching `fly.toml` (per `CLAUDE.md` rule: off-limits)
- touching `zantara_core.py` (off-limits)
- adding runtime dependencies beyond what `cell-core` already requires (its `pyproject.toml` declares `dependencies = []`)
- inflating the image by more than 5 MB
- breaking existing Docker build cache for the large pip layer
- removing graceful-degradation fallbacks inside services (SYMBIOSIS Legge 4)

### Success criteria

1. `flyctl ssh console ... -C 'python -c "import cell_core.genome; import cell_core.metabolic; import cell_core.hgt; print(OK)"'` prints `OK`.
2. `GET /api/metabolic/stats` returns 200 with a real JSON body (no longer 503).
3. `GET /api/skill/stats` returns 200 with real counts from SQLite (no longer the fake empty structure).
4. `GET /api/experience/query` returns 200 against a real trajectory.
5. `GET /health` healthy for 30 consecutive minutes post-deploy.
6. Image size delta < 5 MB vs the currently-deployed image.
7. Build time delta < 30 s.
8. CI `tests.yml` and `fly-deploy.yml` remain green.
9. Red team (`./scripts/ai-dispatch.sh redteam ...`) approves before merge.

### Explicit non-goals (deferred to a future PR)

- **SQLite persistence across rolling deploys.** The `api` process has no `/data` volume mount; `METABOLIC_DB_PATH` defaults to `~/.agent/decisions/organism_metrics.db` and `EXPERIENCE_DB_PATH` to `~/.nuzantara/experience.db`, both inside the container filesystem. Snapshots and recorded trajectories will be **wiped on every rolling deploy**. Handling this requires adding `[[mounts]] processes = ['api']` to `fly.toml`, which is off-limits without explicit escalation to Zero. Tracked as a follow-up brief.
- **Metric baselines (SYMBIOSIS Pilastro 7 T0 capture).** Capturable only after persistence is resolved.
- Changes to `requirements-prod.txt` dependency list (cell-core brings no new deps).

## 3. Architecture — Option C

### Summary

Move the Fly build context from `apps/backend-rag/` to **monorepo root** by passing the context path to `flyctl deploy` via CLI flags (`--dockerfile`, `--config`), rather than editing `fly.toml [build]`. The Dockerfile paths are rewritten to be relative to monorepo root. A new root-level `.dockerignore` keeps the context slim by whitelisting only `apps/backend-rag/` and `packages/cell-core/`.

### Why not A or B

- **Option A** (stage `packages/cell-core` under `apps/backend-rag/vendor/` via CI copy): introduces staging logic that must be duplicated in `tests.yml`, `fly-deploy.yml`, and any local reproduction. Cognitively smellier (fake vendor dir vs real monorepo).
- **Option B** (pre-built wheel published into `apps/backend-rag/wheels/`): adds wheel-versioning burden with zero runtime benefit (cell-core has no external deps). Creates dev/prod divergence relative to the editable install pattern already used in CI.
- **Option C** mirrors the CI pattern (`pip install -e ../../packages/cell-core`) in the Docker build — **one mental model**.

### Build context diagram

```
BEFORE (broken)
  Fly build context: apps/backend-rag/
    └─ backend/ scripts/ training-data/ requirements-prod.txt Dockerfile
       (packages/cell-core/ is INVISIBLE — outside context)

AFTER (Option C)
  Fly build context: <monorepo root>
    ├─ apps/backend-rag/           (whitelisted in root .dockerignore)
    │  └─ backend/ scripts/ training-data/ requirements-prod.txt Dockerfile
    └─ packages/cell-core/         (whitelisted in root .dockerignore)
       └─ cell_core/ pyproject.toml
```

## 4. File-level changes (atomic PR)

| File                                     | Change type     | Notes                                                                                                                                                                                                                                                          |
| ---------------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/backend-rag/Dockerfile`            | MODIFY          | COPY paths rewritten with `apps/backend-rag/...` prefix; add cell-core COPY + editable install layer after `requirements-prod.txt` install (cache-preserving); runtime stage also COPIES `/app/packages`; `PYTHONPATH` extends with `/app/packages/cell-core`. |
| `.github/workflows/fly-deploy.yml`       | MODIFY          | `deploy` job: remove `working-directory: apps/backend-rag`; invoke `flyctl deploy` from repo root with `--dockerfile apps/backend-rag/Dockerfile --config apps/backend-rag/fly.toml`.                                                                          |
| `.dockerignore` (root)                   | REPLACE         | Current root `.dockerignore` appears oriented to a mouth-Vercel flow. Audit needed (see §5). Rewrite to whitelist only `apps/backend-rag/` + `packages/cell-core/` and exclude the rest.                                                                       |
| `apps/backend-rag/.dockerignore`         | KEEP (annotate) | Fly will no longer use this once context moves to repo root, but leave it in place with a one-line `# NOTE:` comment pointing at the new authoritative root `.dockerignore`.                                                                                   |
| `apps/backend-rag/fly.toml`              | NO CHANGE       | `[build] dockerfile = 'Dockerfile'` remains; `flyctl deploy --dockerfile` overrides.                                                                                                                                                                           |
| `apps/backend-rag/requirements-prod.txt` | NO CHANGE       | cell-core has `dependencies = []`.                                                                                                                                                                                                                             |
| `backend/` source code                   | NO CHANGE       | Graceful-degradation fallbacks (`_GENOME_AVAILABLE`) remain — Legge 4.                                                                                                                                                                                         |

### 4.1 Dockerfile sketch

```dockerfile
# ZANTARA RAG Backend — Fly.io Deployment (OPTIMIZED FOR <8GB)
# Multi-stage build. Python 3.11 + FastAPI + Qdrant + Sentence Transformers.
# Build context: monorepo root (set by flyctl deploy --dockerfile flag).

FROM python:3.11-slim as builder
RUN apt-get update && apt-get install -y build-essential curl \
    && rm -rf /var/lib/apt/lists/* && apt-get clean
WORKDIR /app

COPY apps/backend-rag/requirements-prod.txt .
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN pip install --no-cache-dir --user -r requirements-prod.txt \
    && find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type f -name "*.pyc" -delete \
    && find /root/.local -type f -name "*.pyo" -delete

# cell-core editable install (last; preserves pip layer cache)
COPY packages/cell-core /app/packages/cell-core
RUN pip install --no-cache-dir --user -e /app/packages/cell-core

FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 nuzantara && mkdir -p /app /data \
    && chown -R nuzantara:nuzantara /app /data
WORKDIR /app

COPY --from=builder /root/.local /home/nuzantara/.local
COPY --from=builder /app/packages /app/packages
COPY apps/backend-rag/backend ./backend
COPY apps/backend-rag/scripts ./scripts
COPY apps/backend-rag/training-data ./training-data
COPY apps/backend-rag/*.py ./

ENV PYTHONPATH=/app:/app/backend:/app/packages/cell-core:/home/nuzantara/.local/lib/python3.11/site-packages
ENV PATH=/home/nuzantara/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

RUN find /home/nuzantara/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /home/nuzantara/.local -type f -name "*.pyc" -delete \
    && find /home/nuzantara/.local -type f -name "*.pyo" -delete \
    && find /home/nuzantara/.local -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /home/nuzantara/.local -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && rm -rf /home/nuzantara/.local/share/playwright 2>/dev/null || true

RUN chown -R nuzantara:nuzantara /app
USER nuzantara
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1
CMD sh -c "uvicorn backend.app.main_cloud:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"
```

Notes:

- `CMD` keeps `main_cloud:app` (current default). `fly.toml [processes]` overrides at runtime with `main_api:app` / `main_rag:app` — unchanged.
- cell-core install layer is placed **after** the large `requirements-prod.txt` pip layer so that changes to cell-core do not invalidate the expensive ML dependency layer.

### 4.2 `fly-deploy.yml` deploy-step rewrite

```yaml
deploy:
  name: Fly.io rolling deploy
  needs: run-migrations
  runs-on: ubuntu-latest
  env:
    FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
    FLY_ACCESS_TOKEN: ${{ secrets.FLY_API_TOKEN }}
  steps:
    - uses: actions/checkout@v4
    - uses: superfly/flyctl-actions/setup-flyctl@master
    - name: Deploy (rolling strategy, monorepo context)
      run: |
        flyctl deploy \
          --strategy rolling \
          --app nuzantara-rag \
          --remote-only \
          --dockerfile apps/backend-rag/Dockerfile \
          --config apps/backend-rag/fly.toml
```

Key changes vs current:

- Dropped `working-directory: apps/backend-rag`; step now runs from repo root.
- Added `--dockerfile` and `--config` flags so Fly uses monorepo root as context while still finding Dockerfile + fly.toml.

### 4.3 Root `.dockerignore` sketch

```dockerignore
# Build context: monorepo root (flyctl deploy --dockerfile apps/backend-rag/Dockerfile)
# Whitelist approach: exclude everything, then re-include what the backend image needs.

*

!apps/backend-rag/backend/
!apps/backend-rag/scripts/
!apps/backend-rag/training-data/
!apps/backend-rag/requirements-prod.txt
!apps/backend-rag/requirements.txt
!apps/backend-rag/Dockerfile
!apps/backend-rag/*.py
!packages/cell-core/

# Exclude noise inside included dirs
**/__pycache__/
**/*.pyc
**/*.pyo
**/*.pyd
**/.DS_Store
**/*.log
**/.pytest_cache/
**/.venv/
**/venv/
**/node_modules/

# Tests and dev-only files
apps/backend-rag/backend/tests/
apps/backend-rag/backend/.env*
packages/cell-core/tests/

# Secrets (defense in depth)
**/google_credentials.json
**/*credentials*.json
**/*.pem
**/*.key
**/.env
**/.env.*

# Large binaries
**/*.pdf
**/*.docx
**/*.xlsx
**/*.zip
**/*.tar.gz
**/*.jpg
**/*.png
**/*.gif
**/*.mp4
**/*.mov
```

## 5. Risks and mitigations

### 5.1 Root `.dockerignore` may conflict with other Docker builds

The current root `.dockerignore` is scoped to `apps/mouth/`. Risk: replacing it could break another build that depends on its current whitelist.

**Mitigation:**

- Audit before writing: `grep -rn "docker build\|flyctl deploy\|Dockerfile" .github/workflows/` to list every Docker build in CI.
- Confirm that `apps/mouth/` deploys via Vercel (frontend), not Docker — in which case the current root `.dockerignore` is dead code (Vercel ignores `.dockerignore`).
- If any other Docker build uses the root `.dockerignore`, merge carefully instead of replacing.
- If uncertain, fall back to a Dockerfile-named `.dockerignore` alternative: `apps/backend-rag/Dockerfile.dockerignore` with a `# syntax=docker/dockerfile:1.7` directive — BuildKit will pick it up for this Dockerfile only. Decision recorded during implementation.

### 5.2 Build context size explosion

Monorepo root contains node_modules across apps, `.git`, docs, large KB files. Without strict `.dockerignore`, `flyctl deploy` could upload 500+ MB of irrelevant context.

**Mitigation:** root `.dockerignore` above uses exclude-all-then-whitelist. Verify with `docker build --progress=plain -f apps/backend-rag/Dockerfile . 2>&1 | grep "transferring context"` locally; expected < 100 MB.

### 5.3 Build cache invalidation

Every dependency-layer cache invalidation costs ~3–4 min of rebuild (ML stack is heavy).

**Mitigation:**

- The cell-core COPY is placed **after** `requirements-prod.txt` install, so changes to cell-core do not invalidate the expensive pip layer.
- The `requirements-prod.txt` path changes from `COPY requirements-prod.txt .` to `COPY apps/backend-rag/requirements-prod.txt .`. This **will** invalidate the pip layer once at the first post-merge deploy. Acceptable one-time cost.

### 5.4 PYTHONPATH ordering

`cell_core` is now reachable both via the editable-install site-packages (user `/home/nuzantara/.local/...`) and via the explicit `/app/packages/cell-core` entry. Order: `/app:/app/backend:/app/packages/cell-core:/home/nuzantara/.local/...`. This ensures service-level imports (e.g. `from cell_core.genome import Genome`) resolve deterministically; duplicate path resolution is harmless for Python.

### 5.5 Image size

cell-core source is ~50 KB. Editable install creates a small `.egg-link`. Image delta expected < 1 MB.

**Mitigation:** assert `docker images` delta < 5 MB in pre-deploy local test.

### 5.6 `apps/backend-rag/.dockerignore` now dead

Fly no longer uses it once context is root. Leaving it in place is safe but confusing for future readers.

**Mitigation:** add a top-of-file `# NOTE:` comment pointing to the authoritative root `.dockerignore`. Do not delete (preserves history and local `docker build` reproducibility scoped to the subdir, if ever used).

### 5.7 Local dev Docker builds

Anyone running `cd apps/backend-rag && docker build -t rag-test .` after this change will fail — the Dockerfile now assumes repo-root context.

**Mitigation:** update `apps/backend-rag/CLAUDE.md` Deploy Checklist section with a one-liner: `docker build -f apps/backend-rag/Dockerfile -t rag-test .` **from repo root**, not from `apps/backend-rag/`.

### 5.8 Preserving graceful degradation

SYMBIOSIS Legge 4: if cell-core imports fail at runtime, services must not crash the app; they degrade. Current services have `_GENOME_AVAILABLE` guards; this PR must not remove them.

**Mitigation:** no backend code changes in this PR. Guards remain.

## 6. Testing plan

### 6.1 Local pre-commit (Air)

1. `cd ~/Projects/nuzantara && docker build -f apps/backend-rag/Dockerfile -t rag-test .` — builds cleanly.
2. `docker run --rm rag-test python -c "import cell_core.genome; import cell_core.metabolic.service; import cell_core.hgt; print('OK')"` — prints `OK`.
3. `docker images rag-test` — record size; capture delta vs currently-deployed `nuzantara-rag:latest`.
4. Record build timings (before vs after).

### 6.2 CI gates (no change needed)

- `tests.yml` already does `pip install -e ../../packages/cell-core` — keep as-is.
- `fly-deploy.yml` pre-deploy-gate already does the same — keep as-is.
- Import chain gate: `python -c "from backend.app.dependencies import get_current_user"` remains untouched.

### 6.3 Red team (required per SYMBIOSIS Legge 12)

```bash
./scripts/ai-dispatch.sh redteam \
  "Dockerfile monorepo context switch + cell-core editable install (PR #62)"
```

Must return "approved" before merge.

### 6.4 Post-deploy smoke tests (required)

Existing `post-deploy-health` job covers `/health` with auto-rollback. Additional manual smoke after merge:

```bash
# 1. Module import chain
flyctl ssh console --app nuzantara-rag \
  -C 'python -c "import cell_core.genome; import cell_core.metabolic; import cell_core.hgt; print(OK)"'

# 2. Three endpoint verifications
API_KEY="<from .env>"
curl -sf -H "X-API-Key: $API_KEY" https://nuzantara-rag.fly.dev/api/metabolic/stats | jq .
curl -sf -H "X-API-Key: $API_KEY" https://nuzantara-rag.fly.dev/api/skill/stats | jq .
curl -sf -H "X-API-Key: $API_KEY" https://nuzantara-rag.fly.dev/api/experience/query | jq .
```

Success criteria (§2) must be satisfied. If any endpoint regresses: rollback via `flyctl releases rollback --app nuzantara-rag --yes`.

## 7. Rollback plan

- Automatic: `post-deploy-health` job rolls back on `/health` failure.
- Manual: `flyctl releases rollback --app nuzantara-rag --yes`.
- No data-layer changes in this PR; rollback is safe.

## 8. Documentation updates

Included in the PR:

1. `apps/backend-rag/CLAUDE.md` — Critical Gotchas: add entry about monorepo-root Docker build context, one-line warning that local `docker build` must run from repo root.
2. `.claude/rules/cicatrix-scars.md` — mark PR #56 scar resolved with a dated entry (`Resolved: 2026-04-16 via PR #62`).

## 9. Out of scope (future work)

- **SQLite persistence across rolling deploys** for `api` process (requires `[[mounts]] processes = ['api']` in `fly.toml`; off-limits without Zero escalation).
- **Metric baseline capture** (SYMBIOSIS Pilastro 7 T0) — blocked on persistence.
- **KBLI ingest or any data migrations** — unrelated.

## 10. Links

- Closes scar from PR #56 (commit `31ec067b8`).
- Related PRs: #54 (Experience), #55 (Skill), #57 (Sprint parallel), #60 / #61 (Metabolic wire-up).
- References: `SYMBIOSIS.md` Legge 4 (graceful degradation), Legge 7 (numbers before), Legge 12 (red team mandatory).

---

**Author:** Claude Opus 4.6 (1M context), Air session, 2026-04-16
**Approved approach:** Option C
**Status:** design ready for user review → writing-plans
