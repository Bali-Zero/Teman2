# syntax=docker/dockerfile:1.7
# ZANTARA RAG Backend — Fly.io Deployment (OPTIMIZED FOR <8GB)
# Multi-stage build. Python 3.11 + FastAPI + Qdrant + Sentence Transformers.
#
# BUILD CONTEXT: monorepo root (set by `flyctl deploy --dockerfile apps/backend-rag/Dockerfile --config apps/backend-rag/fly.toml` in .github/workflows/fly-deploy.yml).
# Local: `docker build -f apps/backend-rag/Dockerfile -t rag-test .` FROM repo root, not from apps/backend-rag/.
#
# BuildKit cache mounts (added 2026-05-18, switched to uv 2026-05-19):
# uv cache mounted at /root/.cache/uv. Cache persists across builds, drastically
# reducing rebuild time for ML deps (torch + transformers + sentence-transformers).
# uv is 10-100× faster than pip for resolution + install, and `--require-hashes`
# against `requirements-prod.lock.txt` guarantees reproducible builds (hash-pinned).
# See apps/backend-rag/docs/uv-migration.md for the full migration rationale.

# ========================================
# Stage 1: Build Stage
# ========================================
FROM python:3.11-slim as builder

# Install build dependencies + uv (Astral's Rust-based pip replacement).
# uv is installed via pip into the builder stage's system Python; it is
# only used for installing dependencies into /root/.local and never ships
# in the runtime image.
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && pip install --no-cache-dir uv

WORKDIR /app

# Copy the cell-core workspace package (referenced as editable dep from
# apps/backend-rag/requirements-prod.lock.txt as `-e ../../packages/cell-core`).
# Must be in place BEFORE uv pip install -r resolves that line.
COPY packages/cell-core /app/packages/cell-core

# Copy backend-rag directory (requirements files + any build-time helpers).
# Keeping the whole dir lets `uv pip install -r requirements-prod.lock.txt`
# run from `/app/apps/backend-rag/` so the relative
# `-e ../../packages/cell-core` in the lock file resolves to
# `/app/packages/cell-core` — the same path used by local dev and by CI
# (tests.yml, fly-deploy.yml). Single declaration site for cell-core.
COPY apps/backend-rag /app/apps/backend-rag

# Install Python dependencies via uv (skip Playwright browsers to save ~500MB).
# `--require-hashes` enforces SHA256 verification of every wheel against the
# hashes recorded in requirements-prod.lock.txt — any PyPI re-upload or MITM
# fails the build. To regenerate the lock: see docs/uv-migration.md.
#
# Layout: uv `--prefix /root/.local` installs into the exact same shape that
# `pip install --user` produced (uv has no `--user` flag): lib/python3.11/
# site-packages + bin/. The runtime stage then COPYs /root/.local intact to
# /home/nuzantara/.local — PATH and PYTHONPATH already point there. Drop-in
# replacement for the previous `pip install --user` line.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
WORKDIR /app/apps/backend-rag
# uv --require-hashes does NOT accept editable installs (no hashes possible
# on local paths). cell-core was stripped from the lock and is installed
# separately AFTER the hashed deps.
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install --prefix /root/.local -r requirements-prod.lock.txt \
    && uv pip install --prefix /root/.local -e ../../packages/cell-core \
    && { find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true; } \
    && find /root/.local -type f -name "*.pyc" -delete \
    && find /root/.local -type f -name "*.pyo" -delete
WORKDIR /app

# ========================================
# Stage 1b: Node 22 donor
# ========================================
# `@anthropic-ai/claude-code` declares `engines: { node: ">=22.0.0" }`. Debian
# trixie's own `nodejs` package is 20.19.2, so installing it from apt produced
# `npm WARN EBADENGINE ... required: >=22.0.0, current: v20.19.2` — the CLI ran
# well enough to print its version and was, by its own declaration, unsupported.
# That is not a cosmetic warning: backend/llm/claude_oauth_client.py shells out to
# this CLI for Max-plan OAuth, the Anthropic paid API is banned by project policy,
# and so there is no fallback transport behind it.
#
# `-trixie-slim` is chosen, not `-slim`: it is the SAME Debian release as this
# image's base (confirmed by the `deb13uN` package suffixes in the build log), so
# the copied binary meets the glibc it was built against by construction rather
# than by luck. It is also a first-party Docker Hub official image, from the same
# registry and trust domain as `python:3.11-slim` above — deliberately NOT a
# third-party APT repository, which is exactly what 403'd on 2026-07-27 and broke
# this build. Debian `trixie-backports` was checked first and does not exist (404),
# so this is the only route that avoids a third-party host.
FROM node:22-trixie-slim AS node22

# ========================================
# Stage 2: Runtime Stage
# ========================================
FROM python:3.11-slim

# Install runtime dependencies:
# - curl + ca-certificates: healthcheck
# - nodejs + npm: required by the `claude` CLI (Claude Code), used by
#   backend/llm/claude_oauth_client.py for Max OAuth calls.
# - @anthropic-ai/claude-code: Claude CLI installed globally.
#
# Project policy forbids ANTHROPIC_API_KEY (see
# memory/feedback_claude_oauth_only.md) — Max plan OAuth via `claude -p`
# subprocess is the only approved Claude transport.
#
# NODE DOES NOT COME FROM NODESOURCE (changed 2026-07-28). The third-party
# NodeSource APT repo began answering 403 that evening and broke this build
# INTERMITTENTLY — `Snyk Docker Security` failed at 19:57, 19:58, 20:06, 20:20 and
# 20:24, and was building again by 20:42 on main with this file unchanged.
#
# That correction matters, because an earlier revision of this comment said the
# image "stopped building", which overstated it: what was actually measured was a
# window of failures ("7 successes through 19:39, failures from 19:58"), read as a
# steady state without checking for recovery. An intermittent third-party
# dependency inside a production image build is a *better* reason to delete it than
# a permanent one — a break that comes and goes leaves no lasting red for anyone to
# notice, which is precisely how this went unseen (see the alarm added to
# security.yml's snyk-docker job).
#
# Probed from outside CI, so it was not a runner artifact:
#
#   403  https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key
#   403  https://deb.nodesource.com/node_20.x/dists/nodistro/Release
#   200  https://deb.nodesource.com/            <- the site itself is up
#   200  https://deb.nodesource.com/setup_20.x
#
# Note what that scope ruled out: vendoring the GPG key would NOT have fixed it,
# because the repository path was 403 too. The dependency itself is the defect.
#
# Node now comes from the `node22` stage above, NOT from apt. An earlier revision of
# this comment claimed Debian trixie "ships nodejs 20.19.2, exactly the 20.x this
# CLI needs" — that was simply wrong: the CLI declares `node >=22.0.0`, and apt's
# 20.19.2 made every build warn `EBADENGINE` while still succeeding. Only `curl` and
# `ca-certificates` (for HEALTHCHECK) still come from apt.
#
# Copying `bin/node` + `lib/node_modules` is what a working node+npm needs; the npm
# symlink is what the official image itself creates. `npm install -g` then resolves
# to the same /usr/local prefix as before, so `claude` still lands on
# /usr/local/bin/claude and nothing downstream moves.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node22 /usr/local/bin/node /usr/local/bin/node
COPY --from=node22 /usr/local/lib/node_modules /usr/local/lib/node_modules

# The major-version check is a GATE, not decoration: if this image ever silently
# regresses to a node < 22, the build must fail HERE rather than ship a CLI running
# on an engine it declares unsupported. `npm install -g` is deliberately AFTER it.
#
# Compared NUMERICALLY on the major, not matched against a version-shaped regex. The
# first draft used `grep -Eq '^v(2[2-9]|[3-9][0-9])\.'`, which reads correctly and
# would have rejected node v100 — a range written as a pattern is a form standing in
# for a quantity, and it goes wrong at exactly the boundary nobody tests.
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && node --version && npm --version \
    && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 22 ] \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force \
    && rm -rf /root/.npm \
    && node --version && which claude && claude --version

# Create non-root user for security
RUN useradd -m -u 1000 nuzantara && \
    mkdir -p /app /data && \
    chown -R nuzantara:nuzantara /app /data

WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/nuzantara/.local

# Copy editable cell-core source (required for .egg-link to resolve at runtime)
COPY --from=builder /app/packages /app/packages

# Copy crm-cell source so backend in-process HGT handlers can import
# crm_cell.* at runtime without relying on external PYTHONPATH state.
COPY apps/crm-cell/crm_cell /app/apps/crm-cell/crm_cell

# Copy application code (paths relative to monorepo root)
COPY apps/backend-rag/backend ./backend
COPY apps/backend-rag/scripts ./scripts
COPY apps/backend-rag/training-data ./training-data
COPY apps/backend-rag/*.py ./

# Copy KBLI data files needed by the two Qdrant indexers
# (backend/scripts/index_kbli_gold_content.py + reindex_kbli_2025_final.py).
# Both resolve the repo root by walking up from __file__ looking for these
# marker files; without them in the image the walk exhausts and the scripts
# crash — they cannot run where their credentials (QDRANT_URL, OPENAI_API_KEY)
# actually live.
COPY apps/kbli-navigator/lib/kbli-gold-content.ts ./apps/kbli-navigator/lib/kbli-gold-content.ts
COPY apps/kbli-navigator/data/kbli-2025.json ./apps/kbli-navigator/data/kbli-2025.json
COPY data/source_documents/KBLI_2025_FINAL_CLEAN.json ./source_documents/KBLI_2025_FINAL_CLEAN.json

# Set Python path (cell-core included for explicit import resolution)
ENV PYTHONPATH=/app:/app/backend:/app/packages/cell-core:/app/apps/crm-cell:/home/nuzantara/.local/lib/python3.11/site-packages
ENV PATH=/home/nuzantara/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Aggressive cleanup to reduce image size
RUN find /home/nuzantara/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /home/nuzantara/.local -type f -name "*.pyc" -delete \
    && find /home/nuzantara/.local -type f -name "*.pyo" -delete \
    && find /home/nuzantara/.local -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /home/nuzantara/.local -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && rm -rf /home/nuzantara/.local/share/playwright 2>/dev/null || true

# Change ownership of all files to non-root user.
# CRITICAL: includes /home/nuzantara so that the `claude` CLI (Claude Code)
# can create its cache under ~/.claude. Without this, the CLI hangs on
# first invocation waiting for writable HOME (see commit message of
# the preceding Dockerfile change for full context).
RUN mkdir -p /home/nuzantara/.claude \
    && chown -R nuzantara:nuzantara /app /home/nuzantara

# Switch to non-root user
USER nuzantara

# Expose port (use PORT env var, default to 8080 for Fly.io)
EXPOSE 8080

# Health check (model downloads on first request, not at startup)
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Start uvicorn from root directory using module path.
# Bind to 0.0.0.0 (all IPv4 interfaces, Fly.io compatible). Use PORT env var.
# CRITICAL: 1 worker only — each worker loads ~2GB of ML models.
# fly.toml [processes] overrides CMD at runtime (main_api:app for api, main_rag:app for rag).
CMD sh -c "uvicorn backend.app.main_cloud:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"
