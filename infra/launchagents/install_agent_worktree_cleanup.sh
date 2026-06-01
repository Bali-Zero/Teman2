#!/bin/bash
# install_agent_worktree_cleanup.sh — W62 ANTIBODY #1
#
# Install (or reload) the daily LaunchAgent that reaps abandoned agent
# worktrees via scripts/agent_start.py --cleanup (WIP-safe + skip-recent safe).
#
# Usage:
#   bash infra/launchagents/install_agent_worktree_cleanup.sh
#   bash infra/launchagents/install_agent_worktree_cleanup.sh --uninstall

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABEL="com.nuzantara.agent-worktree-cleanup.daily"
SRC="$PLIST_SRC_DIR/$LABEL.plist.example"
DEST="$PLIST_DEST_DIR/$LABEL.plist"

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
        if [[ ! -f "$SRC" ]]; then
            echo "[install] FATAL: source plist missing: $SRC" >&2
            exit 1
        fi
        if [[ -f "$DEST" ]]; then
            bak="$DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$DEST" 2>/dev/null || true
            cp "$DEST" "$bak"
            echo "[install] backed up existing → $bak"
        fi
        bootout
        # Copy + mode 0444 per VADEMECUM hardening (no secrets in this plist).
        cp "$SRC" "$DEST"
        chmod 0444 "$DEST"
        if ! plutil -lint "$DEST" >/dev/null 2>&1; then
            echo "[install] FATAL: $DEST plutil lint failed"
            plutil -lint "$DEST"
            exit 1
        fi
        echo "[install] bootstrapping $LABEL"
        launchctl bootstrap "gui/$UID_VAL" "$DEST"
        echo "[install] done. Verify: launchctl print gui/$UID_VAL/$LABEL | grep -E 'state|runs'"
        ;;
    --uninstall)
        bootout
        if [[ -f "$DEST" ]]; then
            chmod u+w "$DEST" 2>/dev/null || true
            rm -f "$DEST"
            echo "[install] removed $DEST"
        fi
        ;;
    *)
        echo "Usage: $0 [install|--uninstall]" >&2
        exit 2
        ;;
esac
