#!/bin/bash
# Metabolic Rollup Pro — SYMBIOSIS Pillar 7 daily cron wrapper (Pro local)
# Invoked by ~/Library/LaunchAgents/com.cell.metabolic-rollup.plist @ 23:45 WITA
#
# Organ: scripts/ → produce organism_metrics.db (scope='host', collector='pro')
# Consume: MOS SQLite, escalations_pro.jsonl, cron JSONL
# Pro does NOT have Fly PG tunnel — TTR/DO will be NULL by design (not_applicable_by_design)
#
# VADEMECUM §11: launchd does NOT inherit PATH/HOME. Declare explicitly.

set -euo pipefail

REPO="/Users/nuzantara/Desktop/nuzantara"
CELLCORE="$REPO/packages/cell-core"
LOG_DIR="$HOME/logs/cron"
mkdir -p "$LOG_DIR"

# Load secrets (TELEGRAM token). File is 600, owner-only.
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Python fallback chain (F8 fix: resilient to .venv recreation)
PY=""
for candidate in \
    "$REPO/apps/backend-rag/.venv/bin/python" \
    "/opt/homebrew/bin/python3.11" \
    "/opt/homebrew/bin/python3" \
    "/usr/bin/python3"
do
    if [ -x "$candidate" ]; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "ERR: no python interpreter found" >&2
    exit 2
fi

cd "$REPO"
export PYTHONPATH="$CELLCORE:${PYTHONPATH:-}"
export METABOLIC_DB_PATH="${METABOLIC_DB_PATH:-$HOME/.agent/decisions/organism_metrics.db}"

# mode=pro: no PG_DSN, writes 1 row with scope='host', collector='pro'.
# TTR+DO will be NULL with metadata.error='not_applicable_by_design'.
"$PY" scripts/metabolic_rollup.py \
    --db-path "$METABOLIC_DB_PATH" \
    --mode pro \
    --collector-host pro \
    --notify \
    >> "$LOG_DIR/metabolic-rollup-pro.log" 2>&1
rc=$?

# Innervation W1.1: emit liveness sidecar regardless of rc — the aggregator
# only cares that we ran, the status field tells it how the run went.
ORGAN_LAST_SEEN_DIR="$HOME/.organism/last_seen"
mkdir -p "$ORGAN_LAST_SEEN_DIR"
if [ "$rc" -eq 0 ]; then
    organ_status=ok
else
    organ_status=fail
fi
"$PY" -c "
import json, time
out = '$ORGAN_LAST_SEEN_DIR/pro.metabolic_rollup.json'
open(out, 'w').write(json.dumps({
    'ts': time.time(),
    'status': '$organ_status',
    'organ_id': 'pro.metabolic_rollup',
    'metadata': {'rc': $rc, 'mode': 'pro'},
}))
" 2>>"$LOG_DIR/metabolic-rollup-pro.log" || true

exit "$rc"
