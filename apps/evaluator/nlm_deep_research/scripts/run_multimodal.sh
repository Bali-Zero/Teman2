#!/bin/bash
# ARCH-6: Multi-Modal Content Factory — cron wrapper
# Runs today's scheduled multimodal tasks.
#
# Cron schedule (WITA):
#   Mon 06:00 = Sun 22:00 UTC  → NB-2 audio
#   Tue 06:00 = Mon 22:00 UTC  → NB-3 mind-map
#   Wed 06:00 = Tue 22:00 UTC  → NB-4 infographic
#   Thu 06:00 = Wed 22:00 UTC  → NB-6 audio
#   Fri 06:00 = Thu 22:00 UTC  → NB-7 audio
#   Sun 06:00 = Sat 22:00 UTC  → full suite
#
# Crontab entries (Pro, using UTC):
#   0 22 * * 0 /path/to/run_multimodal.sh   # Mon WITA (Sun UTC)
#   0 22 * * 1 /path/to/run_multimodal.sh   # Tue WITA
#   0 22 * * 2 /path/to/run_multimodal.sh   # Wed WITA
#   0 22 * * 3 /path/to/run_multimodal.sh   # Thu WITA
#   0 22 * * 4 /path/to/run_multimodal.sh   # Fri WITA
#   0 22 * * 6 /path/to/run_multimodal.sh   # Sun WITA (full suite)
#
# Usage:
#   ./run_multimodal.sh
#   ./run_multimodal.sh --dry-run
#   ./run_multimodal.sh --force

# Shared alarm gateway — see _alert.sh for what the old inline curl hid.
. "$(cd "$(dirname "$0")" && pwd)/_alert.sh" 2>/dev/null || true
# A missing helper must not turn "no alarm" into "the wrapper dies while
# handling a failure": fall back to a LOUD no-op, never a silent one.
command -v alert >/dev/null 2>&1 || alert() {
    echo "ALERT NOT SENT — _alert.sh missing [$1]: ${*:2}" >&2
    return 1
}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/output"
LOG_FILE="$LOG_DIR/multimodal_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

# Load secrets if available
if [ -f "$HOME/.zshrc.secrets" ]; then
    set +u
    # shellcheck disable=SC1090
    source "$HOME/.zshrc.secrets" 2>/dev/null || true
    set -u
fi

PYTHON="python3"
if [ -f "$PROJECT_ROOT/apps/backend-rag/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S WITA')] Starting multimodal pipeline..." | tee -a "$LOG_FILE"

cd "$PROJECT_ROOT"
set +e  # errexit would abort ON the pipeline, before the capture below
PYTHONPATH=. $PYTHON -m apps.evaluator.nlm_deep_research.multimodal_pipeline --run "$@" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE="${PIPESTATUS[0]}"
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
    PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.heartbeat_monitor \
        --record "multimodal_pipeline" 2>/dev/null || true
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S WITA')] Multimodal pipeline FAILED (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
    MSG="🚨 Multimodal pipeline FAILED (exit $EXIT_CODE) — check $LOG_FILE"
    alert p0 "${MSG}"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S WITA')] Multimodal pipeline finished (exit=$EXIT_CODE)" | tee -a "$LOG_FILE"
exit $EXIT_CODE
