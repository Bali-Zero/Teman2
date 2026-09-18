#!/bin/bash
# install_mailbox_janitor.sh — install (or reload) the fleet mailbox janitor
# LaunchAgent on the machine this runs on (M5, Pro or Mini).
#
# The tracked plist is Pro/Mini shaped (/Users/nuzantara/nuzantara). This script
# renders the repo root and HOME for the local machine, lints the result with
# BOTH plutil and plistlib (plutil is lenient about XML comments, plistlib is
# what audit_launchd_crons.py uses), backs up any previous copy, then
# bootstraps it under gui/$UID.
#
# Usage:
#   bash infra/launchagents/install_mailbox_janitor.sh            # install / reload
#   bash infra/launchagents/install_mailbox_janitor.sh uninstall
#   bash infra/launchagents/install_mailbox_janitor.sh render     # print the rendered plist, touch nothing
#
# MAILBOX_JANITOR_REPO_ROOT overrides the payload checkout (default ~/nuzantara,
# the canonical main checkout: never a worktree, whose path dies with it).

set -uo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${MAILBOX_JANITOR_REPO_ROOT:-${HOME}/nuzantara}"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABEL="com.nuzantara.mailbox-janitor.daily"
SRC="$SRC_DIR/$LABEL.plist"
DEST="$PLIST_DEST_DIR/$LABEL.plist"

MODE="${1:-install}"

render() {
    sed -e "s#/Users/nuzantara/nuzantara#${REPO_ROOT}#g" \
        -e "s#/Users/nuzantara#${HOME}#g" "$SRC"
}

bootout() {
    if launchctl print "gui/$UID_VAL/$LABEL" >/dev/null 2>&1; then
        echo "[install] booting out $LABEL"
        launchctl bootout "gui/$UID_VAL/$LABEL" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

if [[ ! -f "$SRC" ]]; then
    echo "[install] FATAL: source plist missing: $SRC" >&2
    exit 1
fi

case "$MODE" in
    render)
        render
        ;;
    install)
        for payload in scripts/mailbox_janitor_cron.sh scripts/mailbox_janitor.py; do
            if [[ ! -f "$REPO_ROOT/$payload" ]]; then
                echo "[install] FATAL: payload missing: $REPO_ROOT/$payload" >&2
                exit 1
            fi
        done
        mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR"
        if [[ -f "$DEST" ]]; then
            bak="$DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$DEST" 2>/dev/null || true
            cp "$DEST" "$bak"
            echo "[install] backed up existing to $bak"
        fi
        bootout
        tmp="$DEST.tmp.$$"
        render > "$tmp"
        if ! plutil -lint "$tmp" >/dev/null 2>&1; then
            echo "[install] FATAL: plutil lint failed on rendered plist" >&2
            plutil -lint "$tmp"; rm -f "$tmp"
            exit 1
        fi
        if ! python3 -c 'import plistlib,sys; plistlib.load(open(sys.argv[1],"rb"))' "$tmp" 2>&1; then
            echo "[install] FATAL: plistlib cannot parse the rendered plist (XML comment hyphens?)" >&2
            rm -f "$tmp"
            exit 1
        fi
        mv "$tmp" "$DEST"
        chmod 0444 "$DEST"
        echo "[install] bootstrapping $LABEL (payload $REPO_ROOT/scripts/mailbox_janitor_cron.sh)"
        if ! launchctl bootstrap "gui/$UID_VAL" "$DEST"; then
            echo "[install] FATAL: launchctl bootstrap failed for $LABEL (plist left at $DEST, job NOT loaded)" >&2
            exit 1
        fi
        if ! launchctl print "gui/$UID_VAL/$LABEL" >/dev/null 2>&1; then
            echo "[install] FATAL: $LABEL not visible under gui/$UID_VAL after bootstrap" >&2
            exit 1
        fi
        echo "[install] done: $LABEL loaded. Verify: launchctl print gui/$UID_VAL/$LABEL | grep -E 'state|runs'"
        ;;
    uninstall|--uninstall)
        bootout
        if [[ -f "$DEST" ]]; then
            chmod u+w "$DEST" 2>/dev/null || true
            rm -f "$DEST"
            echo "[install] removed $DEST"
        fi
        ;;
    *)
        echo "Usage: $0 [install|uninstall|render]" >&2
        exit 2
        ;;
esac
