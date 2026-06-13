#!/usr/bin/env bash
# install_cicatrix_autoarchive.sh — install/reload the daily cicatrix-scars
# auto-archive LaunchAgent (keeps .claude/rules/cicatrix-scars.md under 40k).
#
# Usage:
#   bash infra/launchagents/install_cicatrix_autoarchive.sh            # install
#   bash infra/launchagents/install_cicatrix_autoarchive.sh --uninstall
#
# Substitutes __HOME__ / __REPO_ROOT__ / __EXPECT_BRANCH__ into the .example
# plist (no user-specific paths committed). Hardens to 0444 (no secrets).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABEL="com.nuzantara.cicatrix-autoarchive.daily"
SRC="$PLIST_SRC_DIR/$LABEL.plist.example"
DEST="$PLIST_DEST_DIR/$LABEL.plist"
EXPECT_BRANCH="$(git -C "$REPO_ROOT" symbolic-ref --short HEAD 2>/dev/null || echo main)"

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
        if [[ -f "$DEST" ]]; then
            bak="$DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$DEST" 2>/dev/null || true
            cp "$DEST" "$bak"; echo "[install] backed up existing → $bak"
        fi
        bootout
        sed -e "s|__HOME__|$HOME|g" \
            -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
            -e "s|__EXPECT_BRANCH__|$EXPECT_BRANCH|g" \
            "$SRC" > "$DEST"
        chmod 0444 "$DEST"
        if ! plutil -lint "$DEST" >/dev/null 2>&1; then
            echo "[install] FATAL: $DEST plutil lint failed"; plutil -lint "$DEST"; exit 1
        fi
        echo "[install] bootstrapping $LABEL (REPO_ROOT=$REPO_ROOT, EXPECT_BRANCH=$EXPECT_BRANCH)"
        launchctl bootstrap "gui/$UID_VAL" "$DEST"
        echo "[install] done. Verify: launchctl print gui/$UID_VAL/$LABEL | grep -E 'state|runs'"
        echo "[install] Manual run:  bash $PLIST_SRC_DIR/cicatrix_autoarchive.sh"
        ;;
    --uninstall)
        bootout
        if [[ -f "$DEST" ]]; then chmod u+w "$DEST" 2>/dev/null || true; rm -f "$DEST"; echo "[install] removed $DEST"; fi
        ;;
    *)
        echo "usage: $0 [install|--uninstall]" >&2; exit 2 ;;
esac
