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
REPO_ROOT="${CODEX_AUTOFIX_REPO_ROOT:-${HOME}/Desktop/nuzantara/.worktrees/codex-autofix-ci-runtime}"
REPO_SLUG="${CODEX_AUTOFIX_REPO_SLUG:-Balizero1987/Teman2}"
STATE_DIR="${CODEX_AUTOFIX_STATE_DIR:-${HOME}/.agent/decisions/state}"
STATE_FILE="${STATE_DIR}/codex_autofix_ci.state"
LOG_DIR="${CODEX_AUTOFIX_LOG_DIR:-${HOME}/logs/codex-autofix-ci}"
TELEGRAM_NOTIFY="${HOME}/.claude/scripts/hotfix-notify.sh"
CODEX_AUTOMATION_LIB="${CODEX_AUTOMATION_LIB:-${HOME}/scripts/codex-automation-lib.sh}"

mkdir -p "$STATE_DIR" "$LOG_DIR"
# shellcheck source=/Users/nuzantara/scripts/codex-automation-lib.sh
[ -f "$CODEX_AUTOMATION_LIB" ] && source "$CODEX_AUTOMATION_LIB"

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
    if [ -x "$TELEGRAM_NOTIFY" ]; then
        "$TELEGRAM_NOTIFY" "$@" || true
    fi
}
is_uint() {
    case "${1:-}" in
        ""|*[!0-9]*) return 1 ;;
        *) return 0 ;;
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

# Last 24h failures, json: id, name, conclusion, headBranch, headSha, displayTitle, createdAt
if [ -n "${CODEX_AUTOFIX_FAILED_RUNS_JSON:-}" ]; then
    FAILED_RUNS="$CODEX_AUTOFIX_FAILED_RUNS_JSON"
elif [ -n "${CODEX_AUTOFIX_FAILED_RUNS_JSON_FILE:-}" ]; then
    FAILED_RUNS=$(cat "$CODEX_AUTOFIX_FAILED_RUNS_JSON_FILE")
else
    FAILED_RUNS=$(gh run list \
        --repo "$REPO_SLUG" \
        --status failure \
        --limit 20 \
        --json databaseId,name,headBranch,headSha,displayTitle,createdAt \
        2>/dev/null || echo "[]")
fi

if [ "$FAILED_RUNS" = "[]" ] || [ -z "$FAILED_RUNS" ]; then
    log "No failed runs found"
    codex_state idle no_failed_runs "No failed GitHub Actions runs found" "" "$REPO_ROOT"
    exit 0
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

    ELIGIBLE_RUN_JSON="$run_json"
    break
done < <(printf '%s\n' "$FAILED_RUNS" | jq -c --arg now "$NOW_EPOCH" --arg cooldown "$COOLDOWN_PER_RUN" --arg statefile "$STATE_FILE" '
    .[] | select(
        .headBranch != "main" and
        .headBranch != "master" and
        .name != "Codex auto-fix on CI failure"
    ) | {
        run_id: (.databaseId | tostring),
        name: (.name // ""),
        branch: (.headBranch // ""),
        sha: (.headSha // ""),
        title: (.displayTitle // ""),
        created_at: (.createdAt // "")
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

# ───────────────────────────────────────────────────────────────
# Get failure context: workflow logs for the run
# ───────────────────────────────────────────────────────────────
RUN_LOG_FILE="${LOG_DIR}/run-${RUN_ID}.log"
log "Fetching workflow logs to $RUN_LOG_FILE"

gh run view "$RUN_ID" --repo "$REPO_SLUG" --log-failed > "$RUN_LOG_FILE" 2>&1 || {
    log "Failed to fetch logs for run $RUN_ID"
    codex_state blocked log_fetch_failed "Failed to fetch logs for run $RUN_ID; cap not consumed" "" "$REPO_ROOT"
    notify "🔴 Codex autofix: failed to fetch logs for run $RUN_ID"
    exit 1
}

# Mark this run as attempted only after a real fix attempt can start. Log-fetch
# failures are blocked observations, not daily-cap-consuming fix attempts.
echo "${RUN_ID} ${NOW_EPOCH} ${BRANCH} ${WORKFLOW_NAME}" >> "$STATE_FILE"
echo $((ATTEMPTS_TODAY + 1)) > "$COUNT_FILE"
codex_state action attempt_started "Fetched logs for run $RUN_ID; launching Codex" "$FIX_BRANCH" "$REPO_ROOT"

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
        # Switch back to main before popping (popping on a feature branch contaminates it)
        git checkout main 2>/dev/null || true
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

git fetch origin "$BRANCH" 2>&1 | head -5
git checkout "$BRANCH" 2>&1 | head -3 || {
    log "Cannot checkout $BRANCH (likely deleted). Skipping."
    notify "⚠️ Codex autofix: branch $BRANCH not checkoutable"
    git checkout main 2>&1 | head -2 || true
    restore_stash
    exit 0
}
git reset --hard "$SHA" 2>&1 | head -3

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

log "Launching Codex (timeout ${CODEX_TIMEOUT}s, profile=xhigh)..."

if timeout "$CODEX_TIMEOUT" codex --profile xhigh exec "$CODEX_PROMPT" > "${LOG_DIR}/codex-output-${RUN_ID}.log" 2>&1; then
    log "Codex completed"
else
    rc=$?
    log "Codex failed/timeout (exit $rc)"
    codex_state blocked codex_failed "Codex exit $rc on run $RUN_ID" "$FIX_BRANCH" "$REPO_ROOT"
    notify "🔴 Codex autofix: timed out or failed on run $RUN_ID workflow $WORKFLOW_NAME"
    git checkout "$BRANCH" 2>&1 | head -2 || true
    git branch -D "$FIX_BRANCH" 2>&1 | head -2 || true
    exit 0
fi

# ───────────────────────────────────────────────────────────────
# Check if Codex committed something
# ───────────────────────────────────────────────────────────────
COMMITS_AHEAD=$(git rev-list --count "${BRANCH}..${FIX_BRANCH}" 2>/dev/null || echo 0)

if [ "$COMMITS_AHEAD" -eq 0 ]; then
    log "Codex made no commit. Likely could not fix cleanly."
    codex_state skipped no_commit "Codex made no commit for run $RUN_ID" "$FIX_BRANCH" "$REPO_ROOT"
    if [ -f "/tmp/codex-autofix-${RUN_ID}.txt" ]; then
        REASON=$(cat "/tmp/codex-autofix-${RUN_ID}.txt" | head -200)
        notify "⚠️ Codex autofix: declined run $RUN_ID workflow $WORKFLOW_NAME — $REASON"
    else
        notify "⚠️ Codex autofix: no commit on run $RUN_ID workflow $WORKFLOW_NAME (no FAIL_REASON either)"
    fi
    git checkout "$BRANCH" 2>&1 | head -2 || true
    git branch -D "$FIX_BRANCH" 2>&1 | head -2 || true
    exit 0
fi

# ───────────────────────────────────────────────────────────────
# Push fix branch + open PR
# ───────────────────────────────────────────────────────────────
log "Codex committed $COMMITS_AHEAD changes. Pushing $FIX_BRANCH..."

if ! git push -u origin "$FIX_BRANCH" 2>&1 | head -10; then
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
python3 ~/Desktop/nuzantara/scripts/codex_tri_llm_review.py --pr <this-pr-number>
\`\`\`

### Verification
- [ ] CI green
- [ ] Tri-LLM panel ≥2/3 green
- [ ] Manual review

🤖 Generated by [Codex CLI](https://openai.com/codex) — autonomous autofix
EOF
)

if PR_URL=$(gh pr create \
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

# Return to main + restore stashed work
git checkout main 2>&1 | head -2 || true
restore_stash

log "Done. Daily counter: $((ATTEMPTS_TODAY + 1))/$DAILY_CAP"
