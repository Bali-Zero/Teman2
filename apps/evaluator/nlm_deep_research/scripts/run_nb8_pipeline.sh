#!/usr/bin/env bash
# NB-8 Expat Life Bali — NLM pipeline cron wrapper
# Schedule: 40 2 * * 1-6   (02:40 WITA Mon-Sat)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/nlm_nb8_pipeline.log
# Brief:    ~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb8.json
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

# Detect venv (Pro uses .venv, Air uses venv)
if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: No virtualenv found" >&2
    exit 1
fi

LOCK_FILE="$SCRIPT_DIR/../nb8.lock"
LOG_FILE="${HOME}/.openclaw/logs/nlm_nb8_pipeline.log"
mkdir -p "$(dirname "$LOG_FILE")"

# PID lock — prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] NB-8 pipeline already running (PID $PID)" >> "$LOG_FILE"
        exit 0
    fi
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [WARN] Stale NB-8 lock (PID $PID) — cleaning up" >> "$LOG_FILE"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

cd "$PROJECT_ROOT"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] NB-8 Expat Life pipeline (PID $$)" >> "$LOG_FILE"

# Run pipeline
set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.nb8_pipeline "$@" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] NB-8 pipeline completed successfully" >> "$LOG_FILE"
    # ARCH-9 heartbeat — writes heartbeat_nb8_pipeline.json so sentinel reads
    # truthful success signal (not stale gateway projection). See T16 fix.
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "nb8_pipeline" 2>/dev/null || true
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] NB-8 pipeline failed (exit $EXIT_CODE)" >> "$LOG_FILE"
    MSG="⚠️ NB-8 Expat Life pipeline FAILED (exit $EXIT_CODE) — check ~/.openclaw/logs/nlm_nb8_pipeline.log"
    alert p0 "${MSG}"
fi

exit $EXIT_CODE
