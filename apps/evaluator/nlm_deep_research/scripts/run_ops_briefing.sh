#!/usr/bin/env bash
# ARCH-10: Weekly Ops Intelligence Executive Briefing
# Cron: 0 0 * * 1  (Monday 00:00 UTC = 08:00 WITA)
#
# Queries NB-11 (Ops Live) and NB-12 (Business Intelligence),
# detects anomalies, sends Telegram executive briefing.

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
LOG_FILE="$LOG_DIR/ops_briefing_$(date +%Y%m%d).log"
PID_FILE="/tmp/nz_ops_briefing.pid"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%H:%M:%S') [OpsIntelligence] Already running (pid=$OLD_PID) — exiting" | tee -a "$LOG_FILE"
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
    echo "$(date '+%H:%M:%S') [OpsIntelligence] ERROR: venv not found at $VENV" | tee -a "$LOG_FILE"
    exit 1
fi

echo "$(date '+%H:%M:%S') [OpsIntelligence] Starting weekly executive briefing" | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"
set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.ops_intelligence --briefing 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "ops_briefing" 2>/dev/null || true
else
    echo "$(date '+%H:%M:%S') [OpsIntelligence] FAILED (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    MSG="🚨 OpsIntelligence briefing FAILED (exit $EXIT_CODE) — check $LOG_FILE"
    alert p0 "${MSG}"
fi

echo "$(date '+%H:%M:%S') [OpsIntelligence] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
