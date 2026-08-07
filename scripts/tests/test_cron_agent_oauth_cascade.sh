#!/usr/bin/env bash
# test_cron_agent_oauth_cascade.sh — the seat cascade must rotate past a dead seat.
#
# WHY THIS EXISTS (measured on Pro, 2026-08-07)
#   Three of the four numbered OAuth seats were revoked and the fourth was alive,
#   yet every agent job died on seat 1. The classifier that decides "this seat is
#   unusable, try the next" judged the SHAPE of the sentence: its whole-text anchor
#   knows "authentication failed" and the CLI says
#       Failed to authenticate. API Error: 401 OAuth access token has been revoked.
#   so it read a hard refusal as a final answer and broke the loop. Two daily agent
#   jobs (indexing-daily, conversation-cleanup) had not run for seven nights.
#
# WHAT IT PINS
#   guilt     — a non-zero exit whose output carries an auth/quota marker rotates.
#   innocence — a SUCCESSFUL run whose answer merely discusses rate limits does not
#               (that is why the anchor is strict; the cure must not loosen it), and
#               a genuine non-auth failure does not burn every remaining seat.
#   end-to-end— the wrapper itself, in a fake world, reaches the live seat and says so.
#
# Runs anywhere: no network, no real claude, no real Telegram, no real HOME.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"

PASS=0
FAIL=0

ok()   { printf '  ok   %s\n' "$1"; PASS=$((PASS + 1)); }
bad()  { printf '  FAIL %s\n' "$1"; FAIL=$((FAIL + 1)); }
check() { if [[ "$1" == "$2" ]]; then ok "$3"; else bad "$3 (want=$1 got=$2)"; fi; }

[[ -f "$WRAPPER" ]] || { echo "wrapper not found: $WRAPPER"; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/cron-agent-cascade.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# The real thing the organism runs, verbatim from the CLI on 2026-08-07.
AUTH_REFUSAL='Failed to authenticate. API Error: 401 OAuth access token has been revoked.'

# ── Part 1: the classifier, sourced from the wrapper itself ───────────────────
# Sourcing the real definitions (never a copy of them) is the point: a copy would
# drift and the corpus would grade a fiction.
eval "$(sed -n '/^claude_stderr_retryable()/,/^}/p;/^claude_stdout_retryable()/,/^}/p;/^claude_retryable_files()/,/^}/p' "$WRAPPER")"

verdict() { # <stdout-text> <stderr-text> <exit-code> -> prints RETRY|FINAL
    local o="$TMP/o" e="$TMP/e"
    printf '%s' "$1" > "$o"
    printf '%s' "$2" > "$e"
    if claude_retryable_files "$o" "$e" "$3"; then echo RETRY; else echo FINAL; fi
}

echo "classifier:"

check RETRY "$(verdict "$AUTH_REFUSAL" "" 1)" \
    "guilt: the real revoked-seat refusal (stdout, exit 1) rotates"

check RETRY "$(verdict 'Error: 429 rate limit reached, retry later' "" 1)" \
    "guilt: a quota refusal on stdout rotates"

check RETRY "$(verdict "" "API Error: 401 unauthorized" 1)" \
    "guilt: stderr-borne auth error still rotates (unchanged path)"

check RETRY "$(verdict 'rate limit exceeded' "" 0)" \
    "innocence kept: an exit-0 diagnostic that IS the whole output still rotates"

check FINAL "$(verdict 'I reviewed the retry code. It handles HTTP 401 and rate limit
responses by backing off. No changes needed; the quota logic is correct.' "" 0)" \
    "innocence: a SUCCESSFUL answer discussing 401/rate limits does NOT rotate"

check FINAL "$(verdict 'Traceback (most recent call last):
  File "prompt.py", line 3
SyntaxError: invalid syntax' "" 1)" \
    "innocence: a genuine non-auth failure does not burn the remaining seats"

check RETRY "$(verdict '{"is_error": true, "result": "401 unauthorized"}' "" 1)" \
    "guilt: the JSON error-envelope path is unchanged"

check FINAL "$(verdict '{"is_error": false, "result": "all good, no 401 seen"}' "" 0)" \
    "innocence: a successful JSON envelope mentioning 401 does NOT rotate"

# ── Part 2: the wrapper end-to-end, in a fake world ───────────────────────────
# W107 discipline: prove the behaviour by RUNNING it, so "did not rotate" is
# distinguishable from "never got there".

cat > "$TMP/fake-claude" <<'FAKE'
#!/usr/bin/env bash
# Seats "dead-a"/"dead-b" are revoked; "live-c" answers. Records every attempt.
echo "$CLAUDE_CODE_OAUTH_TOKEN" >> "$FAKE_CLAUDE_ATTEMPTS"
case "${CLAUDE_CODE_OAUTH_TOKEN:-}" in
    dead-*)
        echo 'Failed to authenticate. API Error: 401 OAuth access token has been revoked.'
        exit 1
        ;;
    *)
        echo 'PONG from the live seat'
        exit 0
        ;;
esac
FAKE

cat > "$TMP/fake-timeout" <<'FAKE'
#!/usr/bin/env bash
shift   # drop the duration; macOS has no coreutils timeout by default
exec "$@"
FAKE

# A gateway that records instead of sending. Placed next to a COPY of the
# wrapper so `dirname $0` finds it — that is how the wrapper resolves it.
mkdir -p "$TMP/bin"
cp "$WRAPPER" "$TMP/bin/cron-agent.sh"
cat > "$TMP/bin/tg_notify.py" <<'FAKE'
import os, sys
with open(os.environ["FAKE_TG_LOG"], "a", encoding="utf-8") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\n")
FAKE

chmod +x "$TMP/fake-claude" "$TMP/fake-timeout" "$TMP/bin/cron-agent.sh"
echo "do the thing" > "$TMP/prompt.txt"

run_cascade() { # <token-1> <token-2> <token-3> -> prints "<rc>|<used-label>|<attempts>"
    local home="$TMP/home-$RANDOM"
    mkdir -p "$home"
    : > "$TMP/attempts"
    : > "$TMP/tg"
    local rc
    env -i \
        HOME="$home" CRON_AGENT_HOME="$home" \
        FAKE_CLAUDE_ATTEMPTS="$TMP/attempts" FAKE_TG_LOG="$TMP/tg" \
        CRON_AGENT_CLAUDE_BIN="$TMP/fake-claude" \
        CRON_AGENT_TIMEOUT_BIN="$TMP/fake-timeout" \
        CLAUDE_CODE_OAUTH_TOKEN_1="$1" \
        CLAUDE_CODE_OAUTH_TOKEN_2="$2" \
        CLAUDE_CODE_OAUTH_TOKEN_3="$3" \
        /usr/bin/env bash "$TMP/bin/cron-agent.sh" agent probe-job "$TMP/prompt.txt" \
        >/dev/null 2>&1
    rc=$?
    local used
    used="$(grep -o 'used: tier2-claude-[a-z0-9_]*' "$home/logs/cron-agent/probe-job.log" 2>/dev/null | tail -1)"
    printf '%s|%s|%s' "$rc" "${used:-none}" "$(wc -l < "$TMP/attempts" | tr -d ' ')"
}

echo "end-to-end:"

check "0|used: tier2-claude-token_3|3" "$(run_cascade dead-a dead-b live-c)" \
    "two revoked seats are skipped and the third answers"

check "0|used: tier2-claude-token_1|1" "$(run_cascade live-a live-b live-c)" \
    "innocence: a live first seat is used immediately, no needless rotation"

# ── Part 3: the time budget — a WORKING seat must not be starved ─────────────
# Equal division (remaining / attempts_left) starves the only attempt that was
# ever going to succeed, because dead seats cost seconds and the live one costs
# real time. Measured on Pro 2026-08-07 with all four seats re-issued: 120s per
# entry, indexing-daily (118s) passed by two seconds, weekly-dep-audit was
# killed on all five in turn.
#
# These two need a timeout that REALLY bounds its child — the fake above
# ignores its duration on purpose, so it cannot judge an allocation. Neither
# Mac in this fleet ships coreutils `timeout`, and a check that only ever runs
# on CI is a check that hides defects (W108), so the stand-in below is built
# here rather than depended upon. It honours the only two things the wrapper
# reads: the child is really bounded, and a kill reports 124.

cat > "$TMP/portable-timeout" <<'FAKE'
#!/usr/bin/env bash
dur="$1"; shift
mark="$(mktemp "${TMPDIR:-/tmp}/pt-mark.XXXXXX")"
"$@" &
child=$!
( sleep "$dur"; printf killed > "$mark"; kill -TERM "$child" 2>/dev/null ) &
watcher=$!
wait "$child" 2>/dev/null; rc=$?
kill -TERM "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null
# The mark is written BEFORE the kill, so this is a fact, not a race.
[ -s "$mark" ] && rc=124
rm -f "$mark"
exit "$rc"
FAKE
chmod +x "$TMP/portable-timeout"
REAL_TIMEOUT="$TMP/portable-timeout"

run_slow() { # <budget> <floor> <sleep-seconds> -> "<rc>|<used>|<attempts>|<wall>"
    local home="$TMP/home-slow-$RANDOM"
    mkdir -p "$home"
    : > "$TMP/attempts"
    local t0 rc t1
    t0=$(date +%s)
    env -i \
        HOME="$home" CRON_AGENT_HOME="$home" \
        FAKE_CLAUDE_ATTEMPTS="$TMP/attempts" FAKE_TG_LOG="$TMP/tg" \
        FAKE_CLAUDE_SLEEP="$3" \
        CRON_AGENT_CLAUDE_BIN="$TMP/fake-slow-claude" \
        CRON_AGENT_TIMEOUT_BIN="$REAL_TIMEOUT" \
        CRON_AGENT_TIMEOUT="$1" \
        CRON_AGENT_MIN_ATTEMPT_SECONDS="$2" \
        CLAUDE_CODE_OAUTH_TOKEN_1=live-a \
        CLAUDE_CODE_OAUTH_TOKEN_2=live-b \
        /usr/bin/env bash "$TMP/bin/cron-agent.sh" agent slow-job "$TMP/prompt.txt" \
        >/dev/null 2>&1
    rc=$?
    t1=$(date +%s)
    local used
    used="$(grep -o 'used: tier2-claude-[a-z0-9_]*' "$home/logs/cron-agent/slow-job.log" 2>/dev/null | tail -1)"
    printf '%s|%s|%s|%s' "$rc" "${used:-none}" "$(wc -l < "$TMP/attempts" | tr -d ' ')" "$((t1-t0))"
}

echo "time budget:"

if [[ -z "$REAL_TIMEOUT" ]]; then
    echo "  SKIP no real timeout(1) on PATH — the allocation checks cannot run here"
else
    cat > "$TMP/fake-slow-claude" <<'FAKE'
#!/usr/bin/env bash
echo "$CLAUDE_CODE_OAUTH_TOKEN" >> "$FAKE_CLAUDE_ATTEMPTS"
sleep "${FAKE_CLAUDE_SLEEP:-0}"
echo 'PONG after honest work'
FAKE
    chmod +x "$TMP/fake-slow-claude"

    # 3 entries (token_1, token_2, keychain), budget 21s.
    #   equal division  -> 21/3 = 7s per attempt: an 8s job dies on all three
    #   with the floor  -> max(10, 7) = 10s: the first seat finishes its work
    # Asserted on the OUTCOME (succeeded, on the first seat, one attempt), not
    # on a wall-clock value — pinning the exact second tests the test machine.
    out="$(run_slow 21 10 8)"
    check "0|used: tier2-claude-token_1|1" "${out%|*}" \
        "guilt: a seat doing 8s of work is not killed by a 7s equal slice"

    # The floor must never overrun the global deadline: a seat that never
    # returns still has to be abandoned within the budget. Sized so the breach
    # is VISIBLE — at 21s the last attempt never starts (the budget is already
    # spent) and capped/uncapped measure 21s vs 22s, indistinguishable. At 25s
    # the third attempt does start with 5s left, so dropping the cap hands it
    # the full 10s floor: measured 26s capped vs 31s uncapped.
    out="$(run_slow 25 10 999)"
    rc="${out%%|*}"; wall="${out##*|}"
    tries="$(printf '%s' "$out" | cut -d'|' -f3)"
    if [[ "$rc" == "124" && "$wall" -le 28 ]]; then
        ok "innocence: the floor never overruns the global deadline (rc=124, ${wall}s)"
    else
        bad "innocence: global deadline (want rc=124 and wall<=28, got rc=$rc wall=${wall}s)"
    fi
    # The other edge of the same knob, and the reason the floor is 300 and not
    # the whole 600: a floor large enough to swallow the budget lets ONE hung
    # seat consume everything, and the cascade never reaches a fallback — the
    # cure would have re-created the disease it was written for, at the other
    # sign. `attempt_timeout` is an upper bound, so a seat that FAILS fast still
    # rotates freely; only a HUNG one exposes this, which is why it is asserted
    # here rather than in the fast-failure checks above.
    if [[ "$tries" -ge 2 ]]; then
        ok "innocence: a hung seat does not eat the whole budget ($tries attempts, fallback still reached)"
    else
        bad "innocence: one hung seat consumed the entire cascade (only $tries attempt)"
    fi
fi

echo
if [[ $FAIL -eq 0 ]]; then
    echo "PASS ($PASS checks)"
    exit 0
fi
echo "FAIL ($FAIL of $((PASS + FAIL)) checks)"
exit 1
