#!/bin/bash
# codex-nightly-autofix-ci.sh
# Watcher for GitHub Actions failures on nuzantara repo. For each new failure,
# spawns Codex CLI locally (OAuth, NO API key) to attempt minimal fix and pushes
# a PR branch. State file tracks already-handled failures to avoid loops.
#
# Idempotent. Cap: 3 fix attempts per 24h window, 1 attempt per failed run.
#
# Cron schedule: every 30 minutes during work hours WITA (06-22).
# Outside work hours: every 60 minutes (handled by LaunchAgent StartCalendarInterval).
#
# Hard rules respected:
# - No ANTHROPIC_API_KEY anywhere
# - No OPENAI_API_KEY (Codex uses OAuth Pro $200)
# - No --dangerously-bypass-approvals-and-sandbox
# - No --no-verify, no force-push
# - PATH explicit (cron has minimal PATH)

set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin

# ───────────────────────────────────────────────────────────────
# Config
# ───────────────────────────────────────────────────────────────
REPO_ROOT="${CODEX_AUTOFIX_REPO_ROOT:-${HOME}/nuzantara/.worktrees/codex-autofix-ci-runtime}"
REPO_SLUG="${CODEX_AUTOFIX_REPO_SLUG:-Balizero1987/Teman2}"
STATE_DIR="${CODEX_AUTOFIX_STATE_DIR:-${HOME}/.agent/decisions/state}"
STATE_FILE="${STATE_DIR}/codex_autofix_ci.state"
LOG_DIR="${CODEX_AUTOFIX_LOG_DIR:-${HOME}/logs/codex-autofix-ci}"
TELEGRAM_NOTIFY="${HOME}/.claude/scripts/hotfix-notify.sh"
CODEX_AUTOMATION_LIB="${CODEX_AUTOMATION_LIB:-${HOME}/scripts/codex/automation-lib.sh}"
GH_BIN="${CODEX_AUTOFIX_GH_BIN:-gh}"
# Comma-separated exact GitHub logins.  Do not use shell-glob matching here:
# actor data is remote input and a wildcard is not a principal.
TRUSTED_ACTORS="${CODEX_AUTOFIX_TRUSTED_ACTORS:-Balizero1987}"
CANONICAL_REPO="${CODEX_AUTOFIX_CANONICAL_REPO:-}"

mkdir -p "$STATE_DIR" "$LOG_DIR"
# shellcheck source=/Users/nuzantara/scripts/codex/automation-lib.sh
[ -f "$CODEX_AUTOMATION_LIB" ] && source "$CODEX_AUTOMATION_LIB"

# Seat rotation (2026-08-20): alternate between the ChatGPT Pro subscriptions
# instead of pinning to whichever CODEX_HOME the codex CLI defaults to.
# scripts/lib/codex_seat.sh is the single source for the seat list and the
# rotation counter — do not re-derive either here (W106b: a duplicated list
# is the very defect that file exists to kill). Judged by REPLY at call time,
# never by this script's own exit code (W104). Exported here so the later
# `env -u ... codex ...` invocation inherits it — `env -u` only strips the
# names it is told to strip.
CODEX_SEAT_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" 2>/dev/null && pwd)/codex_seat.sh"
if [ -f "$CODEX_SEAT_LIB" ]; then
    # shellcheck disable=SC1090
    . "$CODEX_SEAT_LIB"
    CODEX_SEAT="$(codex_seat_pick 2>/dev/null || true)"
    if [ -n "$CODEX_SEAT" ]; then
        export CODEX_HOME="$CODEX_SEAT"
        echo "[$(basename "$0")] codex seat: $CODEX_SEAT" >&2
    fi
fi

# Cap: max 3 autofix attempts per rolling 24h
DAILY_CAP=3
RECENT_WINDOW_HOURS=24

# Per-run timeout for Codex
CODEX_TIMEOUT=1800  # 30 min

# Cooldown between attempts on same workflow_run.id
COOLDOWN_PER_RUN=86400  # 24h

# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
notify() {
    if command -v codex_auto_notify >/dev/null 2>&1; then
        codex_auto_notify "$1"
    elif [ -x "$TELEGRAM_NOTIFY" ]; then
        "$TELEGRAM_NOTIFY" "$@" || true
    fi
}
is_uint() {
    case "${1:-}" in
        ""|*[!0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}
is_commit_sha() {
    local candidate="${1:-}"

    [ "${#candidate}" -eq 40 ] || return 1
    case "$candidate" in
        *[!0123456789abcdefABCDEF]*) return 1 ;;
        *) return 0 ;;
    esac
}
is_trusted_actor() {
    local candidate="${1:-}"

    [ -n "$candidate" ] || return 1
    case ",$TRUSTED_ACTORS," in
        *,"$candidate",*) return 0 ;;
        *) return 1 ;;
    esac
}
is_autofix_branch_namespace() {
    case "${1:-}" in
        agent/*|feature/*|feat/*|fix/*|chore/*|docs/*|refactor/*|test/*|perf/*|build/*|ci/*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}
codex_state() {
    if command -v codex_auto_write_state >/dev/null 2>&1; then
        codex_auto_write_state "com.nuzantara.codex-autofix-ci" "$@" || true
    fi
}

# Idempotence guard — mkdir-based mutex (macOS-compatible, no flock dependency)
LOCK_DIR="${STATE_DIR}/codex_autofix_ci.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if is_uint "$LOCK_PID" && ! kill -0 "$LOCK_PID" 2>/dev/null; then
        log "Stale lock detected (pid $LOCK_PID is not running). Reclaiming."
        rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR"
    elif [ -d "$LOCK_DIR" ] && [ "$(find "$LOCK_DIR" -maxdepth 0 -mmin +240 2>/dev/null)" ]; then
        log "Stale lock detected (>4h old). Reclaiming."
        rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR"
    else
        log "Another instance running, exiting"
        codex_state skipped locked "Another instance running" "" "$REPO_ROOT"
        exit 0
    fi
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# ───────────────────────────────────────────────────────────────
# Daily cap check
# ───────────────────────────────────────────────────────────────
TODAY=$(date '+%Y-%m-%d')
COUNT_FILE="${STATE_DIR}/codex_autofix_ci_count_${TODAY}"
ATTEMPTS_TODAY=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)

if [ "$ATTEMPTS_TODAY" -ge "$DAILY_CAP" ]; then
    log "Daily cap $DAILY_CAP reached ($ATTEMPTS_TODAY attempts today). Skipping."
    codex_state skipped daily_cap "Daily cap reached ($ATTEMPTS_TODAY/$DAILY_CAP)" "" "$REPO_ROOT"
    exit 0
fi

PRIMARY_REPO_ROOT="${CODEX_AUTOFIX_PRIMARY_REPO_ROOT:-${HOME}/nuzantara}"
if command -v codex_auto_ensure_runtime_worktree >/dev/null 2>&1; then
    codex_auto_ensure_runtime_worktree "$PRIMARY_REPO_ROOT" "$REPO_ROOT" "origin/main" || {
        log "Runtime worktree unavailable: $REPO_ROOT"
        codex_state blocked missing_worktree "Runtime worktree unavailable" "" "$REPO_ROOT"
        notify "🔴 Codex autofix-ci: runtime worktree unavailable at $REPO_ROOT"
        exit 1
    }
fi

# ───────────────────────────────────────────────────────────────
# Fetch recent failures
# ───────────────────────────────────────────────────────────────
log "Polling GitHub Actions failures on $REPO_SLUG..."

cd "$REPO_ROOT"

if [ "${CODEX_AUTOFIX_DRY_RUN:-0}" != "1" ] &&
    [ -n "$(git status --porcelain 2>/dev/null)" ] &&
    [ "${CODEX_AUTOFIX_ALLOW_STASH:-0}" != "1" ]; then
    log "Working tree dirty — skipping full run before CI failure scan. Set CODEX_AUTOFIX_ALLOW_STASH=1 to override."
    codex_state skipped dirty_worktree "Runtime worktree dirty before CI failure scan" "" "$REPO_ROOT"
    notify "⚠️ Codex autofix-ci: skipped because working tree is dirty"
    exit 0
fi

# Last 24h failures, json: id, name, conclusion, headBranch, headSha, displayTitle,
# createdAt, event.  Provenance fields are retrieved per-run below: `gh run list`
# does not expose the full actor/fork record we must verify before unattended work.
if [ -n "${CODEX_AUTOFIX_FAILED_RUNS_JSON:-}" ]; then
    FAILED_RUNS="$CODEX_AUTOFIX_FAILED_RUNS_JSON"
elif [ -n "${CODEX_AUTOFIX_FAILED_RUNS_JSON_FILE:-}" ]; then
    FAILED_RUNS=$(cat "$CODEX_AUTOFIX_FAILED_RUNS_JSON_FILE")
else
    FAILED_RUNS=$("$GH_BIN" run list \
        --repo "$REPO_SLUG" \
        --status failure \
        --limit 20 \
        --json databaseId,name,headBranch,headSha,displayTitle,createdAt,event \
        2>/dev/null || echo "[]")
fi

if [ "$FAILED_RUNS" = "[]" ] || [ -z "$FAILED_RUNS" ]; then
    log "No failed runs found"
    codex_state idle no_failed_runs "No failed GitHub Actions runs found" "" "$REPO_ROOT"
    exit 0
fi

if [ -z "$CANONICAL_REPO" ]; then
    CANONICAL_REPO=$("$GH_BIN" api "repos/$REPO_SLUG" --jq '.full_name' 2>/dev/null || true)
fi
if [ -z "$CANONICAL_REPO" ] || [ "$CANONICAL_REPO" = "null" ]; then
    log "Cannot establish canonical repository for autofix provenance. Failing closed."
    codex_state blocked provenance_repository_unavailable "Canonical repository unavailable" "" "$REPO_ROOT"
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# Filter: not yet handled, within cooldown, on a branch (not main)
# ───────────────────────────────────────────────────────────────
NOW_EPOCH=$(date +%s)

# Pick first eligible failure. Use JSON lines, not TSV: some jq builds emit
# escaped "\t" through @tsv here, which corrupts run_id/log paths.
ELIGIBLE_RUN_JSON=""
while IFS= read -r run_json; do
    run_id=$(printf '%s\n' "$run_json" | jq -r '.run_id')
    if ! is_uint "$run_id"; then
        log "Skipping malformed run id: $run_id"
        continue
    fi

    # Skip if already attempted within cooldown
    if grep -qE "^${run_id}[[:space:]]" "$STATE_FILE" 2>/dev/null; then
        last_attempt=$(grep -E "^${run_id}[[:space:]]" "$STATE_FILE" | tail -1 | awk '{print $2}')
        if is_uint "$last_attempt" && [ $((NOW_EPOCH - last_attempt)) -lt "$COOLDOWN_PER_RUN" ]; then
            continue
        fi
    fi

    branch=$(printf '%s\n' "$run_json" | jq -r '.branch')
    sha=$(printf '%s\n' "$run_json" | jq -r '.sha')
    event=$(printf '%s\n' "$run_json" | jq -r '.event')
    actor=$(printf '%s\n' "$run_json" | jq -r '.actor_login')
    triggering_actor=$(printf '%s\n' "$run_json" | jq -r '.triggering_actor_login')
    head_repository=$(printf '%s\n' "$run_json" | jq -r '.head_repository')

    # The REST action-run object is the authority for provenance.  Hermetic
    # tests may inject the same complete fields, but real `gh run list` output
    # lacks actor/fork data and must be supplemented rather than trusted.
    if [ -z "$actor" ] || [ -z "$triggering_actor" ] || [ -z "$head_repository" ]; then
        if ! run_metadata=$("$GH_BIN" api "repos/$REPO_SLUG/actions/runs/$run_id" 2>/dev/null); then
            log "Skipping run $run_id: provenance lookup failed"
            continue
        fi
        actor=$(printf '%s\n' "$run_metadata" | jq -r '.actor.login // empty')
        triggering_actor=$(printf '%s\n' "$run_metadata" | jq -r '.triggering_actor.login // empty')
        head_repository=$(printf '%s\n' "$run_metadata" | jq -r '.head_repository.full_name // empty')
        event=$(printf '%s\n' "$run_metadata" | jq -r '.event // empty')
        metadata_branch=$(printf '%s\n' "$run_metadata" | jq -r '.head_branch // empty')
        metadata_sha=$(printf '%s\n' "$run_metadata" | jq -r '.head_sha // empty')
        if [ "$metadata_branch" != "$branch" ] || [ "$metadata_sha" != "$sha" ]; then
            log "Skipping run $run_id: provenance branch or SHA disagrees with listing"
            continue
        fi
    fi

    if ! is_autofix_branch_namespace "$branch"; then
        log "Skipping run $run_id: branch namespace is not sanctioned"
        continue
    fi
    if ! is_commit_sha "$sha"; then
        log "Skipping run $run_id: malformed failed SHA"
        continue
    fi
    case "$event" in
        push|pull_request) ;;
        *)
            log "Skipping run $run_id: event $event is not sanctioned"
            continue
            ;;
    esac
    if [ "$head_repository" != "$CANONICAL_REPO" ]; then
        log "Skipping run $run_id: head repository is not canonical"
        continue
    fi
    if ! is_trusted_actor "$actor" || ! is_trusted_actor "$triggering_actor"; then
        log "Skipping run $run_id: actor provenance is not trusted"
        continue
    fi

    ELIGIBLE_RUN_JSON="$run_json"
    break
# RECURSION BRAKE (2026-07-06): never select a failure on one of our OWN
# codex/auto-fix-ci-* branches — each failed fix PR became the next cycle's
# target (#2063→#2064→#2065, hourly daisy-chain capped only by DAILY_CAP).
# Also skip dependabot/* branches: dependabot force-pushes/recreates them, so
# a fix PR based on one has a mutable base and gets orphaned (today's chain
# root was a 98-package bump). Revert the dependabot line if we ever WANT
# codex attempting dependabot repairs — the recursion line must stay.
done < <(printf '%s\n' "$FAILED_RUNS" | jq -c --arg now "$NOW_EPOCH" --arg cooldown "$COOLDOWN_PER_RUN" --arg statefile "$STATE_FILE" '
    .[] | select(
        .headBranch != "main" and
        .headBranch != "master" and
        (.headBranch | startswith("codex/auto-fix-ci-") | not) and
        (.headBranch | startswith("dependabot/") | not) and
        .name != "Codex auto-fix on CI failure"
    ) | {
        run_id: (.databaseId | tostring),
        name: (.name // ""),
        branch: (.headBranch // ""),
        sha: (.headSha // ""),
        title: (.displayTitle // ""),
        created_at: (.createdAt // ""),
        event: (.event // ""),
        actor_login: (.actor.login // .actorLogin // ""),
        triggering_actor_login: (.triggering_actor.login // .triggeringActorLogin // ""),
        head_repository: (.head_repository.full_name // .headRepositoryFullName // "")
    }
' | head -10)

if [ -z "$ELIGIBLE_RUN_JSON" ]; then
    log "No eligible failures (all already handled or in cooldown)"
    codex_state idle no_eligible_failures "No eligible failures outside cooldown" "" "$REPO_ROOT"
    exit 0
fi

RUN_ID=$(printf '%s\n' "$ELIGIBLE_RUN_JSON" | jq -r '.run_id')
WORKFLOW_NAME=$(printf '%s\n' "$ELIGIBLE_RUN_JSON" | jq -r '.name')
BRANCH=$(printf '%s\n' "$ELIGIBLE_RUN_JSON" | jq -r '.branch')
SHA=$(printf '%s\n' "$ELIGIBLE_RUN_JSON" | jq -r '.sha')
TITLE=$(printf '%s\n' "$ELIGIBLE_RUN_JSON" | jq -r '.title')

if ! is_uint "$RUN_ID"; then
    log "Invalid GitHub Actions run id after parsing: $RUN_ID"
    exit 1
fi

log "Eligible failure: run $RUN_ID workflow=$WORKFLOW_NAME branch=$BRANCH sha=${SHA:0:7}"
FIX_BRANCH="codex/auto-fix-ci-${RUN_ID}"

if [ "${CODEX_AUTOFIX_DRY_RUN:-0}" = "1" ]; then
    log "[dry-run] selected run_id=$RUN_ID workflow=$WORKFLOW_NAME branch=$BRANCH title=$TITLE"
    codex_state idle dry_run "Selected run $RUN_ID on $BRANCH" "" "$REPO_ROOT"
    exit 0
fi

# Freeze a complete pre-push hook bundle from a reviewed main commit BEFORE
# checking out the failed branch.  The branch under repair is untrusted input
# for this unattended process; it must not choose the hook or the three gate
# helpers that decide whether its outer push is permitted.
if ! git -C "$PRIMARY_REPO_ROOT" fetch origin main --quiet; then
    log "Cannot refresh trusted main for the pre-push bundle. Failing closed."
    codex_state blocked trusted_hook_fetch_failed "Could not refresh trusted main" "$FIX_BRANCH" "$REPO_ROOT"
    exit 1
fi
if ! TRUSTED_PREPUSH_HOOKS=$(codex_auto_prepare_trusted_prepush \
    "$PRIMARY_REPO_ROOT" "$STATE_DIR" "origin/main"); then
    log "Cannot prepare a verified trusted pre-push bundle. Failing closed."
    codex_state blocked trusted_hook_prepare_failed "Could not prepare trusted pre-push bundle" "$FIX_BRANCH" "$REPO_ROOT"
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# Get failure context: workflow logs for the run
# ───────────────────────────────────────────────────────────────
RUN_LOG_FILE="${LOG_DIR}/run-${RUN_ID}.log"
log "Fetching workflow logs to $RUN_LOG_FILE"

"$GH_BIN" run view "$RUN_ID" --repo "$REPO_SLUG" --log-failed > "$RUN_LOG_FILE" 2>&1 || {
    log "Failed to fetch logs for run $RUN_ID"
    codex_state blocked log_fetch_failed "Failed to fetch logs for run $RUN_ID; cap not consumed" "" "$REPO_ROOT"
    notify "🔴 Codex autofix: failed to fetch logs for run $RUN_ID"
    exit 1
}

# Truncate logs to last 8000 chars (focus on actual failure)
TAIL_LOGS=$(tail -c 8000 "$RUN_LOG_FILE")

# ───────────────────────────────────────────────────────────────
# Checkout failing branch + reset to that SHA
# ───────────────────────────────────────────────────────────────
log "Checkout $BRANCH @ $SHA"

# Stash dirty work before destructive checkout (cf. cicatrix scar 2026-04-29 untracked-files-loss)
STASH_TAG="codex-autofix-${RUN_ID}"
HAD_STASH=0
if [ -n "$(git status --porcelain)" ]; then
    if [ "${CODEX_AUTOFIX_ALLOW_STASH:-0}" != "1" ]; then
    log "Working tree dirty — skipping before checkout. Set CODEX_AUTOFIX_ALLOW_STASH=1 to permit auto-stash."
        codex_state skipped dirty_worktree "Runtime worktree dirty before checkout" "$FIX_BRANCH" "$REPO_ROOT"
        notify "⚠️ Codex autofix-ci: skipped because working tree became dirty before checkout"
        exit 0
    fi
    log "Working tree dirty — stashing as $STASH_TAG because CODEX_AUTOFIX_ALLOW_STASH=1"
    git stash push -u -m "$STASH_TAG" 2>&1 | head -3 || true
    HAD_STASH=1
fi

restore_stash() {
    if [ "$HAD_STASH" -eq 1 ]; then
        # Switch away from the fix branch before popping.
        git checkout --detach "${SHA:-HEAD}" 2>/dev/null || true
        STASH_REF=$(git stash list 2>/dev/null | grep "$STASH_TAG" | head -1 | cut -d: -f1 || echo "")
        if [ -n "$STASH_REF" ]; then
            git stash pop "$STASH_REF" 2>&1 | head -5 || log "stash pop $STASH_REF failed (manual: git stash list / git stash apply)"
        fi
        HAD_STASH=0  # idempotent: don't pop twice on EXIT trap
    fi
}

# Auto-restore stash on any exit (success, failure, signal)
# Combined with mkdir-mutex trap above
trap 'restore_stash; rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

if ! FETCH_OUTPUT=$(git fetch origin "$BRANCH" 2>&1); then
    printf '%s\n' "$FETCH_OUTPUT" | head -5
    log "Cannot fetch $BRANCH (likely deleted). Skipping without consuming daily cap."
    codex_state skipped branch_not_fetchable "Branch $BRANCH not fetchable; cap not consumed" "$FIX_BRANCH" "$REPO_ROOT"
    notify "⚠️ Codex autofix: branch $BRANCH not fetchable"
    restore_stash
    exit 0
fi
printf '%s\n' "$FETCH_OUTPUT" | head -5

FETCHED_SHA=$(git rev-parse FETCH_HEAD 2>/dev/null || true)
if [ "$FETCHED_SHA" != "$SHA" ]; then
    log "Fetched branch no longer matches failed SHA; skipping without checkout."
    codex_state skipped branch_sha_changed "Fetched $BRANCH at $FETCHED_SHA, expected $SHA" "$FIX_BRANCH" "$REPO_ROOT"
    notify "⚠️ Codex autofix: branch $BRANCH moved since failed run $RUN_ID"
    restore_stash
    exit 0
fi

git checkout --detach FETCH_HEAD 2>&1 | head -3 || {
    log "Cannot checkout $BRANCH (likely deleted). Skipping."
    codex_state skipped branch_not_checkoutable "Branch $BRANCH not checkoutable; cap not consumed" "$FIX_BRANCH" "$REPO_ROOT"
    notify "⚠️ Codex autofix: branch $BRANCH not checkoutable"
    restore_stash
    exit 0
}
if ! RESET_OUTPUT=$(git reset --hard "$SHA" 2>&1); then
    printf '%s\n' "$RESET_OUTPUT" | head -5
    log "Cannot reset to $SHA. Skipping without consuming daily cap."
    codex_state skipped sha_not_resettable "SHA $SHA not resettable; cap not consumed" "$FIX_BRANCH" "$REPO_ROOT"
    notify "⚠️ Codex autofix: SHA ${SHA:0:7} not resettable"
    restore_stash
    exit 0
fi
printf '%s\n' "$RESET_OUTPUT" | head -3

# Mark this run as attempted only after a real fix attempt can start. Log-fetch
# failures and missing branches are blocked/skipped observations, not
# daily-cap-consuming fix attempts.
echo "${RUN_ID} ${NOW_EPOCH} ${BRANCH} ${WORKFLOW_NAME}" >> "$STATE_FILE"
echo $((ATTEMPTS_TODAY + 1)) > "$COUNT_FILE"
codex_state action attempt_started "Fetched logs and checked out run $RUN_ID; launching Codex" "$FIX_BRANCH" "$REPO_ROOT"

# ───────────────────────────────────────────────────────────────
# Run Codex autofix
# ───────────────────────────────────────────────────────────────
log "Creating fix branch $FIX_BRANCH"
git checkout -b "$FIX_BRANCH" 2>&1 | head -3

CODEX_PROMPT=$(cat <<EOF
You are auto-fixing a GitHub Actions failure in the Nuzantara monorepo.

Workflow: ${WORKFLOW_NAME}
Branch: ${BRANCH}
Failed SHA: ${SHA}
Run ID: ${RUN_ID}

Failure logs (last 8000 chars):
\`\`\`
${TAIL_LOGS}
\`\`\`

Your task:
1. Read the relevant repository files (especially AGENTS.md root + path-specific in apps/backend-rag/, scripts/, apps/backend-rag/backend/llm/)
2. Identify the MINIMAL change needed to make the failed workflow pass
3. Implement ONLY that change. Do not refactor unrelated code.
4. Run the relevant test/lint locally to verify
5. Commit with message: "fix(ci): auto-fix workflow ${WORKFLOW_NAME} run ${RUN_ID}"

HARD RULES:
- NO ANTHROPIC_API_KEY anywhere — use claude_oauth_client.py if Anthropic needed
- NO new OPENAI_API_KEY usage beyond existing embedding model
- NO --no-verify, NO --force-push, NO bypass of approvals
- Edits LIMITED to files directly implicated in the failure
- If the fix requires more than 50 LOC across 3+ files, STOP and write FAIL_REASON to /tmp/codex-autofix-${RUN_ID}.txt instead

If you cannot fix the failure cleanly, write the reason to /tmp/codex-autofix-${RUN_ID}.txt and exit without committing.
EOF
)

log "Launching Codex (timeout ${CODEX_TIMEOUT}s, isolated workspace-write sandbox)..."

if timeout "$CODEX_TIMEOUT" env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u OPENAI_ORG_ID -u OPENAI_PROJECT \
    codex --ignore-user-config --sandbox workspace-write --ephemeral --cd "$REPO_ROOT" \
    exec "$CODEX_PROMPT" > "${LOG_DIR}/codex-output-${RUN_ID}.log" 2>&1; then
    log "Codex completed"
else
    rc=$?
    log "Codex failed/timeout (exit $rc)"
    codex_state blocked codex_failed "Codex exit $rc on run $RUN_ID" "$FIX_BRANCH" "$REPO_ROOT"
    notify "🔴 Codex autofix: timed out or failed on run $RUN_ID workflow $WORKFLOW_NAME"
    git checkout --detach "$SHA" 2>&1 | head -2 || true
    git branch -D "$FIX_BRANCH" 2>&1 | head -2 || true
    exit 0
fi

# ───────────────────────────────────────────────────────────────
# Check if Codex committed something
# ───────────────────────────────────────────────────────────────
COMMITS_AHEAD=$(git rev-list --count "${SHA}..${FIX_BRANCH}" 2>/dev/null || echo 0)

if [ "$COMMITS_AHEAD" -eq 0 ]; then
    log "Codex made no commit. Likely could not fix cleanly."
    codex_state skipped no_commit "Codex made no commit for run $RUN_ID" "$FIX_BRANCH" "$REPO_ROOT"
    if [ -f "/tmp/codex-autofix-${RUN_ID}.txt" ]; then
        REASON=$(cat "/tmp/codex-autofix-${RUN_ID}.txt" | head -200)
        notify "⚠️ Codex autofix: declined run $RUN_ID workflow $WORKFLOW_NAME — $REASON"
    else
        notify "⚠️ Codex autofix: no commit on run $RUN_ID workflow $WORKFLOW_NAME (no FAIL_REASON either)"
    fi
    git checkout --detach "$SHA" 2>&1 | head -2 || true
    git branch -D "$FIX_BRANCH" 2>&1 | head -2 || true
    exit 0
fi

# ───────────────────────────────────────────────────────────────
# Push fix branch + open PR
# ───────────────────────────────────────────────────────────────
log "Codex committed $COMMITS_AHEAD changes. Pushing $FIX_BRANCH with pinned trusted hooks..."

if ! codex_auto_verify_trusted_prepush "$PRIMARY_REPO_ROOT" "$TRUSTED_PREPUSH_HOOKS"; then
    log "Trusted pre-push bundle changed or cannot be verified. Refusing push."
    codex_state blocked trusted_hook_verify_failed "Trusted pre-push bundle cannot be verified" "$FIX_BRANCH" "$REPO_ROOT"
    exit 1
fi

if ! git -c core.hooksPath="$TRUSTED_PREPUSH_HOOKS" push -u origin "$FIX_BRANCH" 2>&1 | head -10; then
    log "Push failed"
    codex_state blocked push_failed "Push failed for $FIX_BRANCH" "$FIX_BRANCH" "$REPO_ROOT"
    notify "🔴 Codex autofix: push failed for $FIX_BRANCH"
    exit 1
fi

log "Opening PR..."
PR_BODY=$(cat <<EOF
## Auto-fix from Codex CLI (OAuth Pro)

**Failed workflow:** \`${WORKFLOW_NAME}\` on run [#${RUN_ID}](https://github.com/${REPO_SLUG}/actions/runs/${RUN_ID})
**Failed SHA:** \`${SHA}\`
**Failed branch:** \`${BRANCH}\`

### What changed
Codex generated this PR to attempt a minimal fix for the CI failure. Review carefully before merging.

### Tri-LLM panel review
This PR is eligible for tri-LLM panel review (Codex + Opus 4.7 + DeepSeek). Run:
\`\`\`bash
python3 ~/nuzantara/scripts/codex_tri_llm_review.py --pr <this-pr-number>
\`\`\`

### Verification
- [ ] CI green
- [ ] Tri-LLM panel ≥2/3 green
- [ ] Manual review

🤖 Generated by [Codex CLI](https://openai.com/codex) — autonomous autofix
EOF
)

if PR_URL=$("$GH_BIN" pr create \
    --repo "$REPO_SLUG" \
    --base "$BRANCH" \
    --head "$FIX_BRANCH" \
    --title "fix(ci): auto-fix workflow ${WORKFLOW_NAME} run ${RUN_ID}" \
    --body "$PR_BODY" 2>&1 | tail -5 | grep -E "^https"); then
    log "PR opened: $PR_URL"
    codex_state action pr_opened "PR opened: $PR_URL" "$FIX_BRANCH" "$REPO_ROOT"
    notify "✅ Codex autofix: PR opened $PR_URL for workflow $WORKFLOW_NAME"
else
    log "PR creation failed (maybe already exists?)"
    codex_state blocked pr_failed "PR creation failed for $FIX_BRANCH" "$FIX_BRANCH" "$REPO_ROOT"
    notify "⚠️ Codex autofix: PR creation failed for run $RUN_ID (check if duplicate)"
fi

# Return to a neutral detached base + restore stashed work
git fetch origin main 2>&1 | head -3 || true
git checkout --detach origin/main 2>&1 | head -2 || true
restore_stash

log "Done. Daily counter: $((ATTEMPTS_TODAY + 1))/$DAILY_CAP"
