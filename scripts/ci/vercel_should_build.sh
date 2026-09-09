#!/usr/bin/env bash
# Vercel "Ignored Build Step" — decides whether this commit can change what the browser
# receives. Wired in twice with the SAME line: apps/mouth/vercel.json `ignoreCommand` (wins,
# versioned with the tree it judges) and the project's `commandForIgnoringBuildStep` (the
# fallback if the file ever drops the key). Both are capped at 256 characters, so the field
# holds only a pointer to this file and the reasoning lives here.
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
#   2. The pointer must NORMALISE, never point here bare:
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
# PRODUCTION (rewritten 2026-09-10; the 2026-08-18 version built EVERY production commit).
# The base for a production deployment is neither `VERCEL_GIT_PREVIOUS_SHA` nor `HEAD^`:
#   * VERCEL_GIT_PREVIOUS_SHA names the previous ATTEMPT — skips and cancellations included —
#     so it advances past a frontend commit whose own build never shipped, and no later diff
#     spans that commit again. That stranded balizero.com on a 2026-08-15 build for three
#     days (#4309), and is why the interim rule was "production never skips".
#   * HEAD^ is the previous commit, not the previous PUSH. The merge queue lands batches of up
#     to four squash commits in one push and Vercel deploys the tip, so HEAD^..HEAD sees only
#     the last PR of the batch; a frontend PR earlier in the same batch is invisible to it.
# The only base that answers the real question — "does this commit change what is LIVE?" — is
# the commit production is serving, and production says so itself: kita.balizero.com/api/health
# returns `{"commit": "<sha>"}` (the probe the Frontend Live Sentinel and the mini.vercel_autopromote
# organ already trust). Diff that against HEAD; no frontend path -> SKIP. Any doubt -> BUILD:
# probe down, field missing, sha unknown and unfetchable, live == HEAD. A dead autopromote organ
# degrades to today's behaviour (every commit builds), never to a stale site, because the live
# sha then stops moving and every later diff keeps spanning the unshipped change.
# Measured before arming: 301 commits on main in 7 days, 79 of which change the bundle — this
# rule builds 79, the interim rule built ~245 (one per push). Tests pin the batch shape, the
# stranded shape and every fail-open path. SHOULD_BUILD_LIVE_PROBE_URL overrides the probe
# (test seam and emergency lever; a `file://` URL works).
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
# Keep in step with BUNDLE_PATHS in scripts/vercel_prod_deploy.py and the `paths:` of
# .github/workflows/frontend-live-sentinel.yml: a commit they call bundle-relevant must BUILD
# here, or the sentinel goes red for a build this script declined to make.
FRONTEND_RE='^(apps/mouth/|packages/|package\.json|package-lock\.json|vercel\.json|apps/mouth/vercel\.json)'

PROD_BRANCH="${VERCEL_GIT_PROD_BRANCH:-main}"
REF="${VERCEL_GIT_COMMIT_REF:-}"
BASE="${VERCEL_GIT_PREVIOUS_SHA:-}"
LIVE_PROBE_URL="${SHOULD_BUILD_LIVE_PROBE_URL:-https://kita.balizero.com/api/health}"

log() { printf 'should-build: %s\n' "$1" >&2; }

# The repository URL Vercel itself advertises in the build env (VERCEL_GIT_REPO_OWNER/SLUG; the
# repo is public, an anonymous fetch suffices). SHOULD_BUILD_FETCH_URL overrides it — test seam
# and emergency lever. Empty when nothing can be constructed. The value may carry credentials
# or another sensitive locator and must never be copied into Vercel logs.
repo_fetch_url() {
  if [ -n "${SHOULD_BUILD_FETCH_URL:-}" ]; then
    printf '%s' "$SHOULD_BUILD_FETCH_URL"
  elif [ -n "${VERCEL_GIT_REPO_OWNER:-}" ] && [ -n "${VERCEL_GIT_REPO_SLUG:-}" ]; then
    printf 'https://github.com/%s/%s.git' "$VERCEL_GIT_REPO_OWNER" "$VERCEL_GIT_REPO_SLUG"
  fi
}

# Verdict from a list of changed files. Judge grep by its exit code explicitly: 0 = matched,
# 1 = no match, >=2 = grep itself failed. Collapsing that into `&& exit 1 || exit 0` would turn a
# grep error into a SKIP — the one outcome this script must never produce by accident.
verdict_from_changed() { # verdict_from_changed <changed-file-list>
  printf '%s\n' "$1" | grep -qE "$FRONTEND_RE"
  case $? in
    0) log "frontend paths changed -> BUILD"; exit 1 ;;
    1) log "no frontend path in $(printf '%s\n' "$1" | grep -c .) changed file(s) -> SKIP"; exit 0 ;;
    *) log "grep failed -> BUILD (fail-open)"; exit 1 ;;
  esac
}

# PRODUCTION. Compare HEAD against the commit production is serving, never against a previous
# attempt (see the header). Every path that cannot establish the live commit builds.
production_verdict() {
  local body live head_sha url changed
  if ! body=$(curl -fsS --max-time 20 "$LIVE_PROBE_URL" 2>/dev/null); then
    log "production: live probe failed -> BUILD (fail-open)"
    exit 1
  fi
  live=$(printf '%s' "$body" | grep -oE '"commit"[[:space:]]*:[[:space:]]*"[0-9a-f]{40}"' | head -1 | grep -oE '[0-9a-f]{40}')
  if [ -z "$live" ]; then
    log "production: live probe exposes no 40-hex commit -> BUILD (fail-open)"
    exit 1
  fi
  head_sha=$(git rev-parse HEAD 2>/dev/null) || { log "cannot resolve HEAD -> BUILD"; exit 1; }
  if [ "$live" = "$head_sha" ]; then
    log "production: live commit equals HEAD (a redeploy) -> BUILD"
    exit 1
  fi
  if ! git cat-file -e "${live}^{commit}" 2>/dev/null; then
    # The container's clone is shallow and may not hold the live commit. Cheapest first: the
    # production branch's recent history (the live commit is normally a few days back), then
    # the exact sha (GitHub serves any reachable sha to a shallow fetch). The URL, never a
    # named remote: measured 2026-08-10, the container has no usable `origin`.
    url=$(repo_fetch_url)
    if [ -z "$url" ]; then
      log "production: live commit ${live:0:9} not in clone and no repo URL to fetch it -> BUILD (fail-open)"
      exit 1
    fi
    git fetch --no-tags --depth=200 "$url" "$PROD_BRANCH" >/dev/null 2>&1 || true
    if ! git cat-file -e "${live}^{commit}" 2>/dev/null; then
      git fetch --no-tags --depth=1 "$url" "$live" >/dev/null 2>&1 || true
    fi
    if ! git cat-file -e "${live}^{commit}" 2>/dev/null; then
      log "production: live commit ${live:0:9} not fetchable -> BUILD (fail-open)"
      exit 1
    fi
    log "production: fetched live commit ${live:0:9}"
  fi
  if ! changed=$(git diff --name-only "$live" HEAD 2>/dev/null); then
    log "production: git diff failed against live ${live:0:9} -> BUILD (fail-open)"
    exit 1
  fi
  log "production: comparing HEAD against live ${live:0:9}"
  verdict_from_changed "$changed"
}

# WHY THE TEST IS `VERCEL_ENV` FIRST. The branch comparison alone is not the deployment
# environment: `vercel --prod` can promote a non-production branch, and that deployment is
# production no matter what its ref says. `VERCEL_ENV` is the documented system variable for
# exactly this question, so it leads; the branch test stays as the second arm because
# `VERCEL_GIT_PROD_BRANCH` may be absent (the `:-main` fallback is correct for this repo) and
# because the corpus runs the script outside Vercel entirely, where only the ref exists.
if [ "${VERCEL_ENV:-}" = "production" ] || { [ -n "$REF" ] && [ "$REF" = "$PROD_BRANCH" ]; }; then
  log "production deployment (env='${VERCEL_ENV:-unset}' ref='${REF:-unset}') -> judged against what is live, never a previous attempt"
  production_verdict
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
  # from the repository URL (repo_fetch_url above). Every failure still exits 1 (BUILD), with
  # each failed transport named. Git stderr is never logged because it can normalize and repeat
  # credentials or query tokens from the fetch URL.
  if [ -z "$BASE" ]; then
    fetched=
    if git fetch --no-tags --depth=200 origin "$PROD_BRANCH" >/dev/null 2>&1; then
      fetched=origin
    else
      FETCH_URL=$(repo_fetch_url)
      if [ -z "$FETCH_URL" ]; then
        log "cannot fetch $PROD_BRANCH (no origin, no repo env to build a URL) -> BUILD (fail-open). origin fetch failed"
        exit 1
      fi
      if git fetch --no-tags --depth=200 "$FETCH_URL" "$PROD_BRANCH" >/dev/null 2>&1; then
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

verdict_from_changed "$CHANGED"
