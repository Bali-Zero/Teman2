#!/usr/bin/env bash
# ARCH-2: Weekly Persona Validation — verify and restore missing persona notes
# Cron: 0 1 * * 0  (Sunday 01:00 UTC = 09:00 WITA)
#
# Checks all 7 domain notebooks (NB-2 through NB-8) for persona notes.
# Auto-restores any that are missing. Sends Telegram alert if restoration needed.

# Shared alarm gateway — see _alert.sh for what the old inline curl hid.
. "$(cd "$(dirname "$0")" && pwd)/_alert.sh" 2>/dev/null || true
# A missing helper must not turn "no alarm" into "the wrapper dies while
# handling a failure": fall back to a LOUD no-op, never a silent one.
command -v alert >/dev/null 2>&1 || alert() {
    echo "ALERT NOT SENT — _alert.sh missing [$1]: ${*:2}" >&2
    return 1
}

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
set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.persona_engine --validate 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "persona_validate" 2>/dev/null || true
else
    echo "$(date '+%H:%M:%S') [PersonaEngine] FAILED (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    MSG="🚨 PersonaEngine validate FAILED (exit $EXIT_CODE) — check $LOG_FILE"
    alert p0 "${MSG}"
fi

echo "$(date '+%H:%M:%S') [PersonaEngine] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
