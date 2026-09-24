#!/usr/bin/env bash
# Install/verify/remove the Mini-only weekly KBLI OSS refresh LaunchAgent (F4).
# The shipper runs this on Mini after merge, after one manual wrapper run.
# No Sentinel job_registry row: that registry lives on Pro and reads Pro-local
# cron-runner receipts, so a Mini row there would describe a job it cannot see.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="com.nuzantara.kbli-oss-refresh.weekly"
PLIST_SRC="$REPO_ROOT/infra/launchagents/$LABEL.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/kbli-oss-refresh-run.sh"
RUNNER="$REPO_ROOT/scripts/cron-runner.sh"
LOOP="$REPO_ROOT/scripts/kbli_filiera/oss_refresh_loop.py"
RECEIPT="$HOME/.agent/decisions/state/kbli_oss_refresh.last.json"
HEARTBEAT="$HOME/.organism/last_seen/mini.kbli_oss_refresh.json"
LOG_DIR="$HOME/logs/kbli-oss-refresh"
UID_VAL="$(id -u)"
MODE="${1:-install}"

require_mini() {
    local current
    # Lower-cased before the compare, same idiom as the wrapper and the
    # sibling Mini wrappers (D4).
    current="$(hostname -s 2>/dev/null || hostname)"
    current="$(printf '%s' "$current" | tr '[:upper:]' '[:lower:]')"
    if [ "$current" != "mini-pro2" ]; then
        echo "FATAL: $LABEL is Mini-only; current host=$current" >&2
        exit 69
    fi
}

lint_sources() {
    local path
    for path in "$PLIST_SRC" "$WRAPPER" "$RUNNER" "$LOOP"; do
        [ -f "$path" ] || { echo "FATAL: required source missing: $path" >&2; return 1; }
    done
    /usr/bin/plutil -lint "$PLIST_SRC"
    /bin/bash -n "$WRAPPER"
}

bootout() {
    if /bin/launchctl print "gui/$UID_VAL/$LABEL" >/dev/null 2>&1; then
        /bin/launchctl bootout "gui/$UID_VAL/$LABEL"
    fi
}

verify_receipts() {
    local now path age
    now="$(date +%s)"
    for path in "$RECEIPT" "$HEARTBEAT"; do
        if [ ! -s "$path" ]; then
            echo "MISSING: $path"
            return 1
        fi
        /usr/bin/python3 -m json.tool "$path" >/dev/null
        age=$((now - $(/usr/bin/stat -f %m "$path")))
        echo "OK: $path age=${age}s"
        /usr/bin/tail -n 1 "$path"
    done
}

case "$MODE" in
    --lint|lint)
        lint_sources
        echo "source lint clean: plist, wrapper, runner, loop"
        ;;
    install|--install)
        require_mini
        lint_sources
        /bin/mkdir -p "$(dirname "$PLIST_DEST")" "$LOG_DIR" "$(dirname "$RECEIPT")"
        /bin/chmod +x "$WRAPPER"
        if [ -f "$PLIST_DEST" ]; then
            backup="$PLIST_DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            /bin/cp "$PLIST_DEST" "$backup"
            /bin/chmod 0400 "$backup"
            echo "backed up $PLIST_DEST -> $backup"
        fi
        bootout
        /bin/cp "$PLIST_SRC" "$PLIST_DEST"
        /bin/chmod 0444 "$PLIST_DEST"
        /usr/bin/plutil -lint "$PLIST_DEST"
        /bin/launchctl bootstrap "gui/$UID_VAL" "$PLIST_DEST"
        echo "installed $LABEL (not kickstarted); first run: $0 --kickstart, then $0 --verify"
        ;;
    --kickstart|kickstart)
        require_mini
        /bin/launchctl kickstart -k "gui/$UID_VAL/$LABEL"
        echo "kickstarted $LABEL; after completion run: $0 --verify"
        ;;
    --verify|verify)
        require_mini
        lint_sources
        /bin/launchctl print "gui/$UID_VAL/$LABEL" | /usr/bin/grep -E "state =|runs =|last exit code|program =" || true
        verify_receipts
        ;;
    --uninstall|uninstall)
        require_mini
        bootout
        if [ -f "$PLIST_DEST" ]; then
            /bin/chmod u+w "$PLIST_DEST"
            /bin/rm -f "$PLIST_DEST"
        fi
        echo "uninstalled $LABEL; receipts/logs/reports retained for audit"
        ;;
    *)
        echo "Usage: $0 [--lint|install|--kickstart|--verify|--uninstall]" >&2
        exit 64
        ;;
esac
