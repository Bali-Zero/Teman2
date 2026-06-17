#!/usr/bin/env bash
# start-all.sh — start wa-mirror processes for all employees with persisted sessions.
# Skips employees without a sessions/+<e164>/ dir (those need start-one with QR first).

set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

echo "━━━ wa-mirror single-account-per-process — START ALL ━━━"
echo ""

LAUNCHED=0
SKIPPED=0
RUNNING=0

if [ -n "${WA_MIRROR_SUPERVISED_NAMES:-}" ]; then
    ALL_NAMES=$(printf '%s\n' $WA_MIRROR_SUPERVISED_NAMES)
else
    ALL_NAMES=$(python3 -c "
import json
data = json.load(open('$ACCOUNTS_JSON'))
for a in data['accounts']:
    print(a['name'].lower())
" 2>/dev/null)
fi

while IFS= read -r NAME; do
    [ -z "$NAME" ] && continue
    E164=$(get_e164 "$NAME")
    if [ -z "$E164" ]; then
        echo "⚠️   $NAME — invalid/missing E.164 in $ACCOUNTS_JSON, skipping"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    SESDIR="$(session_dir "$E164")"
    PIDFILE="$(pid_file "$NAME")"

    # W77 lifecycle gate: respect the roster's declared intent instead of
    # blindly launching every account with a session dir.
    STATUS="$(get_expected_status "$NAME")"
    if [ "$STATUS" != "ACTIVE" ]; then
        echo "⏸️   $NAME — expected_status=$STATUS, skipping (declared non-active in roster)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    NODE="$(get_assigned_node "$NAME")"
    if [ -n "$NODE" ] && [ "$NODE" != "$(hostname -s)" ] && [ "$NODE" != "$(hostname)" ]; then
        echo "⏭️   $NAME — assigned_node=$NODE != $(hostname -s), skipping (runs on another node)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Skip if already running
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "⏭️   $NAME — already running PID $PID"
            RUNNING=$((RUNNING + 1))
            continue
        fi
        rm -f "$PIDFILE"
    fi

    # Skip if no session (needs onboarding via start-one.sh)
    if [ ! -d "$SESDIR" ] || [ -z "$(ls -A "$SESDIR" 2>/dev/null)" ]; then
        echo "🔑  $NAME — no session, skipping (run: bash start-one.sh $NAME)"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    echo "🚀  $NAME — launching..."
    bash "$SCRIPT_DIR/start-one.sh" "$NAME" 2>&1 | grep -E "spawned|Connected|QR|❌" | sed 's/^/   /'
    LAUNCHED=$((LAUNCHED + 1))
    sleep 2  # stagger spawn to avoid simultaneous WA reconnect storm
done <<< "$ALL_NAMES"

echo ""
echo "━━━ Summary ━━━"
echo "  Launched:        $LAUNCHED"
echo "  Already running: $RUNNING"
echo "  No session yet:  $SKIPPED"
echo ""
echo "Status:  bash $SCRIPT_DIR/status.sh"
