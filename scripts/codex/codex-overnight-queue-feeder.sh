#!/bin/bash
# codex-overnight-queue-feeder.sh
#
# Cron 21:30 WITA — runs 30min before overnight-runner (22:00).
# Auto-populates ~/codex-overnight/queue/ with eligible tasks if queue is empty.
#
# Sources for tasks (in priority order):
#   1. GitHub issues with label "overnight-eligible" (not assigned, not closed)
#   2. Files in ~/codex-overnight/backlog/*.md (manually pre-staged tasks)
#   3. Code review .md files in ~/.claude/state/codex-reviews/ with P1 issues
#      (escalated from PostToolUse hook, batched into single overnight task)
#
# Cap: 1 task/night max (overnight runner processes only first in queue anyway).
# Idempotent: skips if queue already has entries.

set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin

REPO_ROOT="${CODEX_FEEDER_REPO_ROOT:-${HOME}/Desktop/nuzantara/.worktrees/codex-overnight-feeder-runtime}"
REPO_SLUG="${CODEX_FEEDER_REPO_SLUG:-Balizero1987/Teman2}"
QUEUE_DIR="${CODEX_FEEDER_QUEUE_DIR:-${HOME}/codex-overnight/queue}"
BACKLOG_DIR="${CODEX_FEEDER_BACKLOG_DIR:-${HOME}/codex-overnight/backlog}"
REVIEWS_DIR="${CODEX_FEEDER_REVIEWS_DIR:-${HOME}/.claude/state/codex-reviews}"
LOG_DIR="${CODEX_FEEDER_LOG_DIR:-${HOME}/logs/codex-overnight-queue-feeder}"
STATE_DIR="${CODEX_FEEDER_STATE_DIR:-${HOME}/.agent/decisions/state}"
TELEGRAM_NOTIFY="${HOME}/.claude/scripts/hotfix-notify.sh"
CODEX_AUTOMATION_LIB="${CODEX_AUTOMATION_LIB:-${HOME}/scripts/codex-automation-lib.sh}"

mkdir -p "$QUEUE_DIR" "$BACKLOG_DIR" "$LOG_DIR" "$STATE_DIR"
# shellcheck source=/Users/nuzantara/scripts/codex-automation-lib.sh
[ -f "$CODEX_AUTOMATION_LIB" ] && source "$CODEX_AUTOMATION_LIB"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
notify() { [ -x "$TELEGRAM_NOTIFY" ] && "$TELEGRAM_NOTIFY" "$@" 2>/dev/null || true; }
is_uint() {
    case "${1:-}" in
        ""|*[!0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}
codex_state() {
    if command -v codex_auto_write_state >/dev/null 2>&1; then
        codex_auto_write_state "com.nuzantara.codex-overnight-feeder" "$@" || true
    fi
}

# Lock
LOCK_DIR="${STATE_DIR}/codex_overnight_feeder.lock.d"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if is_uint "$LOCK_PID" && ! kill -0 "$LOCK_PID" 2>/dev/null; then
        log "Stale lock detected (pid $LOCK_PID is not running). Reclaiming."
        rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR"
    elif [ -d "$LOCK_DIR" ] && [ "$(find "$LOCK_DIR" -maxdepth 0 -mmin +60 2>/dev/null)" ]; then
        rmdir "$LOCK_DIR" 2>/dev/null || rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR"
    else
        log "Another feeder running, exiting"
        codex_state skipped locked "Another feeder running" "" "$REPO_ROOT"
        exit 0
    fi
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# Skip if queue already has entries
QUEUE_COUNT=$(find "$QUEUE_DIR" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$QUEUE_COUNT" -gt 0 ]; then
    log "Queue already has $QUEUE_COUNT entries — skipping feed"
    codex_state idle queue_has_entries "Queue already has $QUEUE_COUNT entries" "" "$REPO_ROOT"
    exit 0
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TASK_FILE=""

# ─────────────────────────────────────────────
# Source 1: GitHub issues label:overnight-eligible
# ─────────────────────────────────────────────
log "Checking GitHub issues with label 'overnight-eligible'..."

if [ "${CODEX_FEEDER_SKIP_GH:-0}" = "1" ]; then
    GH_ISSUE=""
else
    GH_ISSUE=$(gh issue list \
        --repo "$REPO_SLUG" \
        --label "overnight-eligible" \
        --state open \
        --search "no:assignee" \
        --limit 1 \
        --json number,title,body,url \
        2>/dev/null | python3 -c "
import json, sys
try:
    issues = json.load(sys.stdin)
    if issues:
        i = issues[0]
        print(f\"# Overnight task — GitHub issue #{i['number']}\n\n## Title\n{i['title']}\n\n## URL\n{i['url']}\n\n## Body\n{i.get('body') or '(no body)'}\")
except Exception:
    pass
" 2>/dev/null || echo "")
fi

if [ -n "$GH_ISSUE" ]; then
    TASK_FILE="${QUEUE_DIR}/gh-issue-${TIMESTAMP}.md"
    echo "$GH_ISSUE" > "$TASK_FILE"
    log "Queued from GH issue: $TASK_FILE"
    codex_state action queued "Queued GH issue task $(basename "$TASK_FILE")" "" "$REPO_ROOT"
    notify "🌙 Overnight feeder: queued GH issue task for tonight ($(basename "$TASK_FILE"))"
    exit 0
fi

# ─────────────────────────────────────────────
# Source 2: Manual backlog
# ─────────────────────────────────────────────
log "Checking ~/codex-overnight/backlog/..."
BACKLOG_TASK=$(find "$BACKLOG_DIR" -maxdepth 1 -name "*.md" -type f 2>/dev/null | sort | head -1)
if [ -n "$BACKLOG_TASK" ]; then
    TASK_FILE="${QUEUE_DIR}/backlog-${TIMESTAMP}-$(basename "$BACKLOG_TASK")"
    mv "$BACKLOG_TASK" "$TASK_FILE"
    log "Queued from backlog: $TASK_FILE"
    codex_state action queued "Queued backlog task $(basename "$TASK_FILE")" "" "$REPO_ROOT"
    notify "🌙 Overnight feeder: queued backlog task for tonight ($(basename "$TASK_FILE"))"
    exit 0
fi

# ─────────────────────────────────────────────
# Source 3: Batch P1 reviews (last 7 days, ≥3 reviews)
# ─────────────────────────────────────────────
log "Checking P1 reviews accumulation..."

if [ -d "$REVIEWS_DIR" ]; then
    P1_LIST_FILE=$(mktemp "${TMPDIR:-/tmp}/codex-p1-reviews.XXXXXX")
    find "$REVIEWS_DIR" -maxdepth 1 -name "*.md" -mtime -7 -type f 2>/dev/null | head -10 > "$P1_LIST_FILE"
    P1_REVIEWS=$(cat "$P1_LIST_FILE")
    P1_COUNT=$(wc -l < "$P1_LIST_FILE" | tr -d ' ')
    rm -f "$P1_LIST_FILE"

    if [ "$P1_COUNT" -ge 3 ]; then
        TASK_FILE="${QUEUE_DIR}/p1-batch-${TIMESTAMP}.md"
        {
            echo "# Overnight task — Batch fix accumulated P1 review issues"
            echo ""
            echo "## Context"
            echo ""
            echo "Multiple files have accumulated P1 issues from PostToolUse codex-auto-review."
            echo "This overnight task addresses them as a batch (max 5 LOC per file, max 200 LOC total)."
            echo ""
            echo "## Files with pending P1 issues"
            echo ""
            for review in $P1_REVIEWS; do
                fname=$(basename "$review" .md | tr '_' '/')
                echo "- \`$fname\` (review: $review)"
            done
            echo ""
            echo "## Operating instructions"
            echo ""
            echo "1. For each review file, parse P1 issues only (skip P0 — already handled by Stop drain)"
            echo "2. Apply minimal fix per P1 issue"
            echo "3. Cap: max 5 LOC per file, max 200 LOC total across all files"
            echo "4. Run available pytest/ruff for affected scope"
            echo "5. Single PR titled 'fix(p1): batch address Codex review findings <date>'"
            echo "6. If a P1 requires >5 LOC, skip it (note in PR body why)"
        } > "$TASK_FILE"
        log "Queued P1 batch: $TASK_FILE ($P1_COUNT reviews)"
        codex_state action queued "Queued P1 review batch ($P1_COUNT reviews)" "" "$REPO_ROOT"
        notify "🌙 Overnight feeder: queued P1 batch task ($P1_COUNT reviews) for tonight"
        exit 0
    fi
fi

log "No eligible tasks found in any source — overnight queue stays empty"
codex_state idle no_eligible_tasks "No eligible overnight tasks found" "" "$REPO_ROOT"
