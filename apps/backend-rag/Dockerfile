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

# Copy requirements (path relative to monorepo root)
COPY apps/backend-rag/requirements-prod.txt .

# Install Python dependencies (skip Playwright browsers to save ~500MB)
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN pip install --no-cache-dir --user -r requirements-prod.txt \
    && find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type f -name "*.pyc" -delete \
    && find /root/.local -type f -name "*.pyo" -delete

# cell-core (DNA-recording package: Genome, Experience, Skill, Metabolic, HGT).
# Installed editable AFTER the large ML pip layer so cell-core changes don't
# invalidate that cache. Editable install matches the pattern used in CI
# (tests.yml + fly-deploy.yml gate). Closes PR #56 scar.
COPY packages/cell-core /app/packages/cell-core
RUN pip install --no-cache-dir --user -e /app/packages/cell-core

# ========================================
# Stage 2: Runtime Stage
# ========================================
FROM python:3.11-slim

# Install only runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

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

# Change ownership of all files to non-root user
RUN chown -R nuzantara:nuzantara /app

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
