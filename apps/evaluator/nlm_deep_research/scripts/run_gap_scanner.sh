#!/usr/bin/env bash
# ARCH-5 Gap Scanner — Layer A / Layer B / Remediation Loop
#
# Cron schedule (Pro, UTC):
#   Layer A  (daily 05:30 WITA):       30 21 * * *   run_gap_scanner.sh --layer-a
#   Layer B  (Sunday 03:00 WITA):       0 19 * * 0   run_gap_scanner.sh --layer-b
#   Remediate (Sunday 04:30 WITA):     30 20 * * 0   run_gap_scanner.sh --remediate
#
# Layer A: query each notebook for unanswerable questions → coverage_matrix.json
# Layer B: test freshness of each topic (FRESH/AGING/STALE/GAP) → coverage_matrix.json
# Remediate: for each GAP/STALE topic → Gemini search → nlm source add (fills the gap)

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
# PR-D1 (2026-04-30): also source canonical secrets file (PR-C3 introduced
# this path; .zshrc.secrets above is the legacy fallback). Either is fine —
# the if-fi guards mean dev environments without the file still work.
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
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

PIPELINE_NAME="gap_scanner"
if [ "$LAYER" = "--layer-b" ]; then
    PIPELINE_NAME="gap_scanner_layer_b"
elif [ "$LAYER" = "--remediate" ]; then
    PIPELINE_NAME="gap_scanner_remediation"
fi

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "$PIPELINE_NAME" 2>/dev/null || true
else
    echo "$(date '+%H:%M:%S') [GapScanner] FAILED ($LAYER, exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_OWNER_CHAT_ID:-}" ]; then
        MSG="🚨 GapScanner FAILED ($LAYER, exit $EXIT_CODE) — check $LOG_FILE"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
            -d "text=${MSG}" >/dev/null 2>&1 || true
    fi
fi

echo "$(date '+%H:%M:%S') [GapScanner] Done (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit "$EXIT_CODE"
