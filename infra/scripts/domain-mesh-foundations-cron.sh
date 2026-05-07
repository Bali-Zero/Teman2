#!/bin/bash
set -uo pipefail

LOG_DIR="$HOME/logs/domain-mesh-foundations"
SNAPSHOT_DIR="$HOME/.cache/domain-mesh-foundations/snapshots"
mkdir -p "$LOG_DIR" "$SNAPSHOT_DIR"

LOG_FILE="$LOG_DIR/foundations-daily-$(date +%Y%m%d).log"
SNAPSHOT_FILE="$SNAPSHOT_DIR/gov-apis-health-$(date +%Y%m%d).json"

REPO_ROOT="${HOME}/Desktop/nuzantara"
cd "$REPO_ROOT/apps/mata-garuda" || exit 1

source "$REPO_ROOT/.venv/bin/activate" 2>/dev/null

python -c "
import asyncio, json, sys
from mata_garuda.foundations import probe_inventory
report = asyncio.run(probe_inventory())
data = {
    'total': report.total,
    'operational': report.operational,
    'results': [r.__dict__ for r in report.results],
}
sys.stdout.write(json.dumps(data, indent=2))
" > "$SNAPSHOT_FILE" 2>>"$LOG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date) FAILED foundations daily probe" >> "$LOG_FILE"
    exit $EXIT_CODE
fi

OPERATIONAL=$(python -c "import json; d=json.load(open('$SNAPSHOT_FILE')); print(d['operational'])")
TOTAL=$(python -c "import json; d=json.load(open('$SNAPSHOT_FILE')); print(d['total'])")
echo "$(date) gov-apis snapshot: $OPERATIONAL/$TOTAL operational" >> "$LOG_FILE"

# TODO Phase 1: compare vs 7-day baseline + Telegram alert if drop > 10pp
exit 0
