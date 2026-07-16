#!/bin/bash
# install_cost_ledger_bridge.sh — arm the cost-ledger bridge + cost-breaker H24.
#
# Companion to install_fase0_governance.sh (kept SEPARATE so the existing
# 3-label governance installer is untouched). Arms two StartInterval LaunchAgents
# (KeepAlive false, NO secrets in any plist):
#
#   com.nuzantara.cost-ledger-export (1800s) -> cost_ledger_export_run.sh
#       READ-ONLY bridge: SELECT recent (provider, cost_usd, ts_utc) from the Fly
#       PG ledger (llm_cost_events, mig 117) and write daily JSONL the breaker
#       reads. PG password from the macOS Keychain (T3.2), never in the plist.
#   com.nuzantara.cost-breaker (3600s)       -> cost_breaker_run.sh
#       The P9 GOVERN breaker, now reading KNOWN spend from the export dir
#       (LLM_COST_JSONL_ROOT) instead of UNKNOWN. STOP push token sourced from
#       ~/.nuzantara-secrets.env by the wrapper, never in the plist.
#
# The exporter is installed BEFORE the breaker so the JSONL exists on the
# breaker's first tick. RUNTIME HOME = the deploy worktree
# (~/nuzantara-deploy), the deploy-puller-refreshed checkout that carries
# these scripts (W69 convention).
#
# GRACEFUL (W64): a label whose runtime script is not yet present in the deploy
# worktree is SKIPPED with a warning, not a hard failure — re-run post-merge +
# deploy-pull to arm it (never ship a cron that no-ops on a missing script).
#
# Usage:
#   bash infra/launchagents/install_cost_ledger_bridge.sh
#   bash infra/launchagents/install_cost_ledger_bridge.sh --uninstall
#   bash infra/launchagents/install_cost_ledger_bridge.sh --verify

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC_DIR="$REPO_ROOT/infra/launchagents"
PLIST_DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/logs"
STATE_DIR="$HOME/.agent/decisions/state"
EXPORT_DIR="$HOME/.agent/cost-ledger"
UID_VAL="$(id -u)"

# The runtime checkout the plists point at. Must carry the bridge scripts.
RUNTIME_ROOT="$HOME/nuzantara-deploy"

# Install order: the exporter (signal-writer) first, the breaker (consumer) last.
LABELS=(
    "com.nuzantara.cost-ledger-export"
    "com.nuzantara.cost-breaker"
)

# Each label's runtime script — install is SKIPPED if it is absent. A case()
# function, NOT a `declare -A` (macOS /bin/bash is 3.2, no associative arrays).
runtime_for() {
    case "$1" in
        com.nuzantara.cost-ledger-export) echo "$RUNTIME_ROOT/scripts/cost_ledger_export_run.sh" ;;
        com.nuzantara.cost-breaker)       echo "$RUNTIME_ROOT/scripts/cost_breaker_run.sh" ;;
        *) echo "" ;;
    esac
}

MODE="${1:-install}"

mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR" "$STATE_DIR" "$EXPORT_DIR"

bootout() {
    local label="$1"
    if launchctl print "gui/$UID_VAL/$label" >/dev/null 2>&1; then
        echo "[install] booting out $label"
        launchctl bootout "gui/$UID_VAL/$label" 2>&1 | grep -v "Boot-out failed" || true
    fi
}

case "$MODE" in
    install)
        installed=0
        for label in "${LABELS[@]}"; do
            src="$PLIST_SRC_DIR/$label.plist"
            dest="$PLIST_DEST_DIR/$label.plist"
            runtime="$(runtime_for "$label")"
            if [[ ! -f "$src" ]]; then
                echo "[install] FATAL: source plist missing: $src" >&2
                exit 1
            fi
            if [[ ! -f "$runtime" ]]; then
                echo "[install] SKIP $label — runtime script absent: $runtime"
                echo "[install]   (re-run after this PR merges + the deploy worktree syncs)"
                continue
            fi
            if [[ -f "$dest" ]]; then
                bak="$dest.pre-install-$(date +%Y%m%d-%H%M%S)"
                chmod u+w "$dest" 2>/dev/null || true
                cp "$dest" "$bak"
                chmod 0444 "$bak" 2>/dev/null || true
                echo "[install] backed up existing -> $bak"
            fi
            bootout "$label"
            cp "$src" "$dest"
            chmod 0444 "$dest"
            if ! plutil -lint "$dest" >/dev/null 2>&1; then
                echo "[install] FATAL: $dest plutil lint failed" >&2
                plutil -lint "$dest"
                exit 1
            fi
            echo "[install] bootstrapping $label"
            launchctl bootstrap "gui/$UID_VAL" "$dest"
            installed=$((installed + 1))
        done
        if [[ "$installed" == "0" ]]; then
            echo "[install] FATAL: nothing installed — no runtime script present at $RUNTIME_ROOT/scripts" >&2
            exit 1
        fi
        echo "[install] done ($installed agent(s)). Verify with: bash $0 --verify"
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
        echo "--- exported JSONL (the breaker's KNOWN-spend source) ---"
        shopt -s nullglob
        files=("$EXPORT_DIR"/llm_cost_log.*.jsonl)
        if [[ ${#files[@]} -eq 0 ]]; then
            echo "  no JSONL under $EXPORT_DIR yet (exporter has not run)"
        else
            for f in "${files[@]}"; do
                age=$(( $(date +%s) - $(stat -f %m "$f") ))
                echo "  $(basename "$f")  rows=$(wc -l < "$f" | tr -d ' ')  age=${age}s"
            done
        fi
        ;;
    *)
        echo "Usage: $0 [install|--uninstall|--verify]" >&2
        exit 2
        ;;
esac
