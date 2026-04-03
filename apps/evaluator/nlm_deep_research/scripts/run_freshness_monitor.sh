#!/usr/bin/env bash
# ARCH-5 Layer C: Regulatory freshness monitor (bi-daily: 07:00 and 19:00 WITA)
# Cron: 0 23,11 * * *  (23:00 UTC = 07:00 WITA, 11:00 UTC = 19:00 WITA)
#
# Morning run: --scan (check government sites for regulatory changes)
# Evening run: --remediate-stale (trigger NLM research for STALE/GAP topics)
#
# Pass argument: --scan OR --remediate-stale

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
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.freshness_monitor "$ACTION" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Record heartbeat
if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "freshness_monitor" 2>/dev/null || true
fi

echo "$(date '+%H:%M:%S') [FreshnessMonitor] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
