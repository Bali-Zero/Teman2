#!/usr/bin/env bash
# T4 Social Media Monitor — cron wrapper
# Schedule: 0 */6 * * *  (every 6 hours)
# Machine:  Air (antonellosiano@Nuzantara-9)
# Log:      ~/.openclaw/logs/t4_monitor.log
# Shared alarm gateway — see _alert.sh.
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

# Air uses venv (not .venv). Pro uses .venv — detect at runtime.
if [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
fi

LOCK_FILE="$SCRIPT_DIR/../t4.lock"
LOG_FILE="${HOME}/.openclaw/logs/t4_monitor.log"
mkdir -p "$(dirname "$LOG_FILE")"

# PID lock — prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] T4 monitor already running (PID $PID)" >> "$LOG_FILE"
        exit 0
    fi
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [WARN] Stale lock (PID $PID) — cleaning up" >> "$LOG_FILE"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

cd "$PROJECT_ROOT"

# Ensure ~/.local/bin is in PATH (nlm CLI lives there)
export PATH="$HOME/.local/bin:$PATH"

# Load env vars — safe grep-based extraction (avoids sourcing multi-line values like GOOGLE_CREDENTIALS_JSON)
ENV_FILE="$PROJECT_ROOT/apps/backend-rag/.env"
if [ -f "$ENV_FILE" ]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        [[ "$key" =~ [^A-Za-z0-9_] ]] && continue
        export "$key=$value"
    done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=.+$' "$ENV_FILE" | grep -v '^GOOGLE_CREDENTIALS_JSON=')
fi

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] T4 monitor (PID $$)" >> "$LOG_FILE"

set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.t4_monitor \
    --notebook-id "cff93ab0-813a-42f2-a8de-36987e724271" \
    --log-level INFO \
    2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

# This wrapper had no alarm at all: it ran the job and echoed [DONE], which
# under errexit simply never printed when the job died. `t4_monitor` is one of
# the 9 jobs the Cell's cron_sensor watches for STALENESS, so a dead run was
# eventually noticed — but "eventually, by absence" is not a failure report.
if [ "$EXIT_CODE" -ne 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] T4 monitor failed (exit $EXIT_CODE)" >> "$LOG_FILE"
    alert p0 "⚠️ T4 monitor FAILED (exit $EXIT_CODE) — check $LOG_FILE"
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] T4 monitor completed" >> "$LOG_FILE"
fi

exit "$EXIT_CODE"
