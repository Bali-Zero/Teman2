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
#   * removing the production guard entirely -> 4 fail  (measured 2026-08-18)
#   * production arm rewritten 2026-09-10 to diff against what is LIVE. Measured on the
#     46-case corpus of that day:
#       - production always builds (the 2026-08-18 interim rule)      -> 4 fail
#       - production judged against VERCEL_GIT_PREVIOUS_SHA            -> 4 fail (the freeze case among them)
#       - production judged against HEAD^ (Vercel's documented example) -> 8 fail (batch, freeze, rollback)
#       - live-probe failure read as SKIP                              -> 4 fail
#   * keying it on the literal "main" instead of $PROD_BRANCH -> 2 fail, one in each direction
#   * dropping the VERCEL_ENV arm, leaving the branch test alone -> 1 fail
#   * making the guard unconditional (`if true`) -> 11 fail. Recorded because it is the shape a
#     future "just always build, it is safer" edit would take, and it must not pass quietly.
#
#   CORRECTED 2026-08-18, and the wrong version is quoted because it is the reason nobody looked.
#   This header used to say: removing the `$REF = main` guard fails nothing, the `base == HEAD`
#   guard covers the same case, "the two guards are redundant on purpose and the suite asserts the
#   OUTCOME (main always builds), which is the thing that matters." The first two clauses were
#   true. The last one was not, and it is the one that got believed. The suite asserted main
#   always builds in the only two shapes it had: no previous SHA, and a previous SHA equal to
#   HEAD. It never asserted the shape a production deployment takes once the project has one
#   behind it — a previous SHA pointing at an EARLIER commit. There both guards were bypassed and
#   main skipped, which is what froze balizero.com for three days from 2026-08-15. A mutation that
#   kills nothing is worth a second look: here it was not redundancy, it was a guard unreachable
#   from the case that mattered, and the note explained the zero away instead of chasing it.
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

# The guard reads VERCEL_ENV, so the corpus must own its value rather than inherit one. A shell
# that happens to export VERCEL_ENV=production would turn every SKIP case green-to-red at once and
# the failure would look like a code defect. Empty is neither "production" nor unset-and-guessed;
# per-case assignments below still win, because the caller's environment beats this default.
export VERCEL_ENV=

# The production arm asks what is LIVE through a probe URL. The corpus never touches the real
# endpoint: by default it points at a file that does not exist, so every production case that
# does not stage its own probe exercises the fail-open path (BUILD). Cases that want a verdict
# write a health body and point the probe at it — curl reads `file://` URLs like any other.
PROBE_DIR=$(mktemp -d)
export SHOULD_BUILD_LIVE_PROBE_URL="file://$PROBE_DIR/does-not-exist.json"
probe_says() { # probe_says <sha|raw-json> ; sets the probe to a body carrying that commit
  case "$1" in
    *"{"*) printf '%s' "$1" > "$PROBE_DIR/health.json" ;;
    *) printf '{"status":"ok","commit":"%s"}' "$1" > "$PROBE_DIR/health.json" ;;
  esac
  export SHOULD_BUILD_LIVE_PROBE_URL="file://$PROBE_DIR/health.json"
}
probe_dead() { export SHOULD_BUILD_LIVE_PROBE_URL="file://$PROBE_DIR/does-not-exist.json"; }

PASS=0; FAIL=0
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT" "$PROBE_DIR"' EXIT

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

run_log_safe() { # run_log_safe <expected> <label> <required-log-fragment> <sentinel>...
  local want="$1" label="$2" required="$3" output got rc sentinel safe=1
  shift 3
  output=$( ( cd "$WORK" && bash "$SCRIPT" >/dev/null ) 2>&1 ); rc=$?
  case $rc in 1) got=BUILD ;; 0) got=SKIP ;; *) got="rc=$rc" ;; esac
  for sentinel in "$@"; do
    [[ "$output" != *"$sentinel"* ]] || safe=0
  done
  if [ "$got" = "$want" ] && [[ "$output" == *"$required"* ]] && [ "$safe" -eq 1 ]; then
    PASS=$((PASS+1)); printf '  ok    %-58s %s\n' "$label" "$got"
  else
    FAIL=$((FAIL+1))
    printf '  FAIL  %-58s want %s without sentinel, got %s; log=%s\n' \
      "$label" "$want" "$got" "$output"
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
echo "=== PRODUCTION: judged against what is LIVE, never against a previous attempt"
# The probe is the only base production trusts. Without it (dead URL, no field, unknown sha)
# every shape below builds — the 2026-07-27 outage re-created by an optimisation is the one
# outcome this arm may never produce, so the fail-open cases come first.
git -C "$WORK" checkout -q main
probe_dead
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "main, probe unreachable, no previous SHA -> builds"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$MAIN_TIP" \
  run BUILD "main, probe unreachable, previous SHA == HEAD -> builds"
probe_says '{"status":"ok"}'
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "main, probe answers without a .commit field -> builds"
probe_says '{"status":"ok","commit":"abc123"}'
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "main, probe .commit is not a 40-hex sha -> builds"
probe_says "$MAIN_TIP"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "main, live == HEAD (a redeploy of the served commit) -> builds"

# The saving: a docs-only commit on top of what is live skips. This is the ~220-builds-a-week
# case measured 2026-09-09 (301 main commits in 7 days, 79 touching the bundle), and the shape
# the 2026-08-18 interim rule paid for in full by building every one of them.
commit "docs/prod-note.md" "a docs-only commit landing on main"
DOCS_ON_MAIN=$(git -C "$WORK" rev-parse HEAD)
probe_says "$MAIN_TIP"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$MAIN_TIP" \
  run SKIP "main, docs-only delta vs what is LIVE -> skips"
VERCEL_ENV=production VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run SKIP "same, VERCEL_ENV=production and no previous SHA -> still skips (the SHA is not consulted)"

# GUILT, the stranded shape (balizero.com frozen 2026-08-15..18): a frontend commit whose own
# build never shipped, then a docs commit. VERCEL_GIT_PREVIOUS_SHA points at the frontend
# ATTEMPT, so a diff against it is docs-only; the diff against what is LIVE is not.
commit "apps/mouth/app/stranded.tsx" "a frontend commit whose build was superseded"
STRANDED=$(git -C "$WORK" rev-parse HEAD)
commit ".claude/skills/modus/PENDING-ARMS.md" "a ledger line, also on main"
probe_says "$MAIN_TIP"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$STRANDED" \
  run BUILD "main, docs-only vs the previous ATTEMPT but frontend vs LIVE -> builds (the freeze)"

# GUILT, the batch shape: the merge queue lands up to four squash commits in ONE push and Vercel
# deploys the tip. `git diff HEAD^ HEAD` (Vercel's documented example) sees only the last commit
# of the batch — here docs-only — and would skip a frontend PR that landed one commit earlier.
# Against what is LIVE the batch is one diff and the frontend change is in it.
probe_says "$DOCS_ON_MAIN"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$DOCS_ON_MAIN" \
  run BUILD "main, batch of [frontend, docs] pushed at once, live = before the batch -> builds"

# INNOCENCE after a build ships: once production serves the frontend commit, the docs commit on
# top of it is a docs-only delta again.
probe_says "$STRANDED"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$STRANDED" \
  run SKIP "main, live has caught up to the frontend commit, docs on top -> skips"

# A rollback: production serves an OLDER commit than the newest frontend change. The diff spans
# the rolled-back change, so this builds — the same answer the interim rule gave, and the
# autopromote organ's to make, not this script's.
probe_says "$MAIN_TIP"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= \
  run BUILD "main, production rolled back behind a frontend commit -> builds"

# The frontend commit above must not leak into the branches the rest of the corpus cuts from
# main: every later merge-base diff would carry it and every docs-only SKIP would turn BUILD.
git -C "$WORK" checkout -q main
git -C "$WORK" reset -q --hard "$MAIN_TIP"

# The live sha is not in the clone (Vercel's clone is shallow). It is fetched by sha from the
# repository URL — the object lives in upstream on a branch this clone never fetched.
# `-b main` is load-bearing: the bare upstream was `git init`ed with the host's default branch
# name as HEAD, which is `master` on a stock CI runner, so an unqualified clone checks out an
# unborn branch, the "live" commit is born without the frontend base file, and the diff against
# it reads a frontend DELETION -> BUILD. Measured 2026-09-10: green on a Mac with
# init.defaultBranch=main, red on ubuntu-latest, for exactly that reason.
SIDE="$ROOT/side"
git clone -q -b main "$UPSTREAM" "$SIDE"
[ -f "$SIDE/apps/mouth/app/page.tsx" ] || { FAIL=$((FAIL+1)); printf '  FAIL  %-58s\n' "fixture: side clone must carry the frontend base"; }
git -C "$SIDE" config user.email t@example.com
git -C "$SIDE" config user.name t
git -C "$SIDE" checkout -q -b live-only
mkdir -p "$SIDE/docs" && echo "served" > "$SIDE/docs/served-elsewhere.md"
git -C "$SIDE" add -A && git -C "$SIDE" commit -q -m "the commit production serves, unknown to this clone"
git -C "$SIDE" push -q origin live-only
LIVE_ELSEWHERE=$(git -C "$SIDE" rev-parse HEAD)
git -C "$UPSTREAM" config uploadpack.allowAnySHA1InWant true
if git -C "$WORK" cat-file -e "${LIVE_ELSEWHERE}^{commit}" 2>/dev/null; then
  FAIL=$((FAIL+1)); printf '  FAIL  %-58s %s\n' "fixture: live sha must be absent from the clone" "present"
fi
commit "docs/after-live.md" "docs on main, live commit sits on another branch"
probe_says "$LIVE_ELSEWHERE"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$UPSTREAM" \
  run_log_safe SKIP "live sha absent from the clone, fetched by sha from the URL -> docs-only skips" "fetched live commit" "$UPSTREAM"
# A second unknown live sha — the first one is in the clone now, fetched by the case above.
echo "served again" > "$SIDE/docs/served-elsewhere-2.md"
git -C "$SIDE" add -A && git -C "$SIDE" commit -q -m "another commit production serves, unknown to this clone"
git -C "$SIDE" push -q origin live-only
probe_says "$(git -C "$SIDE" rev-parse HEAD)"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$ROOT/does-not-exist.git" \
  run BUILD "live sha absent and the URL is dead -> builds (fail-open)"
probe_says "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$UPSTREAM" \
  run BUILD "live sha that no repository has -> builds (fail-open)"
probe_dead

# INNOCENCE. The guard must key on "is this the production branch", not on the literal string
# main. Point production elsewhere and main is an ordinary branch again, skipping exactly as
# before — without this, a hardcoded name would silently disable the whole optimisation on every
# other branch the day production is renamed, and nothing would say so.
PROD_PREV=$(git -C "$WORK" rev-parse HEAD)
commit "docs/renamed-prod.md" "docs only, main no longer production"
VERCEL_GIT_PROD_BRANCH=release VERCEL_GIT_COMMIT_REF=main VERCEL_GIT_PREVIOUS_SHA="$PROD_PREV" \
  run SKIP "main is NOT production when VERCEL_GIT_PROD_BRANCH names another branch"

# ...and whichever branch IS production inherits the arm (probe dead -> builds).
git -C "$WORK" checkout -q -b release main
PROD_PREV=$(git -C "$WORK" rev-parse HEAD)
commit "docs/release-note.md" "docs only, on the configured production branch"
VERCEL_GIT_PROD_BRANCH=release VERCEL_GIT_COMMIT_REF=release VERCEL_GIT_PREVIOUS_SHA="$PROD_PREV" \
  run BUILD "the configured production branch gets the arm, whatever it is called"

# The ref is not the environment. `vercel --prod` promotes whatever branch it is pointed at, and
# that deployment is production however its ref reads — so a branch test alone can skip a real
# production build. VERCEL_ENV is the documented variable for this question and answers it
# directly. Raised by an adversarial review of the first version of this fix, which keyed on the
# branch alone; the case below is that review's own repro.
VERCEL_ENV=production VERCEL_GIT_COMMIT_REF=release VERCEL_GIT_PREVIOUS_SHA="$PROD_PREV" \
  run BUILD "VERCEL_ENV=production on a NON-production branch (vercel --prod), probe dead"

# INNOCENCE for that arm: a preview is still a preview, and a docs-only preview still skips.
# Without this, keying on the environment could quietly become "always build".
VERCEL_ENV=preview VERCEL_GIT_COMMIT_REF=release VERCEL_GIT_PREVIOUS_SHA="$PROD_PREV" \
  run SKIP "VERCEL_ENV=preview, docs-only delta -> still skips"
git -C "$WORK" checkout -q main
git -C "$WORK" reset -q --hard "$MAIN_TIP"

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
echo "=== NO-ORIGIN CONTAINER: Vercel's clone has no usable origin at all (measured 2026-08-10)"
# The live failure was not an unreachable origin but a MISSING one: `fatal: 'origin' does not
# appear to be a git repository` on every first deployment, so the fail-open bought a full
# build each time. These cases delete the remote AND the tracking ref, so a SKIP can only come
# from the URL-fallback fetch (SHOULD_BUILD_FETCH_URL stands in for the constructed GitHub URL).
git -C "$WORK" checkout -q -b docs/noorigin main
commit "research/operations/no-origin-note.md" "docs only, container without origin"
git -C "$WORK" update-ref -d refs/remotes/origin/main
git -C "$WORK" remote remove origin
VERCEL_GIT_COMMIT_REF=docs/noorigin VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$UPSTREAM" \
  run SKIP "no origin remote, URL fallback resolves -> docs-only skips"

# The override is an operational seam. A credentialed URL (or any sensitive locator) must
# never be echoed into build logs on either success or failure.
FETCH_SENTINEL=SAFE_FETCH_TARGET_93af
PRIVATE_UPSTREAM="$ROOT/$FETCH_SENTINEL/upstream.git"
mkdir -p "$(dirname "$PRIVATE_UPSTREAM")"
git clone -q --bare "$UPSTREAM" "$PRIVATE_UPSTREAM"
VERCEL_GIT_COMMIT_REF=docs/noorigin VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$PRIVATE_UPSTREAM" \
  run_log_safe SKIP "URL fallback succeeds without logging its target" "from url -> merge-base" "$FETCH_SENTINEL"

git -C "$WORK" checkout -q -b feat/noorigin main
commit "apps/mouth/app/no-origin.tsx" "frontend, container without origin"
VERCEL_GIT_COMMIT_REF=feat/noorigin VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$UPSTREAM" \
  run BUILD "no origin remote, URL fallback resolves, frontend delta (guilt)"

git -C "$WORK" checkout -q -b docs/nourl main
commit "docs/no-url.md" "docs only, and nothing fetchable at all"
VERCEL_GIT_COMMIT_REF=docs/nourl VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$ROOT/$FETCH_SENTINEL/does-not-exist.git" \
  run_log_safe BUILD "dead URL fails open without logging its target" "cannot fetch main from origin or URL" "$FETCH_SENTINEL"

# Git can normalize a failed HTTP locator before echoing it (for example, stripping userinfo
# while retaining the query string), so exact-string replacement is not a sufficient redactor.
FETCH_USERINFO_SENTINEL=SENTINEL_USERINFO_8c17
FETCH_QUERY_SENTINEL=SENTINEL_QUERY_5e62
CRED_FETCH_URL="http://sentinel-user:${FETCH_USERINFO_SENTINEL}@127.0.0.1:1/repo.git?access_token=${FETCH_QUERY_SENTINEL}"
VERCEL_GIT_COMMIT_REF=docs/nourl VERCEL_GIT_PREVIOUS_SHA= SHOULD_BUILD_FETCH_URL="$CRED_FETCH_URL" \
  run_log_safe BUILD "normalized HTTP errors never leak credentials" \
  "origin fetch failed | URL fetch failed" "$FETCH_USERINFO_SENTINEL" "$FETCH_QUERY_SENTINEL"

git -C "$WORK" remote add origin "$UPSTREAM"
git -C "$WORK" fetch -q origin main:refs/remotes/origin/main

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

# The same line lives in apps/mouth/vercel.json as `ignoreCommand`, where it OVERRIDES the
# dashboard field. Two copies drift silently unless something compares them, so this does.
VJSON="$(dirname "$SCRIPT")/../../apps/mouth/vercel.json"
IGNORE_CMD=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("ignoreCommand",""))' "$VJSON" 2>/dev/null)
if [ "$IGNORE_CMD" = "$POINTER" ]; then
  PASS=$((PASS+1)); printf '  ok    %-58s %s\n' "apps/mouth/vercel.json ignoreCommand == pointer" "identical"
else
  FAIL=$((FAIL+1)); printf '  FAIL  %-58s\n        vercel.json: %s\n        pointer:     %s\n' "apps/mouth/vercel.json ignoreCommand == pointer" "$IGNORE_CMD" "$POINTER"
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
