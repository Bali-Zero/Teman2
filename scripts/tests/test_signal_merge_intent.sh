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
has() { case "$2" in *"$1"*) echo 1 ;; *) echo 0 ;; esac; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/signal_intent_test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/bin"
cat > "$SANDBOX/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "pr view") [ "${FAKE_HAS_LABEL:-0}" = 0 ] || echo "localci:merge-shadow-ok"; exit 0 ;;
  "pr edit")
    case "$*" in
      *--add-label*)
        n="$(cat "$FAKE_COUNT" 2>/dev/null || echo 0)"
        if [ "$n" -lt "${FAKE_ADD_FAILS:-0}" ]; then echo $((n + 1)) > "$FAKE_COUNT"; echo "502 bad gateway" >&2; exit 1; fi ;;
    esac
    [ "${FAKE_EDIT_RC:-0}" = 0 ] || { echo "label not found" >&2; exit "$FAKE_EDIT_RC"; }; exit 0 ;;
  "pr merge") [ "${FAKE_MERGE_RC:-0}" = 0 ] || { echo "boom" >&2; exit "$FAKE_MERGE_RC"; }; echo "Auto-merge enabled"; exit 0 ;;
  "api repos/"*) [ "${FAKE_RULES_RC:-0}" = 0 ] || exit "$FAKE_RULES_RC"; echo "${FAKE_RULES_COUNT:-1}"; exit 0 ;;
esac
echo "FAKE_GH: unhandled: $*" >&2; exit 99
FAKEGH
# the read-back: FAKE_VERIFY=valid always valid, never always invalid, default (after-write) valid once an add-label happened
cat > "$SANDBOX/bin/verify" <<'FAKEVERIFY'
#!/usr/bin/env bash
printf 'VERIFY %s\n' "$*" >> "$FAKE_GH_LOG"
# FAKE_VERIFY_UNREADABLE=N: the first N reads are unreadable (rc 2), then the FAKE_VERIFY mode applies
u="$(cat "$FAKE_COUNT.v" 2>/dev/null || echo 0)"
if [ "$u" -lt "${FAKE_VERIFY_UNREADABLE:-0}" ]; then echo $((u + 1)) > "$FAKE_COUNT.v"; echo "LABEL_UNREADABLE: 502" >&2; exit 2; fi
case "${FAKE_VERIFY:-after-write}" in
  valid) exit 0 ;;
  never) echo "LABEL_INVALID pr=$2: label predates head"; exit 1 ;;
  *) grep -q -e '--add-label' "$FAKE_GH_LOG" && exit 0; echo "LABEL_INVALID pr=$2: label absent"; exit 1 ;;
esac
FAKEVERIFY
printf '#!/usr/bin/env bash\necho "$1" >> "$FAKE_SLEEP_LOG"\n' > "$SANDBOX/bin/sleep"
chmod +x "$SANDBOX/bin/gh" "$SANDBOX/bin/verify" "$SANDBOX/bin/sleep"

run() {  # run <PR> [ENV=VAL...]
  local pr="$1"; shift
  LOG="$SANDBOX/log"; : > "$LOG"; rm -f "$SANDBOX/count" "$SANDBOX/count.v"
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
check "label ko + arm ko, queue present: exit 3 (the arm result)" "$([ $RC = 3 ] && echo 1 || echo 0)"

# Mutant: the old behaviour, a label failure only warns (exit 0 while the queue exists). The scenario above must go red.
mkdir -p "$SANDBOX/mut"; cp "$HELPER" "$PROBE_SRC" "$SANDBOX/mut/" 2>/dev/null
sed 's/^\[ "\$label" = applied \] && exit 0$/exit 0/' "$HELPER" > "$SANDBOX/mut/signal_merge_intent.sh"
HELPER_REAL="$HELPER"; HELPER="$SANDBOX/mut/signal_merge_intent.sh"
run 7 FAKE_EDIT_RC=1 FAKE_RULES_COUNT=1
check "mutant (label failure no longer fatal) is caught" "$([ $RC = 0 ] && echo 1 || echo 0)"
HELPER="$HELPER_REAL"

# Mutant: always remove before add (never trust a valid label). The valid-label scenario must go red.
sed 's/^  if gh pr view .*$/  if true; then has=1; fi/' "$HELPER" > "$SANDBOX/mut/signal_merge_intent.sh"
sed -i.bak 's/^  0) ;;$/  0) apply_label || label=failed ;;/' "$SANDBOX/mut/signal_merge_intent.sh"
HELPER="$SANDBOX/mut/signal_merge_intent.sh"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY=valid
check "mutant (valid label still removed) is caught" "$([ "$(has '--remove-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"
HELPER="$HELPER_REAL"

# Mutant: the read-back skipped. A write whose read-back would fail must go red.
sed 's/^    out="\$(verify_label)" \&\& return 0$/    return 0/' "$HELPER" > "$SANDBOX/mut/signal_merge_intent.sh"
HELPER="$SANDBOX/mut/signal_merge_intent.sh"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never
check "mutant (no read-back after the write) is caught" "$([ $RC = 0 ] && echo 1 || echo 0)"
HELPER="$HELPER_REAL"

# C2: the read-back is bounded — one initial read plus TRIES read-backs, never one, never unbounded
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never
check "read-back bound: VERIFY calls == 1 + TRIES (5)" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 5 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never SIGNAL_INTENT_TRIES=2
check "read-back bound follows SIGNAL_INTENT_TRIES (3 calls with 2)" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 3 ] && echo 1 || echo 0)"

# L1: the backoff restarts for the read-back — worst case stays under the poller's 60 s helper timeout
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=3 FAKE_VERIFY=never SIGNAL_INTENT_BACKOFF_S=2
total="$(paste -sd+ "$SLEEPLOG" | bc)"
check "backoff restarts per phase: write 14s + read-back 14s = 28s, under 60 (got ${total}s)" "$([ "$total" = 28 ] && [ "$total" -lt 60 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY_UNREADABLE=3 FAKE_ADD_FAILS=3 FAKE_VERIFY=never SIGNAL_INTENT_BACKOFF_S=2
total="$(paste -sd+ "$SLEEPLOG" | bc)"
check "worst case across all three phases is 42s, under 60 (got ${total}s)" "$([ "$total" -lt 60 ] && echo 1 || echo 0)"

# L4: an unreadable verify is unknown, never a reason to remove the label
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=1 FAKE_VERIFY=valid
check "unreadable once on a valid label: re-read, exit 0, no remove, no add" "$([ $RC = 0 ] && [ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99
check "never readable: exit 2, loud, nothing removed or added, reads bounded by TRIES" "$([ $RC = 2 ] && [ "$(has 'SIGNAL_INTENT_FAIL' "$ERR")" = 1 ] && [ "$(has '--remove-label' "$CALLS")" = 0 ] && [ "$(has '--add-label' "$CALLS")" = 0 ] && [ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" = 4 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=1 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99
check "never readable, queue present: arm attempted, exit still 2" "$([ $RC = 2 ] && [ "$(has 'pr merge 7' "$CALLS")" = 1 ] && echo 1 || echo 0)"
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=1
check "unreadable once then invalid: refresh (remove, then add) as for any stale label" "$([ $RC = 0 ] && [ "$(has '--remove-label' "$CALLS")" = 1 ] && [ "$(has '--add-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"

# Mutants for the three above
mutate() { sed "$1" "$HELPER_REAL" > "$SANDBOX/mut/signal_merge_intent.sh"; HELPER="$SANDBOX/mut/signal_merge_intent.sh"; }
mutate 's/^    out="\$(verify_label)" \&\& return 0$/    out="$(verify_label)" \&\& return 0; break/'
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never
check "mutant (single read-back try) is caught" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" != 5 ] && echo 1 || echo 0)"
mutate 's/^    out="\$(verify_label)" \&\& return 0$/    out="$(verify_label)" \&\& return 0; [ "$i" -ge "$TRIES" ] \&\& [ "$i" -lt 25 ] \&\& TRIES=$((TRIES + 1))/'
run 7 FAKE_RULES_COUNT=0 FAKE_VERIFY=never
check "mutant (unbounded read-back) is caught" "$([ "$(printf '%s\n' "$CALLS" | grep -c '^VERIFY')" != 5 ] && echo 1 || echo 0)"
mutate '/^  BACKOFF="\${SIGNAL_INTENT_BACKOFF_S:-2}"$/d'
run 7 FAKE_RULES_COUNT=0 FAKE_ADD_FAILS=3 FAKE_VERIFY=never SIGNAL_INTENT_BACKOFF_S=2
total="$(paste -sd+ "$SLEEPLOG" | bc)"
check "mutant (backoff not reset) is caught" "$([ "$total" -ge 60 ] && echo 1 || echo 0)"
mutate 's/^  \*) label=failed; why=.*$/  *) apply_label || label=failed ;;/'
run 7 FAKE_RULES_COUNT=0 FAKE_HAS_LABEL=1 FAKE_VERIFY_UNREADABLE=99
check "mutant (unreadable treated as invalid) is caught" "$([ "$(has '--remove-label' "$CALLS")" = 1 ] && echo 1 || echo 0)"
HELPER="$HELPER_REAL"

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
