#!/usr/bin/env bash
# install_wr3_reflexion.sh — install/reload the weekly WR3 Reflexion synthesizer
# LaunchAgent (F21 cure). Replaces the old unversioned HOME-only plist that ran
# the 816-byte S7.3 stub.
#
# Usage:
#   bash infra/launchagents/install_wr3_reflexion.sh            # install + bootstrap
#   bash infra/launchagents/install_wr3_reflexion.sh --uninstall
#
# PRECONDITION: the plist points at the deploy worktree
#   /Users/nuzantara/Desktop/nuzantara-deploy/scripts/wr3_reflexion_synthesis.py
# which only exists AFTER this PR merges to main and the deploy-puller syncs it.
# Run this on the Pro AFTER merge+sync (same runtime-host pattern as the supervisor).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs"
UID_VAL="$(id -u)"

LABEL="com.balizero.wr3.reflexion.weekly"
SRC="$PLIST_SRC_DIR/$LABEL.plist"
DEST="$PLIST_DEST_DIR/$LABEL.plist"
TARGET_SCRIPT="/Users/nuzantara/Desktop/nuzantara-deploy/scripts/wr3_reflexion_synthesis.py"

MODE="${1:-install}"
mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR"

bootout() {
    if launchctl print "gui/$UID_VAL/$LABEL" >/dev/null 2>&1; then
        echo "[install] booting out $LABEL"
        launchctl bootout "gui/$UID_VAL/$LABEL" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

case "$MODE" in
    install)
        [[ -f "$SRC" ]] || { echo "[install] FATAL: source plist missing: $SRC" >&2; exit 1; }
        if [[ ! -f "$TARGET_SCRIPT" ]]; then
            echo "[install] WARN: target script not present yet: $TARGET_SCRIPT" >&2
            echo "[install] WARN: run this AFTER the PR merges + deploy-puller syncs scripts/." >&2
        fi
        if [[ -f "$DEST" ]]; then
            bak="$DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$DEST" 2>/dev/null || true
            cp "$DEST" "$bak"; echo "[install] backed up existing → $bak"
        fi
        bootout
        cp "$SRC" "$DEST"
        chmod 0444 "$DEST"
        if ! plutil -lint "$DEST" >/dev/null 2>&1; then
            echo "[install] FATAL: $DEST plutil lint failed"; plutil -lint "$DEST"; exit 1
        fi
        echo "[install] bootstrapping $LABEL"
        launchctl bootstrap "gui/$UID_VAL" "$DEST"
        echo "[install] done. Verify: launchctl print gui/$UID_VAL/$LABEL | grep -E 'state|runs'"
        echo "[install] Manual run: WR3_REPO_ROOT=/Users/nuzantara/Desktop/nuzantara-deploy \\"
        echo "            /Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/.venv/bin/python \\"
        echo "            $TARGET_SCRIPT"
        ;;
    --uninstall)
        bootout
        if [[ -f "$DEST" ]]; then chmod u+w "$DEST" 2>/dev/null || true; rm -f "$DEST"; echo "[install] removed $DEST"; fi
        ;;
    *)
        echo "usage: $0 [install|--uninstall]" >&2; exit 2 ;;
esac
