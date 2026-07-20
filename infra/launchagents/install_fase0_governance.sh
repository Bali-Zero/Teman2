#!/bin/bash
# install_fase0_governance.sh — FASE-0 armament rearm (W69 BUCO #2 + W67 mutual-watch)
#
# Arms the H24 governance-liveness layer on Pro/Mini that W69 found disarmed
# (running only per-PR in CI, never H24). Three LaunchAgents, StartInterval-based
# (KeepAlive false), NO secrets in any plist (the deadman sources its own token):
#
#   com.nuzantara.verify-the-verifiers (600s) -> verify_the_verifiers.py --scope all
#       Silent writer: emits verify_the_verifiers.json AND renders disarmed
#       safety gates observable (disarmed_ids). The P1 §4 meta-verifier, H24.
#   com.nuzantara.mcp-integrity (900s)         -> verify_mcp_integrity.sh
#       MCP reachability guardian: emits mcp_integrity.json + a drift baseline.
#       RED only on a NEW failure vs baseline (read-only; never restarts).
#   com.nuzantara.cost-breaker-deadman (600s)  -> cost_breaker_deadman.sh
#       The G5 second observer: alerts (Telegram, cooldown) if ANY of the three
#       alive-signals above goes stale > 1800s — i.e. governance went mute.
#   com.nuzantara.review-gate (600s)           -> review_gate_run.sh
#       Review-ONLY tri-LLM gate: posts a 3-LLM review COMMENT on each open
#       agent/* PR whose head SHA is new. NEVER labels/approves/merges (Legge 5).
#       fcntl.flock single-run; idempotent per (pr, head_sha); per-sweep cap.
#       Auto-merge is a separate deferred phase (GitHub App check-run).
#
# Signal-writers are installed BEFORE the deadman so their signals exist when it
# first runs. RUNTIME HOME = the deploy worktree (~/nuzantara-deploy),
# the deploy-puller-refreshed checkout that carries the FASE-0 scripts (the main
# checkout was on an older branch missing them — see W69).
#
# GRACEFUL: a label whose runtime script is not yet present (e.g. mcp-integrity
# before this PR has merged + the deploy worktree has synced) is SKIPPED with a
# warning, not a hard failure — re-run post-merge to arm it (W64: never ship a
# cron that no-ops; refuse to install one whose script is absent).
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
RUNTIME_ROOT="$HOME/nuzantara-deploy"

# Install order: signal-writers first, the deadman (watcher) last.
LABELS=(
    "com.nuzantara.verify-the-verifiers"
    "com.nuzantara.mcp-integrity"
    "com.nuzantara.cost-breaker-deadman"
    "com.nuzantara.review-gate"
)
# Each label's runtime script — install is SKIPPED if it is absent. A case()
# function, NOT a `declare -A` associative array: macOS /bin/bash is 3.2 and
# associative arrays are bash 4+ only (they raise "invalid arithmetic operator").
runtime_for() {
    case "$1" in
        com.nuzantara.verify-the-verifiers) echo "$RUNTIME_ROOT/scripts/verify_the_verifiers.py" ;;
        com.nuzantara.mcp-integrity)        echo "$RUNTIME_ROOT/scripts/verify_mcp_integrity.sh" ;;
        com.nuzantara.cost-breaker-deadman) echo "$RUNTIME_ROOT/scripts/cost_breaker_deadman.sh" ;;
        com.nuzantara.review-gate)          echo "$RUNTIME_ROOT/scripts/review_gate_run.sh" ;;
        *) echo "" ;;
    esac
}

MODE="${1:-install}"

# The P4 seam-verify Stop-hook, versioned in-repo. Installed to ~/.claude/hooks and
# registered in settings.json so the verify-the-verifiers gate (id: seam_verify) sees
# it ARMED. Idempotent; advisory-only (never blocks). No secrets involved.
HOOK_SRC="$REPO_ROOT/scripts/hooks/seam_verify.py"
HOOK_DEST="$HOME/.claude/hooks/seam_verify.py"
SETTINGS_JSON="$HOME/.claude/settings.json"

install_seam_verify_hook() {
    if [[ ! -f "$HOOK_SRC" ]]; then
        echo "[install] SKIP seam_verify hook — source absent: $HOOK_SRC"
        return 0
    fi
    mkdir -p "$(dirname "$HOOK_DEST")"
    cp "$HOOK_SRC" "$HOOK_DEST"
    chmod +x "$HOOK_DEST"
    echo "[install] seam_verify hook -> $HOOK_DEST"
    # Register under Stop in settings.json if not already present (idempotent).
    if [[ -f "$SETTINGS_JSON" ]]; then
        python3 - "$SETTINGS_JSON" <<'PYREG'
import json, os, sys
p = sys.argv[1]
try:
    d = json.load(open(p))
except Exception as e:
    print(f"[install]   settings.json unreadable, skip register: {e}")
    sys.exit(0)
stop = d.setdefault("hooks", {}).setdefault("Stop", [])
already = any(
    "seam_verify.py" in (h.get("command", ""))
    for grp in stop if isinstance(grp, dict)
    for h in grp.get("hooks", [])
)
if already:
    print("[install]   seam_verify already registered in settings.json")
    sys.exit(0)
stop.append({"hooks": [{"type": "command",
                        "command": "python3 ~/.claude/hooks/seam_verify.py",
                        "timeout": 15000}]})
tmp = p + ".tmp"
json.dump(d, open(tmp, "w"), indent=2, ensure_ascii=False)
os.replace(tmp, p)
print("[install]   registered seam_verify under Stop in settings.json")
PYREG
    else
        echo "[install]   no settings.json — hook copied but not registered"
    fi
}

mkdir -p "$PLIST_DEST_DIR" "$LOG_DIR" "$STATE_DIR"

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
                echo "[install] backed up existing → $bak"
            fi
            bootout "$label"
            # Copy + mode 0444 per VADEMECUM hardening (NO secrets in these plists).
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
        # The seam-verify Stop-hook is orthogonal to the LaunchAgents (it lives in
        # ~/.claude/hooks, not launchd) — install it regardless of how many agents
        # were installed, so it arms even where the deploy worktree isn't present.
        install_seam_verify_hook
        if [[ "$installed" == "0" ]]; then
            echo "[install] WARN: no LaunchAgent installed — no runtime script at $RUNTIME_ROOT/scripts" >&2
            echo "[install]   (seam_verify hook was still handled above)"
        fi
        echo "[install] done ($installed agent(s) + seam_verify hook). Verify with: bash $0 --verify"
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
        if [[ -f "$HOOK_DEST" ]]; then
            rm -f "$HOOK_DEST"
            echo "[install] removed $HOOK_DEST (settings.json registration left intact — harmless if file absent)"
        fi
        echo "[install] uninstalled."
        ;;
    --verify)
        for label in "${LABELS[@]}"; do
            echo "--- $label ---"
            launchctl print "gui/$UID_VAL/$label" 2>/dev/null \
                | grep -E "state =|runs =|last exit code" || echo "  NOT LOADED"
        done
        echo "--- alive signals (deadman observes the first 3) ---"
        for f in verify_the_verifiers.json sentinel_meta_watchdog.json mcp_integrity.json cost_breaker_deadman.json; do
            if [[ -f "$STATE_DIR/$f" ]]; then
                age=$(( $(date +%s) - $(stat -f %m "$STATE_DIR/$f") ))
                echo "  $f  age=${age}s"
            else
                echo "  $f  MISSING"
            fi
        done
        echo "--- seam_verify hook ---"
        if [[ -f "$HOOK_DEST" ]]; then
            echo "  installed: $HOOK_DEST"
            if grep -q "seam_verify.py" "$SETTINGS_JSON" 2>/dev/null; then
                echo "  registered in settings.json: yes"
            else
                echo "  registered in settings.json: NO (run install)"
            fi
        else
            echo "  NOT installed (run install)"
        fi
        ;;
    *)
        echo "Usage: $0 [install|--uninstall|--verify]" >&2
        exit 2
        ;;
esac
