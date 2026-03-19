#!/bin/bash

# Configuration
PROJECT_DIR="/Users/antonellosiano/Projects/nuzantara"
PYTHON_EXEC="/Users/antonellosiano/.pyenv/shims/python3"
EVAL_DIR="$PROJECT_DIR/apps/evaluator"
LOG_FILE="$PROJECT_DIR/logs/judgement_day.log"
REPORT_EMAIL="zero@balizero.com"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Execution
echo "[$DATE] Starting Judgement Day (RAG Evaluation)..." >> "$LOG_FILE"
cd "$EVAL_DIR"

# Run evaluation
export PYTHONPATH="$PROJECT_DIR/apps/backend-rag/backend:$PYTHONPATH"
"$PYTHON_EXEC" judgement_day.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# Report handling
REPORT_FILE="$EVAL_DIR/red_team_report.md"

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-7849498029:AAEjuP_uPt6KqD23Y8tVXVKnygJX8_TzW2g}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-1125336968}"

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$DATE] ✅ Evaluation completed." >> "$LOG_FILE"
    
    # Try to send email if mail command exists
    if command -v mail &> /dev/null; then
        mail -s "NUZANTARA: Judgement Day Report - $DATE" "$REPORT_EMAIL" < "$REPORT_FILE"
        echo "[$DATE] Report sent to $REPORT_EMAIL" >> "$LOG_FILE"
    else
        echo "[$DATE] ⚠️ mail command not found. Report saved at $REPORT_FILE" >> "$LOG_FILE"
    fi
else
    echo "[$DATE] ❌ Evaluation FAILED with exit code $EXIT_CODE." >> "$LOG_FILE"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🚨 *Air Judgement Day FAILED* (exit $EXIT_CODE)%0ACheck: ~/Projects/nuzantara/apps/evaluator/red_team_report.md" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
fi

echo "----------------------------------------" >> "$LOG_FILE"
