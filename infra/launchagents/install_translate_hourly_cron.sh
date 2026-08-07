#!/bin/bash
# install_translate_hourly_cron.sh — mouth main-dirt structural fix, 2026-08-07
#
# Installs (or reloads) com.balizero.translate.hourly, now pointed at
# scripts/translate-articles-cron-wrapper.sh instead of translate-articles.py
# directly, so the hourly translation run works in an isolated worktree and
# auto-promotes its output via PR instead of writing straight into the main
# checkout's tracked working tree (cicatrix-superscar.md Family #1/#2 shape).
#
# This plist previously lived ONLY on-disk in ~/Library/LaunchAgents with no
# repo-tracked source of truth — bringing it here closes that HOME-fork gap
# too. Modeled on install_repomap_cron.sh's bootout/backup/bootstrap pattern.
#
# Usage:
#   bash infra/launchagents/install_translate_hourly_cron.sh
#   bash infra/launchagents/install_translate_hourly_cron.sh --uninstall

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABEL="com.balizero.translate.hourly"

MODE="${1:-install}"

mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR"

bootout() {
    local label="$1"
    if launchctl print "gui/$UID_VAL/$label" >/dev/null 2>&1; then
        echo "[install_translate_hourly_cron] booting out $label"
        launchctl bootout "gui/$UID_VAL/$label" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

bootstrap() {
    local label="$1"
    local plist="$PLIST_DEST_DIR/$label.plist"
    if [[ ! -f "$plist" ]]; then
        echo "[install_translate_hourly_cron] WARN: $plist missing"
        return 1
    fi
    if ! plutil -lint "$plist" >/dev/null 2>&1; then
        echo "[install_translate_hourly_cron] FATAL: $plist plutil lint failed"
        plutil -lint "$plist"
        return 1
    fi
    echo "[install_translate_hourly_cron] bootstrapping $label"
    launchctl bootstrap "gui/$UID_VAL" "$plist"
}

case "$MODE" in
    install)
        src="$PLIST_SRC_DIR/$LABEL.plist"
        dest="$PLIST_DEST_DIR/$LABEL.plist"
        wrapper="$REPO_ROOT/scripts/translate-articles-cron-wrapper.sh"
        if [[ ! -f "$src" ]]; then
            echo "[install_translate_hourly_cron] FATAL: source plist missing: $src" >&2
            exit 1
        fi
        if [[ ! -x "$wrapper" ]]; then
            echo "[install_translate_hourly_cron] FATAL: wrapper not executable: $wrapper" >&2
            exit 1
        fi
        # Backup existing
        if [[ -f "$dest" ]]; then
            bak="$dest.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$dest" 2>/dev/null || true
            cp "$dest" "$bak"
            echo "[install_translate_hourly_cron] backed up existing → $bak"
        fi
        # Bootout if loaded
        bootout "$LABEL"
        # Copy + mode 0644 per VADEMECUM hardening
        cp "$src" "$dest"
        chmod 0644 "$dest"
        echo "[install_translate_hourly_cron] copied $src → $dest"
        # Bootstrap
        bootstrap "$LABEL"
        # Show status
        launchctl print "gui/$UID_VAL/$LABEL" 2>/dev/null \
            | grep -E "state|last exit code|program" | head -5 \
            || echo "[install_translate_hourly_cron] WARN: $LABEL not visible after bootstrap"
        echo ""
        echo "[install_translate_hourly_cron] install complete."
        echo "Logs:"
        echo "  - $LOG_DIR/translate-hourly.log"
        echo "  - $LOG_DIR/translate-hourly.error.log"
        echo "  - $LOG_DIR/translate-hourly-wrapper.log (new — worktree/PR promotion trail)"
        ;;
    --uninstall|uninstall)
        bootout "$LABEL"
        dest="$PLIST_DEST_DIR/$LABEL.plist"
        if [[ -f "$dest" ]]; then
            chmod u+w "$dest" 2>/dev/null || true
            rm -f "$dest"
            echo "[install_translate_hourly_cron] removed $dest"
        fi
        echo "[install_translate_hourly_cron] uninstall complete."
        ;;
    *)
        echo "Usage: $0 [install|--uninstall]" >&2
        exit 64
        ;;
esac

exit 0
