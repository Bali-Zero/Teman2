# shellcheck shell=bash
# claude_seat.sh — reach a WORKING Claude seat from a plain script.
#
# WHY THIS EXISTS (measured on Pro, 2026-08-08)
#   Scripts that just write `claude -p ...` get nothing under cron. Two separate
#   reasons, both measured in the context the cron actually uses (`bash -lc`,
#   which is what 27 of Pro's 135 crontab lines invoke):
#
#     * `claude: command not found` — the binary lives in ~/.local/bin, which is
#       on neither the login-shell nor the default cron PATH.
#     * no seat in the environment — the numbered OAuth tokens live in
#       ~/.nuzantara-secrets.env, which a login shell does not read.
#
#   The fallback everyone assumed was there is not: the bare keychain identity
#   answers `Not logged in - Please run /login`, because reading the keychain
#   secret needs `-g`, which returns rc=36 (authorization denied, user
#   interaction required) in any non-GUI session. Across every file in
#   ~/logs/cron-agent/ that rung was tried 905 times and succeeded 0 times.
#   An interactive login cannot fix it: cron is never a GUI session.
#
#   So a script needing Claude must bring its own seat. This is that.
#
# USAGE
#   source "$(dirname "$0")/lib/claude_seat.sh"     # or an absolute path
#   answer=$(claude_seat_run --model claude-sonnet-4-6 -p "...") || {
#       # every seat refused; stderr already says which and why
#   }
#
#   stdout is the model's answer and nothing else. Diagnostics go to stderr.
#   No token value is ever printed, logged, or written to disk (superscar #4).
#
# THE REFUSAL RULE IS NOT REIMPLEMENTED HERE
#   Deciding "this seat refused, try the next" is subtle: `claude` prints auth
#   failures to STDOUT and exits 1, so an rc check misses them and a loose text
#   match steals successful answers that merely discuss rate limits. That rule
#   already exists, cured and pinned, in cron-agent.sh. Two tools that must
#   agree on one question do not get to invent two answers, so this file
#   EXTRACTS the live classifier rather than copying it. If the extraction
#   fails, this file refuses to run instead of guessing.

# How many CLAUDE_CODE_OAUTH_TOKEN_<n> slots to consider. It is a VARIABLE and not
# a literal because on 2026-08-23 this range read `1 2 3 4 5` in three separate
# places: the Team seat was armed in the secrets file as slot 6 and no cron could
# ever select it — with only that seat alive the picker returned SUSPEND while a
# valid seat sat in the environment. Raise this when a seat is added; the three
# call sites and the error message follow automatically.
: "${CLAUDE_SEAT_SLOTS:=6}"
_claude_seat_slots() { seq 1 "${CLAUDE_SEAT_SLOTS:-6}"; }

_claude_seat_wrapper_path() {
    # Where is the cron-agent wrapper whose refusal classifier we reuse?
    # This file is deployed in TWO shapes and both must work:
    #   * in the repo, at <root>/scripts/lib/claude_seat.sh
    #   * delivered live, at ~/scripts/lib/claude_seat.sh, next to ~/scripts/cron-agent.sh
    # The first draft only handled the repo shape, and my probe did not catch it
    # because the probe rebuilt the repo layout under /tmp — it measured the
    # world I had staged, not the one the delivery creates.
    #
    # Resolve relative to THIS FILE before asking git: the classifier and this
    # helper must be the same VERSION, and `git rev-parse --git-common-dir`
    # answers with the MAIN checkout even from a worktree, which can sit
    # hundreds of commits behind (W106b).
    [ -n "${CLAUDE_SEAT_WRAPPER:-}" ] && { printf '%s' "$CLAUDE_SEAT_WRAPPER"; return 0; }
    local here root cand
    if [ -n "${CLAUDE_SEAT_REPO_ROOT:-}" ]; then
        printf '%s' "$CLAUDE_SEAT_REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"; return 0
    fi
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || here=""
    if [ -n "$here" ]; then
        # repo shape: scripts/lib -> <root>
        cand="$(cd "$here/../.." 2>/dev/null && pwd)/infra/launchagents/wrappers/cron-agent.sh"
        [ -f "$cand" ] && { printf '%s' "$cand"; return 0; }
        # delivered shape: ~/scripts/lib -> ~/scripts/cron-agent.sh
        cand="$(cd "$here/.." 2>/dev/null && pwd)/cron-agent.sh"
        [ -f "$cand" ] && { printf '%s' "$cand"; return 0; }
    fi
    root="$(git rev-parse --git-common-dir 2>/dev/null)" || root=""
    if [ -n "$root" ]; then
        cand="$(cd "$(dirname "$root")" 2>/dev/null && pwd)/infra/launchagents/wrappers/cron-agent.sh"
        [ -f "$cand" ] && { printf '%s' "$cand"; return 0; }
    fi
    return 1
}

_claude_seat_load_classifier() {
    [ -n "${_CLAUDE_SEAT_CLASSIFIER_LOADED:-}" ] && return 0
    local wrapper extracted
    wrapper="$(_claude_seat_wrapper_path)" || {
        echo "claude_seat: cannot locate cron-agent.sh (looked next to this file, in ~/scripts, and via git)" >&2
        return 2
    }
    [ -f "$wrapper" ] || { echo "claude_seat: missing $wrapper" >&2; return 2; }
    extracted="$(sed -n '/^claude_stderr_retryable()/,/^}/p;/^claude_stdout_retryable()/,/^}/p;/^claude_retryable_files()/,/^}/p;/^claude_oauth_env()/,/^}/p' "$wrapper")"
    case "$extracted" in
        *claude_retryable_files*) : ;;
        *) echo "claude_seat: could not extract the refusal classifier from $wrapper — refusing to guess" >&2; return 2 ;;
    esac
    printf '%s\n' "$extracted" | bash -n 2>/dev/null || {
        echo "claude_seat: extracted classifier does not parse — refusing to guess" >&2; return 2
    }
    eval "$extracted" || return 2
    _CLAUDE_SEAT_CLASSIFIER_LOADED=1
    return 0
}

_claude_seat_binary() {
    if [ -n "${CLAUDE_SEAT_BIN:-}" ]; then
        # An override that does not exist is a caller mistake, not a seat to try.
        # Accepting it blindly turns "you pointed me at nothing" into whatever
        # error the exec happens to produce three frames later.
        [ -x "$CLAUDE_SEAT_BIN" ] || return 1
        printf '%s' "$CLAUDE_SEAT_BIN"; return 0
    fi
    local c
    c="$(command -v claude 2>/dev/null)" && [ -n "$c" ] && { printf '%s' "$c"; return 0; }
    # ~/.local/bin is on neither the login-shell nor the cron PATH; this is the
    # single most common reason a cron-side `claude` call does nothing at all.
    [ -x "$HOME/.local/bin/claude" ] && { printf '%s' "$HOME/.local/bin/claude"; return 0; }
    return 1
}

_claude_seat_load_secrets() {
    # Only if the caller has not already supplied a seat — never clobber an
    # environment that was set up deliberately.
    local i var
    for i in $(_claude_seat_slots); do
        var="CLAUDE_CODE_OAUTH_TOKEN_${i}"
        [ -n "${!var:-}" ] && return 0
    done
    [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && return 0
    local f="${CLAUDE_SEAT_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
    # `source <missing> || true` does NOT degrade under `set -e`: source is a
    # special builtin and the shell exits before the `||` runs. Guard with -f.
    if [ -f "$f" ]; then
        set -a
        # shellcheck disable=SC1090
        . "$f" >/dev/null 2>&1 || true
        set +a
    fi
    return 0
}

# claude_seat_run <claude args...>
#   Tries each configured seat in order and returns the first answer that is not
#   a refusal. Prints the answer on stdout; returns 1 if every seat refused.
claude_seat_run() {
    _claude_seat_load_classifier || return 2
    _claude_seat_load_secrets

    local bin
    bin="$(_claude_seat_binary)" || {
        echo "claude_seat: no claude binary (not on PATH, not at ~/.local/bin/claude)" >&2
        return 2
    }

    local tokens=() labels=() i var tok existing is_dup
    for i in $(_claude_seat_slots); do
        var="CLAUDE_CODE_OAUTH_TOKEN_${i}"
        tok="${!var:-}"
        [ -z "$tok" ] && continue
        is_dup=0
        for existing in ${tokens[@]+"${tokens[@]}"}; do
            [ "$existing" = "$tok" ] && is_dup=1
        done
        [ "$is_dup" -eq 1 ] && continue
        tokens+=("$tok"); labels+=("token_$i")
    done
    if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
        is_dup=0
        for existing in ${tokens[@]+"${tokens[@]}"}; do
            [ "$existing" = "$CLAUDE_CODE_OAUTH_TOKEN" ] && is_dup=1
        done
        [ "$is_dup" -eq 0 ] && { tokens+=("$CLAUDE_CODE_OAUTH_TOKEN"); labels+=("legacy"); }
    fi

    if [ "${#tokens[@]}" -eq 0 ]; then
        # Deliberately NOT falling through to a bare invocation: that is the
        # keychain identity, proven 0-for-905 under cron. Failing loudly beats
        # a call that silently returns an auth error as if it were an answer.
        echo "claude_seat: no OAuth seat configured (looked for CLAUDE_CODE_OAUTH_TOKEN_1..${CLAUDE_SEAT_SLOTS:-6} and the legacy var)" >&2
        echo "claude_seat: the bare keychain identity is NOT used as a fallback — it cannot work in a non-GUI session" >&2
        return 2
    fi

    local out err rc idx label env_args part
    out="$(mktemp "${TMPDIR:-/tmp}/claude-seat-out.XXXXXX")"
    err="$(mktemp "${TMPDIR:-/tmp}/claude-seat-err.XXXXXX")"
    # shellcheck disable=SC2317
    _claude_seat_cleanup() { rm -f "$out" "$err"; }

    for idx in "${!tokens[@]}"; do
        label="${labels[$idx]}"
        env_args=()
        while IFS= read -r -d '' part; do env_args+=("$part"); done \
            < <(claude_oauth_env "${tokens[$idx]}")
        : > "$out"; : > "$err"
        "${env_args[@]}" "$bin" "$@" < /dev/null > "$out" 2> "$err"
        rc=$?
        if claude_retryable_files "$out" "$err" "$rc"; then
            echo "claude_seat: $label refused (rc=$rc) — rotating" >&2
            continue
        fi
        if [ "$rc" -ne 0 ]; then
            echo "claude_seat: $label failed with a NON-auth error (rc=$rc) — not rotating, the next seat would fail the same way" >&2
            cat "$err" >&2
            _claude_seat_cleanup
            return "$rc"
        fi
        cat "$out"
        _claude_seat_cleanup
        return 0
    done

    echo "claude_seat: every seat refused (${#tokens[@]} tried: ${labels[*]})" >&2
    _claude_seat_cleanup
    return 1
}

# ── Interactive seat selection ────────────────────────────────────────────────
# The rotation above (claude_seat_run) is for one-shot `-p` calls. An INTERACTIVE
# session is a long-lived TUI that cannot rotate its own auth mid-flight, so the
# fallback there is: pick a LIVE seat BEFORE launch. Same refusal classifier, so
# "live vs capped" is decided the one cured way, never a second guess.

# _claude_seat_probe <bin> <token>   (token "" = default/keychain seat)
#   rc 0 = the seat answered (live); rc 1 = it refused (capped/auth). No value printed.
_claude_seat_probe() {
    local bin="$1" tok="$2" out err rc part
    local -a env_args=()
    while IFS= read -r -d '' part; do env_args+=("$part"); done < <(claude_oauth_env "$tok")
    out="$(mktemp "${TMPDIR:-/tmp}/claude-seat-probe-out.XXXXXX")"
    err="$(mktemp "${TMPDIR:-/tmp}/claude-seat-probe-err.XXXXXX")"
    "${env_args[@]}" "$bin" -p "reply PONG only" \
        --model "${CLAUDE_SEAT_PROBE_MODEL:-claude-sonnet-4-6}" < /dev/null > "$out" 2> "$err"
    rc=$?
    if claude_retryable_files "$out" "$err" "$rc"; then rm -f "$out" "$err"; return 1; fi
    rm -f "$out" "$err"
    [ "$rc" -eq 0 ]
}

# claude_seat_pick — echo a selector for the first LIVE seat.
#   stdout: "default"  (bare keychain/Team seat answers — used in a GUI/interactive
#                        session; NOT usable under cron, proven 0-for-905)
#         | "token_N"  (numbered OAuth seat N is live)
#   rc 1 = every seat refused (caller SUSPENDS — never downgrades to a weaker model)
#   rc 2 = setup failure (no classifier / no binary)
# Set CLAUDE_SEAT_TRY_DEFAULT=0 to skip the Team seat and go straight to the MAX
# rotation (the MAX seats have a rolling 5h window, no weekly ceiling — better for
# sustained interactive work once the Team seat's weekly cap is the bottleneck).
claude_seat_pick() {
    _claude_seat_load_classifier || return 2
    _claude_seat_load_secrets
    local bin; bin="$(_claude_seat_binary)" || { echo "claude_seat: no claude binary" >&2; return 2; }
    if [ "${CLAUDE_SEAT_TRY_DEFAULT:-1}" = "1" ]; then
        if _claude_seat_probe "$bin" ""; then echo "default"; return 0; fi
        echo "claude_seat: default seat refused — trying numbered seats" >&2
    fi
    local i var tok seen=() dup existing
    for i in $(_claude_seat_slots); do
        var="CLAUDE_CODE_OAUTH_TOKEN_${i}"; tok="${!var:-}"
        [ -z "$tok" ] && continue
        dup=0
        for existing in ${seen[@]+"${seen[@]}"}; do [ "$existing" = "$tok" ] && dup=1; done
        [ "$dup" -eq 1 ] && continue
        seen+=("$tok")
        if _claude_seat_probe "$bin" "$tok"; then echo "token_${i}"; return 0; fi
        echo "claude_seat: token_${i} refused — rotating" >&2
    done
    echo "claude_seat: no live seat (default + numbered all refused) — SUSPEND, do not downgrade" >&2
    return 1
}
