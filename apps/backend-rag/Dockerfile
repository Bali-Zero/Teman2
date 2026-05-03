# ZANTARA RAG Backend — Fly.io Deployment (OPTIMIZED FOR <8GB)
# Multi-stage build. Python 3.11 + FastAPI + Qdrant + Sentence Transformers.
#
# BUILD CONTEXT: monorepo root (set by `flyctl deploy --dockerfile apps/backend-rag/Dockerfile --config apps/backend-rag/fly.toml` in .github/workflows/fly-deploy.yml).
# Local: `docker build -f apps/backend-rag/Dockerfile -t rag-test .` FROM repo root, not from apps/backend-rag/.

# ========================================
# Stage 1: Build Stage
# ========================================
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy the cell-core workspace package (referenced as editable dep from
# apps/backend-rag/requirements-prod.txt as `-e ../../packages/cell-core`).
# Must be in place BEFORE pip install -r resolves that line.
COPY packages/cell-core /app/packages/cell-core

# Copy backend-rag directory (requirements files + any build-time helpers).
# Keeping the whole dir lets `pip install -r requirements-prod.txt` run
# from `/app/apps/backend-rag/` so the relative `-e ../../packages/cell-core`
# in the requirements file resolves to `/app/packages/cell-core` — the same
# path used by local dev and by CI (tests.yml, fly-deploy.yml). Single
# declaration site for cell-core, no more duplicated workaround.
COPY apps/backend-rag /app/apps/backend-rag

# Install Python dependencies (skip Playwright browsers to save ~500MB)
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
WORKDIR /app/apps/backend-rag
RUN pip install --no-cache-dir --user -r requirements-prod.txt \
    && find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type f -name "*.pyc" -delete \
    && find /root/.local -type f -name "*.pyo" -delete
WORKDIR /app

# ========================================
# Stage 2: Runtime Stage
# ========================================
FROM python:3.11-slim

# Install runtime dependencies:
# - curl + ca-certificates: healthcheck + HTTPS to Node repo
# - gnupg (build-only, removed after): Node.js repo GPG verification
# - nodejs 20.x: required by the `claude` CLI (Claude Code),
#   used by backend/llm/claude_oauth_client.py for Max OAuth calls.
# - @anthropic-ai/claude-code: Claude CLI installed globally.
#
# Project policy forbids ANTHROPIC_API_KEY (see
# memory/feedback_claude_oauth_only.md) — Max plan OAuth via `claude -p`
# subprocess is the only approved Claude transport.
# Image-size impact: Node.js ~90MB + CLI ~40MB ≈ +130MB on ~2GB base.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force \
    && apt-get remove -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* /root/.npm \
    && which claude && claude --version

# Create non-root user for security
RUN useradd -m -u 1000 nuzantara && \
    mkdir -p /app /data && \
    chown -R nuzantara:nuzantara /app /data

WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/nuzantara/.local

# Copy editable cell-core source (required for .egg-link to resolve at runtime)
COPY --from=builder /app/packages /app/packages

# Copy application code (paths relative to monorepo root)
COPY apps/backend-rag/backend ./backend
COPY apps/backend-rag/scripts ./scripts
COPY apps/backend-rag/training-data ./training-data
COPY apps/backend-rag/*.py ./

# Set Python path (cell-core included for explicit import resolution)
ENV PYTHONPATH=/app:/app/backend:/app/packages/cell-core:/home/nuzantara/.local/lib/python3.11/site-packages
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
