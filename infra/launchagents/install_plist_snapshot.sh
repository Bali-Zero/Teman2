#!/bin/bash
# install_plist_snapshot.sh — plist disaster-recovery snapshot installer.
#
# Installs (or reloads) the daily LaunchAgent that mirrors every loaded
# com.{nuzantara,balizero,cell,matagaruda}.* plist into
# infra/launchagents/_snapshot-live/ with secrets REDACTED, lint+grep-verified,
# and committed to a dedicated DR branch.
#
# Cicatrix lineage: 2026-04-29 plist-truncation P0 (51/54 lost, no git copy) +
# W65 plist-secret leak. This installer DOES NOT run the snapshot — it only
# bootstraps the cron. The script itself is the deliverable.
#
# Usage:
#   bash infra/launchagents/install_plist_snapshot.sh
#   bash infra/launchagents/install_plist_snapshot.sh --uninstall

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
UID_VAL="$(id -u)"

LABEL="com.nuzantara.plist-snapshot.daily"
SRC="$PLIST_SRC_DIR/$LABEL.plist"
DEST="$PLIST_DEST_DIR/$LABEL.plist"
SNAPSHOT_SH="$PLIST_SRC_DIR/plist_snapshot_dr.sh"

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
        # The snapshot script must be present + executable before bootstrap.
        if [[ ! -f "$SNAPSHOT_SH" ]]; then
            echo "[install] FATAL: snapshot script missing: $SNAPSHOT_SH" >&2
            exit 1
        fi
        chmod 0755 "$SNAPSHOT_SH"
        echo "[install] chmod 0755 $SNAPSHOT_SH"

        # Backup existing dest if any.
        if [[ -f "$DEST" ]]; then
            bak="$DEST.pre-install-$(date +%Y%m%d-%H%M%S)"
            chmod u+w "$DEST" 2>/dev/null || true
            cp "$DEST" "$bak"
            # The backup carries no secret (this plist has none), but harden it
            # anyway per W65 ("hardening leaked its own backup").
            chmod 0644 "$bak"
            echo "[install] backed up existing → $bak"
        fi

        bootout

        # Copy + mode 0644 (no secrets in THIS plist; the snapshot it produces
        # is redacted, so no secret ever lands on disk world-readable).
        cp "$SRC" "$DEST"
        chmod 0644 "$DEST"
        echo "[install] copied $SRC → $DEST"

        if ! plutil -lint "$DEST" >/dev/null 2>&1; then
            echo "[install] FATAL: $DEST plutil lint failed"
            plutil -lint "$DEST"
            exit 1
        fi

        echo "[install] bootstrapping $LABEL"
        launchctl bootstrap "gui/$UID_VAL" "$DEST"

        launchctl print "gui/$UID_VAL/$LABEL" 2>/dev/null \
            | grep -E "state|last exit code|program" | head -5 \
            || echo "[install] WARN: $LABEL not visible after bootstrap"

        echo ""
        echo "[install] install complete."
        echo "Logs:"
        echo "  - $LOG_DIR/plist-snapshot.log"
        echo "  - $LOG_DIR/plist-snapshot.error.log"
        echo ""
        echo "Smoke test (no git, redaction + lint + leak-verify only):"
        echo "  PLIST_SNAPSHOT_DRY_RUN=true bash $SNAPSHOT_SH"
        echo ""
        echo "Kill switch:"
        echo "  launchctl setenv PLIST_SNAPSHOT_ENABLED false"
        ;;
    --uninstall|uninstall)
        bootout
        if [[ -f "$DEST" ]]; then
            chmod u+w "$DEST" 2>/dev/null || true
            rm -f "$DEST"
            echo "[install] removed $DEST"
        fi
        echo "[install] uninstall complete."
        ;;
    *)
        echo "Usage: $0 [install|--uninstall]" >&2
        exit 64
        ;;
esac

exit 0
