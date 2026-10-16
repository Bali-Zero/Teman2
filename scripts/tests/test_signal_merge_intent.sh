#!/usr/bin/env bash
# test_signal_merge_intent.sh — proof for scripts/signal_merge_intent.sh and the
# label-as-armed selectors in scripts/ci/queue_rearm_population.sh. gh and the label read-back are faked.
#
#   guilt     — B31: a label write that keeps failing, or a read-back that never shows a valid label, is
#               exit 2 and loud WHATEVER the queue state; an arm failure with the queue present => exit 3;
#               a labelled PR is NOT a re-arm candidate.
#   innocence — a valid label is left alone (no remove, no write); an absent one is added; a stale one is
#               removed then added; a failing add that recovers inside the bound is exit 0; queue present =>
#               label then arm; queue absent => label, no arm; probe failure => arm attempted.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "$HERE/.." && pwd)"
HELPER="$SCRIPTS/signal_merge_intent.sh"
POP="$SCRIPTS/ci/queue_rearm_population.sh"
PROBE_SRC="$SCRIPTS/merge_queue_rule.sh"

failures=0
check() { if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"; else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi; }
sumsleeps() { paste -sd+ "$SLEEPLOG" | awk -F+ '{ s = 0; for (i = 1; i <= NF; i++) s += $i; print s }'; }
has() { case "$2" in *"$1"*) echo 1 ;; *) echo 0 ;; esac; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/signal_intent_test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/bin"
cat > "$SANDBOX/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "pr view") [ -z "${FAKE_VIEW_BAD:-}" ] || printf '\377\376\n'; [ -z "${FAKE_VIEW_SLEEP:-}" ] || /bin/sleep "$FAKE_VIEW_SLEEP"; [ "${FAKE_HAS_LABEL:-0}" = 0 ] || echo "${FAKE_LABEL_NAME:-localci:merge-shadow-ok}"; exit 0 ;;
  "pr edit")
    case "$*" in
      *--add-label*)
        [ -z "${FAKE_ADD_SLEEP:-}" ] || /bin/sleep "$FAKE_ADD_SLEEP"
        n="$(cat "$FAKE_COUNT" 2>/dev/null || echo 0)"
        if [ "$n" -lt "${FAKE_ADD_FAILS:-0}" ]; then echo $((n + 1)) > "$FAKE_COUNT"; echo "502 bad gateway" >&2; exit 1; fi ;;
    esac
    [ "${FAKE_EDIT_RC:-0}" = 0 ] || { echo "label not found" >&2; exit "$FAKE_EDIT_RC"; }; exit 0 ;;
  "pr merge") [ "${FAKE_MERGE_RC:-0}" = 0 ] || { echo "${FAKE_MERGE_MSG:-boom}" >&2; exit "$FAKE_MERGE_RC"; }; echo "Auto-merge enabled"; exit 0 ;;
  "api repos/"*) [ "${FAKE_RULES_RC:-0}" = 0 ] || exit "$FAKE_RULES_RC"; echo "${FAKE_RULES_COUNT:-1}"; exit 0 ;;
esac
echo "FAKE_GH: unhandled: $*" >&2; exit 99
FAKEGH
# the read-back: FAKE_VERIFY=valid always valid, never always invalid, default (after-write) valid once an add-label happened
cat > "$SANDBOX/bin/verify" <<'FAKEVERIFY'
#!/usr/bin/env bash
printf 'VERIFY %s\n' "$*" >> "$FAKE_GH_LOG"
# FAKE_FIRST_VERIFY_SLEEP=N: the very first read takes N real seconds
if [ -n "${FAKE_FIRST_VERIFY_SLEEP:-}" ] && [ ! -e "$FAKE_COUNT.s" ]; then : > "$FAKE_COUNT.s"; /bin/sleep "$FAKE_FIRST_VERIFY_SLEEP"; fi
# FAKE_VERIFY_UNREADABLE=N: the first N reads are unreadable (rc 2), then the FAKE_VERIFY mode applies
u="$(cat "$FAKE_COUNT.v" 2>/dev/null || echo 0)"
if [ "$u" -lt "${FAKE_VERIFY_UNREADABLE:-0}" ]; then echo $((u + 1)) > "$FAKE_COUNT.v"; echo "LABEL_UNREADABLE: 502" >&2; exit 2; fi
[ -z "${FAKE_VERIFY_RC:-}" ] || { echo "LABEL_UNKNOWN rc ${FAKE_VERIFY_RC}" >&2; exit "$FAKE_VERIFY_RC"; }
case "${FAKE_VERIFY:-after-write}" in
  valid) exit 0 ;;
  never) echo "LABEL_INVALID pr=$2: label predates head"; exit 1 ;;
  unreadable-after-write) grep -q -e '--add-label' "$FAKE_GH_LOG" && { echo "LABEL_UNREADABLE: 502" >&2; exit 2; }; echo "LABEL_INVALID pr=$2: label absent"; exit 1 ;;
  *) grep -q -e '--add-label' "$FAKE_GH_LOG" && exit 0; echo "LABEL_INVALID pr=$2: label absent"; exit 1 ;;
esac
FAKEVERIFY
REAL_PY="$(command -v python3)"
printf '#!/usr/bin/env bash\ncase "$1" in *label_census.py) if [ -n "${FAKE_PY_LOG:-}" ]; then echo "PY $*" >> "$FAKE_PY_LOG"; exit 0; fi ;; esac\nexec %s "$@"\n' "$REAL_PY" > "$SANDBOX/bin/python3"
printf '#!/usr/bin/env bash\necho "$1" >> "$FAKE_SLEEP_LOG"\n[ "${FAKE_REAL_SLEEP:-0}" = 1 ] && exec /bin/sleep "$1"\nexit 0\n' > "$SANDBOX/bin/sleep"
printf '#!/bin/sh\nprintf "VERIFY killed\\n" >> "$FAKE_GH_LOG"\nkill -KILL $$\n' > "$SANDBOX/bin/verify-kill"
printf '#!/bin/sh\nprintf "VERIFY termed\\n" >> "$FAKE_GH_LOG"\nkill -TERM $$\n' > "$SANDBOX/bin/verify-term"
printf '#!/bin/sh\nprintf "VERIFY badutf\\n" >> "$FAKE_GH_LOG"\nprintf "\\377\\376 not utf8\\n"\nexit 0\n' > "$SANDBOX/bin/verify-badutf"
chmod +x "$SANDBOX/bin/verify-kill" "$SANDBOX/bin/verify-term" "$SANDBOX/bin/verify-badutf"
chmod +x "$SANDBOX/bin/gh" "$SANDBOX/bin/verify" "$SANDBOX/bin/sleep" "$SANDBOX/bin/python3"

run() {  # run <PR> [ENV=VAL...]
  local pr="$1"; shift
  LOG="$SANDBOX/log"; : > "$LOG"; rm -f "$SANDBOX/count" "$SANDBOX/count.v" "$SANDBOX/count.s"
  SLEEPLOG="$SANDBOX/sleeps"; : > "$SLEEPLOG"
  OUT="$(env FAKE_SLEEP_LOG="$SLEEPLOG" FAKE_GH_LOG="$LOG" FAKE_COUNT="$SANDBOX/count" SIGNAL_INTENT_VERIFY="$SANDBOX/bin/verify" SIGNAL_INTENT_BACKOFF_S=0 PATH="$SANDBOX/bin:$PATH" "$@" bash "$HELPER" "$pr" 2>"$SANDBOX/err")"
  RC=$?
  CALLS="$(cat "$LOG")"
  ERR="$(cat "$SANDBOX/err")"
}

run 7 FAKE_RULES_COUNT=1
check "queue present, label absent: exit 0" "$([ $RC = 0 ] && echo 1 || echo 0)"
check "queue present: label then arm" "$([ "$(has 'pr edit 7' "$CALLS")" = 1 ] && [ "$(has 'pr merge 7' "$CALLS")" = 1 ] && echo 1 || echo 0)"
check "queue present: report arm=armed" "$(has 'arm=armed' "$OUT")"
first="$(printf '%s\n' "$CALLS" | grep -v -e '^api ' -e '^pr view' -e '^VERIFY' | head -1)"
check "label is the first mutating call (before the arm)" "$(has 'pr edit' "$first")"
check "the label is read back after the write" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" -ge 2 ] && echo 1 || echo 0)"

run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY=valid
check "label present and valid: no remove, no add, exit 0" "$([ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && [ $RC = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1
rm_line="$(printf '%s\n' "$CALLS" | grep -n -e '--remove-label' | head -1 | cut -d: -f1)"; add_line="$(printf '%s\n' "$CALLS" | grep -n -e '--add-label' | head -1 | cut -d: -f1)"
check "label present but stale: refreshed (remove, then add) so a new LabeledEvent exists" "$([ -n "$rm_line" ] && [ -n "$add_line" ] && [ "$rm_line" -lt "$add_line" ] && [ $RC = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0
check "label absent: added without a remove" "$([ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"

run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=2
check "add fails twice then succeeds (retry inside the bound): exit 0, three adds" "$([ $RC = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 3 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9
check "add keeps failing: exit 2, loud, exactly the bounded number of adds" "$([ $RC = 2 ] && [ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && [ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 4 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9 SIGNAL_INTENT_TRIES=2
check "the bound is SIGNAL_INTENT_TRIES" "$([ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 2 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never
check "write ok but the read-back never shows a valid label: exit 2, loud, no arm" "$([ $RC = 2 ] && [ "$(has 'read-back' "$ERR")" = 1 ] && [ "$(has 'pr merge' "$CALLS")" = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_EDIT_RC=1
check "label refresh failing: no add, exit 2 (queue absent)" "$([ $RC = 2 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && echo 1 || echo 0)"

run 7 FAKE_RULES_COUNT=0
check "queue absent: exit 0" "$([ $RC = 0 ] && echo 1 || echo 0)"
check "queue absent: label applied, no merge call" "$([ "$(has 'pr edit 7' "$CALLS")" = 1 ] && [ "$(has 'pr merge' "$CALLS")" = 0 ] && echo 1 || echo 0)"
check "queue absent: report arm=skipped" "$(has 'arm=skipped' "$OUT")"

for q in 1 probefail; do
  if [ $q = probefail ]; then run 7 FAKE_EDIT_RC=1 FAKE_RULES_RC=1; else run 7 FAKE_EDIT_RC=1 FAKE_RULES_COUNT=1; fi
  check "label failure, queue $q: the arm is still attempted but the exit is 2 (fatal)" "$([ $RC = 2 ] && [ "$(has 'pr merge 7' "$CALLS")" = 1 ] && echo 1 || echo 0)"
  check "label failure, queue $q: SIGNAL_INTENT_FAIL on stderr, label=failed reported" "$([ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && [ "$(has 'label=failed' "$OUT")" = 1 ] && echo 1 || echo 0)"
done
run 7 FAKE_EDIT_RC=1 FAKE_RULES_COUNT=1 FAKE_MERGE_RC=1
check "label ko + arm ko, queue present: exit 2 (the label is what merges after the flip)" "$([ $RC = 2 ] && [ "$(has 'arm=failed' "$ERR")" = 1 ] && echo 1 || echo 0)"

# The mutants of the helper's logic are the b31-* table of scripts/localci/tests/mutants/merger_mutants.py (a bash-sed copy of it lived here).

# C2: the read-back is bounded — one initial read plus TRIES read-backs, never one, never unbounded
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never
check "read-back bound: VERIFY calls == 1 + TRIES (5)" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 5 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never SIGNAL_INTENT_TRIES=2
check "read-back bound follows SIGNAL_INTENT_TRIES (3 calls with 2)" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 3 ] && echo 1 || echo 0)"

# L1: the backoff restarts for the read-back — worst case stays under the poller's 60 s helper timeout
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=3 FAKE_VERIFY=never SIGNAL_INTENT_BACKOFF_S=2
total="$(sumsleeps)"
check "backoff restarts per phase: write 14s + read-back 14s = 28s, under 60 (got ${total}s)" "$([ "$total" = 28 ] && [ "$total" -lt 60 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY_UNREADABLE=3 FAKE_ADD_FAILS=3 FAKE_VERIFY=never SIGNAL_INTENT_BACKOFF_S=2
total="$(sumsleeps)"
check "worst case across all three phases is 42s, under 60 (got ${total}s)" "$([ "$total" -lt 60 ] && echo 1 || echo 0)"

# C3: a read-back that is UNREADABLE after the write is not a success
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=unreadable-after-write
check "read-back unreadable after the write: exit 2, 'read-back' on stderr, VERIFY == 5, no arm" "$([ $RC = 2 ] && [ "$(has 'read-back' "$ERR")" = 1 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 5 ] && [ "$(has 'pr merge' "$CALLS")" = 0 ] && echo 1 || echo 0)"

# L5: the default backoff (variable unset or empty) and the wall-clock deadline
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY_UNREADABLE=3 FAKE_ADD_FAILS=3 FAKE_VERIFY=never SIGNAL_INTENT_BACKOFF_S=
total="$(sumsleeps)"
check "default backoff (empty): worst-case sleep is exactly 42s (got ${total}s)" "$([ "$total" = 42 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 SIGNAL_INTENT_DEADLINE_S=0
check "deadline 0: no network call of the label phase at all, exit 2, the deadline is named" "$([ $RC = 2 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && [ "$(has 'pr view' "$CALLS")" = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 0 ] && [ "$(has 'deadline 0s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
# the REAL clock: sleeps are real, 1-2 s, against a 2 s deadline
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9 FAKE_REAL_SLEEP=1 SIGNAL_INTENT_DEADLINE_S=2 SIGNAL_INTENT_BACKOFF_S=1
# bash counts SECONDS in whole wall seconds, so a 2 s deadline is 1 to 2 real seconds: every bound below holds for both
adds="$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')"; shortest="$(sort -n "$SLEEPLOG" | head -1)"; longest="$(sort -n "$SLEEPLOG" | tail -1)"
check "real clock, write: a 2 s deadline stops the adds at 1 to 3 (not 4), exit 2, named, no empty sleep and none past the time left" "$([ $RC = 2 ] && [ "$adds" -ge 1 ] && [ "$adds" -le 3 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && [ "$shortest" -ge 1 ] && [ "$longest" -le 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never FAKE_REAL_SLEEP=1 SIGNAL_INTENT_DEADLINE_S=2 SIGNAL_INTENT_BACKOFF_S=1
reads="$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')"
check "real clock, read-back: the first read and 1 to 2 read-backs (not 4), label left applied, exit 2, named" "$([ $RC = 2 ] && [ "$reads" -ge 2 ] && [ "$reads" -le 4 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99 FAKE_REAL_SLEEP=1 SIGNAL_INTENT_DEADLINE_S=2 SIGNAL_INTENT_BACKOFF_S=1
reads="$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')"
check "real clock, first read: 1 to 3 reads (not 4), nothing written, exit 2, named" "$([ $RC = 2 ] && [ "$reads" -ge 1 ] && [ "$reads" -le 3 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
# the deadline falls INSIDE a network call: the next call is refused (every call is asked, not only the loops)
run 7 FAKE_RULES_COUNT=0 FAKE_FIRST_VERIFY_SLEEP=2 SIGNAL_INTENT_DEADLINE_S=2
check "deadline spent during the first read: no view, no write, no read-back, exit 2, named" "$([ $RC = 2 ] && [ "$(has 'pr view' "$CALLS")" = 0 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 1 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VIEW_SLEEP=2 SIGNAL_INTENT_DEADLINE_S=2
check "deadline spent during the view (no label): no add, exit 2, named" "$([ $RC = 2 ] && [ "$(has 'pr view' "$CALLS")" = 1 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VIEW_SLEEP=2 SIGNAL_INTENT_DEADLINE_S=2
check "deadline spent during the view (label stale): neither remove nor add, exit 2, named" "$([ $RC = 2 ] && [ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_SLEEP=2 SIGNAL_INTENT_DEADLINE_S=2
check "deadline spent during the add: no read-back (one VERIFY only), exit 2, named, the add was made" "$([ $RC = 2 ] && [ "$(has '--add-label' "$CALLS")" = 1 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 1 ] && [ "$(has 'deadline 2s reached' "$ERR")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 SIGNAL_INTENT_DEADLINE_S=08
check "a zero-padded deadline (08) is decimal, not an octal error: exit 0" "$([ $RC = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 SECONDS=1000
check "an exported SECONDS does not eat the deadline: exit 0, label applied" "$([ $RC = 0 ] && [ "$(has 'label=applied' "$OUT")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=99 SIGNAL_INTENT_TRIES=00
check "SIGNAL_INTENT_TRIES=00 is not zero tries: falls back to 4 adds" "$([ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 4 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=99 SIGNAL_INTENT_TRIES=08
check "SIGNAL_INTENT_TRIES=08 is eight, not an octal error" "$([ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 8 ] && echo 1 || echo 0)"
for scenario in "FAKE_RULES_COUNT=1" "FAKE_RULES_COUNT=0" "FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY=valid" "FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=2"; do
  run 7 $scenario
  check "a successful run ($scenario) prints no SIGNAL_INTENT_FAIL and says label=applied" "$([ $RC = 0 ] && [ -z "$ERR" ] && [ "$(has 'label=applied' "$OUT")" = 1 ] && echo 1 || echo 0)"
done
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9 SIGNAL_INTENT_DEADLINE_S=3 SIGNAL_INTENT_BACKOFF_S=2
longest="$(sort -n "$SLEEPLOG" | tail -1)"
check "no sleep runs past the deadline (longest ${longest}s, cap 3s)" "$([ "$longest" -le 3 ] && [ "$longest" -ge 2 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=1 SIGNAL_INTENT_DEADLINE_S=garbage SIGNAL_INTENT_BACKOFF_S=2
check "a garbage deadline falls back to the default: the retry still happens, one sleep of exactly 2s, exit 0" "$([ $RC = 0 ] && [ "$(cat "$SLEEPLOG")" = 2 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9 SIGNAL_INTENT_BACKOFF_S=2
total="$(sumsleeps)"
check "write never succeeds: pauses between tries only, 2+4+8 = 14s (got ${total}s)" "$([ "$total" = 14 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99 SIGNAL_INTENT_BACKOFF_S=2
total="$(sumsleeps)"
check "first read never readable: pauses between tries only, 14s (got ${total}s)" "$([ "$total" = 14 ] && echo 1 || echo 0)"

# Predicate census (README, B31): every remaining conditional of the helper, guilt and innocence
run ""
check "empty PR argument: exit 1" "$([ $RC = 1 ] && echo 1 || echo 0)"
for t in 0 abc; do
  run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9 SIGNAL_INTENT_TRIES=$t
  check "SIGNAL_INTENT_TRIES=$t falls back to 4 tries" "$([ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 4 ] && echo 1 || echo 0)"
done
run 7 FAKE_RULES_COUNT=0 FAKE_PY_LOG="$SANDBOX/py" SIGNAL_INTENT_VERIFY=
check "no override: the real read-back is label_census.py verify on the repo and PR" "$(has 'verify --repo Bali-Zero/Teman2 --pr 7' "$(cat "$SANDBOX/py" 2>/dev/null)")"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=valid
check "a valid label is read exactly once" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=9
check "a plain write failure does not claim a deadline" "$([ "$(has 'deadline' "$ERR")" = 0 ] && [ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_LABEL_NAME=xlocalci:merge-shadow-ok-2
check "another label that merely contains ours is not ours: no remove" "$([ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_ADD_FAILS=1
check "stale label, first add fails: removed once, then only the add is retried" "$([ $RC = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c -e '--remove-label')" = 1 ] && [ "$(printf '%s\n' "$CALLS" | grep -c -e '--add-label')" = 2 ] && echo 1 || echo 0)"
for msg in "already queued" "Auto-Merge enabled" "already enabled" "pull request is clean"; do
  run 7 FAKE_RULES_COUNT=1 FAKE_MERGE_RC=1 "FAKE_MERGE_MSG=$msg"
  check "arm refused with '$msg' is not an arm failure: exit 0, armed" "$([ $RC = 0 ] && [ "$(has 'arm=armed' "$OUT")" = 1 ] && echo 1 || echo 0)"
done
run 7 FAKE_RULES_COUNT=1 FAKE_MERGE_RC=1 "FAKE_MERGE_MSG=GraphQL: something else"
check "arm refused with an unknown message: exit 3" "$([ $RC = 3 ] && echo 1 || echo 0)"

# The effective configuration (SIGNAL_INTENT_SHOW_CONFIG=1): defaults and sanitisers, pinned as values
cfg() { run 7 SIGNAL_INTENT_SHOW_CONFIG=1 SIGNAL_INTENT_TRIES= SIGNAL_INTENT_DEADLINE_S= SIGNAL_INTENT_BACKOFF_S= "$@"; }
cfg
check "config: defaults are tries=4 deadline=45 backoff=2, silently" "$([ "$OUT" = "tries=4 deadline=45 backoff=2" ] && [ -z "$ERR" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_TRIES=abc SIGNAL_INTENT_DEADLINE_S=x SIGNAL_INTENT_BACKOFF_S=y
check "config: garbage falls back to the defaults, silently" "$([ "$OUT" = "tries=4 deadline=45 backoff=2" ] && [ -z "$ERR" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_TRIES=3 SIGNAL_INTENT_DEADLINE_S=9 SIGNAL_INTENT_BACKOFF_S=1
check "config: explicit values are kept" "$([ "$OUT" = "tries=3 deadline=9 backoff=1" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_TRIES=08 SIGNAL_INTENT_DEADLINE_S=08 SIGNAL_INTENT_BACKOFF_S=08
check "config: zero-padded values are decimal" "$([ "$OUT" = "tries=8 deadline=8 backoff=8" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_TRIES=00
check "config: tries 00 is not zero tries" "$([ "$OUT" = "tries=4 deadline=45 backoff=2" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_TRIES=0 SIGNAL_INTENT_DEADLINE_S=0 SIGNAL_INTENT_BACKOFF_S=0
check "config: tries 0 -> 4, deadline 0 and backoff 0 are kept" "$([ "$OUT" = "tries=4 deadline=0 backoff=0" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_TRIES=-3
check "config: a negative tries is garbage" "$([ "$OUT" = "tries=4 deadline=45 backoff=2" ] && echo 1 || echo 0)"
cfg SIGNAL_INTENT_SHOW_CONFIG=0
check "config: SHOW_CONFIG=0 runs the helper" "$([ "$(has 'tries=' "$OUT")" = 0 ] && [ "$(has 'SIGNAL_INTENT' "$OUT")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0
check "no SHOW_CONFIG in the environment: the helper runs" "$([ "$(has 'tries=' "$OUT")" = 0 ] && [ "$(has 'SIGNAL_INTENT' "$OUT")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0
check "the base branch defaults to main and the repo to Bali-Zero/Teman2 in the queue probe" "$([ "$(has 'rules/branches/main' "$CALLS")" = 1 ] && [ "$(has 'repos/Bali-Zero/Teman2/' "$CALLS")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 SIGNAL_INTENT_REPO=o/r SIGNAL_INTENT_BASE=dev
check "SIGNAL_INTENT_REPO and SIGNAL_INTENT_BASE reach the probe and the writes" "$([ "$(has 'repos/o/r/rules/branches/dev' "$CALLS")" = 1 ] && [ "$(has '--repo o/r' "$CALLS")" = 1 ] && echo 1 || echo 0)"

# B31'': a verify code nobody named (126, 127, 137, 255) is UNKNOWN: read again, never success, never a write, exit 2 in both queue states
for rc in 126 127 137 255; do
  for q in 0 1; do
    run 7 FAKE_RULES_COUNT=$q FAKE_VERIFY_RC=$rc FAKE_HAS_LABEL=1
    check "verify rc $rc (queue rules $q): exit 2, label=failed, SIGNAL_INTENT_FAIL, nothing written, four reads" "$([ $RC = 2 ] && [ "$(has 'label=failed' "$OUT")" = 1 ] && [ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 4 ] && echo 1 || echo 0)"
  done
done
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_RC=137 FAKE_VERIFY_UNREADABLE=0
check "verify rc 137 on a label that is really there is never read as valid: no 'label=applied'" "$([ "$(has 'label=applied' "$OUT")" = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 PATH="$SANDBOX/nogh:/usr/bin:/bin"
check "gh cannot start (rc 127 from the executor): label=failed, the arm fails too (exit 2), loud, no traceback" "$([ $RC = 2 ] && [ "$(has 'Traceback' "$ERR")" = 0 ] && [ "$(has 'label=failed' "$ERR")" = 1 ] && [ "$(has 'arm=failed' "$ERR")" = 1 ] && echo 1 || echo 0)"

# B31'' cure: a verify killed by a signal (negative rc), one that cannot start (rc 127) and invalid UTF-8 are all UNKNOWN reads, never a write, never success
for v in verify-kill verify-term; do
  run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 SIGNAL_INTENT_VERIFY="$SANDBOX/bin/$v"
  check "$v: exit 2, label=failed, SIGNAL_INTENT_FAIL, no pr edit, four reads" "$([ $RC = 2 ] && [ "$(has 'label=failed' "$OUT")" = 1 ] && [ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 4 ] && echo 1 || echo 0)"
done
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 SIGNAL_INTENT_VERIFY="$SANDBOX/bin/does-not-exist"
check "a verify that cannot start: exit 2, (rc=127), no pr edit" "$([ $RC = 2 ] && [ "$(has '(rc=127)' "$ERR")" = 1 ] && [ "$(has 'pr edit' "$CALLS")" = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 SIGNAL_INTENT_VERIFY="$SANDBOX/bin/verify-badutf"
check "invalid UTF-8 from the verify: no traceback, valid label, exit 0" "$([ $RC = 0 ] && [ "$(has 'Traceback' "$ERR")" = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VIEW_BAD=1 FAKE_HAS_LABEL=1
check "invalid UTF-8 from gh: no traceback, the stale label is refreshed, exit 0" "$([ $RC = 0 ] && [ "$(has 'Traceback' "$ERR")" = 0 ] && [ "$(has '--remove-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"

# L4: an unreadable verify is unknown, never a reason to remove the label
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=1 FAKE_VERIFY=valid
check "unreadable once on a valid label: re-read, exit 0, no remove, no add" "$([ $RC = 0 ] && [ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99
check "never readable: exit 2, loud, nothing removed or added, reads bounded by TRIES" "$([ $RC = 2 ] && [ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && [ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 4 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=1 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99
check "never readable, queue present: arm attempted, exit still 2" "$([ $RC = 2 ] && [ "$(has 'pr merge 7' "$CALLS")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=1
check "unreadable once then invalid: refresh (remove, then add) as for any stale label" "$([ $RC = 0 ] && [ "$(has '--remove-label' "$CALLS")" = 1 ] && [ "$(has '--add-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"


run 7 FAKE_RULES_COUNT=1 FAKE_MERGE_RC=1
check "arm failure with queue: exit 3" "$([ $RC = 3 ] && echo 1 || echo 0)"

run 7 FAKE_RULES_RC=1
check "rules probe failure: arm still attempted, exit 0" "$([ $RC = 0 ] && [ "$(has 'pr merge 7' "$CALLS")" = 1 ] && echo 1 || echo 0)"

run 7 FAKE_RULES_COUNT=1
run abc
check "non-numeric PR: exit 1" "$([ $RC = 1 ] && echo 1 || echo 0)"

pop='[{"number":1,"title":"labelled","mergeable":"MERGEABLE","autoMergeRequest":null,"mergeQueueEntry":null,"labels":[{"name":"localci:merge-shadow-ok"}]},
      {"number":2,"title":"bare","mergeable":"MERGEABLE","autoMergeRequest":null,"mergeQueueEntry":null,"labels":[]},
      {"number":3,"title":"unknown-labelled","mergeable":"UNKNOWN","autoMergeRequest":null,"mergeQueueEntry":null,"labels":[{"name":"localci:merge-shadow-ok"}]},
      {"number":4,"title":"unknown-bare","mergeable":"UNKNOWN","autoMergeRequest":null,"mergeQueueEntry":null,"labels":[]}]'
popcall() { printf '%s' "$pop" | env MERGE_QUEUE_RULE="$1" bash "$POP" "$2"; }
for state in present unknown; do
  cand="$(popcall $state --candidates)"
  check "watcher, queue $state: labelled-unarmed PR stays a re-arm candidate" "$([ "$(has $'1\t' "$cand")" = 1 ] && [ "$(has $'2\t' "$cand")" = 1 ] && echo 1 || echo 0)"
  check "watcher, queue $state: labelled UNKNOWN still undecided (2)" "$([ "$(popcall $state --undecidable)" = 2 ] && echo 1 || echo 0)"
done
cand="$(popcall absent --candidates)"
check "watcher, queue absent: labelled PR is armed, not a candidate" "$([ "$(has $'1\t' "$cand")" = 0 ] && [ "$(has $'2\t' "$cand")" = 1 ] && echo 1 || echo 0)"
check "watcher, queue absent: labelled UNKNOWN not undecided (1)" "$([ "$(popcall absent --undecidable)" = 1 ] && echo 1 || echo 0)"

PROBE="$SCRIPTS/merge_queue_rule.sh"
probe() { env FAKE_GH_LOG="$SANDBOX/log" PATH="$SANDBOX/bin:$PATH" "$@" bash "$PROBE"; }
check "probe: present" "$([ "$(probe FAKE_RULES_COUNT=2)" = present ] && echo 1 || echo 0)"
check "probe: absent" "$([ "$(probe FAKE_RULES_COUNT=0)" = absent ] && echo 1 || echo 0)"
check "probe: failure => unknown" "$([ "$(probe FAKE_RULES_RC=1)" = unknown ] && echo 1 || echo 0)"

[ "$failures" = 0 ] && echo "ALL PASS" || { echo "$failures FAILED"; exit 1; }
