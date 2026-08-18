#!/bin/bash
# install_seat_usage_cron.sh — arm the per-machine seat-usage collector (consumption dashboard feed).
#
# Renders scripts/usage/com.nuzantara.seat-usage.plist.template into
# ~/Library/LaunchAgents (substituting __REPO__/__HOME__), bootstraps it, and
# verifies with a REAL one-shot collector run — never just the plist load
# (famiglia #2: esiste ≠ armato; green launchctl is not a working collector).
#
# The snapshot feeds ~/.agent/cost-ledger/seat_usage_snapshot.json — the file
# orchestrators read to ROUTE across seats (MODEL_ROSTER.md §Throughput
# doctrine: the dashboard is informative, never a limiter).
#
# Runtime root = $HOME/nuzantara (same convention as the army lanes' plists —
# the checkout that auto-pulls on Pro/Mini). W64 graceful: if the collector
# script is absent in that checkout, SKIP with a warning, never install a
# cron armed at nothing (W81).
#
# Usage:
#   bash infra/launchagents/install_seat_usage_cron.sh            # install + verify
#   bash infra/launchagents/install_seat_usage_cron.sh --uninstall
#   bash infra/launchagents/install_seat_usage_cron.sh --verify   # one-shot collector run only

set -uo pipefail

LABEL="com.nuzantara.seat-usage"
RUNTIME_ROOT="$HOME/nuzantara"
COLLECTOR="$RUNTIME_ROOT/scripts/usage/seat_usage_collector.py"
TEMPLATE_REL="scripts/usage/com.nuzantara.seat-usage.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
OUT_SNAPSHOT="$HOME/.agent/cost-ledger/seat_usage_snapshot.json"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

# Resolve the template from the checkout this installer itself lives in (a
# worktree run still finds its own copy), falling back to the runtime root.
SELF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="$SELF_ROOT/$TEMPLATE_REL"
[ -f "$TEMPLATE" ] || TEMPLATE="$RUNTIME_ROOT/$TEMPLATE_REL"

MODE="${1:-install}"

verify_run() {
    # PROVE the collector by its downstream artifact, not its exit code:
    # snapshot file must exist and be fresh (mtime within 2 minutes).
    /usr/bin/python3 "$COLLECTOR" --out "$OUT_SNAPSHOT"
    local rc=$?
    if [ $rc -ne 0 ]; then
        echo "VERIFY FAIL: collector exited $rc" >&2
        return 1
    fi
    if [ ! -f "$OUT_SNAPSHOT" ]; then
        echo "VERIFY FAIL: collector exited 0 but wrote no snapshot at $OUT_SNAPSHOT (W84 green-but-dead)" >&2
        return 1
    fi
    local age
    age=$(( $(date +%s) - $(stat -f %m "$OUT_SNAPSHOT") ))
    if [ "$age" -gt 120 ]; then
        echo "VERIFY FAIL: snapshot exists but is ${age}s old — this run did not write it" >&2
        return 1
    fi
    echo "VERIFY OK: $OUT_SNAPSHOT fresh (${age}s old)"
}

case "$MODE" in
    --uninstall)
        launchctl bootout "gui/$UID_VAL/$LABEL" 2>/dev/null
        rm -f "$PLIST_DEST"
        echo "uninstalled $LABEL"
        ;;
    --verify)
        verify_run
        ;;
    install|--install)
        if [ ! -f "$COLLECTOR" ]; then
            echo "SKIP: $COLLECTOR not present in the runtime checkout — pull first, then re-run (W64 graceful, W81 never arm at nothing)" >&2
            exit 3
        fi
        if [ ! -f "$TEMPLATE" ]; then
            echo "SKIP: template $TEMPLATE_REL not found in either checkout" >&2
            exit 3
        fi
        mkdir -p "$LOG_DIR" "$(dirname "$OUT_SNAPSHOT")" "$HOME/Library/LaunchAgents"
        # W64: dedicated log dir must exist BEFORE launchd first writes — a
        # missing log dir silently killed 35 crontab lines on 2026-08-18.
        sed -e "s|__REPO__|$RUNTIME_ROOT|g" -e "s|__HOME__|$HOME|g" "$TEMPLATE" > "$PLIST_DEST"
        launchctl bootout "gui/$UID_VAL/$LABEL" 2>/dev/null
        launchctl bootstrap "gui/$UID_VAL" "$PLIST_DEST" || {
            echo "bootstrap failed for $LABEL" >&2
            exit 1
        }
        # The proof must come from LAUNCHD writing the artifact — a direct
        # collector run here would certify a fresh snapshot over a dead
        # LaunchAgent (famiglia #2). Kickstart the job and poll the
        # snapshot's mtime; only a daemon-written fresh file passes.
        before_mtime=0
        [ -f "$OUT_SNAPSHOT" ] && before_mtime="$(stat -f %m "$OUT_SNAPSHOT")"
        launchctl kickstart "gui/$UID_VAL/$LABEL" || {
            echo "kickstart failed for $LABEL — the agent is loaded but not runnable" >&2
            exit 1
        }
        deadline=$(( $(date +%s) + 60 ))
        while [ "$(date +%s)" -lt "$deadline" ]; do
            if [ -f "$OUT_SNAPSHOT" ] && [ "$(stat -f %m "$OUT_SNAPSHOT")" -gt "$before_mtime" ]; then
                echo "ARMED OK: launchd wrote $OUT_SNAPSHOT (mtime advanced past $before_mtime)"
                exit 0
            fi
            /bin/sleep 2
        done
        echo "ARM FAIL: agent bootstrapped+kickstarted but no launchd-written snapshot within 60s — read $LOG_DIR/seat-usage.err.log (W84: loaded is not working)" >&2
        exit 1
        ;;
    *)
        echo "usage: $0 [--uninstall|--verify]" >&2
        exit 2
        ;;
esac
