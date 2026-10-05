#!/usr/bin/env bash
# Source-safe process-group watchdog — SINGLE SOURCE of run_with_timeout (ledger L50).
# Previously a deliberate duplicate of the copy in scripts/ai-dispatch.sh (ledgered by D1);
# L50 deleted the dispatcher's in-file copy, so ai-dispatch.sh and seat_build.sh both
# source this file. ai-dispatch.sh cannot be sourced itself: it changes directory,
# enables strict mode, and dispatches at top level.
# Fleet hosts have neither timeout(1) nor gtimeout(1), so this stays pure Bash.

run_with_timeout() {
    local secs="$1"
    shift
    (
        set +e
        set -m
        "$@" &
        local child_pid=$!
        local child_pgid="$child_pid"
        local grace="${AI_DISPATCH_TIMEOUT_GRACE_SECS:-2}"
        local deadline=$(( $(date +%s) + secs ))

        cleanup_timeout_group() {
            trap - EXIT INT TERM
            if kill -TERM -- -"$child_pgid" 2>/dev/null; then
                sleep "$grace"
                # The leader may exit while a descendant ignores TERM.
                kill -KILL -- -"$child_pgid" 2>/dev/null || true
            fi
            wait "$child_pid" 2>/dev/null || true
        }
        trap cleanup_timeout_group EXIT
        trap 'cleanup_timeout_group; exit 130' INT TERM

        while kill -0 "$child_pid" 2>/dev/null; do
            if [ "$(date +%s)" -ge "$deadline" ]; then
                cleanup_timeout_group
                exit 124
            fi
            sleep 1
        done
        wait "$child_pid"
        local child_rc=$?
        cleanup_timeout_group
        exit "$child_rc"
    )
}
