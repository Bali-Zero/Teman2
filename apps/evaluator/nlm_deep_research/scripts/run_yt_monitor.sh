#!/usr/bin/env bash
# YouTube Channel Monitor for NLM Notebooks
# Cron: 30 */6 * * *  (every 6h at :30, offset from T4 monitor at :00)
# Runs on Pro via OpenClaw

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
cd "$PROJECT_ROOT"

# Activate venv
if [ -f "apps/backend-rag/.venv/bin/activate" ]; then
    source apps/backend-rag/.venv/bin/activate
elif [ -f "apps/backend-rag/venv/bin/activate" ]; then
    source apps/backend-rag/venv/bin/activate
fi

# Run monitor
set +e  # errexit would abort ON the pipeline, before the capture below
python -m apps.evaluator.nlm_deep_research.yt_monitor \
    --max-age 30 \
    --threshold 0.35 \
    2>&1 | tee -a "$PROJECT_ROOT/apps/evaluator/nlm_deep_research/yt_monitor.log"

EXIT_CODE=${PIPESTATUS[0]}
set -e

# Alert on failure
if [ "$EXIT_CODE" -ne 0 ]; then
    alert p0 "⚠️ YT Monitor failed (exit $EXIT_CODE). Check yt_monitor.log"
fi

exit "$EXIT_CODE"
