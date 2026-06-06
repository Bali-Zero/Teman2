#!/bin/bash
# install_chronic_failure_digest.sh
#
# Install (or reload) the weekly chronic-failure digest LaunchAgent.
# Complements ~/scripts/audit-launchd-daily.sh: the daily audit alerts only on a
# *delta* (new-since-yesterday), so a job red for many consecutive days drops off
# the radar after day 1 (W55 suppression family). This digest re-reads the last N
# daily JSON snapshots, computes per-job consecutive-red streaks, cross-references
# circuit_breakers.json + dlq.json, and emits ONE weekly Telegram digest.
#
# Usage:
#   bash infra/launchagents/install_chronic_failure_digest.sh
#   bash infra/launchagents/install_chronic_failure_digest.sh --uninstall

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABEL="com.nuzantara.chronic-failure-digest.weekly"

MODE="${1:-install}"

mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR"

bootout() {
    local label="$1"
    if launchctl print "gui/$UID_VAL/$label" >/dev/null 2>&1; then
        echo "[install_chronic_failure_digest] booting out $label"
        launchctl bootout "gui/$UID_VAL/$label" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

bootstrap() {
    local label="$1"
    local plist="$PLIST_DEST_DIR/$label.plist"
    if [[ ! -f "$plist" ]]; then
        echo "[install_chronic_failure_digest] WARN: $plist missing"
        return 1
    fi
    if ! plutil -lint "$plist" >/dev/null 2>&1; then
        echo "[install_chronic_failure_digest] FATAL: $plist plutil lint failed"
        plutil -lint "$plist"
        return 1
    fi
    echo "[install_chronic_failure_digest] bootstrapping $label"
    launchctl bootstrap "gui/$UID_VAL" "$plist"
}

case "$MODE" in
    install)
        src="$PLIST_SRC_DIR/$LABEL.plist"
        dest="$PLIST_DEST_DIR/$LABEL.plist"
        wrapper="$PLIST_SRC_DIR/chronic_failure_digest.sh"
        digest="$PLIST_SRC_DIR/chronic_failure_digest.py"

        if [[ ! -f "$src" ]]; then
            echo "[install_chronic_failure_digest] FATAL: source plist missing: $src" >&2
            exit 1
        fi
        if [[ ! -f "$wrapper" || ! -f "$digest" ]]; then
            echo "[install_chronic_failure_digest] FATAL: digest scripts missing in $PLIST_SRC_DIR" >&2
            exit 1
        fi

        # Ensure the runner scripts are executable.
        chmod +x "$wrapper" "$digest" 2>/dev/null || true

        # Backup existing dest plist if present.
        if [[ -f "$dest" ]]; then
            bak="$dest.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$dest" 2>/dev/null || true
            cp "$dest" "$bak"
            chmod 0400 "$bak" 2>/dev/null || true   # hardening: backups not world-readable (W65)
            echo "[install_chronic_failure_digest] backed up existing → $bak"
        fi

        bootout "$LABEL"
        cp "$src" "$dest"
        chmod 0644 "$dest"
        echo "[install_chronic_failure_digest] copied $src → $dest"

        bootstrap "$LABEL"
        launchctl print "gui/$UID_VAL/$LABEL" 2>/dev/null \
            | grep -E "state|last exit code|program" | head -5 \
            || echo "[install_chronic_failure_digest] WARN: $LABEL not visible after bootstrap"
        echo ""
        echo "[install_chronic_failure_digest] install complete."
        echo "Schedule: Monday 08:30 WITA (weekly)."
        echo "Logs:"
        echo "  - $LOG_DIR/chronic-failure-digest.log"
        echo "  - $LOG_DIR/chronic-failure-digest.error.log"
        echo "Smoke test (no Telegram POST):"
        echo "  CHRONIC_DIGEST_DRY_RUN=1 python3 $digest"
        ;;
    --uninstall|uninstall)
        bootout "$LABEL"
        dest="$PLIST_DEST_DIR/$LABEL.plist"
        if [[ -f "$dest" ]]; then
            chmod u+w "$dest" 2>/dev/null || true
            rm -f "$dest"
            echo "[install_chronic_failure_digest] removed $dest"
        fi
        echo "[install_chronic_failure_digest] uninstall complete."
        ;;
    *)
        echo "Usage: $0 [install|--uninstall]" >&2
        exit 64
        ;;
esac

exit 0
