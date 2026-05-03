#!/usr/bin/env bash
# ARCH-2: Weekly Persona Validation — verify and restore missing persona notes
# Cron: 0 1 * * 0  (Sunday 01:00 UTC = 09:00 WITA)
#
# Checks all 7 domain notebooks (NB-2 through NB-8) for persona notes.
# Auto-restores any that are missing. Sends Telegram alert if restoration needed.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/logs"
LOG_FILE="$LOG_DIR/persona_validate_$(date +%Y%m%d).log"
PID_FILE="/tmp/nz_persona_validate.pid"

mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%H:%M:%S') [PersonaEngine] Already running (pid=$OLD_PID) — exiting" | tee -a "$LOG_FILE"
        exit 0
    fi
fi
echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

# Load environment
if [ -f "$HOME/.zshrc.secrets" ]; then
    set +u
    # shellcheck disable=SC1090
    source "$HOME/.zshrc.secrets" 2>/dev/null || true
    set -u
fi

# Activate venv
VENV="$PROJECT_ROOT/apps/backend-rag/.venv"
if [ ! -f "$VENV/bin/activate" ]; then
    VENV="$PROJECT_ROOT/apps/backend-rag/venv"
fi
if [ -f "$VENV/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$VENV/bin/activate"
else
    echo "$(date '+%H:%M:%S') [PersonaEngine] ERROR: venv not found" | tee -a "$LOG_FILE"
    exit 1
fi

echo "$(date '+%H:%M:%S') [PersonaEngine] Starting weekly persona validation" | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.persona_engine --validate 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "persona_validate" 2>/dev/null || true
else
    echo "$(date '+%H:%M:%S') [PersonaEngine] FAILED (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="🚨 PersonaEngine validate FAILED (exit $EXIT_CODE) — check $LOG_FILE"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" >/dev/null 2>&1 || true
    fi
fi

echo "$(date '+%H:%M:%S') [PersonaEngine] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
