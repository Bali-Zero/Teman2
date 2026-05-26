#!/bin/bash
# install_repomap_cron.sh - SOTA L4 2026-05-24
#
# Install (or reload) the two LaunchAgents that power the repomap +
# branch-cleanup pipeline.
#
# Usage:
#   bash infra/launchagents/install_repomap_cron.sh
#   bash infra/launchagents/install_repomap_cron.sh --uninstall

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABELS=(
    "com.nuzantara.repomap.15min"
    "com.nuzantara.branch-cleanup.weekly"
)

MODE="${1:-install}"

mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR"

bootout() {
    local label="$1"
    if launchctl print "gui/$UID_VAL/$label" >/dev/null 2>&1; then
        echo "[install_repomap_cron] booting out $label"
        launchctl bootout "gui/$UID_VAL/$label" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

bootstrap() {
    local label="$1"
    local plist="$PLIST_DEST_DIR/$label.plist"
    if [[ ! -f "$plist" ]]; then
        echo "[install_repomap_cron] WARN: $plist missing"
        return 1
    fi
    if ! plutil -lint "$plist" >/dev/null 2>&1; then
        echo "[install_repomap_cron] FATAL: $plist plutil lint failed"
        plutil -lint "$plist"
        return 1
    fi
    echo "[install_repomap_cron] bootstrapping $label"
    launchctl bootstrap "gui/$UID_VAL" "$plist"
}

case "$MODE" in
    install)
        for label in "${LABELS[@]}"; do
            src="$PLIST_SRC_DIR/$label.plist"
            dest="$PLIST_DEST_DIR/$label.plist"
            if [[ ! -f "$src" ]]; then
                echo "[install_repomap_cron] FATAL: source plist missing: $src" >&2
                exit 1
            fi
            # Backup existing
            if [[ -f "$dest" ]]; then
                bak="$dest.pre-install-$(date +%Y%m%d-%H%M%S)"
                chmod u+w "$dest" 2>/dev/null || true
                cp "$dest" "$bak"
                echo "[install_repomap_cron] backed up existing → $bak"
            fi
            # Bootout if loaded
            bootout "$label"
            # Copy + mode 0444 per VADEMECUM hardening
            cp "$src" "$dest"
            chmod 0644 "$dest"
            echo "[install_repomap_cron] copied $src → $dest"
            # Bootstrap
            bootstrap "$label"
            # Show status
            launchctl print "gui/$UID_VAL/$label" 2>/dev/null \
                | grep -E "state|last exit code|program" | head -5 \
                || echo "[install_repomap_cron] WARN: $label not visible after bootstrap"
            echo ""
        done
        echo "[install_repomap_cron] install complete."
        echo "Logs:"
        echo "  - $LOG_DIR/repomap.log"
        echo "  - $LOG_DIR/repomap.error.log"
        echo "  - $LOG_DIR/branch-cleanup.log"
        ;;
    --uninstall|uninstall)
        for label in "${LABELS[@]}"; do
            bootout "$label"
            dest="$PLIST_DEST_DIR/$label.plist"
            if [[ -f "$dest" ]]; then
                chmod u+w "$dest" 2>/dev/null || true
                rm -f "$dest"
                echo "[install_repomap_cron] removed $dest"
            fi
        done
        echo "[install_repomap_cron] uninstall complete."
        ;;
    *)
        echo "Usage: $0 [install|--uninstall]" >&2
        exit 64
        ;;
esac

exit 0
