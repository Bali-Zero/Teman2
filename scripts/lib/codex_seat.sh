# shellcheck shell=sh
# codex_seat.sh — which ChatGPT Pro seat a non-interactive `codex` call uses.
#
# Sourceable from sh, bash and zsh. Defines functions only; sourcing it has no
# other effect and never exits the caller.
#
# WHY THIS EXISTS — measured on all three machines 2026-08-12, by REPLY and not
# by exit code (W104: `codex --version` returns 0 on a seat that answers 401):
#
#   M5    ~/.codex LIVE       ~/.codex-o2 LIVE      -> two paid seats
#   Pro   ~/.codex 401 DEAD   ~/.codex-acct2 LIVE   -> the DEFAULT seat on the
#                                                      cron workhorse is dead
#   Mini  ~/.codex LIVE                             -> one seat
#
# Every wrapper in the fleet invoked codex with no CODEX_HOME — i.e. always
# ~/.codex. So on Pro every cron codex call has been answering
# "401 Unauthorized: Missing bearer" while a paid, logged-in seat sat one
# environment variable away; and on M5 the second ChatGPT Pro subscription was
# never touched by anything. Two accounts were one account, and on the machine
# that runs the crons they were zero.
#
# TWO NAMES, ONE ROLE. The second seat is called `~/.codex-o2` by the repo SSOT
# (FLEET_TOPOLOGY.json, codex.md, the fleet-order spec) and `~/.codex-acct2` by
# the global CLAUDE.md. Both names exist in the fleet TODAY, on different
# machines. A list that knows only one of them makes the other machine's second
# seat invisible — which is this very defect, relocated. Both are listed. If a
# machine ever has both, they hold two distinct auth.json, i.e. honestly two
# seats.
#
# `auth.json` presence is a PROXY for "usable" and it can lie: a revoked token
# leaves the file exactly where it was. That is deliberately not load-bearing
# here. It buys one thing only — never spending an attempt on a directory that
# has never been logged into at all, which cannot possibly answer. Deciding
# that a seat with a file is actually dead belongs to the caller, which reads
# the reply: claude-cascade.sh's retry classifier already matches `401
# unauthorized` and moves to the next seat.

# Every live seat, one absolute path per line, in preference order.
# Override the search list with CODEX_SEAT_DIRS (colon-separated, PATH-style).
codex_seat_dirs() {
    # The trailing newline is load-bearing: `read` returns non-zero at EOF even
    # when it read a partial last line, so without it the loop silently drops
    # the LAST seat in the list — which is the second subscription.
    printf '%s\n' "${CODEX_SEAT_DIRS:-$HOME/.codex:$HOME/.codex-o2:$HOME/.codex-acct2}" |
        tr ':' '\n' |
        while IFS= read -r _seat_dir; do
            [ -n "$_seat_dir" ] || continue
            [ -f "$_seat_dir/auth.json" ] || continue
            printf '%s\n' "$_seat_dir"
        done |
        awk '!seen[$0]++'
}

codex_seat_count() {
    codex_seat_dirs | grep -c . || true
}

# The Nth live seat, 0-based, wrapping. Prints nothing when there are none —
# callers must treat empty as "no seat", never as "use the default".
codex_seat_nth() {
    _seat_n=$(codex_seat_count)
    [ "$_seat_n" -gt 0 ] || return 0
    _seat_i=$(( ${1:-0} % _seat_n + 1 ))
    codex_seat_dirs | sed -n "${_seat_i}p"
}

# Which seat goes first this run, as a counter that advances on every read.
#
# Without rotation the order is fixed, so seat 1 absorbs every request and seat
# 2 is reached only once seat 1 is exhausted — a reserve tank, not a second
# tank, and the two weekly buckets never drain evenly.
#
# Best-effort BY DESIGN: if the state file cannot be written the offset stays 0
# and the order is simply fixed, which is exactly the old behaviour. No call
# may fail to reach a provider because a bookkeeping file could not be written.
codex_seat_offset() {
    _seat_f="${CODEX_SEAT_STATE_FILE:-$HOME/.cache/nuzantara/codex-seat.rotation}"
    _seat_v=0
    [ -r "$_seat_f" ] && _seat_v=$(cat "$_seat_f" 2>/dev/null)
    case "$_seat_v" in *[!0-9]* | "") _seat_v=0 ;; esac
    mkdir -p "$(dirname "$_seat_f")" 2>/dev/null &&
        printf '%s' "$(( (_seat_v + 1) % 1000000 ))" >"$_seat_f" 2>/dev/null
    printf '%s' "$_seat_v"
}

# For one-shot callers that just want "a working seat, alternating between the
# subscriptions". Prints an absolute CODEX_HOME, or nothing at all.
codex_seat_pick() {
    codex_seat_nth "$(codex_seat_offset)"
}
