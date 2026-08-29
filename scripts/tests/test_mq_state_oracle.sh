#!/usr/bin/env bash
# test_mq_state_oracle.sh — proof for `mq state` (scripts/mq.sh + mq_state_verdict.py).
#
# WHAT IT PINS, and where each row's ground truth comes from
#   Every fixture below is a shape the merge queue actually produced, recorded
#   in MEMORY_MERGE_QUEUE_TRAPS.md with the postmortem's own verdict. The test
#   asserts THAT verdict, not merely "a" verdict.
#
#     trap #10 (PR #5036)  both fields absent -> INDETERMINATE, NEVER "not armed"
#     trap #1  (table)     entry present + auto null -> IN_QUEUE, null BY SUCCESS
#     trap #1  (table)     auto set + no entry       -> ARMED
#     trap #8              DIRTY -> "0 pending" is silence, not green
#     trap #3              head moved after arm -> the arm rode the PR, not the sha
#     roll-up  (#5039/52)  rollup=SUCCESS over fewer contexts than required -> FALSE GREEN
#     roll-up  (#5039)     CANCELLED contexts -> bucket 'cancel', never 'fail'
#     roll-up  (#5192)     entry UNMERGEABLE -> only the timeline says WHY
#     signal 3             matched=0 in a bounded page is NOT "never queued"
#
#   Plus a CLASS assertion no single fixture can carry: no fixture, ever,
#   produces the string NOT_ARMED — the oracle has no such verdict by design.
#
# No network and no real gh: the end-to-end rows drive `mq state` through a
# fake `gh` on PATH, with the same poverty check as test_mq_sh.sh (W108 — a
# fake world too poor to judge reports its own poverty as a pass).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
MQSH="$REPO_ROOT/mq.sh"
VERDICT="$REPO_ROOT/mq_state_verdict.py"
[ -f "$MQSH" ] || { echo "FAIL: mq.sh not found at $MQSH"; exit 2; }
[ -f "$VERDICT" ] || { echo "FAIL: mq_state_verdict.py not found at $VERDICT"; exit 2; }

failures=0
total=0
check() {  # check <name> <0-or-1>
  total=$((total + 1))
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}
has() { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }
# nope: the NEGATED form. `nope cmd` is not a thing — `!` is shell syntax,
# not a command, so it lands in argv[0] and every negative assertion would
# report "!: command not found" and FAIL regardless of the truth (caught by
# running this corpus, not by reading it).
nope() { if "$@"; then echo 0; else echo 1; fi; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/mqstate_test.XXXXXX")" || {
  echo "FAIL: mktemp could not create a scratch world — this is an ENVIRONMENT failure," >&2
  echo "      not a verdict on the code under test." >&2
  exit 2
}
trap 'rm -rf "$SANDBOX"' EXIT

# judge <payload-json> -> $OUT (human render), $JOUT (json render), $RC
judge() {
  OUT="$(printf '%s' "$1" | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
  JOUT="$(printf '%s' "$1" | python3 "$VERDICT" --pr 1 --json 2>&1)"
}
verdict_of() { printf '%s' "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["verdict"])' 2>/dev/null; }

# A rollup helper so each fixture stays readable.
rollup() {  # rollup <state> <totalCount> <nodes-json>
  printf '"commits":{"nodes":[{"commit":{"statusCheckRollup":{"state":"%s","contexts":{"totalCount":%s,"nodes":%s}}}}]}' "$1" "$2" "$3"
}

ALL_VERDICTS=""

# ---------------------------------------------------------------------------
echo "trap #10 (PR #5036) — both fields absent is the arm->entry WINDOW, not a disarm:"
P="{\"pr\":{\"number\":5036,\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":32,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "verdict is INDETERMINATE" "$(yesno [ "$(verdict_of "$JOUT")" = "INDETERMINATE" ])"
check "never says NOT_ARMED" "$(nope has 'NOT_ARMED' "$JOUT")"
check "names the mutation as the disambiguator" "$(yesno has 'already queued to merge' "$OUT")"
# The disambiguator is ASYMMETRIC: it refuses on an armed PR, and ARMS an
# unarmed one. Advertising it as "harmless" would be true of one branch and
# a trap on the other — so the text must carry the condition, not the comfort.
check "and warns the mutation ARMS an unarmed PR, not merely refuses" \
      "$(yesno has 'ONLY RUN IT IF YOU INTEND TO ARM' "$OUT")"
check "and never calls that command harmless" "$(nope has 'harmless' "$OUT")"
check "queue-branch runs present -> ejection is flagged as CONSISTENT, not asserted" \
      "$(yesno has 'consistent with an EJECTION' "$OUT")"
check "points at the only source for WHY" "$(yesno has 'RemovedFromMergeQueueEvent' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #1 — entry present + autoMergeRequest null is SUCCESS, not a disarm:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"AWAITING_CHECKS\",\"position\":1},$(rollup SUCCESS 11 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":8,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "verdict is IN_QUEUE" "$(yesno [ "$(verdict_of "$JOUT")" = "IN_QUEUE" ])"
check "carries the entry sub-state" "$(yesno has 'AWAITING_CHECKS' "$OUT")"
check "says the null is BY SUCCESS" "$(yesno has 'null BY SUCCESS' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #1 — armed but not yet queued:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"2026-08-29T10:00:00Z\"},\"mergeQueueEntry\":null,$(rollup PENDING 11 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "verdict is ARMED" "$(yesno [ "$(verdict_of "$JOUT")" = "ARMED" ])"

# ---------------------------------------------------------------------------
echo "signal 3 — a zero inside a BOUNDED page is not 'never queued':"
check "zero renders the window instead of a claim" "$(yesno has 'does NOT mean' "$OUT")"
check "zero never claims 'has not been built'" "$(nope has 'has not been built' "$OUT")"

# ---------------------------------------------------------------------------
echo "terminal states:"
P="{\"pr\":{\"state\":\"MERGED\",\"mergedAt\":\"2026-08-29T07:44:58Z\",\"mergeable\":\"UNKNOWN\",\"mergeStateStatus\":\"UNKNOWN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 3 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":8,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "MERGED wins over the ambiguous fields" "$(yesno [ "$(verdict_of "$JOUT")" = "MERGED" ])"
check "a merged PR is not warned about mergeable=UNKNOWN" "$(nope has 'still recomputing' "$OUT")"
check "a merged PR is not warned FALSE GREEN (3 of 11 is moot once landed)" \
      "$(nope has 'FALSE GREEN' "$OUT")"

P="{\"pr\":{\"state\":\"CLOSED\",\"mergedAt\":null,\"mergeable\":\"UNKNOWN\",\"mergeStateStatus\":\"UNKNOWN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_count\":11,\"queue_runs\":null,\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "CLOSED without mergedAt is CLOSED, not INDETERMINATE" "$(yesno [ "$(verdict_of "$JOUT")" = "CLOSED" ])"
check "an unavailable run listing says CANNOT-VERIFY" "$(yesno has 'CANNOT-VERIFY' "$OUT")"

# ---------------------------------------------------------------------------
echo "roll-up (#5039/#5052) — SUCCESS over fewer contexts than required is a FALSE GREEN:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 4 '[]')},\"required_count\":27,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "4-of-27 SUCCESS is called out" "$(yesno has 'FALSE GREEN' "$OUT")"
check "the warning names both numbers" "$(yesno has 'over 4 context(s) while main requires 27' "$OUT")"

echo "  innocence — SUCCESS over ENOUGH contexts is NOT called a false green:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 68 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "68-of-11 is clean" "$(nope has 'FALSE GREEN' "$OUT")"

# ---------------------------------------------------------------------------
echo "roll-up (#5039) — CANCELLED is filed under 'cancel', never 'fail':"
NODES='[{"__typename":"CheckRun","name":"a","conclusion":"CANCELLED","status":"COMPLETED"},{"__typename":"CheckRun","name":"b","conclusion":"SUCCESS","status":"COMPLETED"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup FAILURE 2 "$NODES")},\"required_count\":2,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "the cancelled context is counted" "$(yesno has '1 context(s) CANCELLED' "$OUT")"
check "the warning names the bucket that hides it" "$(yesno has "bucket" "$OUT")"

echo "  innocence — no CANCELLED context, no cancelled warning:"
NODES='[{"__typename":"CheckRun","name":"b","conclusion":"SUCCESS","status":"COMPLETED"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 1 "$NODES")},\"required_count\":1,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "clean rollup mentions no CANCELLED" "$(nope has 'CANCELLED' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #8 — a DIRTY PR runs zero workflows, so its silence is not green:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"CONFLICTING\",\"mergeStateStatus\":\"DIRTY\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "DIRTY is called silence, not green" "$(yesno has 'silence, not green' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #3 — the arm rides the PR, not the sha:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "a moved head after arm is flagged" "$(yesno has 'HEAD MOVED' "$OUT")"
check "and says the push inherited the arm without re-passing the gate" \
      "$(yesno has 'WITHOUT re-passing' "$OUT")"

echo "  innocence — an unmoved head is not flagged:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "unmoved head produces no HEAD MOVED" "$(nope has 'HEAD MOVED' "$OUT")"

# ---------------------------------------------------------------------------
echo "roll-up (#5192) — a zombie UNMERGEABLE entry points at the timeline, not at a red check:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"UNMERGEABLE\",\"position\":3},$(rollup SUCCESS 141 '[]')},\"required_count\":11,\"queue_runs\":{\"matched\":8,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "UNMERGEABLE says the queue merges onto the entries AHEAD" \
      "$(yesno has 'entries AHEAD' "$OUT")"

# ---------------------------------------------------------------------------
echo "malformed input is CANNOT-VERIFY, never a verdict:"
OUT="$(printf 'not json at all' | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
check "non-JSON payload exits 3" "$(yesno [ "$RC" = "3" ])"
OUT="$(printf '{}' | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
check "payload with no pr node exits 3" "$(yesno [ "$RC" = "3" ])"
check "and emits no verdict line" "$(nope has 'VERDICT:' "$OUT")"

# ---------------------------------------------------------------------------
echo "CLASS assertion — across every fixture above, no NOT_ARMED verdict exists:"
check "no fixture produced NOT_ARMED" "$(nope has 'NOT_ARMED' "$ALL_VERDICTS")"
check "and the accumulator is not vacuously empty" "$(yesno [ "$(printf '%s' "$ALL_VERDICTS" | wc -w | tr -d ' ')" -ge 10 ])"
check "the module's declared VERDICTS tuple omits it" \
      "$(nope grep -q '^VERDICTS = .*NOT_ARMED' "$VERDICT")"

# ---------------------------------------------------------------------------
# End-to-end through mq.sh with a fake gh. This is where the GATHERING is
# proved: the fixture rows above never touch mq.sh's three API calls or its
# payload assembler.
# ---------------------------------------------------------------------------
new_world() {
  W="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  mkdir -p "$W/bin" "$W/fgh" "$W/state"
  LOG="$W/log"; : > "$LOG"
  cat > "$W/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
set -uo pipefail
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
case " $* " in
  *" graphql "*)
    rc=0; [ -f "$FAKE_GH_STATE/pr_rc" ] && rc="$(cat "$FAKE_GH_STATE/pr_rc")"
    [ -f "$FAKE_GH_STATE/pr_json" ] && cat "$FAKE_GH_STATE/pr_json"
    exit "$rc" ;;
  *"/branches/main/protection"*)
    cat "$FAKE_GH_STATE/required_count" 2>/dev/null || echo 11
    exit 0 ;;
  *"event=merge_group"*)
    cat "$FAKE_GH_STATE/queue_runs" 2>/dev/null || echo '{"matched":0,"window":100,"oldest":"x"}'
    exit 0 ;;
esac
echo "FAKE_GH: unhandled invocation: $*" >&2
exit 99
FAKEGH
  chmod +x "$W/bin/gh"
}
run_state() {
  OUT="$(env MQ_REPO="test-owner/test-repo" MQ_STATE_DIR="$W/state" \
             FAKE_GH_LOG="$LOG" FAKE_GH_STATE="$W/fgh" PATH="$W/bin:$PATH" \
             bash "$MQSH" state "$@" 2>&1)"
  RC=$?
}

new_world
resolved="$(PATH="$W/bin:$PATH" command -v gh)"
if [ "$resolved" != "$W/bin/gh" ]; then
  echo "HARNESS TOO POOR TO JUDGE: PATH did not resolve gh to the fake ($resolved)" >&2
  exit 2
fi

echo "end-to-end — mq state reads three sources and renders the verdict:"
new_world
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"QUEUED\",\"position\":2},$(rollup SUCCESS 11 '[]')}" > "$W/fgh/pr_json"
echo '{"matched":8,"window":100,"oldest":"x"}' > "$W/fgh/queue_runs"
echo 11 > "$W/fgh/required_count"
run_state 4242
check "e2e verdict is IN_QUEUE" "$(yesno has 'VERDICT: IN_QUEUE' "$OUT")"
check "e2e exits 0" "$(yesno [ "$RC" = "0" ])"
check "e2e header carries the PR number it was asked about" "$(yesno has 'PR #4242' "$OUT")"
check "e2e asked GraphQL for mergeQueueEntry (gh pr view cannot serve it)" \
      "$(yesno grep -q 'mergeQueueEntry' "$LOG")"
check "e2e read branch protection for the required count" \
      "$(yesno grep -q 'branches/main/protection' "$LOG")"
check "e2e scoped the run query to THIS pr number" \
      "$(yesno grep -q 'pr-4242-' "$LOG")"
check "e2e NEVER invoked a mutation (no 'pr merge' in the call log)" \
      "$(nope grep -q 'pr merge' "$LOG")"

echo "end-to-end — the load-bearing read failing is CANNOT-VERIFY, not a verdict:"
new_world
echo 1 > "$W/fgh/pr_rc"; : > "$W/fgh/pr_json"
run_state 4242
check "rc is 3" "$(yesno [ "$RC" = "3" ])"
check "says CANNOT-VERIFY" "$(yesno has 'CANNOT-VERIFY' "$OUT")"
check "emits no VERDICT line" "$(nope has 'VERDICT:' "$OUT")"
check "and says an unread state is not an absent one" "$(yesno has 'is not an absent one' "$OUT")"

echo "end-to-end — a degraded SECONDARY read still yields a verdict, labelled:"
new_world
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 4 '[]')}" > "$W/fgh/pr_json"
echo 'not-a-number' > "$W/fgh/required_count"
echo 'not-json' > "$W/fgh/queue_runs"
run_state 4242
check "still produces a verdict" "$(yesno has 'VERDICT: INDETERMINATE' "$OUT")"
check "and admits the required count is unverified" \
      "$(yesno has 'required-context count CANNOT-VERIFY' "$OUT")"

# ---------------------------------------------------------------------------
# The jq filter that counts queue-branch runs is a STRING inside mq.sh, and the
# fake `gh` above answers with the filter's RESULT — so the fake sits ABOVE the
# transformation and none of the rows so far exercise the filter itself (W114:
# a fake at the wrong boundary proves nothing about what it bypassed).
#
# This block extracts the LIVE filter text out of mq.sh — never a copy, or the
# corpus would drift into testing a stale duplicate — and runs it under real jq
# against a payload shaped like the API's.
# ---------------------------------------------------------------------------
echo "the queue-run jq filter, extracted from mq.sh and run under real jq:"
if ! command -v jq >/dev/null 2>&1; then
  echo "  SKIP — jq is not installed; this row cannot judge (declared, not silently passed)"
else
  FILTER="$(sed -n 's/.*--jq "\({matched:.*\)"$/\1/p' "$MQSH" | head -1)"
  FILTER="$(printf '%s' "$FILTER" | sed 's/\\"/"/g; s/\${pr}/4242/g')"
  check "the filter was actually extracted (a blank one would pass everything)" \
        "$(yesno [ -n "$FILTER" ])"

  # A workflow_run's head_branch is NULLABLE. jq's test() aborts the entire
  # filter on a null ("null cannot be matched, as it is not a string", rc=5),
  # so ONE such row anywhere in the page would turn a real count into a
  # CANNOT-VERIFY. The guard must survive it and still count the real match.
  # The EARLIEST timestamp is deliberately NOT first in this array. With it
  # first, the "oldest" assertion below passes whether the filter sorts or
  # simply takes element 0 — a vacuous check. Measured: dropping the `sort`
  # killed nothing until this array was reordered.
  PAYLOAD='{"workflow_runs":[{"head_branch":null,"created_at":"2026-08-29T03:00:00Z"},{"head_branch":"gh-readonly-queue/main/pr-4242-abc","created_at":"2026-08-29T02:00:00Z"},{"head_branch":"gh-readonly-queue/main/pr-9999-def","created_at":"2026-08-29T01:00:00Z"}]}'
  JQOUT="$(printf '%s' "$PAYLOAD" | jq -c "$FILTER" 2>&1)"; JQRC=$?
  check "a null head_branch does not poison the whole page" "$(yesno [ "$JQRC" = "0" ])"
  check "and the real match is still counted (matched:1)" "$(yesno has '"matched":1' "$JQOUT")"
  check "it does not count another PR's queue branch" "$(nope has '"matched":2' "$JQOUT")"
  check "the window depth travels with the count" "$(yesno has '"window":3' "$JQOUT")"
  check "the oldest timestamp is the earliest, not the first" "$(yesno has '"oldest":"2026-08-29T01:00:00Z"' "$JQOUT")"
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "TOTAL $total FAILED 0"
  exit 0
fi
echo "TOTAL $total FAILED $failures"
exit 1
