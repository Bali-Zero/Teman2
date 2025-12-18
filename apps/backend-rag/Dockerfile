# ZANTARA RAG Backend - Fly.io Deployment (OPTIMIZED FOR <8GB)
# Multi-stage build for security and optimization
# Python 3.11 + FastAPI + Qdrant + Sentence Transformers

# ========================================
# Stage 1: Build Stage
# ========================================
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies (skip Playwright browsers to save ~500MB)
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN pip install --no-cache-dir --user -r requirements.txt \
    && find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /root/.local -type f -name "*.pyc" -delete \
    && find /root/.local -type f -name "*.pyo" -delete

# ========================================
# Stage 2: Runtime Stage
# ========================================
FROM python:3.11-slim

# Install only runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 nuzantara && \
    mkdir -p /app /data && \
    chown -R nuzantara:nuzantara /app /data

WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/nuzantara/.local

# Copy application code
COPY backend ./backend
COPY scripts ./scripts
COPY *.py ./

# Set Python path to include /app, /app/backend, and user site-packages
# This aligns with local development structure
ENV PYTHONPATH=/app:/app/backend:/home/nuzantara/.local/lib/python3.11/site-packages
ENV PATH=/home/nuzantara/.local/bin:$PATH
# Prevent Python from writing .pyc files (forces fresh module loading)
ENV PYTHONDONTWRITEBYTECODE=1
# Skip Playwright browser installation at runtime
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
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Start uvicorn from root directory using module path
# This matches the PYTHONPATH configuration and works both locally and in Docker
# Use 0.0.0.0 (IPv4) for reliable binding (Fly.io proxy handles IPv6/IPv4 translation)
# Use shell script to properly expand $PORT environment variable
# Use 2 workers to leverage 2 CPUs per VM (Fly.io assigns 2 CPUs per machine)
CMD ["sh", "-c", "uvicorn backend.app.main_cloud:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2"]
