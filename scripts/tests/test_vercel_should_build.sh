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
echo "=== FAIL-OPEN: anything unresolvable builds"
git -C "$WORK" checkout -q -b weird/norem main
commit "docs/x.md" "docs only, but the remote is unreachable"
git -C "$WORK" remote set-url origin "$ROOT/does-not-exist.git"
VERCEL_GIT_COMMIT_REF=weird/norem VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "unreachable origin (docs-only, yet still builds)"
git -C "$WORK" remote set-url origin "$UPSTREAM"

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
echo "-------------------------------------------------------------"
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
