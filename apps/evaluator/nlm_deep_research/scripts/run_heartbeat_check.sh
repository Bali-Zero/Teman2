#!/usr/bin/env bash
# NLM Pipeline Heartbeat Monitor — cron wrapper
# Schedule: 0 8 * * *   (08:00 WITA daily — digest)
#           */30 * * * * (every 30min — check)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/heartbeat_monitor.log
# Shared alarm gateway — see _alert.sh for what the old inline curl hid.
. "$(cd "$(dirname "$0")" && pwd)/_alert.sh" 2>/dev/null || true
# A missing helper must not turn "no alarm" into "the wrapper dies while
# handling a failure": fall back to a LOUD no-op, never a silent one.
command -v alert >/dev/null 2>&1 || alert() {
    echo "ALERT NOT SENT — _alert.sh missing [$1]: ${*:2}" >&2
    return 1
}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# ── Load secrets (TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID for
#    CRITICAL/DEAD pipeline alerts) ───────────────────────────────────────────
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Detect venv (Pro uses .venv, Air uses venv)
if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: No virtualenv found" >&2
    exit 1
fi

LOG_FILE="${HOME}/.openclaw/logs/heartbeat_monitor.log"
mkdir -p "$(dirname "$LOG_FILE")"

cd "$PROJECT_ROOT"

MODE="${1:---check}"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] Heartbeat monitor ($MODE)" >>"$LOG_FILE"

set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor "$MODE" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] Heartbeat monitor ($MODE) completed" >>"$LOG_FILE"
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] Heartbeat monitor ($MODE) failed (exit $EXIT_CODE)" >>"$LOG_FILE"
    MSG="🚨 HeartbeatMonitor itself FAILED ($MODE, exit $EXIT_CODE) — check $LOG_FILE"
    alert p0 "${MSG}"
fi

exit $EXIT_CODE
