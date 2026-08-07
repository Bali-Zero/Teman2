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

echo
if [[ $FAIL -eq 0 ]]; then
    echo "PASS ($PASS checks)"
    exit 0
fi
echo "FAIL ($FAIL of $((PASS + FAIL)) checks)"
exit 1
