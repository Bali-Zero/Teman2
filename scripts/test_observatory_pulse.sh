#!/usr/bin/env bash
# M1 smoke test for Cell Pulse Observatory.
#
# Emits a fake pulse via cell_core.observatory.emit_pulse_observed,
# verifies it lands in events_outbox, gets consumed by the collector
# into ~/.cell-observatory/observatory.db, and is visible via the
# dashboard health endpoint.
#
# Prerequisites:
# - ~/.nuzantara-secrets.env contains MINIMAX_API_KEY, EVENTBUS_DATABASE_URL,
#   OBSERVATORY_API_KEY (and optionally OBSERVATORY_API_PORT, default 17891)
# - cell-observatory-collector is installed at ~/Desktop/nuzantara/apps/cell-observatory-collector/.venv
# - The collector LaunchAgent is loaded (com.nuzantara.cell-observatory)
# - Postgres is reachable from Pro
# - sqlite3 + psql are on PATH (brew install sqlite3 postgresql@17)
#
# Exit codes:
#   0 — all checks passed
#   1 — emit step failed
#   2 — events_outbox row not found
#   3 — SQLite row not found within timeout
#   4 — dashboard health endpoint unreachable

set -euo pipefail

set -a
source ~/.nuzantara-secrets.env
set +a

PULSE_ID="01SMOKE-$(date +%s)"
WAIT_SECS=10
DB_PATH="${OBSERVATORY_DB_PATH:-$HOME/.cell-observatory/observatory.db}"

echo "===== Cell Observatory M1 Smoke Test ====="
echo "Pulse ID: $PULSE_ID"
echo

echo "1) Inject test pulse via cell_core.observatory.emit_pulse_observed..."
~/Desktop/nuzantara/apps/cell-observatory-collector/.venv/bin/python <<PYEOF
import asyncio
import os
import time

os.environ["CELL_OBSERVATORY_EMIT"] = "true"

from cell_core import observatory

async def main():
    await observatory.emit_pulse_observed(
        cell_id="smoke-test",
        cell_kind="test",
        pulse_id="$PULSE_ID",
        pulse_timestamp_ms=int(time.time() * 1000),
        phase="active",
        sensors=[{"name": "fake-sensor", "status": "green", "value": 1.0}],
        pulse_result={
            "classifier_self": "green",
            "trend_window_min": 15,
            "trend_label": "stable",
        },
        homeostatic_state={"stress_level": 0.1, "energy_level": 0.9},
    )
    print("emit OK")

asyncio.run(main())
PYEOF

echo
echo "2) Verify events_outbox row..."
if ! command -v psql &>/dev/null; then
    echo "[WARN] psql not on PATH — skipping outbox check (install postgresql@17 to enable)"
else
    psql "$EVENTBUS_DATABASE_URL" -c \
        "SELECT id, channel, payload->>'pulse_id' AS pulse_id FROM events_outbox WHERE channel='cell_pulse_observed' AND payload->>'pulse_id'='$PULSE_ID';"
fi

echo
echo "3) Wait ${WAIT_SECS}s for collector to consume..."
sleep "$WAIT_SECS"

echo
echo "4) Verify pulse in local SQLite at $DB_PATH..."
if ! command -v sqlite3 &>/dev/null; then
    echo "[ERROR] sqlite3 not on PATH (brew install sqlite3)"
    exit 3
fi
if [ ! -f "$DB_PATH" ]; then
    echo "[ERROR] DB not found at $DB_PATH (run scripts/bootstrap_db.sh first)"
    exit 3
fi
COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pulse_events WHERE pulse_id='$PULSE_ID';")
echo "SQLite rows for pulse_id=$PULSE_ID: $COUNT"
if [ "$COUNT" = "0" ]; then
    echo "[ERROR] pulse not found in SQLite — collector may not be running"
    exit 3
fi

echo
echo "5) Verify dashboard health endpoint..."
PORT="${OBSERVATORY_API_PORT:-17891}"
curl -fsS -m 5 -H "X-Observatory-Key: $OBSERVATORY_API_KEY" \
    "http://127.0.0.1:$PORT/api/observatory/health" \
    | python3 -m json.tool || {
        echo "[ERROR] dashboard health unreachable on :$PORT"
        exit 4
    }

echo
echo "✓ smoke test passed"
