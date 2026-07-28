#!/usr/bin/env bash
# ARCH-5 Layer C: Regulatory freshness monitor (bi-daily: 07:00 and 19:00 WITA)
# Cron: 0 23,11 * * *  (23:00 UTC = 07:00 WITA, 11:00 UTC = 19:00 WITA)
#
# Morning run: --scan (check government sites for regulatory changes)
# Evening run: --remediate-stale (trigger NLM research for STALE/GAP topics)
#
# Pass argument: --scan OR --remediate-stale

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
LOG_FILE="$LOG_DIR/freshness_monitor_$(date +%Y%m%d).log"
PID_FILE="/tmp/nz_freshness_monitor.pid"
ACTION="${1:---scan}"  # default --scan

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%H:%M:%S') [FreshnessMonitor] Already running (pid=$OLD_PID) — exiting" | tee -a "$LOG_FILE"
        exit 0
    fi
fi
echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

if [ -f "$HOME/.zshrc.secrets" ]; then
    set +u
    source "$HOME/.zshrc.secrets" 2>/dev/null || true
    set -u
fi

VENV="$PROJECT_ROOT/apps/backend-rag/.venv"
if [ ! -f "$VENV/bin/activate" ]; then
    VENV="$PROJECT_ROOT/apps/backend-rag/venv"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"

echo "$(date '+%H:%M:%S') [FreshnessMonitor] Starting $ACTION" | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"
set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.freshness_monitor "$ACTION" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "freshness_monitor" 2>/dev/null || true
else
    echo "$(date '+%H:%M:%S') [FreshnessMonitor] FAILED (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    MSG="🚨 FreshnessMonitor FAILED ($ACTION, exit $EXIT_CODE) — check $LOG_FILE"
    alert p0 "${MSG}"
fi

echo "$(date '+%H:%M:%S') [FreshnessMonitor] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
