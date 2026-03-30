#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Projects/nuzantara"
PYTHON_EXEC="$PROJECT_DIR/apps/backend-rag/venv/bin/python3"
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

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-7849498029:AAEjuP_uPt6KqD23Y8tVXVKnygJX8_TzW2g}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-1125336968}"

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
