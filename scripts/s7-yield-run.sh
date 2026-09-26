#!/usr/bin/env bash
# s7-yield-run.sh — LaunchAgent wrapper for S7, the CRM yield draft generator.
#
# S7 (scripts/s7_yield_draft_local.py) replaces com.balizero.yield-optimizer.weekly,
# retired 2026-08-20: that agent queried `crm_clients`, a table that does not exist
# in production (real table is `clients`), and depended on a 5-tier Claude cascade
# with no cross-family fallback for a print-mode agent — its last run (16/8/2026)
# had ALL FIVE Claude seats fail and the wrapper still `exit 0`'d (cron-theater,
# superscar family #2). S7 queries the real schema and is fully local/fail-closed.
#
# PII contract (UU PDP / SYMBIOSIS Law 2), enforced by s7_yield_draft_local.py itself,
# not by this wrapper:
#   - DB access: read-only role `nuzantara_readonly` via pg-proxy localhost:15432,
#     password from macOS Keychain (service nuzantara-postgres-readonly). Proven
#     readable from THIS exact GUI-launchd context by the sibling LaunchAgent
#     com.nuzantara.cost-ledger-export (30-min interval, live since before 2026-08-20,
#     same `security find-generic-password` call) — see PENDING-ARMS 2026-08-20 s7-cutover.
#   - Drafting LLM: Ollama qwen3.5:9b LOCAL only. If Ollama is down, the script itself
#     aborts non-zero with NO cloud fallback — this wrapper must never weaken that.
#   - stdout/stderr carry client_id + aggregate counts ONLY (script's own privacy-log
#     rule) — safe for this wrapper, cron-runner.sh's receipt, and the Telegram alert
#     to capture verbatim on failure.
#   - Drafts (which DO contain client PII) are written under $HOME, gitignored,
#     outside the repo tree, and are NEVER printed by this wrapper.
#
# Run via cron-runner.sh (not invoked directly by the plist) so failures get a
# Cell-readable receipt AND a deduped Telegram P0 through the proven gateway
# (tg_notify.py) — a wrapper that alarms for itself outside that path tends to go
# mute unheard (superscar W107/W108: 19 of 20 sibling wrappers failed silently this way).
#
# Kill-switch: S7_YIELD_ENABLED=false (S7_YIELD_OFF=1 still honoured). Either one
# writes a status=disabled heartbeat so the healer never mistakes a stopped organ
# for a dead one.
#
# Heartbeat: ~/.organism/last_seen/pro.s7_yield_weekly.json (organs_registry.yaml
# id pro.s7_yield_weekly) on every exit path. Its note carries the exit code only.

set -uo pipefail
unset ANTHROPIC_API_KEY

# Absolute PATH — never rely on a resolved-after-the-fact interpreter (W108: an
# alerting path that shares the failure mode of the thing it reports on is worse
# than no alert).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="${HOME:-/Users/nuzantara}"

REPO_ROOT="${S7_YIELD_REPO_ROOT:-$HOME/nuzantara}"
SCRIPT="$REPO_ROOT/scripts/s7_yield_draft_local.py"
LIMIT="${S7_YIELD_LIMIT:-10}"
ORGAN_ID="pro.s7_yield_weekly"

log() { echo "s7-yield-run: $*" >&2; }

# bash 3.2 exits the whole script when `source` cannot find the file: guard it,
# and fall back to a no-op so a missing library never blocks the run.
if [[ -f "$REPO_ROOT/scripts/lib/heartbeat.sh" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/scripts/lib/heartbeat.sh" || true
fi
if ! declare -F organism_heartbeat >/dev/null 2>&1; then
    organism_heartbeat() { :; }
fi

if [[ "${S7_YIELD_ENABLED:-true}" == "false" || "${S7_YIELD_OFF:-0}" == "1" ]]; then
    log "disabled via S7_YIELD_ENABLED=false / S7_YIELD_OFF=1"
    organism_heartbeat "$ORGAN_ID" "disabled" "kill-switch"
    exit 0
fi

PY="/opt/homebrew/bin/python3"
[[ -x "$PY" ]] || PY="/usr/bin/python3"

if [[ ! -f "$SCRIPT" ]]; then
    log "FATAL — $SCRIPT not found"
    organism_heartbeat "$ORGAN_ID" "error" "script missing"
    exit 1
fi

"$PY" "$SCRIPT" --all --limit "$LIMIT"
rc=$?
if [[ $rc -eq 0 ]]; then
    organism_heartbeat "$ORGAN_ID" "ok" "rc=0"
else
    organism_heartbeat "$ORGAN_ID" "error" "rc=$rc"
fi
exit "$rc"
