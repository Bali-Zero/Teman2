#!/usr/bin/env bash
# intel-scraper-with-observability.sh — Sprint 1 PR-1.2
#
# Wraps the daily intel scraper pipeline with observed-shell emit calls
# at lifecycle boundaries. The wrapped script (run_intel_pipeline.py) is
# left UNCHANGED — observability is extrinsic, decoupled from pipeline
# logic.
#
# This is the canonical pattern for retrofitting observed-shell emission
# onto a non-Python automation: source observed-shell-emit.sh, wrap the
# real workload with start/success/error emits.
#
# Suggested LaunchAgent ProgramArguments invocation:
#
#   <key>ProgramArguments</key>
#   <array>
#       <string>/bin/bash</string>
#       <string>/Users/nuzantara/Desktop/nuzantara/scripts/intel-scraper-with-observability.sh</string>
#   </array>
#
# Required env (set in the plist EnvironmentVariables block):
#   OBSERVED_SHELL_API_URL    — typically http://127.0.0.1:8080
#   OBSERVED_SHELL_API_KEY    — same X-API-Key Brevo + other internal eps use
#   PIPELINE_PYTHON           — venv python (default $HOME/Desktop/nuzantara/apps/bali-intel-scraper/venv/bin/python)
#   PIPELINE_SCRIPT           — default: apps/bali-intel-scraper/scripts/run_intel_pipeline.py
#   PIPELINE_ARGS             — extra args, default: --mode full
#
# Reference: docs/cell-core/observed-shell-tier.md § "Bash wrapper"

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/observed-shell-emit.sh"

PIPELINE_PYTHON="${PIPELINE_PYTHON:-$HOME/Desktop/nuzantara/apps/bali-intel-scraper/venv/bin/python}"
PIPELINE_SCRIPT="${PIPELINE_SCRIPT:-$REPO_ROOT/apps/bali-intel-scraper/scripts/run_intel_pipeline.py}"
PIPELINE_ARGS="${PIPELINE_ARGS:---mode full}"

AUTOMATION="intel-scraper.nightly"
TRACE_ID="intel-$(date -u +%Y%m%dT%H%M%SZ)"

start_ts=$(date -u +%s)

observed_shell_emit "$AUTOMATION" "ok" \
    "$(jq -nc --arg phase start --arg trace "$TRACE_ID" '{phase:$phase,trace_id:$trace}' 2>/dev/null || echo '{"phase":"start"}')" \
    "$TRACE_ID"

# Run the actual pipeline. Exit code propagates to the emit decision.
"$PIPELINE_PYTHON" "$PIPELINE_SCRIPT" $PIPELINE_ARGS
pipeline_rc=$?

end_ts=$(date -u +%s)
duration_ms=$(( (end_ts - start_ts) * 1000 ))

if [[ "$pipeline_rc" -eq 0 ]]; then
    observed_shell_emit "$AUTOMATION" "ok" \
        "$(jq -nc \
            --arg phase finish \
            --argjson duration_ms "$duration_ms" \
            --arg trace "$TRACE_ID" \
            '{phase:$phase,duration_ms:$duration_ms,trace_id:$trace}' 2>/dev/null \
            || printf '{"phase":"finish","duration_ms":%d}' "$duration_ms")" \
        "$TRACE_ID"
else
    observed_shell_emit "$AUTOMATION" "error" \
        "$(jq -nc \
            --arg phase finish \
            --argjson duration_ms "$duration_ms" \
            --argjson rc "$pipeline_rc" \
            --arg trace "$TRACE_ID" \
            '{phase:$phase,duration_ms:$duration_ms,exit_code:$rc,trace_id:$trace}' 2>/dev/null \
            || printf '{"phase":"finish","duration_ms":%d,"exit_code":%d}' "$duration_ms" "$pipeline_rc")" \
        "$TRACE_ID"
fi

exit "$pipeline_rc"
