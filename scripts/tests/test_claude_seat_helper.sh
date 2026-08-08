#!/usr/bin/env bash
# test_claude_seat_helper.sh — a plain script must be able to reach a live seat.
#
# WHY THIS EXISTS (measured on Pro, 2026-08-08)
#   Under `bash -lc` — what 27 of Pro's 135 crontab lines use — `claude` is not
#   on PATH and no OAuth seat is in the environment. The fallback everyone
#   assumed covered this does not exist: the bare keychain identity answers
#   `Not logged in`, because reading the keychain secret needs `-g`, which
#   returns rc=36 in any non-GUI session. It was tried 905 times across
#   ~/logs/cron-agent/ and succeeded 0 times.
#
# WHAT IT PINS
#   guilt     — a refusing seat rotates; an unconfigured helper fails LOUDLY
#               rather than falling through to the bare identity; a missing
#               binary is named rather than silently doing nothing.
#   innocence — a live first seat is used immediately; a SUCCESSFUL answer that
#               merely discusses rate limits is not mistaken for a refusal; a
#               genuine non-auth failure does not burn every remaining seat.
#   shared rule — the refusal verdict comes from cron-agent.sh's live
#               classifier, not a copy. If the extraction ever stops working
#               the helper must refuse to run, not guess.
#
# Runs anywhere: no network, no real claude, no real seat, no real HOME.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
HELPER="$REPO_ROOT/scripts/lib/claude_seat.sh"

[ -f "$HELPER" ] || { echo "FAIL: helper not found at $HELPER"; exit 2; }

failures=0
# `case ... in *x*)` inline inside $( ) trips the parser on the unbalanced ')'.
has()   { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }
check() {
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/claudeseat.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

# A fake `claude` whose behaviour depends on the seat it is handed. It reads the
# token from the environment exactly as the real binary would, and writes its
# verdict to the channel the real CLI uses: auth refusals go to STDOUT with a
# non-zero exit, which is the whole reason the classifier cannot judge rc.
make_fake_claude() {  # $1 = script body deciding per-token behaviour
  local d="$1/bin"; mkdir -p "$d"
  cat > "$d/claude" <<FAKE
#!/usr/bin/env bash
echo "\$CLAUDE_CODE_OAUTH_TOKEN" >> "$1/seats-tried"
$2
FAKE
  chmod +x "$d/claude"
  printf '%s' "$d/claude"
}

run_helper() {  # $1 = fake binary, $2.. = env assignments; prints "rc|stdout|stderr-marker"
  local bin="$1"; shift
  local w; w="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  local out err; out="$w/out"; err="$w/err"
  # Hermetic: strip any seat the RUNNER's shell happens to export, or this
  # corpus tests the developer's environment instead of the helper (the first
  # draft did exactly that — three checks passed on my own live token).
  env -u CLAUDE_CODE_OAUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN_1 -u CLAUDE_CODE_OAUTH_TOKEN_2 \
      -u CLAUDE_CODE_OAUTH_TOKEN_3 -u CLAUDE_CODE_OAUTH_TOKEN_4 -u CLAUDE_CODE_OAUTH_TOKEN_5 \
      "$@" \
      CLAUDE_SEAT_BIN="$bin" \
      CLAUDE_SEAT_SECRETS_FILE=/dev/null \
      bash -c "source '$HELPER'; claude_seat_run --model m -p probe" > "$out" 2> "$err"
  LAST_RC=$?
  LAST_OUT="$(cat "$out")"
  LAST_ERR="$(cat "$err")"
}

# ── the world where seat 1 and 2 are revoked and seat 4 answers ───────────────
W1="$(mktemp -d "$SANDBOX/world.XXXXXX")"
BIN1="$(make_fake_claude "$W1" '
case "$CLAUDE_CODE_OAUTH_TOKEN" in
  dead1|dead2) echo "Failed to authenticate. API Error: 401 OAuth access token has been revoked."; exit 1 ;;
  live4)       echo "THE ANSWER"; exit 0 ;;
  *)           echo "unexpected token"; exit 9 ;;
esac')"

echo "guilt — a refusing seat rotates to the next:"
: > "$W1/seats-tried"
run_helper "$BIN1" CLAUDE_CODE_OAUTH_TOKEN_1=dead1 CLAUDE_CODE_OAUTH_TOKEN_2=dead2 CLAUDE_CODE_OAUTH_TOKEN_4=live4
check "the live seat's answer is returned on stdout" "$(yesno test "$LAST_OUT" = "THE ANSWER")"
check "exit code is 0" "$(yesno test "$LAST_RC" -eq 0)"
check "all three seats were actually tried, in order" \
      "$(yesno test "$(tr '\n' ' ' < "$W1/seats-tried")" = "dead1 dead2 live4 ")"
check "stderr names each rotation" \
      "$(yesno eval 'has "token_1 refused" "$LAST_ERR" && has "token_2 refused" "$LAST_ERR"')"

echo "innocence — a live first seat is used immediately, no needless rotation:"
: > "$W1/seats-tried"
run_helper "$BIN1" CLAUDE_CODE_OAUTH_TOKEN_1=live4
check "only one seat tried" "$(yesno test "$(wc -l < "$W1/seats-tried" | tr -d ' ')" -eq 1)"
check "no rotation message" "$(yesno eval '! has refused "$LAST_ERR"')"

echo "innocence — a SUCCESSFUL answer discussing rate limits is not a refusal:"
W2="$(mktemp -d "$SANDBOX/world.XXXXXX")"
BIN2="$(make_fake_claude "$W2" '
echo "Your quota and rate limit questions are answered in the docs: a 429 means slow down."
exit 0')"
: > "$W2/seats-tried"
run_helper "$BIN2" CLAUDE_CODE_OAUTH_TOKEN_1=s1 CLAUDE_CODE_OAUTH_TOKEN_2=s2
check "the answer is returned, not discarded" "$(yesno has "429 means slow down" "$LAST_OUT")"
check "the second seat was never touched" "$(yesno test "$(wc -l < "$W2/seats-tried" | tr -d ' ')" -eq 1)"

echo "innocence — a genuine NON-auth failure does not burn the remaining seats:"
W3="$(mktemp -d "$SANDBOX/world.XXXXXX")"
BIN3="$(make_fake_claude "$W3" 'echo "ENOENT: cannot read the prompt file" >&2; echo ""; exit 3')"
: > "$W3/seats-tried"
run_helper "$BIN3" CLAUDE_CODE_OAUTH_TOKEN_1=s1 CLAUDE_CODE_OAUTH_TOKEN_2=s2 CLAUDE_CODE_OAUTH_TOKEN_4=s4
check "stopped after the first seat" "$(yesno test "$(wc -l < "$W3/seats-tried" | tr -d ' ')" -eq 1)"
check "the underlying exit code is propagated" "$(yesno test "$LAST_RC" -eq 3)"

echo "guilt — with no seat configured it fails LOUDLY, never bare:"
W4="$(mktemp -d "$SANDBOX/world.XXXXXX")"
BIN4="$(make_fake_claude "$W4" 'echo "BARE IDENTITY ANSWERED"; exit 0')"
: > "$W4/seats-tried"
run_helper "$BIN4"
check "rc=2, not a silent success" "$(yesno test "$LAST_RC" -eq 2)"
check "the binary was never invoked without a seat" \
      "$(yesno test "$(wc -c < "$W4/seats-tried" | tr -d ' ')" -eq 0)"
check "stderr says the keychain is not a fallback" \
      "$(yesno has "NOT used as a fallback" "$LAST_ERR")"

echo "guilt — a missing binary is named, not silently ignored:"
run_helper "$SANDBOX/definitely-not-a-binary" CLAUDE_CODE_OAUTH_TOKEN_1=s1
check "rc=2 and the reason mentions the binary" \
      "$(yesno eval 'test "$LAST_RC" -eq 2 && has "no claude binary" "$LAST_ERR"')"

echo "shared rule — the verdict comes from cron-agent.sh, not a copy:"
copied=$(grep -c 'rate.?limit\|not logged in\|token_revoked' "$HELPER")
check "the helper does NOT reimplement the refusal regex (found $copied occurrence(s))" \
      "$(yesno test "$copied" -eq 0)"
check "it extracts claude_retryable_files from the wrapper" \
      "$(yesno grep -q 'claude_retryable_files' "$HELPER")"
# And if the extraction breaks, it must refuse rather than guess.
W5="$(mktemp -d "$SANDBOX/world.XXXXXX")"
mkdir -p "$W5/infra/launchagents/wrappers"
echo '# a wrapper with no classifier in it' > "$W5/infra/launchagents/wrappers/cron-agent.sh"
BIN5="$(make_fake_claude "$W5" 'echo ANSWER; exit 0')"
: > "$W5/seats-tried"
env CLAUDE_SEAT_REPO_ROOT="$W5" CLAUDE_SEAT_BIN="$BIN5" CLAUDE_SEAT_SECRETS_FILE=/dev/null \
    CLAUDE_CODE_OAUTH_TOKEN_1=s1 \
    bash -c "source '$HELPER'; claude_seat_run -p probe" >/dev/null 2>"$SANDBOX/e5"
rc5=$?
check "an unextractable classifier => rc=2 and a refusal to guess" \
      "$(yesno eval 'test "$rc5" -eq 2 && has "refusing to guess" "$(cat "$SANDBOX/e5")"')"

if [ "$failures" -eq 0 ]; then echo "PASS (all checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
