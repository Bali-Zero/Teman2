#!/usr/bin/env bash
# Vercel "Ignored Build Step" — decides whether this commit can change what the browser
# receives. Wired into the project's `commandForIgnoringBuildStep`, which is capped at 256
# characters, so the field holds only a pointer to this file and the reasoning lives here.
#
# CONTRACT — read this twice, it is not the usual shell convention:
#   exit 0  -> SKIP the build
#   exit 1  -> BUILD
#   ANY OTHER EXIT CODE -> the DEPLOYMENT FAILS. Not "build", not "skip": ERROR.
#
# That third line cost 9 failed deployments on 2026-07-29 between 06:26Z and 06:55Z. The first
# version of the project's ignore setting pointed straight at this file with
# `bash "$(git rev-parse --show-toplevel)/scripts/ci/vercel_should_build.sh"`, wired up BEFORE
# the file existed on main, on the reasoning that a missing script exits 127, and 127 is
# non-zero, and non-zero means build. It does not. `bash: No such file or directory` errored
# every deployment for half an hour — main included — until the setting was rolled back.
# (Production itself never went stale: a failed deployment does not replace the live one, and
# no frontend-relevant commit landed in the window. Vercel's commit status went red but is not
# among main's required checks.) Vercel documents this precisely — "the build continues if the
# command exits with code 1, and is ignored if it exits with 0" — and the doc had been read in
# the same session. The error was generalising "1" to "non-zero".
#
# Two consequences, both load-bearing:
#   1. Every path in this file exits 0 or 1 and nothing else. Pinned by a test that greps for
#      any other literal exit code, because a `exit 2` added later would look harmless.
#   2. The project setting must NORMALISE, never point here bare:
#        S="$(git rev-parse --show-toplevel)/scripts/ci/vercel_should_build.sh"; [ -f "$S" ] || exit 1; bash "$S"; [ $? = 0 ] && exit 0 || exit 1
#      so a missing file, a syntax error, or a signal all become BUILD instead of ERROR. And it
#      is armed only AFTER this file is on main — the ordering that was skipped.
#
# Every failure path builds. A build we did not need costs minutes; a build we needed and
# skipped leaves the entire public surface — balizero.com plus kita/my/prime/visa/tax/zantara,
# all one Vercel project — serving stale code. Those are not symmetric, so this is fail-open
# by construction and never "clever" at the margin.
#
# WHY IT WAS REPLACED (measured 2026-07-29, current billing cycle, 16 days):
#   3,100 deployments, 1,885 of which actually built, 11,091 build-minutes.
#   1,561 of those builds were PR previews — 83% of all build minutes.
#   Of the 1,158 preview builds whose commit could be classified locally, 828 (72%) touched
#   NO frontend path at all: ledger entries, cron wrappers, research captures, backend work.
#
# The previous command opened with `[ -z "$VERCEL_GIT_PREVIOUS_SHA" ] && exit 1` — build when
# there is no previous deployment to compare against. That variable is empty by definition on
# a branch's FIRST deployment, and most PRs here are one or two commits on a fresh branch, so
# the guard fired on almost every PR. The split is visible in the data: across 970 distinct PR
# branches, 89% of first deployments built versus 59% of later ones.
#
# The fix is not to drop the fail-open — it is to give the first deployment something correct
# to compare against: the merge-base with the production branch, which is exactly "what this
# branch changes". Anything that cannot be established still builds.
#
# WHAT IS DELIBERATELY NOT OPTIMISED: the production branch never skips on a missing previous
# SHA. Comparing main against main yields an empty diff, i.e. "skip", and that single line
# would be a machine for freezing production — the failure this repo spent 2026-07-27 and
# 2026-07-28 recovering from. It is guarded explicitly and tested.
#
# Tests: scripts/tests/test_vercel_should_build.sh (guilt + innocence, run in a real git repo).

set -u

# Paths that can change the built app. `vercel.json` is included because build settings live
# there; the previous command omitted it, so a change to how the app is built did not rebuild it.
# The repo-root `vercel.json` is gone as of this change — the project's Root Directory is
# `apps/mouth`, so Vercel read `apps/mouth/vercel.json` and the root file was inert. Proven from
# a real build log, not from the setting: the build ran `next build --webpack` (the apps/mouth
# value), never the root file's `npm run build -w apps/mouth`. It is still matched here on
# purpose — if a root `vercel.json` ever comes back, rebuilding on it is the fail-open answer.
FRONTEND_RE='^(apps/mouth/|packages/|package\.json|package-lock\.json|vercel\.json|apps/mouth/vercel\.json)'

PROD_BRANCH="${VERCEL_GIT_PROD_BRANCH:-main}"
REF="${VERCEL_GIT_COMMIT_REF:-}"
BASE="${VERCEL_GIT_PREVIOUS_SHA:-}"

log() { printf 'should-build: %s\n' "$1" >&2; }

# The production branch never skips. Not on a missing previous SHA, and not on a present one.
#
# The guard used to live inside the `[ -z "$BASE" ]` block below, on the reasoning that the
# danger was comparing main against main and reading the empty diff as "nothing to build". That
# named the right danger and only half the doors. On main `VERCEL_GIT_PREVIOUS_SHA` is normally
# SET, so the block was skipped entirely and the production guard inside it never ran.
#
# What that variable actually holds is the previous *attempted* deployment — including attempts
# this script itself skipped, and attempts Vercel cancelled because a newer commit superseded
# them. It does NOT hold what is live. So the base walks forward past a frontend commit whose own
# build never shipped, and every later commit is judged against that base and correctly finds no
# frontend change. The stranded commit is then unreachable: no future diff ever spans it again.
#
# Measured on 2026-08-18. balizero.com was serving f6dfda99, built 2026-08-15, while main was 75
# commits ahead: 272 files changed in between, 30 of them frontend paths. The individual builds
# saw 4 and 18 files and skipped, each of them right about its own base and all of them wrong
# about production. Among the stranded commits was #4178, which removed `Avg reply: 2 min` — a
# claim measured false against 189 message pairs (average ~9h) — so the page kept serving a
# number we had already proven wrong, for three days, with every check green.
#
# The asymmetry at the top of this file settles which way to fail: an unnecessary production
# build costs ~6 minutes, a wrongly skipped one serves stale code across the whole public surface
# until a human happens to notice. The savings were never here anyway — the 2026-07-29
# measurement put 83% of build minutes in PR previews, and that is where they stay.
if [ -n "$REF" ] && [ "$REF" = "$PROD_BRANCH" ]; then
  log "production branch '$REF' -> BUILD (a previous SHA names the last attempt, not what is live)"
  exit 1
fi

if [ -z "$BASE" ]; then
  # No previous deployment on this ref — this is the case that matters. Measured on the real
  # billing data, first deployments are 89% of the waste: most PRs here are one or two commits
  # on a fresh branch, so `VERCEL_GIT_PREVIOUS_SHA` is empty and there is nothing to diff against.
  #
  # The first version of this block went straight to `git fetch origin main` and, when that
  # failed, built. Armed on 2026-07-29 it turned out to fail EVERY time in Vercel's build
  # container — `should-build: cannot fetch main -> BUILD (fail-open)` — so the entire
  # first-deployment optimisation never fired and the projected saving was not being collected.
  # The guard was safe (it built too much, never too little) but effectively inert on its main case.
  #
  # Worse, the reason was unknowable: the fetch's stderr went to /dev/null, so the log said
  # "cannot fetch" and nothing else. A fail-open branch that does not say WHICH stage opened
  # cannot be repaired from its own evidence. So: cheapest-first resolution, each stage
  # announcing itself without replaying Git stderr, which may contain an authenticated URL.
  # (The production check that used to sit here has moved above this block, where it can also see
  # the deployments that DO have a previous SHA — which is all of them, on main. Leaving a copy
  # here would be unreachable code that reads like a second line of defence.)

  # (1) The merge queue puts the BASE COMMIT in the ref name:
  #     gh-readonly-queue/<base-branch>/pr-<n>-<base-sha>
  # That is exact, needs no network, and covers every queue deployment. Only trust it if the
  # object is actually present in this clone.
  case "$REF" in
    gh-readonly-queue/*)
      cand=${REF##*-}
      if [ ${#cand} -eq 40 ] && git cat-file -e "${cand}^{commit}" 2>/dev/null; then
        BASE=$cand
        log "queue ref carries its base -> ${BASE:0:9} (no network)"
      fi
      ;;
  esac

  # (2) A remote-tracking main already in the clone.
  if [ -z "$BASE" ] && git rev-parse --verify --quiet "refs/remotes/origin/$PROD_BRANCH" >/dev/null 2>&1; then
    if BASE=$(git merge-base "origin/$PROD_BRANCH" HEAD 2>/dev/null) && [ -n "$BASE" ]; then
      log "origin/$PROD_BRANCH present -> merge-base ${BASE:0:9} (no network)"
    else
      BASE=
    fi
  fi

  # (3) Only now pay for the network — and keep the error, which is the whole point.
  #
  # The named remote is tried first, but it is NOT how this resolves on Vercel: measured live
  # on 2026-08-10 (deployment C1BqEsSc…, branch agent/air-m5/ops/tg-senders-batch2), the build
  # container's clone has no usable `origin` at all —
  #     fatal: 'origin' does not appear to be a git repository
  # — so every first deployment fell through to fail-open and bought a full 1,755-page build:
  # the exact 89%-of-waste case this block exists to close, inert for a second reason after
  # the 2026-07-30 rework fixed the first. The cure is to fetch the production branch straight
  # from the repository URL that Vercel itself advertises in the build env
  # (VERCEL_GIT_REPO_OWNER/SLUG; the repo is public, an anonymous fetch suffices).
  # SHOULD_BUILD_FETCH_URL overrides the constructed URL — test seam and emergency lever.
  # Every failure still exits 1 (BUILD), with each failed transport named. Git stderr is never
  # logged because it can normalize and repeat credentials or query tokens from the fetch URL.
  if [ -z "$BASE" ]; then
    fetched=
    if git fetch --no-tags --depth=200 origin "$PROD_BRANCH" >/dev/null 2>&1; then
      fetched=origin
    else
      FETCH_URL="${SHOULD_BUILD_FETCH_URL:-}"
      if [ -z "$FETCH_URL" ] && [ -n "${VERCEL_GIT_REPO_OWNER:-}" ] && [ -n "${VERCEL_GIT_REPO_SLUG:-}" ]; then
        FETCH_URL="https://github.com/${VERCEL_GIT_REPO_OWNER}/${VERCEL_GIT_REPO_SLUG}.git"
      fi
      if [ -z "$FETCH_URL" ]; then
        log "cannot fetch $PROD_BRANCH (no origin, no repo env to build a URL) -> BUILD (fail-open). origin fetch failed"
        exit 1
      fi
      if git fetch --no-tags --depth=200 "$FETCH_URL" "$PROD_BRANCH" >/dev/null 2>&1; then
        # The override is an operational seam and may contain credentials or another
        # sensitive locator. The fetch target must never be copied into Vercel logs.
        fetched=url
      else
        log "cannot fetch $PROD_BRANCH from origin or URL -> BUILD (fail-open). origin fetch failed | URL fetch failed"
        exit 1
      fi
    fi
    if BASE=$(git merge-base FETCH_HEAD HEAD 2>/dev/null) && [ -n "$BASE" ]; then
      log "fetched $PROD_BRANCH from $fetched -> merge-base ${BASE:0:9}"
    else
      log "fetched $PROD_BRANCH from $fetched but no merge-base (shallow clone?) -> BUILD (fail-open)"
      exit 1
    fi
  fi

  log "first deployment of '$REF' -> base ${BASE:0:9}"
fi

HEAD_SHA=$(git rev-parse HEAD 2>/dev/null) || { log "cannot resolve HEAD -> BUILD"; exit 1; }
if [ "$BASE" = "$HEAD_SHA" ]; then
  # Base == HEAD means the diff is empty for a reason we did not intend (already merged, or a
  # re-deploy of the same commit). An empty diff must not be read as "nothing to build".
  log "base equals HEAD -> BUILD (an empty diff here is not evidence of no change)"
  exit 1
fi

if ! CHANGED=$(git diff --name-only "$BASE" HEAD 2>/dev/null); then
  log "git diff failed against ${BASE:0:9} -> BUILD (fail-open)"
  exit 1
fi

# Judge grep by its exit code explicitly: 0 = matched, 1 = no match, >=2 = grep itself failed.
# Collapsing that into `&& exit 1 || exit 0` would turn a grep error into a SKIP — the one
# outcome this script must never produce by accident.
printf '%s\n' "$CHANGED" | grep -qE "$FRONTEND_RE"
case $? in
  0) log "frontend paths changed -> BUILD"; exit 1 ;;
  1) log "no frontend path in $(printf '%s\n' "$CHANGED" | grep -c .) changed file(s) -> SKIP"; exit 0 ;;
  *) log "grep failed -> BUILD (fail-open)"; exit 1 ;;
esac
