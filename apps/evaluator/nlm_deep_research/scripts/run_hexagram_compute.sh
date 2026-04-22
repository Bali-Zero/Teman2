#!/usr/bin/env bash
# Hexagram Dashboard — daily 6-bit state compute
# Schedule: 0 8 * * *  (daily 08:00 WITA)
# Machine:  Pro (nuzantara@Nuzantara)
# Log:      ~/.openclaw/logs/hexagram_compute.log
# Output:   apps/evaluator/nlm_deep_research/hexagram_state.jsonl (append)
#
# Pure observation — no side effects on NBs or pipelines. Reads turiya
# snapshot + coverage + yajna_metrics. Latency typically <1s.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

if [ -d "$PROJECT_ROOT/apps/backend-rag/.venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
elif [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    echo "ERROR: no virtualenv found" >&2
    exit 1
fi

LOG_DIR="${HOME}/.openclaw/logs"
LOG_FILE="${LOG_DIR}/hexagram_compute.log"
mkdir -p "$LOG_DIR"

cd "$PROJECT_ROOT"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] Hexagram compute" >> "$LOG_FILE"

EXIT_CODE=0
PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.hexagram --compute \
    2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] Hexagram compute ok" >> "$LOG_FILE"
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "hexagram_compute" 2>/dev/null || true
else
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [FAIL] Hexagram compute exit=$EXIT_CODE" >> "$LOG_FILE"
fi

exit "$EXIT_CODE"
