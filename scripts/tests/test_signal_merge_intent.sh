#!/usr/bin/env bash
# test_signal_merge_intent.sh — proof for scripts/signal_merge_intent.sh and the
# label-as-armed selectors in scripts/ci/queue_rearm_population.sh. gh is faked.
#
#   guilt     — label failure => exit 2 and no `pr merge`; arm failure with the
#               queue present => exit 3; a labelled PR is NOT a re-arm candidate.
#   innocence — queue present => label then arm; queue absent => label, no arm,
#               exit 0; probe failure => arm attempted; an unlabelled PR stays a candidate.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "$HERE/.." && pwd)"
HELPER="$SCRIPTS/signal_merge_intent.sh"
POP="$SCRIPTS/ci/queue_rearm_population.sh"

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
  "pr edit") [ "${FAKE_EDIT_RC:-0}" = 0 ] || { echo "label not found" >&2; exit "$FAKE_EDIT_RC"; }; exit 0 ;;
  "pr merge") [ "${FAKE_MERGE_RC:-0}" = 0 ] || { echo "boom" >&2; exit "$FAKE_MERGE_RC"; }; echo "Auto-merge enabled"; exit 0 ;;
  "api repos/"*) [ "${FAKE_RULES_RC:-0}" = 0 ] || exit "$FAKE_RULES_RC"; echo "${FAKE_RULES_COUNT:-1}"; exit 0 ;;
esac
echo "FAKE_GH: unhandled: $*" >&2; exit 99
FAKEGH
chmod +x "$SANDBOX/bin/gh"

run() {  # run <PR> [ENV=VAL...]
  local pr="$1"; shift
  LOG="$SANDBOX/log"; : > "$LOG"
  OUT="$(env FAKE_GH_LOG="$LOG" PATH="$SANDBOX/bin:$PATH" "$@" bash "$HELPER" "$pr" 2>"$SANDBOX/err")"
  RC=$?
  CALLS="$(cat "$LOG")"
}

run 7 FAKE_RULES_COUNT=1
check "queue present: exit 0" "$([ $RC = 0 ] && echo 1 || echo 0)"
check "queue present: label then arm" "$([ "$(has 'pr edit 7' "$CALLS")" = 1 ] && [ "$(has 'pr merge 7' "$CALLS")" = 1 ] && echo 1 || echo 0)"
check "queue present: report arm=armed" "$(has 'arm=armed' "$OUT")"
first="$(printf '%s' "$CALLS" | head -1)"
check "label is the first call" "$(has 'pr edit' "$first")"

run 7 FAKE_RULES_COUNT=0
check "queue absent: exit 0" "$([ $RC = 0 ] && echo 1 || echo 0)"
check "queue absent: label applied, no merge call" "$([ "$(has 'pr edit 7' "$CALLS")" = 1 ] && [ "$(has 'pr merge' "$CALLS")" = 0 ] && echo 1 || echo 0)"
check "queue absent: report arm=skipped" "$(has 'arm=skipped' "$OUT")"

run 7 FAKE_EDIT_RC=1
check "label failure: exit 2" "$([ $RC = 2 ] && echo 1 || echo 0)"
check "label failure: no arm, no rules probe" "$([ "$(has 'pr merge' "$CALLS")" = 0 ] && [ "$(has 'api' "$CALLS")" = 0 ] && echo 1 || echo 0)"

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
