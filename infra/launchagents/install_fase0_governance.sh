#!/bin/bash
# install_fase0_governance.sh — FASE-0 armament rearm (W69 BUCO #2)
#
# Arms the H24 governance-liveness layer on Pro/Mini that W69 found disarmed
# (running only per-PR in CI, never H24):
#
#   com.nuzantara.verify-the-verifiers   — runs scripts/verify_the_verifiers.py
#       every 600s. SILENT writer (no Telegram): emits the alive-signal
#       ~/.agent/decisions/state/verify_the_verifiers.json AND renders disarmed
#       safety gates OBSERVABLE (disarmed_ids in the payload). This is the meta-
#       verifier (P1 §4) running H24, not just per-PR.
#   com.nuzantara.cost-breaker-deadman   — runs scripts/cost_breaker_deadman.sh
#       every 600s. The G5 dead-man's switch: the SECOND observer that alerts
#       (Telegram, cooldown-throttled) if verify_the_verifiers.json OR
#       sentinel_meta_watchdog.json goes stale beyond 1800s — i.e. governance
#       has gone mute. Sources its own secrets from ~/.nuzantara-secrets.env.
#
# RUNTIME HOME = the deploy worktree (~/Desktop/nuzantara-deploy), which is the
# stable, deploy-puller-refreshed checkout that actually carries the FASE-0
# scripts (the main checkout was on an older branch missing them — see W69).
# The plists hardcode that path; this installer only copies+bootstraps them.
#
# Usage:
#   bash infra/launchagents/install_fase0_governance.sh
#   bash infra/launchagents/install_fase0_governance.sh --uninstall
#   bash infra/launchagents/install_fase0_governance.sh --verify

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
STATE_DIR="$HOME/.agent/decisions/state"
UID_VAL="$(id -u)"

# The runtime checkout the plists point at. Must carry the FASE-0 scripts.
RUNTIME_ROOT="$HOME/Desktop/nuzantara-deploy"

LABELS=(
    "com.nuzantara.verify-the-verifiers"
    "com.nuzantara.cost-breaker-deadman"
)

MODE="${1:-install}"

mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR" "$STATE_DIR"

bootout() {
    local label="$1"
    if launchctl print "gui/$UID_VAL/$label" >/dev/null 2>&1; then
        echo "[install] booting out $label"
        launchctl bootout "gui/$UID_VAL/$label" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

preflight() {
    # The plists are useless if the runtime scripts they reference are absent.
    # Fail LOUD here rather than ship a cron that no-ops forever (W64).
    local missing=0
    for s in \
        "$RUNTIME_ROOT/scripts/verify_the_verifiers.py" \
        "$RUNTIME_ROOT/scripts/cost_breaker_deadman.sh"; do
        if [[ ! -f "$s" ]]; then
            echo "[install] FATAL: runtime script missing: $s" >&2
            echo "[install]   The plists point at $RUNTIME_ROOT — make sure it" >&2
            echo "[install]   is checked out at a ref that carries the FASE-0 scripts." >&2
            missing=1
        fi
    done
    [[ "$missing" == "0" ]] || exit 1
}

case "$MODE" in
    install)
        preflight
        for label in "${LABELS[@]}"; do
            src="$PLIST_SRC_DIR/$label.plist"
            dest="$PLIST_DEST_DIR/$label.plist"
            if [[ ! -f "$src" ]]; then
                echo "[install] FATAL: source plist missing: $src" >&2
                exit 1
            fi
            if [[ -f "$dest" ]]; then
                bak="$dest.pre-install-$(date +%Y%m%d-%H%M%S)"
                chmod u+w "$dest" 2>/dev/null || true
                cp "$dest" "$bak"
                chmod 0444 "$bak" 2>/dev/null || true
                echo "[install] backed up existing → $bak"
            fi
            bootout "$label"
            # Copy + mode 0444 per VADEMECUM hardening (NO secrets in these
            # plists — the deadman sources its token at runtime).
            cp "$src" "$dest"
            chmod 0444 "$dest"
            if ! plutil -lint "$dest" >/dev/null 2>&1; then
                echo "[install] FATAL: $dest plutil lint failed" >&2
                plutil -lint "$dest"
                exit 1
            fi
            echo "[install] bootstrapping $label"
            launchctl bootstrap "gui/$UID_VAL" "$dest"
        done
        echo "[install] done. Verify with: bash $0 --verify"
        ;;
    --uninstall)
        for label in "${LABELS[@]}"; do
            bootout "$label"
            dest="$PLIST_DEST_DIR/$label.plist"
            if [[ -f "$dest" ]]; then
                chmod u+w "$dest" 2>/dev/null || true
                rm -f "$dest"
                echo "[install] removed $dest"
            fi
        done
        echo "[install] uninstalled."
        ;;
    --verify)
        for label in "${LABELS[@]}"; do
            echo "--- $label ---"
            launchctl print "gui/$UID_VAL/$label" 2>/dev/null \
                | grep -E "state =|runs =|last exit code" || echo "  NOT LOADED"
        done
        echo "--- alive signals ---"
        for f in verify_the_verifiers.json sentinel_meta_watchdog.json cost_breaker_deadman.json; do
            if [[ -f "$STATE_DIR/$f" ]]; then
                age=$(( $(date +%s) - $(stat -f %m "$STATE_DIR/$f") ))
                echo "  $f  age=${age}s"
            else
                echo "  $f  MISSING"
            fi
        done
        ;;
    *)
        echo "Usage: $0 [install|--uninstall|--verify]" >&2
        exit 2
        ;;
esac
