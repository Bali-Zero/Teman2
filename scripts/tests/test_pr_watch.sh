#!/usr/bin/env bash
# test_pr_watch.sh — proof for scripts/pr_watch.sh (deterministic PR watcher).
#
# WHAT IT PINS
#   merged           — a MERGED pr view reply prints "#N MERGED <ts>" and the
#                       PR drops out of polling immediately (no further
#                       gh pr checks/graphql calls for it after that tick).
#   closed            — a CLOSED reply prints "#N CLOSED" and drops out too.
#   multi-pr all-done — two PRs merging on different ticks still produce
#                       exactly one ALL_DONE, only after BOTH are terminal.
#   required-failing dedup — the SAME failing set across ticks emits its
#                       line ONCE; a changed set re-emits; recovery-then-
#                       refail with the same names alerts again.
#   missing-required  — a branch-protection context absent from the FULL
#                       reported name set (not just isRequired ones) is
#                       flagged — the skipped-matrix-job shape.
#   W118 trap         — isInMergeQueue flips true->false while the PR is
#                       still OPEN: EJECTED-FROM-QUEUE fires. Never inferred
#                       from autoMergeRequest (this script never even reads
#                       that field — grepped for in the harness log below).
#   transient gh error — a probe that fails with empty output does not abort
#                       the script; polling continues to the next tick.
#   timeout            — an eternally-OPEN, all-clean PR exits TIMEOUT/1
#                       once PR_WATCH_MAX_MIN elapses.
#
# No network, no real gh: a fake `gh` on PATH answers from per-scenario
# fixture files and logs every invocation for order/absence assertions.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
SCRIPT="$REPO_ROOT/pr_watch.sh"
[ -f "$SCRIPT" ] || { echo "FAIL: pr_watch.sh not found at $SCRIPT"; exit 2; }
[ -x "$SCRIPT" ] || { echo "FAIL: pr_watch.sh not executable at $SCRIPT"; exit 2; }

failures=0
check() {  # check <name> <0-or-1>
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}
has() { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }
count_of() { grep -c -- "$1" "$2" 2>/dev/null || true; }  # never trips set -e in $(...)

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/prwatch_test.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

# One scenario = one fresh world: its own fake-gh state dir, log, PATH.
# Nothing here touches real gh or real GitHub.
new_world() {
  W="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  mkdir -p "$W/bin" "$W/fgh"
  LOG="$W/log"
  : > "$LOG"
  # Per-PR view-response sequences: $W/fgh/view_<pr>  (one JSON line per call,
  # last line repeats once exhausted). Per-PR checks/graphql are simpler —
  # single fixed fixture unless a scenario overrides it (see helpers below).
  cat > "$W/bin/gh" <<'FAKEGH'
#!/usr/bin/env bash
# Fake gh — logs every invocation, answers from $FAKE_GH_STATE. An
# invocation shape this fake does not recognise is a HARNESS bug (exit 99).
set -uo pipefail
printf '%s\n' "$*" >> "$FAKE_GH_LOG"

_next_line() {  # _next_line <fixture-file> <counter-file> -> stdout
  local fx="$1" ctr="$2" n
  n=$(( $(cat "$ctr" 2>/dev/null || echo 0) + 1 ))
  echo "$n" > "$ctr"
  local line
  line="$(sed -n "${n}p" "$fx" 2>/dev/null)"
  [ -z "$line" ] && line="$(tail -1 "$fx" 2>/dev/null)"
  printf '%s\n' "$line"
}

case "${1:-}" in
  repo)
    # repo view --json nameWithOwner --jq .nameWithOwner
    echo "test-owner/test-repo"
    exit 0
    ;;
  api)
    case " $* " in
      *" graphql "*)
        # extract PR number from -F number=<n>
        num=""
        prev=""
        for a in "$@"; do
          case "$prev" in
            -F) case "$a" in number=*) num="${a#number=}";; esac;;
          esac
          prev="$a"
        done
        fx="$FAKE_GH_STATE/graphql_${num}"
        ctr="$FAKE_GH_STATE/graphql_${num}_ctr"
        [ -f "$fx" ] || { echo '{"data":{"repository":{"pullRequest":{"isInMergeQueue":false,"mergeQueueEntry":null}}}}'; exit 0; }
        _next_line "$fx" "$ctr"
        exit 0
        ;;
      *"/branches/main/protection "*)
        rc=0
        [ -f "$FAKE_GH_STATE/required_names_rc" ] && rc="$(cat "$FAKE_GH_STATE/required_names_rc")"
        [ -f "$FAKE_GH_STATE/required_names" ] && cat "$FAKE_GH_STATE/required_names"
        exit "$rc"
        ;;
    esac
    echo "FAKE_GH: unhandled api invocation: $*" >&2
    exit 99
    ;;
  pr)
    case "${2:-}" in
      view)
        num="$3"
        fx="$FAKE_GH_STATE/view_${num}"
        ctr="$FAKE_GH_STATE/view_${num}_ctr"
        rcfx="$FAKE_GH_STATE/view_${num}_rc_seq"
        if [ -f "$fx" ]; then _next_line "$fx" "$ctr"; else echo '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}'; fi
        rc=0
        if [ -f "$rcfx" ]; then
          n="$(cat "$ctr" 2>/dev/null || echo 1)"
          line_rc="$(sed -n "${n}p" "$rcfx" 2>/dev/null)"
          [ -n "$line_rc" ] && rc="$line_rc"
        fi
        exit "$rc"
        ;;
      checks)
        num="$3"
        rc=0
        [ -f "$FAKE_GH_STATE/checks_${num}_rc" ] && rc="$(cat "$FAKE_GH_STATE/checks_${num}_rc")"
        fx="$FAKE_GH_STATE/checks_${num}"
        ctr="$FAKE_GH_STATE/checks_${num}_ctr"
        if [ -f "$fx" ]; then _next_line "$fx" "$ctr"; else echo '[]'; fi
        exit "$rc"
        ;;
    esac
    ;;
esac
echo "FAKE_GH: unhandled invocation: $*" >&2
exit 99
FAKEGH
  chmod +x "$W/bin/gh"
}

# run <args...> — invokes pr_watch.sh via env (real exec, no ambiguity about
# shell-function propagation), capturing combined stdout+stderr in $OUT and
# exit code in $RC.
run() {
  OUT="$(env FAKE_GH_LOG="$LOG" FAKE_GH_STATE="$W/fgh" \
             PATH="$W/bin:$PATH" \
             PR_WATCH_INTERVAL="${PR_WATCH_INTERVAL:-0}" \
             PR_WATCH_MAX_MIN="${PR_WATCH_MAX_MIN:-1}" \
             bash "$SCRIPT" --repo test-owner/test-repo "$@" 2>&1)"
  RC=$?
}

# poverty check — the fake must actually be the one gh resolves to.
new_world
resolved="$(PATH="$W/bin:$PATH" command -v gh)"
if [ "$resolved" != "$W/bin/gh" ]; then
  echo "HARNESS TOO POOR TO JUDGE: PATH did not resolve gh to the fake ($resolved)" >&2
  exit 2
fi

echo "merged — prints MERGED once and stops probing that PR:"
new_world
printf '{"state":"MERGED","mergedAt":"2026-08-21T01:00:00Z","mergeStateStatus":"CLEAN"}\n' > "$W/fgh/view_42"
run 42
check "exit 0" "$(yesno test "$RC" = 0)"
check "prints #42 MERGED with the timestamp" "$(yesno has '#42 MERGED 2026-08-21T01:00:00Z' "$OUT")"
check "prints ALL_DONE" "$(yesno has 'ALL_DONE' "$OUT")"
check "never called pr checks for a PR merged on tick 1" "$(yesno eval '[ "$(count_of "pr checks 42" "$LOG")" = "0" ]')"

echo "closed — prints CLOSED once:"
new_world
printf '{"state":"CLOSED","mergedAt":null,"mergeStateStatus":"CLOSED"}\n' > "$W/fgh/view_43"
run 43
check "exit 0" "$(yesno test "$RC" = 0)"
check "prints #43 CLOSED" "$(yesno has '#43 CLOSED' "$OUT")"

echo "multi-pr — ALL_DONE only after BOTH reach a terminal state:"
new_world
{
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T02:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_50"
printf '{"state":"MERGED","mergedAt":"2026-08-21T01:30:00Z","mergeStateStatus":"CLEAN"}\n' > "$W/fgh/view_51"
run 50 51
check "exit 0" "$(yesno test "$RC" = 0)"
check "#50 MERGED printed" "$(yesno has '#50 MERGED' "$OUT")"
check "#51 MERGED printed" "$(yesno has '#51 MERGED' "$OUT")"
check "exactly one ALL_DONE" "$(yesno eval '[ "$(count_of "ALL_DONE" <(printf "%s" "$OUT"))" = "1" ]')"

echo "required-failing — same set once, changed set re-emits, recovery resets:"
new_world
cat > "$W/fgh/checks_60" <<'JSON'
[{"name":"Backend Tests","state":"FAILURE","isRequired":true}]
[{"name":"Backend Tests","state":"FAILURE","isRequired":true}]
[{"name":"Backend Tests","state":"SUCCESS","isRequired":true}]
[{"name":"Backend Tests","state":"FAILURE","isRequired":true}]
JSON
{
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T03:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_60"
PR_WATCH_MAX_MIN=5 run 60
check "exit 0" "$(yesno test "$RC" = 0)"
check "REQUIRED-FAILING printed exactly twice (not once per tick)" \
  "$(yesno eval '[ "$(count_of "REQUIRED-FAILING: Backend Tests" <(printf "%s" "$OUT"))" = "2" ]')"

echo "missing-required — branch-protection context absent from the FULL reported set:"
new_world
printf 'Backend Tests (Python)\nDetect Secrets\nE2E (matrix, shard 3)\n' > "$W/fgh/required_names"
printf '[{"name":"Backend Tests (Python)","state":"SUCCESS","isRequired":true},{"name":"Detect Secrets","state":"SUCCESS","isRequired":true}]\n[{"name":"Backend Tests (Python)","state":"SUCCESS","isRequired":true},{"name":"Detect Secrets","state":"SUCCESS","isRequired":true}]\n' > "$W/fgh/checks_70"
{
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T04:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_70"
run 70
check "exit 0" "$(yesno test "$RC" = 0)"
check "flags the skipped-matrix context by name" "$(yesno has 'MISSING-REQUIRED: E2E (matrix, shard 3)' "$OUT")"
check "does not flag a context that WAS reported" "$(yesno eval '! has "MISSING-REQUIRED: Backend Tests" "$OUT" && ! has "MISSING-REQUIRED: Detect Secrets" "$OUT"')"

echo "W118 trap — isInMergeQueue true then false while still OPEN fires EJECTED-FROM-QUEUE:"
new_world
printf '{"data":{"repository":{"pullRequest":{"isInMergeQueue":true,"mergeQueueEntry":{"state":"AWAITING_CHECKS","position":1}}}}}\n{"data":{"repository":{"pullRequest":{"isInMergeQueue":false,"mergeQueueEntry":null}}}}\n' > "$W/fgh/graphql_80"
{
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T05:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_80"
PR_WATCH_MAX_MIN=5 run 80
check "exit 0" "$(yesno test "$RC" = 0)"
check "EJECTED-FROM-QUEUE fires exactly once" \
  "$(yesno eval '[ "$(count_of "EJECTED-FROM-QUEUE" <(printf "%s" "$OUT"))" = "1" ]')"
check "the ejected PR is named" "$(yesno has '#80 EJECTED-FROM-QUEUE' "$OUT")"
check "autoMergeRequest is NEVER read by this script (grep the harness log)" \
  "$(yesno eval '! grep -qi "autoMergeRequest" "$LOG"')"

echo "transient gh error — a nonzero-rc gh pr view does not abort; polling continues:"
new_world
{
  printf '{}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T06:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_90"
printf '1\n0\n' > "$W/fgh/view_90_rc_seq"
run 90
check "exit 0 (recovered on the next tick)" "$(yesno test "$RC" = 0)"
check "eventually MERGED" "$(yesno has '#90 MERGED' "$OUT")"
check "the transient tick is logged, not swallowed silently" "$(yesno has 'transient' "$OUT")"

echo "W104 — gh pr checks rc!=0 WITH a body is data, not a tool failure (still used):"
new_world
printf '1\n' > "$W/fgh/checks_91_rc"
printf '[{"name":"Backend Tests","state":"FAILURE","isRequired":true}]\n' > "$W/fgh/checks_91"
{
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T07:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_91"
run 91
check "exit 0" "$(yesno test "$RC" = 0)"
check "the body was used despite rc!=0 (W104)" "$(yesno has '#91 REQUIRED-FAILING: Backend Tests' "$OUT")"

echo "W104 — gh pr checks rc!=0 WITH an empty body IS a real transient failure:"
new_world
printf '1\n' > "$W/fgh/checks_92_rc"
: > "$W/fgh/checks_92"   # empty body, not even '[]'
{
  printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n'
  printf '{"state":"MERGED","mergedAt":"2026-08-21T08:00:00Z","mergeStateStatus":"CLEAN"}\n'
} > "$W/fgh/view_92"
run 92
check "exit 0 (recovers next tick)" "$(yesno test "$RC" = 0)"
check "logs the transient checks failure" "$(yesno has 'transient' "$OUT")"
check "does not fabricate a REQUIRED-FAILING line from an empty body" "$(yesno eval '! has "REQUIRED-FAILING" "$OUT"')"

echo "timeout — an eternally-OPEN, all-clean PR exits TIMEOUT/1:"
new_world
printf '{"state":"OPEN","mergedAt":null,"mergeStateStatus":"CLEAN"}\n' > "$W/fgh/view_95"
PR_WATCH_MAX_MIN=0 run 95
check "exit 1" "$(yesno test "$RC" = 1)"
check "prints TIMEOUT" "$(yesno has 'TIMEOUT' "$OUT")"
check "never prints ALL_DONE on a timeout" "$(yesno eval '! has "ALL_DONE" "$OUT"')"

echo
if [ "$failures" -eq 0 ]; then echo "PASS (all checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
