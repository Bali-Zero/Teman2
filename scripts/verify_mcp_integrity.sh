#!/usr/bin/env bash
# verify_mcp_integrity.sh — MCP server reachability + integrity baseline check.
#
# FASE-0 instrumentation re-arm (2026-06-09). This guardian was a cicatrix
# candidate ("MISSING — re-author or recover from Mini", zero-point-recovery
# 2026-05-28) and is referenced by the `mcp-health` agent spec as its core tool,
# but was never written. This is the first real implementation.
#
# WHAT IT DOES (read-only diagnose — NEVER restarts, NEVER mutates):
#   1. Count MCP servers declared in .mcp.json (config baseline).
#   2. Run `claude mcp list`, parse per-server state:
#        ✓ Connected | ⏸ Pending approval | ✗ Failed | (unknown)
#   3. Compare connected/total against a saved baseline; flag drift.
#   4. Emit a verdict line (GREEN/YELLOW/RED) + optional Telegram alert.
#
# State baseline: ~/.agent/decisions/state/mcp_integrity_baseline.json
#   - First run writes the baseline (current connected+declared counts).
#   - Later runs compare; --update rewrites it deliberately.
#
# Exit codes: 0 = GREEN/YELLOW (informational), 2 = RED (a server FAILED, or
# connected count dropped below baseline floor). RED is the only blocking signal.
#
# Why this is NOT a SPOF: short-lived (list → parse → compare → exit), cannot
# hang (claude mcp list has its own internal timeout), and if it crashes the
# next scheduled tick runs fresh.
#
# Usage:
#   verify_mcp_integrity.sh              # check against baseline
#   verify_mcp_integrity.sh --update     # rewrite baseline to current state
#   verify_mcp_integrity.sh --json       # machine-readable output
#
# Kill switch: env MCP_INTEGRITY_OFF=1 → exits 0 immediately.

set -uo pipefail

# --- Configuration ---------------------------------------------------------

REPO_ROOT="${NUZ_REPO_ROOT:-$HOME/Desktop/nuzantara}"
MCP_CONFIG="$REPO_ROOT/.mcp.json"
STATE_DIR="$HOME/.agent/decisions/state"
BASELINE_FILE="$STATE_DIR/mcp_integrity_baseline.json"
LOG_FILE="$HOME/logs/verify-mcp-integrity.log"
DRIFT_PCT=10                 # flag YELLOW if connected count drifts > this %

UPDATE_BASELINE=0
JSON_OUT=0
for arg in "$@"; do
    case "$arg" in
        --update) UPDATE_BASELINE=1 ;;
        --json)   JSON_OUT=1 ;;
    esac
done

# --- Kill switch ------------------------------------------------------------

if [[ "${MCP_INTEGRITY_OFF:-0}" == "1" ]]; then
    echo "[mcp-integrity] OFF (MCP_INTEGRITY_OFF=1) — skipping"
    exit 0
fi

mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")" 2>/dev/null || true

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE" 2>/dev/null || true; }

# --- 1. Declared count from .mcp.json --------------------------------------

if [[ ! -f "$MCP_CONFIG" ]]; then
    echo "[mcp-integrity] RED: .mcp.json not found at $MCP_CONFIG"
    log "RED: .mcp.json missing"
    exit 2
fi

declared=$(python3 -c "
import json, sys
try:
    d = json.load(open('$MCP_CONFIG'))
    s = d.get('mcpServers', d.get('servers', {}))
    print(len(s))
except Exception:
    print(0)
")

# --- 2. Live reachability via `claude mcp list` ----------------------------
# REAL timeout guard: `claude mcp list` health-checks every server and CAN HANG
# in a no-TTY launchd context (empirically 2026-06-09: two stuck procs piled up
# per cron tick, signal never written → deadman saw it perpetually stale). The
# old "has its own internal timeout" claim was false here. coreutils
# timeout/gtimeout is in the plist PATH (/opt/homebrew/bin).
_to="$(command -v timeout || command -v gtimeout || true)"
if [[ -n "$_to" ]]; then
    raw=$(unset ANTHROPIC_API_KEY; "$_to" 60 claude mcp list 2>&1); cl_rc=$?
else
    raw=$(unset ANTHROPIC_API_KEY; claude mcp list 2>&1); cl_rc=$?
fi
if [[ "$cl_rc" == "124" || "$cl_rc" == "137" ]]; then
    # Timed out/killed: NEVER hang, NEVER let an empty list cascade into a false
    # reachable=0 RED. Emit a FRESH alive-signal (keeps the dead-man's switch
    # satisfied) with a visible YELLOW + reason, then exit 0.
    log "YELLOW declared=$declared mcp_list_timeout=60s reachability-unverified"
    echo "[mcp-integrity] YELLOW — declared=$declared | claude mcp list timed out (60s), reachability unverified"
    python3 -c "
import json
json.dump({'ts': '$(date -u +%Y-%m-%dT%H:%M:%SZ)', 'verdict': 'YELLOW',
           'declared': $declared, 'reachable': -1, 'failed': -1,
           'reason': 'claude mcp list timed out (60s)',
           '_writer': 'verify_mcp_integrity'},
          open('$STATE_DIR/mcp_integrity.json','w'), indent=2)
" 2>/dev/null || true
    exit 0
fi
clean=$(printf '%s' "$raw" | sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g')

connected=$(printf '%s\n' "$clean" | grep -cE '✔ Connected|✓ Connected' || true)
pending=$(printf '%s\n' "$clean" | grep -c '⏸ Pending approval' || true)
failed=$(printf '%s\n' "$clean" | grep -cE '✗ Failed|✗ Failed to connect|✘' || true)
warnings=$(printf '%s\n' "$clean" | grep -c '\[Warning\]' || true)
failed_servers_json=$(printf '%s\n' "$clean" | python3 -c '
import json
import re
import sys

names = []
for raw_line in sys.stdin:
    line = raw_line.strip()
    if not re.search(r"(✗ Failed|✗ Failed to connect|✘)", line):
        continue
    prefix = re.split(r"\s+-\s+(?:✗ Failed|✗ Failed to connect|✘)", line, maxsplit=1)[0].strip()
    if ": " in prefix:
        name = prefix.rsplit(": ", 1)[0].strip()
    else:
        name = prefix.split()[0] if prefix.split() else ""
    if name and name not in names:
        names.append(name)
print(json.dumps(names))
')
failed_servers_csv=$(python3 -c 'import json,sys; print(",".join(json.loads(sys.argv[1])))' "$failed_servers_json")

# reachable = connected + pending (pending = config-valid, just needs approval;
# NOT a failure). failed = the real problem.
reachable=$((connected + pending))

# --- 3. Compare against baseline -------------------------------------------

baseline_connected=""
baseline_declared=""
baseline_failed=""
if [[ -f "$BASELINE_FILE" ]]; then
    baseline_connected=$(python3 -c "import json;print(json.load(open('$BASELINE_FILE')).get('reachable',''))" 2>/dev/null || echo "")
    baseline_declared=$(python3 -c "import json;print(json.load(open('$BASELINE_FILE')).get('declared',''))" 2>/dev/null || echo "")
    baseline_failed=$(python3 -c "import json;print(json.load(open('$BASELINE_FILE')).get('failed',''))" 2>/dev/null || echo "")
fi

verdict="GREEN"
reason=""

# RED only on a NEW failure vs baseline (a server that used to be reachable went
# down) — NOT on any failure: optional/plugin MCP servers (slack/asana/pagerduty/
# github-copilot/…) are chronically unconfigured and would pin RED forever (W64:
# armed-but-wrong = noise). First run captures the current failure count as the
# tolerated baseline.
if [[ -n "$baseline_failed" && "$failed" -gt "$baseline_failed" ]]; then
    verdict="RED"
    reason="MCP failures INCREASED vs baseline ($baseline_failed → $failed)"
elif [[ -z "$baseline_failed" && "$failed" -gt 0 ]]; then
    verdict="YELLOW"
    reason="$failed pre-existing MCP failure(s) captured in baseline (optional/plugin servers)"
elif [[ -n "$baseline_connected" && "$reachable" -lt "$baseline_connected" ]]; then
    # connected dropped vs baseline → could be a regression
    drop=$((baseline_connected - reachable))
    floor=$(( baseline_connected - (baseline_connected * DRIFT_PCT / 100) ))
    if [[ "$reachable" -lt "$floor" ]]; then
        verdict="RED"
        reason="reachable dropped $drop below ${DRIFT_PCT}% floor ($reachable < baseline $baseline_connected)"
    else
        verdict="YELLOW"
        reason="reachable dropped $drop within tolerance ($reachable vs baseline $baseline_connected)"
    fi
elif [[ -n "$baseline_declared" && "$declared" != "$baseline_declared" ]]; then
    verdict="YELLOW"
    reason="declared MCP count changed ($baseline_declared → $declared)"
elif [[ "$warnings" -gt 0 ]]; then
    verdict="YELLOW"
    reason="$warnings config warning(s) (missing env vars)"
fi

# --- 4. Output + baseline write --------------------------------------------

if [[ "$UPDATE_BASELINE" == "1" || ! -f "$BASELINE_FILE" ]]; then
    python3 -c "
import json
json.dump({'declared': $declared, 'reachable': $reachable,
           'connected': $connected, 'pending': $pending, 'failed': $failed,
           'failed_servers': $failed_servers_json,
           'ts': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'},
          open('$BASELINE_FILE','w'), indent=2)
"
    if [[ "$UPDATE_BASELINE" == "1" ]]; then
        echo "[mcp-integrity] baseline updated: declared=$declared reachable=$reachable"
        # Deliberate baseline write is not a health check — never block on it.
        exit 0
    fi
fi

if [[ "$JSON_OUT" == "1" ]]; then
    python3 -c "
import json
print(json.dumps({'verdict':'$verdict','reason':'''$reason''',
  'declared':$declared,'reachable':$reachable,'connected':$connected,
  'pending':$pending,'failed':$failed,'warnings':$warnings,
  'failed_servers':$failed_servers_json,
  'baseline_reachable':'$baseline_connected','baseline_declared':'$baseline_declared'}))
"
else
    echo "[mcp-integrity] $verdict — declared=$declared connected=$connected pending=$pending failed=$failed warnings=$warnings failed_servers=${failed_servers_csv:-none}${reason:+ | $reason}"
fi

log "$verdict declared=$declared connected=$connected pending=$pending failed=$failed warnings=$warnings failed_servers=${failed_servers_csv:-none} ${reason}"

# Per-tick alive-signal (fresh ts EVERY run, distinct from the frozen baseline)
# so the dead-man's switch (cost_breaker_deadman.sh) can detect when THIS
# guardian itself goes mute — closing the FASE-0 mutual-watch loop (W69 §G5).
python3 -c "
import json
json.dump({'ts': '$(date -u +%Y-%m-%dT%H:%M:%SZ)', 'verdict': '$verdict',
           'declared': $declared, 'reachable': $reachable, 'failed': $failed,
           'failed_servers': $failed_servers_json,
           '_writer': 'verify_mcp_integrity'},
          open('$STATE_DIR/mcp_integrity.json','w'), indent=2)
" 2>/dev/null || true

[[ "$verdict" == "RED" ]] && exit 2
exit 0
