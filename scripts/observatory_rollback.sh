#!/usr/bin/env bash
# G2 rollback for Cell Pulse Observatory — emergency teardown.
#
# Usage: scripts/observatory_rollback.sh [--no-wipe]
#
# Steps:
#   1. Disable CELL_OBSERVATORY_EMIT in cell plists (organism, seo_cell, evaluator)
#   2. Reload affected cells (kickstart -k)
#   3. Bootout collector + prune + selfcheck LaunchAgents
#   4. Optional: wipe local SQLite DB (asks for confirmation unless --no-wipe)
#
# Outbox rows in Postgres for cell_pulse_observed are NOT auto-purged —
# they're inert (no consumer running) but can be manually cleaned via:
#   psql "$EVENTBUS_DATABASE_URL" -c "DELETE FROM events_outbox WHERE channel='cell_pulse_observed';"

set -euo pipefail

NO_WIPE=false
for arg in "$@"; do
    case "$arg" in
        --no-wipe) NO_WIPE=true ;;
        *) echo "[ERROR] unknown arg: $arg" >&2; exit 2 ;;
    esac
done

PLIST_DIR="$HOME/Library/LaunchAgents"
DB_PATH="${OBSERVATORY_DB_PATH:-$HOME/.cell-observatory/observatory.db}"

echo "===== Cell Observatory ROLLBACK ====="
echo

echo "1) Disable CELL_OBSERVATORY_EMIT in cell plists..."
for plist_pattern in \
    "$PLIST_DIR/com.cell.organism.plist" \
    "$PLIST_DIR/com.balizero.seo-cell"*.plist \
    "$PLIST_DIR/com.balizero.evaluator"*.plist; do
    for plist in $plist_pattern; do
        [ -f "$plist" ] || continue
        echo "   • $(basename "$plist")"
        original_mode=$(/usr/bin/stat -f "%Lp" "$plist" 2>/dev/null || echo "")
        if ! [[ "$original_mode" =~ ^[0-7]{3,4}$ ]]; then
            echo "     [WARN] could not read mode, falling back to 0444"
            original_mode="444"
        fi
        /bin/chmod u+w "$plist"
        if /usr/bin/plutil -extract EnvironmentVariables.CELL_OBSERVATORY_EMIT raw "$plist" &>/dev/null; then
            /usr/bin/plutil -replace EnvironmentVariables.CELL_OBSERVATORY_EMIT -string "false" "$plist"
        fi
        /bin/chmod "0$original_mode" "$plist"

        LABEL="$(basename "$plist" .plist)"
        launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || true
    done
done

echo
echo "2) Bootout observatory daemons..."
for label in com.nuzantara.cell-observatory \
             com.nuzantara.cell-observatory-prune \
             com.nuzantara.cell-observatory-selfcheck; do
    echo "   • $label"
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
done

echo
if [ "$NO_WIPE" = "true" ]; then
    echo "3) Skipping SQLite wipe (--no-wipe)"
else
    echo "3) Optional: wipe local SQLite DB at $DB_PATH"
    if [ -f "$DB_PATH" ]; then
        read -r -p "   Wipe $DB_PATH? [y/N] " ans
        if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
            /bin/rm -f "$DB_PATH" "${DB_PATH}-wal" "${DB_PATH}-shm"
            echo "   wiped"
        else
            echo "   kept"
        fi
    else
        echo "   no DB at $DB_PATH (already absent)"
    fi
fi

echo
echo "4) Note: events_outbox rows for cell_pulse_observed are NOT auto-purged."
echo "   They are inert (no consumer running) but can be manually cleaned via:"
echo "   psql \"\$EVENTBUS_DATABASE_URL\" -c \"DELETE FROM events_outbox WHERE channel='cell_pulse_observed';\""
echo
echo "✓ rollback complete"
