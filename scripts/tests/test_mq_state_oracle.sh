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
# judge <payload-json> -> $OUT (human), $JOUT (json), $RC.
#
# Refuter finding (Codex, MEDIUM): the first version discarded the exit code.
# If the judge CRASHED on a fixture, its output contained no warning text, so
# every `nope has ...` innocence assertion below passed — on a traceback. The
# rc is now asserted on every fixture row, so a crash is a FAIL, never a pass.
judge() {
  OUT="$(printf '%s' "$1" | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
  JOUT="$(printf '%s' "$1" | python3 "$VERDICT" --pr 1 --json 2>&1)"
  check "  [judge exited 0 — a crash must never satisfy a negative assertion]" \
        "$(yesno [ "$RC" = "0" ])"
}
verdict_of() { printf '%s' "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["verdict"])' 2>/dev/null; }

# A rollup helper so each fixture stays readable.
rollup() {  # rollup <state> <totalCount> <nodes-json>
  printf '"commits":{"nodes":[{"commit":{"statusCheckRollup":{"state":"%s","contexts":{"totalCount":%s,"nodes":%s}}}}]}' "$1" "$2" "$3"
}

ALL_VERDICTS=""

# ---------------------------------------------------------------------------
echo "trap #10 (PR #5036) — both fields absent is the arm->entry WINDOW, not a disarm:"
P="{\"pr\":{\"number\":5036,\"state\":\"OPEN\",\"mergedAt\":null,\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":32,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
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
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"AWAITING_CHECKS\",\"position\":1},$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":8,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "verdict is IN_QUEUE" "$(yesno [ "$(verdict_of "$JOUT")" = "IN_QUEUE" ])"
check "carries the entry sub-state" "$(yesno has 'AWAITING_CHECKS' "$OUT")"
check "says the null is BY SUCCESS" "$(yesno has 'null BY SUCCESS' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #1 — armed but not yet queued:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"2026-08-29T10:00:00Z\"},\"mergeQueueEntry\":null,$(rollup PENDING 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "verdict is ARMED" "$(yesno [ "$(verdict_of "$JOUT")" = "ARMED" ])"

# ---------------------------------------------------------------------------
echo "signal 3 — a zero inside a BOUNDED page is not 'never queued':"
check "zero renders the window instead of a claim" "$(yesno has 'does NOT mean' "$OUT")"
check "zero never claims 'has not been built'" "$(nope has 'has not been built' "$OUT")"

# ---------------------------------------------------------------------------
# Refuter finding (Kimi K3, HIGH). `enabledAt` is a NULLABLE DateTime, so
# `autoMergeRequest` can arrive as a non-null object carrying a null timestamp.
# The verdict was right (INDETERMINATE) and the EVIDENCE was a measured
# falsehood: it announced the absence of an object it had just been handed.
echo "an autoMergeRequest object with a null enabledAt is PRESENT, and must be said so:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":null},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "verdict is still INDETERMINATE (no arm is readable)" \
      "$(yesno [ "$(verdict_of "$JOUT")" = "INDETERMINATE" ])"
check "and does NOT claim the object is absent" "$(nope has 'both absent' "$OUT")"
check "it names what actually arrived" "$(yesno has 'PRESENT but carries no enabledAt' "$OUT")"

echo "  innocence — with autoMergeRequest genuinely null, 'both absent' is the TRUE line:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "the true absence is still reported as absence" "$(yesno has 'both absent' "$OUT")"

# ---------------------------------------------------------------------------
# Refuter finding (Kimi K3, LOW). An armed-state file that exists but will not
# parse silently deleted the HEAD-MOVED check — an omission indistinguishable
# from "never armed", which is the one thing this oracle refuses to imply.
echo "an unreadable armed-state file is CANNOT-VERIFY, not a silent all-clear:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null,\"armed_sha_unreadable\":true}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "the unreadable state file is surfaced" "$(yesno has 'could not be read' "$OUT")"
check "and is not passed off as the head having held still" \
      "$(yesno has 'not evidence' "$OUT")"

# ---------------------------------------------------------------------------
echo "terminal states:"
P="{\"pr\":{\"state\":\"MERGED\",\"mergedAt\":\"2026-08-29T07:44:58Z\",\"mergeable\":\"UNKNOWN\",\"mergeStateStatus\":\"UNKNOWN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 3 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":8,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "MERGED wins over the ambiguous fields" "$(yesno [ "$(verdict_of "$JOUT")" = "MERGED" ])"
check "a merged PR is not warned about mergeable=UNKNOWN" "$(nope has 'still recomputing' "$OUT")"
check "a merged PR is not warned FALSE GREEN (3 of 11 is moot once landed)" \
      "$(nope has 'FALSE GREEN' "$OUT")"

P="{\"pr\":{\"state\":\"CLOSED\",\"mergedAt\":null,\"mergeable\":\"UNKNOWN\",\"mergeStateStatus\":\"UNKNOWN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":null,\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "CLOSED without mergedAt is CLOSED, not INDETERMINATE" "$(yesno [ "$(verdict_of "$JOUT")" = "CLOSED" ])"
check "an unavailable run listing says CANNOT-VERIFY" "$(yesno has 'CANNOT-VERIFY' "$OUT")"

# ---------------------------------------------------------------------------
echo "roll-up (#5039/#5052) — a rollup carrying NO context names cannot vouch for anything:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 4 '[]')},\"required_names\":[\"req-1\",\"req-2\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "a nameless rollup cannot verify presence" "$(yesno has 'no context NAMES to match them against' "$OUT")"
check "and it does not silently pass as green" "$(nope has 'clean' "$OUT")"

echo "  innocence — every required check present by NAME is not called a false green:"
NODES='[{"__typename":"CheckRun","name":"req-1","conclusion":"SUCCESS"},{"__typename":"CheckRun","name":"req-2","conclusion":"SUCCESS"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 2 "$NODES")},\"required_names\":[\"req-1\",\"req-2\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "a rollup whose required checks are all present by name is clean" \
      "$(nope has 'FALSE GREEN' "$OUT")"

# ---------------------------------------------------------------------------
# Refuter finding (Codex, BLOCKER). A required check has an IDENTITY, not a
# cardinality. Sixty-eight green OPTIONAL contexts do not satisfy eleven
# REQUIRED ones that are all absent — and the count-vs-count guard said they
# did. That is the proxy-for-entity substitution this whole verb exists to
# stop, committed inside the cure.
echo "required checks are matched by NAME, not counted:"
NODES='[{"__typename":"CheckRun","name":"optional-a","conclusion":"SUCCESS"},{"__typename":"CheckRun","name":"optional-b","conclusion":"SUCCESS"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 2 "$NODES")},\"required_names\":[\"req-1\",\"req-2\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "a green rollup missing every required check is called out" \
      "$(yesno has 'FALSE GREEN RISK' "$OUT")"
check "and the missing checks are NAMED, not merely counted" "$(yesno has 'req-1, req-2' "$OUT")"

echo "  innocence — the required checks ARE present, so no risk is claimed:"
NODES='[{"__typename":"CheckRun","name":"req-1","conclusion":"SUCCESS"},{"__typename":"CheckRun","name":"req-2","conclusion":"SUCCESS"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 2 "$NODES")},\"required_names\":[\"req-1\",\"req-2\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "present required checks raise nothing" "$(nope has 'FALSE GREEN' "$OUT")"

# Refuter finding (Codex, HIGH). `required_status_checks: null` is a REAL
# answer — the branch's rules live in a ruleset, not in classic protection.
# Flattening it to an empty list printed "requires 0" as a measurement.
echo "an unanswerable required-check probe is CANNOT-VERIFY, never 'requires nothing':"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 2 '[]')},\"required_names\":null,\"queue_runs\":null,\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "the unanswerable probe says CANNOT-VERIFY" "$(yesno has 'required checks CANNOT-VERIFY' "$OUT")"
check "and distinguishes it from 'requires nothing'" "$(yesno has "not the same as" "$OUT")"

echo "  innocence — a branch that genuinely declares none is stated, not warned about:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 2 '[]')},\"required_names\":[],\"queue_runs\":null,\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "an empty requirement list is reported as such" "$(yesno has 'declares no required status checks' "$OUT")"
check "and raises no CANNOT-VERIFY" "$(nope has 'required checks CANNOT-VERIFY' "$OUT")"

# Refuter finding (Codex, MEDIUM). contexts(first:100) is ONE PAGE while
# totalCount counts them all — so "this required check is absent" may only mean
# "absent from the page I fetched".
echo "a truncated context page downgrades 'absent' to CANNOT-VERIFY:"
NODES='[{"__typename":"CheckRun","name":"optional-a","conclusion":"SUCCESS"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 140 "$NODES")},\"required_names\":[\"req-1\"],\"queue_runs\":null,\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "truncation turns 'absent' into CANNOT-VERIFY" "$(yesno has 'CANNOT-VERIFY rather than missing' "$OUT")"
check "and never asserts FALSE GREEN RISK on a partial page" "$(nope has 'FALSE GREEN RISK' "$OUT")"
check "the truncation itself is disclosed" "$(yesno has 'only 1 of 140 rollup contexts' "$OUT")"

# Refuter finding (Codex, HIGH). An armed sha on record with no headRefOid in
# the read used to print "head matches the sha recorded at arm time".
echo "an armed sha with no head in the read is CANNOT-VERIFY, not a match:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"main\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 0 '[]')},\"required_names\":null,\"queue_runs\":null,\"armed_sha\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "no false claim that the head matches" "$(nope has 'head matches' "$OUT")"
check "the gap is labelled instead" "$(yesno has 'head-vs-armed is CANNOT-VERIFY' "$OUT")"

# ---------------------------------------------------------------------------
echo "roll-up (#5039) — CANCELLED is filed under 'cancel', never 'fail':"
NODES='[{"__typename":"CheckRun","name":"a","conclusion":"CANCELLED","status":"COMPLETED"},{"__typename":"CheckRun","name":"b","conclusion":"SUCCESS","status":"COMPLETED"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup FAILURE 2 "$NODES")},\"required_names\":[\"req-1\",\"req-2\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "the cancelled context is counted" "$(yesno has '1 context(s) CANCELLED' "$OUT")"
check "the warning names the bucket that hides it" "$(yesno has "bucket" "$OUT")"

echo "  innocence — no CANCELLED context, no cancelled warning:"
NODES='[{"__typename":"CheckRun","name":"b","conclusion":"SUCCESS","status":"COMPLETED"}]'
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 1 "$NODES")},\"required_names\":[\"req-1\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "clean rollup mentions no CANCELLED" "$(nope has 'CANCELLED' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #8 — a DIRTY PR runs zero workflows, so its silence is not green:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"CONFLICTING\",\"mergeStateStatus\":\"DIRTY\",\"headRefOid\":\"aa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "DIRTY is called silence, not green" "$(yesno has 'silence, not green' "$OUT")"

# ---------------------------------------------------------------------------
echo "trap #3 — the arm rides the PR, not the sha:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "a moved head after arm is flagged" "$(yesno has 'HEAD MOVED' "$OUT")"
check "and says the push inherited the arm without re-passing the gate" \
      "$(yesno has 'WITHOUT re-passing' "$OUT")"

echo "  innocence — an unmoved head is not flagged:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"autoMergeRequest\":{\"enabledAt\":\"t\"},\"mergeQueueEntry\":null,$(rollup SUCCESS 11 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":0,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "unmoved head produces no HEAD MOVED" "$(nope has 'HEAD MOVED' "$OUT")"

# ---------------------------------------------------------------------------
echo "roll-up (#5192) — a zombie UNMERGEABLE entry points at the timeline, not at a red check:"
P="{\"pr\":{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"UNMERGEABLE\",\"position\":3},$(rollup SUCCESS 141 '[]')},\"required_names\":[\"req-1\",\"req-2\",\"req-3\",\"req-4\",\"req-5\",\"req-6\",\"req-7\",\"req-8\",\"req-9\",\"req-10\",\"req-11\"],\"queue_runs\":{\"matched\":8,\"window\":100,\"oldest\":\"x\"},\"armed_sha\":null}"
judge "$P"; ALL_VERDICTS="$ALL_VERDICTS $(verdict_of "$JOUT")"
check "UNMERGEABLE says the queue merges onto the entries AHEAD" \
      "$(yesno has 'entries AHEAD' "$OUT")"

# ---------------------------------------------------------------------------
echo "malformed input is CANNOT-VERIFY, never a verdict:"
OUT="$(printf 'not json at all' | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
check "non-JSON payload exits 3" "$(yesno [ "$RC" = "3" ])"
OUT="$(printf '{}' | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
check "payload with no pr node exits 3" "$(yesno [ "$RC" = "3" ])"
# Refuter finding (Codex, MEDIUM): a JSON LIST is valid JSON and used to raise
# AttributeError with a traceback and rc 1 — the documented contract says 3.
# A caller branching on the exit code would read "a verdict was produced".
OUT="$(printf '[]' | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
check "a JSON list payload exits 3, not 1 with a traceback" "$(yesno [ "$RC" = "3" ])"
check "  and says CANNOT-VERIFY rather than printing a traceback" \
      "$(yesno has 'CANNOT-VERIFY' "$OUT")"
check "  and no traceback reaches the operator" "$(nope has 'Traceback' "$OUT")"
# The generic exception net would ALSO produce rc 3 here, so the explicit
# isinstance guard survives a naive mutation. Its value is the MESSAGE: it
# names the shape that arrived instead of leaving a bare AttributeError to
# describe the problem in terms of the code that tripped over it.
check "  and the message names the shape that arrived" \
      "$(yesno has 'must be a JSON object, got list' "$OUT")"
# The same contract for a well-shaped payload carrying a wrongly-typed field.
OUT="$(printf '{"pr":{"state":"OPEN"},"queue_runs":{"matched":"eight"}}' | python3 "$VERDICT" --pr 1 2>&1)"; RC=$?
check "a wrongly-typed field exits 3, not 1" "$(yesno [ "$RC" = "3" ])"
check "  and names the exception class instead of dumping it" \
      "$(yesno has 'CANNOT-VERIFY' "$OUT")"
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
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"QUEUED\",\"position\":2},$(rollup SUCCESS 11 '[]')}" > "$W/fgh/pr_json"
echo '{"matched":8,"window":100,"oldest":"x"}' > "$W/fgh/queue_runs"
echo 11 > "$W/fgh/required_count"
run_state 4242
check "e2e verdict is IN_QUEUE" "$(yesno has 'VERDICT: IN_QUEUE' "$OUT")"
check "e2e exits 0" "$(yesno [ "$RC" = "0" ])"
check "e2e header carries the PR number it was asked about" "$(yesno has 'PR #4242' "$OUT")"
check "e2e asked GraphQL for mergeQueueEntry (gh pr view cannot serve it)" \
      "$(yesno grep -q 'mergeQueueEntry' "$LOG")"
# Refuter finding (Codex, HIGH): the probe always read `main`'s protection, so
# a PR into release/1.x was judged against the wrong branch's rules entirely.
check "e2e read the protection of the PR OWN base branch, not main" \
      "$(yesno grep -q 'branches/release-1.x/protection' "$LOG")"
check "  and did NOT read main protection" "$(nope grep -q 'branches/main/protection' "$LOG")"
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
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":null,$(rollup SUCCESS 4 '[]')}" > "$W/fgh/pr_json"
echo 'not-a-number' > "$W/fgh/required_count"
echo 'not-json' > "$W/fgh/queue_runs"
run_state 4242
check "still produces a verdict" "$(yesno has 'VERDICT: INDETERMINATE' "$OUT")"
check "and admits the required checks are unverified" \
      "$(yesno has 'required checks CANNOT-VERIFY' "$OUT")"

echo "arg parsing REFUSES rather than guesses (both shapes read the wrong PR or died mute):"
new_world
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"QUEUED\",\"position\":2},$(rollup SUCCESS 11 '[]')}" > "$W/fgh/pr_json"
run_state 4242 --repo
check "--repo with no value is refused, not a silent rc=1" "$(yesno has 'needs a value' "$OUT")"
check "  and it never reached the API" "$(nope grep -q 'graphql' "$LOG")"
new_world
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"QUEUED\",\"position\":2},$(rollup SUCCESS 11 '[]')}" > "$W/fgh/pr_json"
run_state 4242 9999
check "a second positional is refused, never silently preferred" \
      "$(yesno has 'takes ONE PR number' "$OUT")"
check "  and it never queried the wrong PR" "$(nope grep -q 'pr-9999-' "$LOG")"

echo "  innocence — one PR number and a valid --repo still work:"
new_world
printf '%s' "{\"state\":\"OPEN\",\"mergedAt\":null,\"baseRefName\":\"release-1.x\",\"mergeable\":\"MERGEABLE\",\"mergeStateStatus\":\"CLEAN\",\"headRefOid\":\"aa\",\"autoMergeRequest\":null,\"mergeQueueEntry\":{\"state\":\"QUEUED\",\"position\":2},$(rollup SUCCESS 11 '[]')}" > "$W/fgh/pr_json"
run_state 4242 --repo other-owner/other-repo
check "valid --repo is accepted" "$(yesno has 'VERDICT: IN_QUEUE' "$OUT")"
check "  and the override reached the API call" "$(yesno grep -q 'other-owner/other-repo' "$LOG")"

echo "a repo string with extra segments is refused, not split two different ways:"
new_world
run_state 4242 --repo Bali-Zero/junk/Teman2
check "three segments are refused" "$(yesno has 'exactly owner/name' "$OUT")"
# Refuter finding (Codex, HIGH): `%%/*` took `Bali-Zero` and `##*/` took
# `Teman2` for GraphQL while the REST calls used the whole three-segment
# string — one verdict about two different repositories.
check "  and nothing was queried at all" "$(nope grep -q 'graphql' "$LOG")"

echo "the branch-protection jq filter, extracted from mq.sh and run under real jq:"
if ! command -v jq >/dev/null 2>&1; then
  echo "  SKIP — jq is not installed; this row cannot judge (declared, not silently passed)"
else
  PFILTER="$(sed -n "s/^ *local prot_jq='\(.*\)'$/\1/p" "$MQSH" | head -1)"
  check "the protection filter was actually extracted" "$(yesno [ -n "$PFILTER" ])"

  # GitHub returns the SAME required-check list twice — modern `checks[].context`
  # and legacy `contexts`. Concatenating them printed "requires 22" for 11 real
  # checks: a doubled number presented as a measurement.
  DUP='{"required_status_checks":{"checks":[{"context":"a"},{"context":"b"}],"contexts":["a","b"]}}'
  JQOUT="$(printf '%s' "$DUP" | jq -c "$PFILTER" 2>&1)"; JQRC=$?
  check "the two representations are unioned, not concatenated" \
        "$(yesno [ "$JQOUT" = '["a","b"]' ])"
  check "  (filter ran cleanly)" "$(yesno [ "$JQRC" = "0" ])"

  # `required_status_checks: null` is a REAL answer — the rules live in a
  # ruleset. It must stay null, never flatten to [] and print "requires 0".
  NUL='{"required_status_checks":null}'
  JQOUT="$(printf '%s' "$NUL" | jq -c "$PFILTER" 2>&1)"
  check "a null required_status_checks stays null, never becomes []" \
        "$(yesno [ "$JQOUT" = "null" ])"
fi

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
