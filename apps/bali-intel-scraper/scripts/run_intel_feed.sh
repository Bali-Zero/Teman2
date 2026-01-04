#!/bin/bash
# =============================================================================
# BaliZero Intel Feed - Complete News Intelligence Pipeline
# =============================================================================
#
# MODES:
#   quick  - Fast RSS fetch + scoring (every 6 hours)
#   full   - Deep enrichment with Claude Max (once daily)
#
# CRON EXAMPLES:
#   # Quick mode every 6 hours
#   0 */6 * * * /path/to/run_intel_feed.sh quick
#
#   # Full mode once daily at 6 AM
#   0 6 * * * /path/to/run_intel_feed.sh full
#
# =============================================================================

# Mode: quick or full (default: quick)
MODE="${1:-quick}"

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
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/intel_feed_$(date +%Y%m%d).log"

echo "========================================" >> "$LOG_FILE"
echo "🧠 BaliZero Intel Feed - $MODE mode" >> "$LOG_FILE"
echo "📅 Started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Check Ollama (optional)
OLLAMA_FLAG=""
if pgrep -x "ollama" > /dev/null; then
    OLLAMA_FLAG="--use-ollama"
    echo "🤖 Ollama detected - will use for edge cases" >> "$LOG_FILE"
fi

# Run based on mode
case "$MODE" in
    quick)
        echo "🚀 Running QUICK mode (RSS + Score + Send)..." >> "$LOG_FILE"
        python3 scripts/run_intel_feed.py \
            --mode quick \
            --max-age 7 \
            --limit 5 \
            --min-score 50 \
            --api-key "$BALIZERO_API_KEY" \
            $OLLAMA_FLAG \
            >> "$LOG_FILE" 2>&1
        ;;

    full)
        echo "🔬 Running FULL mode (Deep Enrichment with Claude)..." >> "$LOG_FILE"
        python3 scripts/run_intel_feed.py \
            --mode full \
            --max-age 7 \
            --limit 3 \
            --min-score 60 \
            --max-enrich 5 \
            --api-key "$BALIZERO_API_KEY" \
            $OLLAMA_FLAG \
            >> "$LOG_FILE" 2>&1
        ;;

    enrich)
        echo "🔄 Running ENRICH-ONLY mode..." >> "$LOG_FILE"
        python3 scripts/run_intel_feed.py \
            --mode enrich-only \
            --limit 10 \
            --api-key "$BALIZERO_API_KEY" \
            >> "$LOG_FILE" 2>&1
        ;;

    test)
        echo "🧪 Running TEST mode (dry run)..." >> "$LOG_FILE"
        python3 scripts/run_intel_feed.py \
            --mode full \
            --max-age 3 \
            --limit 2 \
            --min-score 40 \
            --max-enrich 2 \
            --dry-run \
            $OLLAMA_FLAG \
            >> "$LOG_FILE" 2>&1
        ;;

    *)
        echo "❌ Unknown mode: $MODE" >> "$LOG_FILE"
        echo "Usage: $0 [quick|full|enrich|test]" >> "$LOG_FILE"
        exit 1
        ;;
esac

echo "✅ Completed: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Show last few lines of log
echo "=== Last 10 lines of log ==="
tail -10 "$LOG_FILE"
