#!/usr/bin/env bash
# Corpus for scripts/ci/vercel_should_build.sh — the Vercel Ignored Build Step.
#
# Superscar #3 discipline: a guard needs GUILT (it builds when a build is genuinely needed)
# and INNOCENCE (it stays quiet on the neighbouring legitimate case). Here the asymmetry is
# extreme — a wrong SKIP freezes the whole public surface, a wrong BUILD costs ~6 minutes —
# so every fail-open path gets its own case rather than being assumed.
#
# Each case runs the real script against a real git repo built in a temp dir, with a real
# "origin" remote, because the script's whole job is talking to git. Nothing is mocked.
#
# Contract under test:  exit 1 = BUILD   exit 0 = SKIP
#
# MUTATION-VERIFIED, and two results are recorded rather than smoothed over:
#   * inverting the exit contract            -> 7 of 11 fail
#   * dropping vercel.json from the paths    -> 1 fails
#   * fetch failure treated as SKIP          -> 1 fails
#   * removing BOTH production guards        -> 2 fail
#   * removing ONLY the `$REF = main` guard  -> 0 fail.  Not a missing test: the `base == HEAD`
#     guard below catches the same case, because on main the merge-base with main IS HEAD. The
#     two guards are redundant on purpose and the suite asserts the OUTCOME (main always builds),
#     which is the thing that matters. Removing both does fail, above.
#   * grep exiting >=2                       -> 0 fail. Genuinely UNCOVERED: this corpus has no
#     way to make grep itself error. The branch is written fail-open and reviewed, not proven.
#   * pointer reverted to a bare invocation  -> 4 fail, every one as `rc=127 (DEPLOYMENT ERROR)`.
#     That IS the 2026-07-29 incident, reproduced. See scripts/ci/vercel_ignore_build_step.sh.
#   * queue-ref base resolution removed     -> 1 fails.  Worth recording HOW: written naively these
#     cases passed with that whole path deleted, because the origin/main path resolved them —
#     three tests that proved nothing. They only bite now because the block deletes the tracking
#     ref and breaks the remote first, so a SKIP can come from nowhere else. A new path needs its
#     OTHER routes removed, or the corpus measures the fallback instead.
#   * origin/main base resolution removed   -> 1 fails.
#   * `git init` dropped from the pointer sandbox -> 4 fail as "sandbox leaked". Worth stating
#     why that check exists at all: setting TMPDIR inside the repo does NOT trip it, because each
#     sandbox runs its own `git init` and therefore is its own toplevel. So the corpus cannot
#     produce a positive by placement alone, and the guard is proven only by this mutation — it
#     defends against a future refactor dropping the init, not against a hostile TMPDIR.

set -uo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../ci" && pwd)/vercel_should_build.sh"
[ -f "$SCRIPT" ] || { echo "FATAL: script not found at $SCRIPT"; exit 2; }

PASS=0; FAIL=0
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT

# --- a repo with a real remote, so `git fetch origin main` works like it does on Vercel ------
UPSTREAM="$ROOT/upstream.git"
WORK="$ROOT/work"
git init -q --bare "$UPSTREAM"
git init -q -b main "$WORK"
git -C "$WORK" config user.email t@example.com
git -C "$WORK" config user.name t
git -C "$WORK" remote add origin "$UPSTREAM"

commit() { # commit <path> <message>
  mkdir -p "$WORK/$(dirname "$1")"
  echo "$2" > "$WORK/$1"
  git -C "$WORK" add -A
  git -C "$WORK" commit -q -m "$2"
}

commit "README.md" "base"
commit "apps/mouth/app/page.tsx" "frontend base"
git -C "$WORK" push -q origin main
MAIN_TIP=$(git -C "$WORK" rev-parse HEAD)

run() { # run <expected: BUILD|SKIP> <label> ; env vars come from the caller
  local want="$1" label="$2" got rc
  ( cd "$WORK" && bash "$SCRIPT" >/dev/null 2>&1 ); rc=$?
  case $rc in 1) got=BUILD ;; 0) got=SKIP ;; *) got="rc=$rc" ;; esac
  if [ "$got" = "$want" ]; then
    PASS=$((PASS+1)); printf '  ok    %-58s %s\n' "$label" "$got"
  else
    FAIL=$((FAIL+1)); printf '  FAIL  %-58s want %s, got %s\n' "$label" "$want" "$got"
  fi
}

echo "=== GUILT: a build is genuinely needed"

git -C "$WORK" checkout -q -b feat/frontend main
commit "apps/mouth/app/new.tsx" "a real frontend change"
VERCEL_GIT_COMMIT_REF=feat/frontend VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "first deploy of a branch that DOES touch apps/mouth"

git -C "$WORK" checkout -q -b feat/pkg main
commit "packages/core/index.ts" "a workspace package change"
VERCEL_GIT_COMMIT_REF=feat/pkg VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "first deploy of a branch touching packages/"

git -C "$WORK" checkout -q -b feat/vjson main
commit "vercel.json" '{"framework":"nextjs"}'
VERCEL_GIT_COMMIT_REF=feat/vjson VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "vercel.json alone rebuilds (the old command ignored it)"

echo
echo "=== INNOCENCE: nothing the browser can see changed"

git -C "$WORK" checkout -q -b docs/ledger main
commit ".claude/skills/modus/PENDING-ARMS.md" "a ledger line"
VERCEL_GIT_COMMIT_REF=docs/ledger VERCEL_GIT_PREVIOUS_SHA= \
  run SKIP "first deploy of a docs-only branch — the 828-build case"

git -C "$WORK" checkout -q -b ops/cron main
commit "infra/launchagents/wrappers/x.sh" "a cron wrapper"
commit "research/operations/note.md" "a capture"
VERCEL_GIT_COMMIT_REF=ops/cron VERCEL_GIT_PREVIOUS_SHA= \
  run SKIP "first deploy of a multi-commit backend/ops branch"

echo
echo "=== THE PRODUCTION GUARD: main must never skip on a missing previous SHA"
# Comparing main against main gives an empty diff. Without the guard this single case would
# freeze balizero.com and every subdomain — the 2026-07-27 outage, re-created by an optimisation.
git -C "$WORK" checkout -q main
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "main with no previous deployment"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$MAIN_TIP" \
  run BUILD "main against its own tip (base == HEAD)"

echo
echo "=== OFFLINE BASE RESOLUTION (added 2026-07-30 after the armed guard proved inert)"
# The first version fetched origin/main and, when the fetch failed, built. Armed in production it
# failed EVERY time — `cannot fetch main -> BUILD (fail-open)` in every first deployment — so the
# 89%-of-waste case never fired. These cases pin the two network-free paths that replaced it.

# (1) The merge queue encodes the base commit in the ref: gh-readonly-queue/main/pr-<n>-<base-sha>.
#
# ISOLATED ON PURPOSE. Written naively these three cases passed with the queue path deleted —
# path (2) resolved them and the mutation showed 0 failures, i.e. they tested nothing. So the
# other two routes are removed for this block: no origin/main tracking ref, unreachable remote.
# A SKIP here can only come from the ref name.
git -C "$WORK" update-ref -d refs/remotes/origin/main
git -C "$WORK" remote set-url origin "$ROOT/does-not-exist.git"

git -C "$WORK" checkout -q -b docs/queued main
commit "docs/queued.md" "docs only, deployed through the merge queue"
VERCEL_GIT_COMMIT_REF="gh-readonly-queue/main/pr-4242-$MAIN_TIP" VERCEL_GIT_PREVIOUS_SHA= \
  run SKIP "queue ref carries its base sha — docs-only skips with NO network"

git -C "$WORK" checkout -q -b feat/queued main
commit "apps/mouth/app/queued.tsx" "frontend, through the merge queue"
VERCEL_GIT_COMMIT_REF="gh-readonly-queue/main/pr-4243-$MAIN_TIP" VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "same path, frontend delta — still builds (guilt)"

# A queue ref whose trailing sha is NOT in this clone must not be trusted into a skip.
VERCEL_GIT_COMMIT_REF="gh-readonly-queue/main/pr-4244-deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" \
VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "queue ref naming a sha this clone does not have -> falls through"

git -C "$WORK" remote set-url origin "$UPSTREAM"
git -C "$WORK" fetch -q origin main:refs/remotes/origin/main

# (2) A remote-tracking origin/main already in the clone resolves offline. A STALE one is safe by
# direction: being behind moves the merge-base EARLIER, which widens the diff and biases to BUILD.
git -C "$WORK" checkout -q -b docs/offline main
commit "docs/offline.md" "docs only, remote unreachable but origin/main is local"
git -C "$WORK" remote set-url origin "$ROOT/does-not-exist.git"
VERCEL_GIT_COMMIT_REF=docs/offline VERCEL_GIT_PREVIOUS_SHA= \
  run SKIP "unreachable remote but origin/main present -> resolved offline"

echo
echo "=== FAIL-OPEN: genuinely unresolvable still builds"
# The real unresolvable case, which the old "unreachable origin" test only appeared to cover: no
# remote-tracking ref AND no reachable remote. Without this, dropping BOTH offline paths would
# leave the suite green.
git -C "$WORK" checkout -q -b weird/norem main
commit "docs/x.md" "docs only, and nothing can establish a base"
git -C "$WORK" update-ref -d refs/remotes/origin/main
VERCEL_GIT_COMMIT_REF=weird/norem VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "no origin/main ref and unreachable remote (docs-only, yet builds)"
git -C "$WORK" remote set-url origin "$UPSTREAM"
git -C "$WORK" fetch -q origin main:refs/remotes/origin/main

VERCEL_GIT_COMMIT_REF=docs/ledger VERCEL_GIT_PREVIOUS_SHA=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef \
  run BUILD "previous SHA that git does not know"

echo
echo "=== SUBSEQUENT DEPLOYS: the path that already worked must keep working"
git -C "$WORK" checkout -q docs/ledger
PREV=$(git -C "$WORK" rev-parse HEAD)
commit "docs/another.md" "more docs"
VERCEL_GIT_COMMIT_REF=docs/ledger VERCEL_GIT_PREVIOUS_SHA="$PREV" \
  run SKIP "second deploy, docs-only delta"
PREV=$(git -C "$WORK" rev-parse HEAD)
commit "apps/mouth/app/late.tsx" "frontend arrives later in the branch"
VERCEL_GIT_COMMIT_REF=docs/ledger VERCEL_GIT_PREVIOUS_SHA="$PREV" \
  run BUILD "second deploy, frontend delta"

echo
echo "=== THE EXIT CONTRACT: nothing may leave this script with a status other than 0 or 1"
# Vercel reads exit 0 as skip and exit 1 as build. Every OTHER status fails the deployment
# outright — which is what happened on 2026-07-29, 9 deployments in ERROR, because a missing
# file exited 127 and 127 was assumed to mean "build". A later edit adding `exit 2` for some
# third outcome would look entirely reasonable and would break production deploys, so the
# statuses are pinned statically rather than left to review.
BAD=$(grep -oE '(^|[;{[:space:]])exit [0-9]+' "$SCRIPT" | grep -oE '[0-9]+$' | grep -vE '^[01]$' | sort -u)
if [ -z "$BAD" ]; then
  PASS=$((PASS+1)); printf '  ok    %-58s %s\n' "guard exits only 0 or 1" "clean"
else
  FAIL=$((FAIL+1)); printf '  FAIL  %-58s found: %s\n' "guard exits only 0 or 1" "$(echo "$BAD" | tr '\n' ' ')"
fi

echo
echo "=== THE POINTER: the command pasted into Vercel must normalise every other status to 1"
# scripts/ci/vercel_ignore_build_step.sh holds the literal value of the project's
# commandForIgnoringBuildStep. Testing the guard alone would have caught none of the incident:
# the guard was innocent, the pointer was the defect, and the pointer was dashboard state that
# no file described. It is executed here against exactly the cases that broke production.
POINTER_FILE="$(dirname "$SCRIPT")/vercel_ignore_build_step.sh"
[ -f "$POINTER_FILE" ] || { echo "FATAL: pointer file not found at $POINTER_FILE"; exit 2; }
POINTER=$(grep -vE '^\s*(#|$)' "$POINTER_FILE")
POINTER_LINES=$(printf '%s\n' "$POINTER" | grep -c .)

if [ "$POINTER_LINES" -eq 1 ]; then
  PASS=$((PASS+1)); printf '  ok    %-58s %s\n' "pointer file holds exactly one command" "1 line"
else
  FAIL=$((FAIL+1)); printf '  FAIL  %-58s got %s lines\n' "pointer file holds exactly one command" "$POINTER_LINES"
fi

# The API rejects >256 chars with invalid_command_for_ignoring_build_step, and rejects the
# WHOLE PATCH body with it — a second setting sent alongside is silently lost too.
PLEN=${#POINTER}
if [ "$PLEN" -le 256 ]; then
  PASS=$((PASS+1)); printf '  ok    %-58s %s chars\n' "pointer fits the 256-char API limit" "$PLEN"
else
  FAIL=$((FAIL+1)); printf '  FAIL  %-58s %s chars (API rejects >256)\n' "pointer fits the 256-char API limit" "$PLEN"
fi

run_pointer() { # run_pointer <expected: BUILD|SKIP> <label> <script-body|MISSING>
  local want="$1" label="$2" body="$3" dir got rc
  dir=$(mktemp -d "$ROOT/ptr.XXXXXX")
  git init -q -b main "$dir"
  mkdir -p "$dir/scripts/ci"
  if [ "$body" != "MISSING" ]; then
    printf '%s\n' "$body" > "$dir/scripts/ci/vercel_should_build.sh"
  fi
  # The pointer resolves its target through `git rev-parse --show-toplevel`. If this temp repo
  # were nested inside the real checkout — a CI runner whose TMPDIR lives under the workspace
  # would do it — that call would resolve to the REAL repo, the "script absent" case would
  # silently execute the REAL guard, and all six cases would pass while testing nothing.
  # Assert the sandbox is the sandbox instead of assuming it.
  local top
  top=$( cd "$dir" && git rev-parse --show-toplevel 2>/dev/null )
  if [ "$(cd "$dir" && pwd -P)" != "$(cd "$top" 2>/dev/null && pwd -P)" ]; then
    FAIL=$((FAIL+1)); printf '  FAIL  %-58s sandbox leaked: toplevel=%s\n' "$label" "$top"
    return
  fi
  ( cd "$dir" && eval "$POINTER" >/dev/null 2>&1 ); rc=$?
  case $rc in 1) got=BUILD ;; 0) got=SKIP ;; *) got="rc=$rc (DEPLOYMENT ERROR)" ;; esac
  if [ "$got" = "$want" ]; then
    PASS=$((PASS+1)); printf '  ok    %-58s %s\n' "$label" "$got"
  else
    FAIL=$((FAIL+1)); printf '  FAIL  %-58s want %s, got %s\n' "$label" "$want" "$got"
  fi
}

# The incident, reproduced. Before the wrapper this was rc=127 and every deployment failed.
run_pointer BUILD "script absent (the 2026-07-29 incident)"            MISSING
run_pointer BUILD "script with a syntax error (bash exits 2)"          'if then fi'
run_pointer BUILD "script exiting 127 for any other reason"            'exit 127'
run_pointer BUILD "script killed by a signal"                          'kill -TERM $$'
# And the two legitimate verdicts must still pass through untouched.
run_pointer BUILD "script says build"                                  'exit 1'
run_pointer SKIP  "script says skip"                                   'exit 0'

echo
echo "-------------------------------------------------------------"
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
