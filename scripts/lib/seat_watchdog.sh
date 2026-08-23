#!/usr/bin/env bash
# Source-safe process-group watchdog vendored from scripts/ai-dispatch.sh.
# ai-dispatch.sh cannot be sourced: it changes directory, enables strict mode,
# and dispatches at top level. This deliberate duplication is ledgered by D1.
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
