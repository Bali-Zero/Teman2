#!/bin/bash
# =============================================================================
# Bali Intel Feed - News Pipeline Cron Wrapper
# Runs every 6 hours: fetch RSS + professional 5-dimension scoring
# =============================================================================

# Load shell environment
export HOME="/Users/antonellosiano"
source "$HOME/.zshrc" 2>/dev/null || source "$HOME/.bashrc" 2>/dev/null

# Set PATH
export PATH="$HOME/.pyenv/shims:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Working directory
cd /Users/antonellosiano/Desktop/nuzantara/apps/bali-intel-scraper

# Load API key from .env.local
if [ -f .env.local ]; then
    export $(grep -v '^#' .env.local | xargs)
fi

# Log file
LOG_FILE="logs/cron_pipeline_$(date +%Y%m%d).log"

echo "========================================" >> "$LOG_FILE"
echo "📰 Bali Intel Feed Started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Optional: Check if Ollama is running (for edge case enhancement)
OLLAMA_FLAG=""
if pgrep -x "ollama" > /dev/null; then
    OLLAMA_FLAG="--use-ollama"
    echo "🤖 Ollama detected - will use for edge cases" >> "$LOG_FILE"
fi

# Run RSS fetcher with professional scoring
echo "🎯 Fetching RSS + Professional 5-Dimension Scoring..." >> "$LOG_FILE"
python3 scripts/rss_fetcher.py \
    --max-age 7 \
    --limit 5 \
    --min-score 50 \
    --api-key "$BALIZERO_API_KEY" \
    --send \
    $OLLAMA_FLAG \
    >> "$LOG_FILE" 2>&1

echo "✅ Completed: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
