#!/bin/bash
# wr2-hardening-chain.sh — runs missed_runs + token_watchdog + quota every 6h.
#
# Each CLI already logs JSON to stdout and exits 0 on success; this script
# invokes them in sequence, aggregates exit codes, and returns the max so
# launchd can detect overall failure.
#
# Sprint 2 W3 (2026-05-03): emits to the cell-core observed-shell tier
# (events_outbox via POST /api/observed-shell/emit) so silent failures
# of the hardening chain are caught by monitoring. Per-CLI emits use
# automation_name = wr2.hardening.<short>; final aggregate emit uses
# wr2.hardening.run with sub_run_count + max_exit. Trace ID is generated
# once per chain invocation so per-CLI emits can be joined to the parent
# run row in observed_shell_events. The emit path is best-effort and
# never fails the parent automation (mirrors ObservedShellBus.emit
# never-raises invariant). Reference contract:
# docs/wr2/sprint2-mapping.md § "hardening (Sprint 2 W3 candidate)".
#
# Run from LaunchAgent every 6h (StartInterval 21600).

set -uo pipefail

WRAPPER="${WR2_WRAPPER:-$HOME/Desktop/nuzantara/scripts/wr2-cron-wrapper.sh}"
LOG_DIR="${WR2_LOG_DIR:-$HOME/.openclaw/workspace/logs/war-room-v2}"
mkdir -p "$LOG_DIR"

# Source observed-shell helper if available (best-effort observability — the
# helper's own failure modes are non-fatal). Path is the canonical Sprint 1
# location; if missing, observed_shell_emit becomes a no-op stub.
OBSERVED_SHELL_HELPER="${OBSERVED_SHELL_HELPER:-$(dirname "$0")/observed-shell-emit.sh}"
if [[ -f "$OBSERVED_SHELL_HELPER" ]]; then
    # shellcheck disable=SC1090
    source "$OBSERVED_SHELL_HELPER"
else
    observed_shell_emit() { return 0; }
fi

# Generate one trace_id per chain invocation. uuidgen is BSD on macOS;
# fallback to /proc/sys/kernel/random/uuid (Linux) or a date-based ID
# if neither is available. Format: 36-char UUID-ish so consumers can
# join across observed_shell_events rows without parsing.
if command -v uuidgen >/dev/null 2>&1; then
    TRACE_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
elif [[ -r /proc/sys/kernel/random/uuid ]]; then
    TRACE_ID=$(< /proc/sys/kernel/random/uuid)
else
    TRACE_ID="hardening-$(date -u +%Y%m%dT%H%M%SZ)-$$"
fi

MAX_EXIT=0
SUB_RUN_COUNT=0

for MOD in \
    backend.services.hardening.missed_runs_cli \
    backend.services.hardening.token_watchdog_cli \
    backend.services.hardening.quota_cli
do
    SHORT="${MOD##*.}"
    LOG="$LOG_DIR/hardening-$SHORT.log"
    echo "[$(date -Iseconds)] ▶ $MOD" >> "$LOG"
    "$WRAPPER" "$MOD" >> "$LOG" 2>&1
    EC=$?
    echo "[$(date -Iseconds)] ◀ $MOD exit=$EC" >> "$LOG"
    SUB_RUN_COUNT=$((SUB_RUN_COUNT + 1))
    if (( EC > MAX_EXIT )); then
        MAX_EXIT=$EC
    fi

    # Per-CLI observed-shell emit. Status maps exit code: 0 → ok, 1 → warning,
    # else → error. Payload is intentionally compact (we have a 8 KB pg_notify
    # limit and CLIs already log full JSON to LOG_DIR). The trace_id ties
    # this row back to the aggregate emit at the bottom.
    if (( EC == 0 )); then
        STATUS="ok"
    elif (( EC == 1 )); then
        STATUS="warning"
    else
        STATUS="error"
    fi
    observed_shell_emit \
        "wr2.hardening.${SHORT}" \
        "$STATUS" \
        "$(printf '{"module":"%s","exit_code":%d,"log_path":"%s"}' "$MOD" "$EC" "$LOG")" \
        "$TRACE_ID"
done

# Aggregate emit — single row representing the chain run. Consumers (Sentinel,
# dashboards) prefer this over scanning per-CLI rows for "did the run happen".
if (( MAX_EXIT == 0 )); then
    AGG_STATUS="ok"
elif (( MAX_EXIT == 1 )); then
    AGG_STATUS="warning"
else
    AGG_STATUS="error"
fi

observed_shell_emit \
    "wr2.hardening.run" \
    "$AGG_STATUS" \
    "$(printf '{"sub_run_count":%d,"max_exit":%d,"log_dir":"%s"}' "$SUB_RUN_COUNT" "$MAX_EXIT" "$LOG_DIR")" \
    "$TRACE_ID"

exit "$MAX_EXIT"
