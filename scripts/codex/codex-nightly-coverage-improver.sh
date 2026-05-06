#!/bin/bash
# codex-nightly-coverage-improver.sh
# Nightly autonomous test coverage improver.
# Cron 03:00 WITA daily. Picks 1 file with coverage <50%, asks Codex to write
# tests for it, runs the new tests, opens a PR if green.
#
# Cap: 1 PR per night, max 200 LOC of new test code.
# Hard rule: only writes files in apps/backend-rag/backend/tests/ subtrees.

set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin

REPO_ROOT="${CODEX_COVERAGE_REPO_ROOT:-${HOME}/Desktop/nuzantara/.worktrees/codex-coverage-improver-runtime}"
REPO_SLUG="${CODEX_COVERAGE_REPO_SLUG:-Balizero1987/Teman2}"
STATE_DIR="${CODEX_COVERAGE_STATE_DIR:-${HOME}/.agent/decisions/state}"
STATE_FILE="${STATE_DIR}/codex_coverage_improver.state"
LOG_DIR="${CODEX_COVERAGE_LOG_DIR:-${HOME}/logs/codex-coverage-improver}"
TELEGRAM_NOTIFY="${HOME}/.claude/scripts/hotfix-notify.sh"
CODEX_AUTOMATION_LIB="${CODEX_AUTOMATION_LIB:-${HOME}/scripts/codex-automation-lib.sh}"

mkdir -p "$STATE_DIR" "$LOG_DIR"
# shellcheck source=/Users/nuzantara/scripts/codex-automation-lib.sh
[ -f "$CODEX_AUTOMATION_LIB" ] && source "$CODEX_AUTOMATION_LIB"

CODEX_TIMEOUT=2400  # 40 min
COVERAGE_THRESHOLD=50  # files below this get prioritized
MAX_NEW_LOC=200

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
        codex_auto_write_state "com.nuzantara.codex-coverage-improver" "$@" || true
    fi
}

# Lock — mkdir-based mutex (macOS-compatible)
LOCK_DIR="${STATE_DIR}/codex_coverage_improver.lock.d"
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

# Daily cap (1/night)
TODAY=$(date '+%Y-%m-%d')
DONE_FLAG="${STATE_DIR}/codex_coverage_improver_${TODAY}.done"
if [ -f "$DONE_FLAG" ]; then
    log "Already ran today. Exiting."
    codex_state idle already_ran_today "Already ran today" "" "$REPO_ROOT"
    exit 0
fi

if [ "${CODEX_COVERAGE_DRY_RUN:-0}" = "1" ]; then
    log "[dry-run] lock acquired; would compute coverage under $REPO_ROOT/apps/backend-rag"
    codex_state idle dry_run "Would compute coverage under $REPO_ROOT/apps/backend-rag" "" "$REPO_ROOT"
    exit 0
fi

if [ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null)" ] && [ "${CODEX_COVERAGE_ALLOW_STASH:-0}" != "1" ]; then
    log "Working tree dirty — skipping full run before coverage scan. Set CODEX_COVERAGE_ALLOW_STASH=1 to override."
    codex_state skipped dirty_worktree "Runtime worktree dirty before coverage scan" "" "$REPO_ROOT"
    notify "⚠️ Codex coverage: skipped because working tree is dirty"
    exit 0
fi

cd "$REPO_ROOT"

# ─────────────────────────────────────────────
# Find target file
# ─────────────────────────────────────────────
log "Computing coverage on apps/backend-rag/..."

cd apps/backend-rag
source .venv/bin/activate

# Quick coverage scan (limited to avoid full-suite cost)
COV_REPORT="${LOG_DIR}/coverage-${TODAY}.txt"
PYTHONPATH=. timeout 600 pytest backend/tests/services/rag/ \
    --cov=backend \
    --cov-report=term-missing:skip-covered \
    --cov-report=json:${LOG_DIR}/coverage-${TODAY}.json \
    -q --tb=no \
    > "$COV_REPORT" 2>&1 || true

if [ ! -f "${LOG_DIR}/coverage-${TODAY}.json" ]; then
    log "Coverage report failed to generate"
    codex_state blocked coverage_report_failed "Coverage report failed to generate" "" "$REPO_ROOT"
    notify "⚠️ Codex coverage: report generation failed"
    exit 1
fi

# Pick file with lowest coverage that's NOT been attempted in last 7 days
TARGET_FILE=$(python3 <<EOF
import json
import time
import os
from pathlib import Path

cov_path = "${LOG_DIR}/coverage-${TODAY}.json"
state_path = "${STATE_FILE}"

with open(cov_path) as f:
    data = json.load(f)

now = time.time()
recent_cutoff = now - 7 * 86400  # 7 days

attempted = set()
if os.path.exists(state_path):
    with open(state_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                ts, fname = parts[0], parts[1]
                try:
                    if float(ts) >= recent_cutoff:
                        attempted.add(fname)
                except ValueError:
                    continue

# Sort by coverage ascending, pick lowest not in attempted
files = data.get("files", {})
candidates = []
for fname, info in files.items():
    pct = info.get("summary", {}).get("percent_covered", 100.0)
    line_count = info.get("summary", {}).get("num_statements", 0)
    if pct < ${COVERAGE_THRESHOLD} and line_count >= 20 and line_count <= 500:
        if fname not in attempted:
            # Skip files we shouldn't touch
            skip_patterns = [
                "migrations/",
                "/tests/",
                "/llm/claude_oauth_client",
                "/prompts/zantara_core",
                "alembic/",
            ]
            if any(p in fname for p in skip_patterns):
                continue
            candidates.append((pct, fname, line_count))

if not candidates:
    print("")
else:
    candidates.sort()
    print(candidates[0][1])
EOF
)

if [ -z "$TARGET_FILE" ]; then
    log "No eligible target file found (all <50% files attempted in last 7d)"
    codex_state idle no_target "No eligible low-coverage target found" "" "$REPO_ROOT"
    touch "$DONE_FLAG"
    exit 0
fi

log "Target file: $TARGET_FILE"

cd "$REPO_ROOT"

# ─────────────────────────────────────────────
# Create branch + run Codex
# ─────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SAFE_FNAME=$(echo "$TARGET_FILE" | tr '/' '_' | sed 's/.py$//')
BRANCH_NAME="codex/coverage-${SAFE_FNAME}-${TIMESTAMP}"

# Stash any unstaged work before checkout (avoids "cannot pull with rebase" trap)
# Stash will be popped on main AFTER the working branch is created clean.
STASH_TAG="codex-coverage-${TIMESTAMP}"
HAD_STASH=0
if [ -n "$(git status --porcelain)" ]; then
    if [ "${CODEX_COVERAGE_ALLOW_STASH:-0}" != "1" ]; then
        log "Working tree dirty — skipping full run to avoid stashing user/Codex work. Set CODEX_COVERAGE_ALLOW_STASH=1 to override."
        codex_state skipped dirty_worktree "Runtime worktree dirty before branch creation" "$BRANCH_NAME" "$REPO_ROOT"
        notify "⚠️ Codex coverage: skipped because working tree is dirty"
        exit 0
    fi
    log "Working tree dirty — stashing as $STASH_TAG (CODEX_COVERAGE_ALLOW_STASH=1)"
    git stash push -u -m "$STASH_TAG" 2>&1 | head -3 || true
    HAD_STASH=1
fi

git checkout main 2>&1 | head -2
git pull origin main --ff-only 2>&1 | head -3 || log "pull failed (continuing with local main HEAD)"
git checkout -b "$BRANCH_NAME" 2>&1 | head -2

# Restore-stash function — call before exit on main (NOT on working branch)
restore_stash() {
    if [ "$HAD_STASH" -eq 1 ]; then
        # Find the stash by tag (in case other stashes happened in between)
        STASH_REF=$(git stash list 2>/dev/null | grep "$STASH_TAG" | head -1 | cut -d: -f1 || echo "")
        if [ -n "$STASH_REF" ]; then
            git stash pop "$STASH_REF" 2>&1 | head -5 || log "stash pop $STASH_REF failed (manual: git stash list / git stash apply)"
        fi
    fi
}

CODEX_PROMPT=$(cat <<EOF
You are improving test coverage on the Nuzantara monorepo.

Target file: \`${TARGET_FILE}\`

Your task:
1. Read \`${TARGET_FILE}\` and understand its public API (functions, classes, methods)
2. Identify the most critical untested code paths (error paths, edge cases, branching logic)
3. Write tests in the corresponding test file under \`apps/backend-rag/backend/tests/\` (mirror the source path structure)
4. Use existing test patterns in that directory (pytest, async patterns, fixtures)
5. Run the new tests with \`PYTHONPATH=. pytest <test_file> -v\` to verify they pass
6. Commit ONLY the new/updated test file with message: "test(${SAFE_FNAME}): improve coverage via Codex nightly"

CONSTRAINTS:
- Maximum ${MAX_NEW_LOC} new LOC of test code total
- Do NOT modify the source file \`${TARGET_FILE}\` itself — only add tests
- Do NOT touch other source files
- Use \`httpx\` not \`requests\` (async first)
- Type hints required
- Use \`pytest\` and \`pytest-asyncio\` patterns from the project
- Read AGENTS.md (root + apps/backend-rag/) for full project rules
- If the source file genuinely cannot be tested in isolation (heavy infra deps without good fixtures), write the reason to /tmp/codex-coverage-${TIMESTAMP}.txt and exit without committing

HARD RULES:
- NO ANTHROPIC_API_KEY anywhere
- NO new OPENAI_API_KEY usage
- NO --no-verify, NO bypass
EOF
)

log "Launching Codex (timeout ${CODEX_TIMEOUT}s, profile=xhigh)..."
codex_state action attempt_started "Launching Codex for $TARGET_FILE" "$BRANCH_NAME" "$REPO_ROOT"

if timeout "$CODEX_TIMEOUT" codex --profile xhigh exec "$CODEX_PROMPT" \
    > "${LOG_DIR}/codex-output-${TIMESTAMP}.log" 2>&1; then
    log "Codex completed"
else
    rc=$?
    log "Codex exit $rc"
fi

# Record attempt
echo "$(date +%s) ${TARGET_FILE}" >> "$STATE_FILE"

# ─────────────────────────────────────────────
# Verify Codex actually committed
# ─────────────────────────────────────────────
COMMITS_AHEAD=$(git rev-list --count "main..${BRANCH_NAME}" 2>/dev/null || echo 0)

if [ "$COMMITS_AHEAD" -eq 0 ]; then
    # Fallback: Codex sandbox sometimes blocks .git/index.lock — check if Codex
    # wrote untracked test files we can commit ourselves (outside sandbox).
    UNTRACKED_TESTS=$(git ls-files --others --exclude-standard backend/tests/ apps/backend-rag/backend/tests/ 2>/dev/null | head -20)

    if [ -n "$UNTRACKED_TESTS" ]; then
        log "Codex did not commit, but found untracked test files (sandbox .git block fallback):"
        echo "$UNTRACKED_TESTS" | head -10 | tee -a "${LOG_DIR}/codex-output-${TIMESTAMP}.log"

        # Stage only the new test files and commit on Codex's behalf
        echo "$UNTRACKED_TESTS" | xargs -I {} git add {} 2>&1 | head -5 || true

        if [ -n "$(git diff --cached --name-only 2>/dev/null)" ]; then
            git commit -m "test(${SAFE_FNAME}): improve coverage via Codex nightly

Codex wrote tests but the sandbox blocked .git/index.lock.
Files committed by codex-nightly-coverage-improver.sh fallback path.
" 2>&1 | head -5

            # Re-check commits ahead
            COMMITS_AHEAD=$(git rev-list --count "main..${BRANCH_NAME}" 2>/dev/null || echo 0)
            log "Fallback commit applied. commits_ahead=$COMMITS_AHEAD"
            codex_state action fallback_commit "Committed tests written by Codex fallback path" "$BRANCH_NAME" "$REPO_ROOT"
        fi
    fi
fi

if [ "$COMMITS_AHEAD" -eq 0 ]; then
    log "Codex made no commit (and no untracked tests found)"
    codex_state skipped no_commit "Codex made no commit for $TARGET_FILE" "$BRANCH_NAME" "$REPO_ROOT"
    if [ -f "/tmp/codex-coverage-${TIMESTAMP}.txt" ]; then
        REASON=$(cat "/tmp/codex-coverage-${TIMESTAMP}.txt" | head -200)
        log "Codex declined: $REASON"
        notify "⚠️ Codex coverage: declined ${TARGET_FILE} — $REASON"
    fi
    git checkout main 2>&1 | head -2
    git branch -D "$BRANCH_NAME" 2>&1 | head -2 || true
    restore_stash
    touch "$DONE_FLAG"
    exit 0
fi

# Sanity check: only test files modified
NON_TEST_CHANGES=$(git diff --name-only "main..${BRANCH_NAME}" | grep -v "/tests/" | wc -l | tr -d ' ')
if [ "$NON_TEST_CHANGES" -gt 0 ]; then
    log "Codex modified non-test files (${NON_TEST_CHANGES}). Rejecting."
    codex_state blocked path_constraint "Codex modified non-test files" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex coverage: violated test-only constraint on ${TARGET_FILE}"
    git checkout main 2>&1 | head -2
    git branch -D "$BRANCH_NAME" 2>&1 | head -2 || true
    restore_stash
    touch "$DONE_FLAG"
    exit 1
fi

# Sanity check: LOC cap
NEW_LOC=$(git diff --shortstat "main..${BRANCH_NAME}" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' | head -1 || echo 0)
if [ "$NEW_LOC" -gt "$MAX_NEW_LOC" ]; then
    log "Codex exceeded LOC cap ($NEW_LOC > $MAX_NEW_LOC). Rejecting."
    codex_state blocked loc_cap "LOC cap exceeded ($NEW_LOC > $MAX_NEW_LOC)" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex coverage: LOC cap exceeded ($NEW_LOC > $MAX_NEW_LOC) on ${TARGET_FILE}"
    git checkout main 2>&1 | head -2
    git branch -D "$BRANCH_NAME" 2>&1 | head -2 || true
    restore_stash
    touch "$DONE_FLAG"
    exit 1
fi

# ─────────────────────────────────────────────
# Push + open PR
# ─────────────────────────────────────────────
log "Pushing branch + opening PR (LOC: $NEW_LOC)..."

if ! git push -u origin "$BRANCH_NAME" 2>&1 | head -10; then
    log "Push failed"
    codex_state blocked push_failed "Push failed for $BRANCH_NAME" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex coverage: push failed for $BRANCH_NAME"
    exit 1
fi

PR_BODY=$(cat <<EOF
## Nightly coverage improvement (Codex)

**Target:** \`${TARGET_FILE}\`
**New test LOC:** ${NEW_LOC}

This PR was auto-generated by the nightly coverage improver. Codex selected this file for having coverage below ${COVERAGE_THRESHOLD}%, then wrote tests targeting critical untested paths.

### Verification
- [ ] CI green (especially the new test cases)
- [ ] Tri-LLM panel ≥2/3 green
- [ ] Manual review

\`\`\`bash
python3 ~/Desktop/nuzantara/scripts/codex_tri_llm_review.py --branch ${BRANCH_NAME}
\`\`\`

🤖 Generated by Codex CLI nightly coverage improver
EOF
)

if PR_URL=$(gh pr create \
    --repo "$REPO_SLUG" \
    --base main \
    --head "$BRANCH_NAME" \
    --title "test(${SAFE_FNAME}): improve coverage via Codex nightly" \
    --body "$PR_BODY" 2>&1 | tail -5 | grep -E "^https"); then
    log "PR opened: $PR_URL"
    codex_state action pr_opened "PR opened: $PR_URL" "$BRANCH_NAME" "$REPO_ROOT"
    notify "✅ Codex coverage: PR opened $PR_URL (+${NEW_LOC} LOC tests for ${TARGET_FILE})"
else
    log "PR creation failed"
    codex_state blocked pr_failed "PR creation failed for $BRANCH_NAME" "$BRANCH_NAME" "$REPO_ROOT"
    notify "⚠️ Codex coverage: PR creation failed for $BRANCH_NAME"
fi

git checkout main 2>&1 | head -2 || true
restore_stash
touch "$DONE_FLAG"

log "Done."
