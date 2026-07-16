#!/usr/bin/env bash
# install_cell_daemon.sh — operator-run installer for com.cell.organism
#
# Per cicatrix-scars.md 2026-04-29 antibody pattern, this script is the
# canonical way to bootstrap the Cell core daemon. Run from a clean
# checkout of nuzantara main repo.
#
# Idempotent: safe to re-run.
set -euo pipefail

REPO_ROOT="/Users/nuzantara/nuzantara"
CELL_DIR="$REPO_ROOT/apps/cell"
SRC_PLIST="$CELL_DIR/com.cell.organism.plist"
DST_PLIST="$HOME/Library/LaunchAgents/com.cell.organism.plist"
LABEL="com.cell.organism"
LOG_DIR="$HOME/logs/cell"

echo "==> Cell daemon installer"
echo "    Source plist: $SRC_PLIST"
echo "    Target plist: $DST_PLIST"

# Preconditions
[ -f "$SRC_PLIST" ] || { echo "FATAL: missing $SRC_PLIST" >&2; exit 1; }
[ -f "$CELL_DIR/.env" ] || { echo "FATAL: missing $CELL_DIR/.env (create from .env.example)" >&2; exit 1; }
[ -x "$CELL_DIR/.venv/bin/python" ] || { echo "FATAL: missing $CELL_DIR/.venv (run pip install -r requirements.txt)" >&2; exit 1; }
[ -x "$CELL_DIR/scripts/launch_cell.sh" ] || { echo "FATAL: missing launch_cell.sh" >&2; exit 1; }

# Log dir
mkdir -p "$LOG_DIR"

# Validate plist schema
plutil -lint "$SRC_PLIST" >/dev/null || { echo "FATAL: $SRC_PLIST plist is malformed" >&2; exit 1; }

# If already loaded, bootout first (idempotent)
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    echo "==> Found existing $LABEL — bootout first"
    # Make writable if previously chmod'd 0444
    chmod u+w "$DST_PLIST" 2>/dev/null || true
    launchctl bootout "gui/$(id -u)" "$DST_PLIST" 2>/dev/null || true
fi

# Copy + chmod read-only (scar 2026-04-29 antibody)
install -m 0444 "$SRC_PLIST" "$DST_PLIST"
echo "==> Installed $DST_PLIST (mode 0444)"

# Bootstrap
launchctl bootstrap "gui/$(id -u)" "$DST_PLIST"
echo "==> Bootstrap OK"

# Wait + verify
sleep 3
if launchctl print "gui/$(id -u)/$LABEL" 2>&1 | grep -q "state = running"; then
    echo "==> $LABEL is RUNNING"
    echo "==> Logs:"
    echo "      tail -f $LOG_DIR/organism.stdout.log"
    echo "      tail -f $LOG_DIR/organism.stderr.log"
else
    echo "==> WARN: $LABEL not in 'running' state — inspect logs:" >&2
    launchctl print "gui/$(id -u)/$LABEL" 2>&1 | grep -E "state =|last exit" | head -5 >&2
    exit 2
fi
