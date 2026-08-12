#!/usr/bin/env bash
# claude-live.sh — start an INTERACTIVE claude on a LIVE seat.
#
# WHY THIS EXISTS
#   The interactive Claude Code session uses only the logged-in default seat and
#   has NO seat rotation: when that seat hits its cap (the Team seat's weekly
#   ceiling, or a MAX seat's rolling window) the session just stalls. The numbered
#   OAuth rotation in lib/claude_seat.sh only fires for one-shot `-p` cron calls.
#   This wrapper closes that gap: it picks a LIVE seat BEFORE launching the TUI,
#   using the same cured refusal classifier, so a session never STARTS on a dead
#   seat.
#
# WHAT IT DOES NOT DO
#   It cannot rotate a session that is already running (the process is already
#   authed). `--relaunch` re-picks a live seat if the session exits, after asking.
#   It NEVER downgrades to a weaker model: if every seat is capped it exits 1 with
#   the reset hint (SUSPEND, per the final-gate invariant), it does not "find
#   something cheaper to run".
#
# USAGE
#   claude-live.sh [--relaunch] [claude args...]     # e.g. claude-live.sh --model claude-opus-5
#   CLAUDE_SEAT_TRY_DEFAULT=0 claude-live.sh          # skip Team seat, go to MAX rotation
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/lib/claude_seat.sh"

RELAUNCH=0
if [ "${1:-}" = "--relaunch" ]; then RELAUNCH=1; shift; fi

# Probe the seat with the SAME model the session will run. A seat can be live for
# one model and capped for another (the Team seat carries an all-models AND a
# Sonnet-only weekly cap), so a Sonnet probe can say "live" while an Opus/Fable
# session is refused. Derive the probe model from --model; if none is given, leave
# the lib default. This does NOT choose the session's model — the CLI still does.
if [ -z "${CLAUDE_SEAT_PROBE_MODEL:-}" ]; then
    _prev=""
    for _a in "$@"; do
        case "$_prev" in --model|-m) export CLAUDE_SEAT_PROBE_MODEL="$_a"; break ;; esac
        case "$_a" in --model=*) export CLAUDE_SEAT_PROBE_MODEL="${_a#--model=}"; break ;; esac
        _prev="$_a"
    done
    unset _prev _a
fi

_launch_once() {
    local sel bin var part
    sel="$(claude_seat_pick)"; local pick_rc=$?
    [ "$pick_rc" -eq 0 ] || return 3          # 3 = no live seat (distinct from claude's own rc)
    bin="$(_claude_seat_binary)" || return 2
    if [ "$sel" = "default" ]; then
        echo "claude-live: seat=default (Team/keychain)" >&2
        "$bin" "$@"; return $?
    fi
    var="CLAUDE_CODE_OAUTH_TOKEN_${sel#token_}"
    echo "claude-live: seat=$sel (MAX rotation)" >&2
    local -a env_args=()
    while IFS= read -r -d '' part; do env_args+=("$part"); done < <(claude_oauth_env "${!var}")
    "${env_args[@]}" "$bin" "$@"; return $?
}

if [ "$RELAUNCH" -eq 1 ]; then
    while true; do
        _launch_once "$@"; rc=$?
        if [ "$rc" -eq 3 ]; then
            echo "claude-live: every seat is capped — SUSPEND (no downgrade). See the reset time above." >&2
            exit 1
        fi
        printf 'claude-live: session exited (rc=%s). Re-pick a live seat and relaunch? [Enter=yes, Ctrl-C=no] ' "$rc" >&2
        read -r _ || { echo >&2; exit "$rc"; }
    done
else
    _launch_once "$@"; rc=$?
    if [ "$rc" -eq 3 ]; then
        echo "claude-live: every seat is capped — SUSPEND (no downgrade). See the reset time above." >&2
        exit 1
    fi
    exit "$rc"
fi
