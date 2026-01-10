# BALI INTEL SCRAPER - Dockerfile
# Python 3.11 FastAPI application for 630+ source scraping

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies + Node.js for Claude CLI
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Claude CLI (for Claude Max subscription)
RUN npm install -g @anthropic-ai/claude-code

# Copy application code
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY api/ ./api/

# Create data directories
RUN mkdir -p data/raw data/articles logs

# Create non-root user
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run API server
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8002"]
