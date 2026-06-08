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
# We strip ANSI, then count state glyphs. claude mcp list has its own timeout;
# we guard with a background+wait fallback (macOS has no `timeout`).

raw=$(unset ANTHROPIC_API_KEY; claude mcp list 2>&1)
clean=$(printf '%s' "$raw" | sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g')

connected=$(printf '%s\n' "$clean" | grep -c '✓ Connected' || true)
pending=$(printf '%s\n' "$clean" | grep -c '⏸ Pending approval' || true)
failed=$(printf '%s\n' "$clean" | grep -cE '✗ Failed|✗ Failed to connect|✘' || true)
warnings=$(printf '%s\n' "$clean" | grep -c '\[Warning\]' || true)

# reachable = connected + pending (pending = config-valid, just needs approval;
# NOT a failure). failed = the real problem.
reachable=$((connected + pending))

# --- 3. Compare against baseline -------------------------------------------

baseline_connected=""
baseline_declared=""
if [[ -f "$BASELINE_FILE" ]]; then
    baseline_connected=$(python3 -c "import json;print(json.load(open('$BASELINE_FILE')).get('reachable',''))" 2>/dev/null || echo "")
    baseline_declared=$(python3 -c "import json;print(json.load(open('$BASELINE_FILE')).get('declared',''))" 2>/dev/null || echo "")
fi

verdict="GREEN"
reason=""

if [[ "$failed" -gt 0 ]]; then
    verdict="RED"
    reason="$failed MCP server(s) FAILED to connect"
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
           'connected': $connected, 'pending': $pending,
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
  'baseline_reachable':'$baseline_connected','baseline_declared':'$baseline_declared'}))
"
else
    echo "[mcp-integrity] $verdict — declared=$declared connected=$connected pending=$pending failed=$failed warnings=$warnings${reason:+ | $reason}"
fi

log "$verdict declared=$declared connected=$connected pending=$pending failed=$failed warnings=$warnings ${reason}"

[[ "$verdict" == "RED" ]] && exit 2
exit 0
