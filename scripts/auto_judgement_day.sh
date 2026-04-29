#!/bin/bash

# Configuration — machine-aware (Pro vs Air). Same pattern as
# curiosity_loop.sh and genome_decay.sh after the renaissance PR-A1 fix.
case "$(whoami)" in
    nuzantara)
        PROJECT_DIR="$HOME/Desktop/nuzantara"
        # Pro uses .venv (CLAUDE.md §14)
        PYTHON_EXEC="$PROJECT_DIR/apps/backend-rag/.venv/bin/python3"
        ;;
    antonellosiano)
        PROJECT_DIR="$HOME/Projects/nuzantara"
        # Air uses venv (CLAUDE.md §14)
        PYTHON_EXEC="$PROJECT_DIR/apps/backend-rag/venv/bin/python3"
        ;;
    *)
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
        PYTHON_EXEC="$PROJECT_DIR/apps/backend-rag/.venv/bin/python3"
        [ -x "$PYTHON_EXEC" ] || PYTHON_EXEC="$PROJECT_DIR/apps/backend-rag/venv/bin/python3"
        ;;
esac
EVAL_DIR="$PROJECT_DIR/apps/evaluator"
LOG_FILE="$PROJECT_DIR/logs/judgement_day.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Check dependencies before running
if ! "$PYTHON_EXEC" -c "import ragas" 2>/dev/null; then
    echo "[$DATE] ⚠️  SKIP: ragas not installed in venv. Run: venv/bin/pip install ragas langchain-google-genai" >> "$LOG_FILE"
    echo "[$DATE]    To enable Judgement Day, install deps and re-run." >> "$LOG_FILE"
    echo "----------------------------------------" >> "$LOG_FILE"
    exit 0
fi

# Execution
echo "[$DATE] Starting Judgement Day (RAG Evaluation)..." >> "$LOG_FILE"
cd "$EVAL_DIR"

# Run evaluation
export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:${PYTHONPATH:-}"
"$PYTHON_EXEC" judgement_day.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# Load secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID)
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
TELEGRAM_CHAT_ID="${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-1125336968}}"

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Evaluation completed." >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Evaluation FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🚨 *Air Judgement Day FAILED* (exit $EXIT_CODE)%0ACheck: ~/Projects/nuzantara/apps/evaluator/red_team_report.md" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
fi

echo "----------------------------------------" >> "$LOG_FILE"
