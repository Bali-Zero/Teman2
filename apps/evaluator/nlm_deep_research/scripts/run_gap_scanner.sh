#!/usr/bin/env bash
# ARCH-5 Layer A: Daily gap discovery (05:30 WITA = 21:30 UTC)
# Cron: 30 21 * * *
#
# Queries each domain notebook for unanswerable questions.
# Results stored in coverage_matrix.json.
#
# Layer B (coverage matrix) runs separately:
# Cron: 0 19 * * 0  (Sunday 03:00 WITA = 19:00 UTC)
# Invoked with --layer-b flag.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/logs"
LOG_FILE="$LOG_DIR/gap_scanner_$(date +%Y%m%d).log"
PID_FILE="/tmp/nz_gap_scanner.pid"
LAYER="${1:---layer-a}"  # default --layer-a, pass --layer-b for weekly run

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$(date '+%H:%M:%S') [GapScanner] Already running (pid=$OLD_PID) — exiting" | tee -a "$LOG_FILE"
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

echo "$(date '+%H:%M:%S') [GapScanner] Starting $LAYER" | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.gap_scanner "$LAYER" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Record heartbeat
PIPELINE_NAME="gap_scanner"
if [ "$LAYER" = "--layer-b" ]; then
    PIPELINE_NAME="gap_scanner_layer_b"
fi
if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "$PIPELINE_NAME" 2>/dev/null || true
fi

echo "$(date '+%H:%M:%S') [GapScanner] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
