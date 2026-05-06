#!/bin/bash
# codex-overnight-runner.sh
# Picks the next task from ~/codex-overnight/queue/ and runs Codex CLI
# in unsupervised mode (gpt-5.5 xhigh) for up to 8h.
#
# Pattern from OpenAI: spec markdown + plan + implementation runbook,
# Codex follows it autonomously, commits to a feature branch, pushes.
#
# Cron schedule: 22:00 WITA daily (one task per night, max).
# Cap: 1 active overnight run at any time (lock).

set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin

REPO_ROOT="${CODEX_OVERNIGHT_REPO_ROOT:-${HOME}/Desktop/nuzantara/.worktrees/codex-overnight-runner-runtime}"
QUEUE_DIR="${CODEX_OVERNIGHT_QUEUE_DIR:-${HOME}/codex-overnight/queue}"
DONE_DIR="${CODEX_OVERNIGHT_DONE_DIR:-${HOME}/codex-overnight/done}"
FAILED_DIR="${CODEX_OVERNIGHT_FAILED_DIR:-${HOME}/codex-overnight/failed}"
LOG_DIR="${CODEX_OVERNIGHT_LOG_DIR:-${HOME}/logs/codex-overnight}"
STATE_DIR="${CODEX_OVERNIGHT_STATE_DIR:-${HOME}/.agent/decisions/state}"
TELEGRAM_NOTIFY="${HOME}/.claude/scripts/hotfix-notify.sh"
CODEX_AUTOMATION_LIB="${CODEX_AUTOMATION_LIB:-${HOME}/scripts/codex-automation-lib.sh}"

mkdir -p "$LOG_DIR" "$STATE_DIR" "$QUEUE_DIR" "$DONE_DIR" "$FAILED_DIR"
# shellcheck source=/Users/nuzantara/scripts/codex-automation-lib.sh
[ -f "$CODEX_AUTOMATION_LIB" ] && source "$CODEX_AUTOMATION_LIB"

OVERNIGHT_TIMEOUT="${CODEX_OVERNIGHT_TIMEOUT:-28800}"  # 8h hard cap
LOCK_FILE="${STATE_DIR}/codex_overnight.lock"

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
        codex_auto_write_state "com.nuzantara.codex-overnight-runner" "$@" || true
    fi
}

# Single-instance lock — there must be ONLY ONE overnight run at a time
# mkdir-based mutex (macOS-compatible). Stale window 10h (overnight cap is 8h + buffer)
LOCK_DIR="${LOCK_FILE%.lock}.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if is_uint "$LOCK_PID" && ! kill -0 "$LOCK_PID" 2>/dev/null; then
        log "Stale lock detected (pid $LOCK_PID is not running). Reclaiming."
        rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR"
    elif [ -d "$LOCK_DIR" ] && [ "$(find "$LOCK_DIR" -maxdepth 0 -mmin +600 2>/dev/null)" ]; then
        log "Stale lock detected (>10h old). Reclaiming."
        rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR"
    else
        log "Another overnight run in progress. Exiting."
        codex_state skipped locked "Another overnight run in progress" "" "$REPO_ROOT"
        exit 0
    fi
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# ─────────────────────────────────────────────
# Pick next task
# ─────────────────────────────────────────────
TASK_FILE=$(find "$QUEUE_DIR" -maxdepth 1 -type f -name "*.md" | sort | head -1)

if [ -z "$TASK_FILE" ]; then
    log "Queue empty. Exiting."
    codex_state idle queue_empty "Queue empty" "" "$REPO_ROOT"
    exit 0
fi

TASK_NAME=$(basename "$TASK_FILE" .md)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_LOG="${LOG_DIR}/${TASK_NAME}-${TIMESTAMP}.log"
BRANCH_NAME="codex-overnight/${TASK_NAME}-${TIMESTAMP}"

log "Picked task: $TASK_FILE"
log "Run log: $RUN_LOG"
log "Branch: $BRANCH_NAME"

if [ "${CODEX_OVERNIGHT_DRY_RUN:-0}" = "1" ]; then
    SPEC_BYTES=$(wc -c < "$TASK_FILE" | tr -d ' ')
    log "[dry-run] would run task=$TASK_NAME bytes=$SPEC_BYTES branch=$BRANCH_NAME"
    codex_state idle dry_run "Would run $TASK_NAME (${SPEC_BYTES} bytes)" "$BRANCH_NAME" "$REPO_ROOT"
    exit 0
fi

# ─────────────────────────────────────────────
# Read task spec
# ─────────────────────────────────────────────
SPEC=$(cat "$TASK_FILE")

# ─────────────────────────────────────────────
# Setup branch
# ─────────────────────────────────────────────
cd "$REPO_ROOT"

# Stash dirty work before checkout
STASH_TAG="codex-overnight-${TIMESTAMP}"
HAD_STASH=0
if [ -n "$(git status --porcelain)" ]; then
    log "Working tree dirty — stashing as $STASH_TAG"
    git stash push -u -m "$STASH_TAG" 2>&1 | tee -a "$RUN_LOG" | head -3 || true
    HAD_STASH=1
fi

restore_stash() {
    if [ "$HAD_STASH" -eq 1 ]; then
        git checkout main 2>/dev/null || true
        STASH_REF=$(git stash list 2>/dev/null | grep "$STASH_TAG" | head -1 | cut -d: -f1 || echo "")
        if [ -n "$STASH_REF" ]; then
            git stash pop "$STASH_REF" 2>&1 | tee -a "$RUN_LOG" | head -5 || log "stash pop $STASH_REF failed"
        fi
        HAD_STASH=0
    fi
}
trap 'restore_stash; rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

git checkout main 2>&1 | tee -a "$RUN_LOG" | head -3
git pull origin main --ff-only 2>&1 | tee -a "$RUN_LOG" | head -3 || log "pull failed (continuing with local HEAD)"

if ! git checkout -b "$BRANCH_NAME" 2>&1 | tee -a "$RUN_LOG" | head -3; then
    log "Branch creation failed"
    codex_state blocked branch_creation_failed "Branch creation failed for $TASK_NAME" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex overnight: branch creation failed for $TASK_NAME"
    mv "$TASK_FILE" "$FAILED_DIR/" || true
    exit 1
fi

# ─────────────────────────────────────────────
# Build runbook prompt
# ─────────────────────────────────────────────
PROMPT=$(cat <<EOF
You are running an unsupervised long-horizon coding task on the Nuzantara monorepo.

This is an OVERNIGHT run with up to 8 hours of compute. You are alone — no human will respond. Plan, implement, verify, repeat. Commit at every milestone. Push frequently to protect against context loss.

TASK SPEC:
${SPEC}

OPERATING RUNBOOK:
1. PLAN — Read the task spec carefully. Read root AGENTS.md + relevant path-specific AGENTS.md (apps/backend-rag/, scripts/, apps/backend-rag/backend/llm/). Outline a milestone-based plan in /tmp/codex-overnight-${TIMESTAMP}-plan.md. Save the plan with a list of milestones, each with acceptance criteria.

2. IMPLEMENT — Work milestone by milestone:
   a. Make minimal changes for that milestone
   b. Run validation (tests, lint, typecheck) for the affected scope
   c. If validation fails, debug and fix BEFORE moving to next milestone
   d. Commit with descriptive message: "feat(<scope>): <milestone>"
   e. Run \`git push -u origin ${BRANCH_NAME}\` after EVERY commit (push-frequently policy from cicatrix scar 2026-04-29)

3. VERIFY — After all milestones:
   a. Run full test suite for the affected app: \`cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q\`
   b. Run import-chain check: \`python -c "from backend.app.dependencies import get_current_user; print('OK')"\`
   c. If everything passes, write final status to /tmp/codex-overnight-${TIMESTAMP}-status.md

4. STATUS — At completion (success OR failure), write to /tmp/codex-overnight-${TIMESTAMP}-status.md:
   - "outcome: success" or "outcome: failed" or "outcome: partial"
   - List of milestones completed
   - List of files changed
   - Any blockers encountered
   - Next-step recommendation

HARD RULES (strict):
- NO ANTHROPIC_API_KEY anywhere — use claude_oauth_client.py if Anthropic needed
- NO new OPENAI_API_KEY usage beyond existing embedding model
- NO --no-verify, NO --force-push, NO bypass of approvals
- NO modifications to backend/prompts/zantara_core.py without explicit task permission
- NO modifications to fly.toml, .env*, secrets/* files
- NO modifications to backend/app/dependencies.py without testing the full import chain
- Push commits frequently — every milestone, every 30 min during work, never accumulate >1h of uncommitted work

CONSTRAINTS:
- Maximum total run time: 8 hours
- All work happens on branch ${BRANCH_NAME}
- If you genuinely cannot complete the task (e.g. missing context, broken environment, ambiguous spec), STOP at a clean checkpoint, write the reason to /tmp/codex-overnight-${TIMESTAMP}-status.md, exit gracefully
EOF
)

# ─────────────────────────────────────────────
# Launch Codex unsupervised
# ─────────────────────────────────────────────
START_TIME=$(date +%s)
log "Launching Codex --profile unsupervised (timeout ${OVERNIGHT_TIMEOUT}s = 8h)..."
codex_state action attempt_started "Starting overnight task $TASK_NAME" "$BRANCH_NAME" "$REPO_ROOT"
notify "🌙 Codex overnight: starting task $TASK_NAME (8h cap, branch=$BRANCH_NAME)"

CODEX_EXIT=0
timeout "$OVERNIGHT_TIMEOUT" codex --profile unsupervised exec "$PROMPT" \
    >> "$RUN_LOG" 2>&1 || CODEX_EXIT=$?

DURATION=$(( $(date +%s) - START_TIME ))
DURATION_HM=$(printf '%dh%02dm' $((DURATION / 3600)) $(((DURATION % 3600) / 60)))

log "Codex exited code=$CODEX_EXIT after $DURATION_HM"

# ─────────────────────────────────────────────
# Collect status
# ─────────────────────────────────────────────
STATUS_FILE="/tmp/codex-overnight-${TIMESTAMP}-status.md"
PLAN_FILE="/tmp/codex-overnight-${TIMESTAMP}-plan.md"

OUTCOME="unknown"
if [ -f "$STATUS_FILE" ]; then
    OUTCOME=$(grep -E "^outcome:" "$STATUS_FILE" | head -1 | awk '{print $2}' || echo "unknown")
fi

COMMITS_AHEAD=$(git rev-list --count "main..${BRANCH_NAME}" 2>/dev/null || echo 0)
log "Outcome: $OUTCOME, commits: $COMMITS_AHEAD"

# Push final state
if [ "$COMMITS_AHEAD" -gt 0 ]; then
    git push -u origin "$BRANCH_NAME" 2>&1 | tee -a "$RUN_LOG" | head -10 || true
fi

# ─────────────────────────────────────────────
# Move task file based on outcome
# ─────────────────────────────────────────────
if [ "$OUTCOME" = "success" ] && [ "$COMMITS_AHEAD" -gt 0 ]; then
    # Open PR for review
    PR_BODY="## Codex overnight run

**Task:** ${TASK_NAME}
**Duration:** ${DURATION_HM}
**Commits:** ${COMMITS_AHEAD}

### Spec
\`\`\`
$(echo "$SPEC" | head -50)
\`\`\`

### Status report
\`\`\`
$(cat "$STATUS_FILE" 2>/dev/null | head -100)
\`\`\`

### Verification
- [ ] CI green
- [ ] Tri-LLM panel ≥2/3 green: \`python3 ~/Desktop/nuzantara/scripts/codex_tri_llm_review.py --branch ${BRANCH_NAME}\`
- [ ] Manual review

🌙 Generated by Codex overnight runner (8h cap, gpt-5.5 xhigh unsupervised)
"
    if PR_URL=$(gh pr create \
        --repo Balizero1987/Teman2 \
        --base main \
        --head "$BRANCH_NAME" \
        --title "feat(overnight): ${TASK_NAME}" \
        --body "$PR_BODY" 2>&1 | tail -5 | grep -E "^https"); then
        log "PR opened: $PR_URL"
        codex_state action pr_opened "Overnight task succeeded: $PR_URL" "$BRANCH_NAME" "$REPO_ROOT"
        notify "✅ Codex overnight: $TASK_NAME success in $DURATION_HM\n$PR_URL"
    else
        log "PR creation failed"
        codex_state blocked pr_failed "Overnight success but PR creation failed" "$BRANCH_NAME" "$REPO_ROOT"
        notify "⚠️ Codex overnight: $TASK_NAME success but PR failed (branch=$BRANCH_NAME)"
    fi
    mv "$TASK_FILE" "$DONE_DIR/$(basename "$TASK_FILE" .md)-${TIMESTAMP}.md"
elif [ "$OUTCOME" = "partial" ] || [ "$COMMITS_AHEAD" -gt 0 ]; then
    codex_state action partial "Overnight partial: commits=$COMMITS_AHEAD outcome=$OUTCOME" "$BRANCH_NAME" "$REPO_ROOT"
    notify "⚠️ Codex overnight: $TASK_NAME partial (${COMMITS_AHEAD} commits, $DURATION_HM, outcome=$OUTCOME). Branch=$BRANCH_NAME"
    mv "$TASK_FILE" "$FAILED_DIR/$(basename "$TASK_FILE" .md)-partial-${TIMESTAMP}.md"
else
    codex_state blocked failed "Overnight failed with no commits" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex overnight: $TASK_NAME failed (no commits, $DURATION_HM)"
    git checkout main 2>&1 | head -2 || true
    git branch -D "$BRANCH_NAME" 2>&1 | head -2 || true
    mv "$TASK_FILE" "$FAILED_DIR/$(basename "$TASK_FILE" .md)-failed-${TIMESTAMP}.md"
fi

# Save plan + status as artifacts
[ -f "$PLAN_FILE" ] && cp "$PLAN_FILE" "${LOG_DIR}/${TASK_NAME}-${TIMESTAMP}-plan.md" || true
[ -f "$STATUS_FILE" ] && cp "$STATUS_FILE" "${LOG_DIR}/${TASK_NAME}-${TIMESTAMP}-status.md" || true

log "Done. Task moved out of queue."
