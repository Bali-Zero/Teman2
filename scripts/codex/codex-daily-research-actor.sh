#!/bin/bash
# codex-daily-research-actor.sh
#
# Daily 06:00 WITA (after 18:00 intel-radar-digest of previous day).
# Reads recent intel_radar_findings flagged as L1 (high priority regulatory),
# for each one launches Codex to:
#   1. Query NB-2 (immigration) or NB-4 (tax) or NB-6 (operations) for grounding
#   2. Draft a regulations update markdown in research/regulatory/<domain>/YYYY-MM-DD-<slug>.md
#   3. Open a PR for review (no auto-apply to KB)
#
# Cap: max 3 PRs per day. Each PR is gated by tri-LLM panel review before merge.
#
# This is "research → action" — converts intel into draft regulatory updates,
# NOT just notifications. Final approval still requires human + tri-LLM panel.

set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin

REPO_ROOT="${CODEX_RESEARCH_REPO_ROOT:-${HOME}/Desktop/nuzantara/.worktrees/codex-research-actor-runtime}"
REPO_SLUG="${CODEX_RESEARCH_REPO_SLUG:-Balizero1987/Teman2}"
STATE_DIR="${CODEX_RESEARCH_STATE_DIR:-${HOME}/.agent/decisions/state}"
STATE_FILE="${STATE_DIR}/codex_research_actor.state"
LOG_DIR="${CODEX_RESEARCH_LOG_DIR:-${HOME}/logs/codex-research-actor}"
TELEGRAM_NOTIFY="${HOME}/.claude/scripts/hotfix-notify.sh"
OVERNIGHT_BACKLOG_DIR="${CODEX_RESEARCH_OVERNIGHT_BACKLOG_DIR:-${HOME}/codex-overnight/backlog}"
CODEX_AUTOMATION_LIB="${CODEX_AUTOMATION_LIB:-${HOME}/scripts/codex-automation-lib.sh}"

mkdir -p "$STATE_DIR" "$LOG_DIR" "$OVERNIGHT_BACKLOG_DIR"
# shellcheck source=/Users/nuzantara/scripts/codex-automation-lib.sh
[ -f "$CODEX_AUTOMATION_LIB" ] && source "$CODEX_AUTOMATION_LIB"

CODEX_TIMEOUT=2400  # 40min per finding
DAILY_PR_CAP=3

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
        codex_auto_write_state "com.nuzantara.codex-research-actor" "$@" || true
    fi
}

LOCK_DIR="${STATE_DIR}/codex_research_actor.lock.d"
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

# Daily cap
TODAY=$(date '+%Y-%m-%d')
COUNT_FILE="${STATE_DIR}/codex_research_actor_count_${TODAY}"
PRS_TODAY=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)

if [ "$PRS_TODAY" -ge "$DAILY_PR_CAP" ]; then
    log "Daily PR cap $DAILY_PR_CAP reached. Exiting."
    codex_state skipped daily_cap "Daily PR cap reached ($PRS_TODAY/$DAILY_PR_CAP)" "" "$REPO_ROOT"
    exit 0
fi

if [ "${CODEX_RESEARCH_DRY_RUN:-0}" = "1" ]; then
    log "[dry-run] lock acquired; would query L1 intel findings for $REPO_SLUG"
    codex_state idle dry_run "Would query L1 intel findings" "" "$REPO_ROOT"
    exit 0
fi

if [ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null)" ] && [ "${CODEX_RESEARCH_ALLOW_STASH:-0}" != "1" ]; then
    log "Working tree dirty — skipping full run before DB query. Set CODEX_RESEARCH_ALLOW_STASH=1 to override."
    codex_state skipped dirty_worktree "Runtime worktree dirty before DB query" "" "$REPO_ROOT"
    notify "⚠️ Codex research-actor: skipped because working tree is dirty"
    exit 0
fi

# ─────────────────────────────────────────────
# Source secrets for DB connection
# ─────────────────────────────────────────────
set -a
[ -f "${HOME}/.nuzantara-secrets.env" ] && source "${HOME}/.nuzantara-secrets.env"
set +a

# ─────────────────────────────────────────────
# Query DB for L1 findings from last 48h not yet actioned
# ─────────────────────────────────────────────
FINDINGS_JSON="${LOG_DIR}/findings-${TODAY}.json"

python3 <<EOF > "$FINDINGS_JSON"
import asyncio
import json
import os
import sys

async def main():
    try:
        import asyncpg
    except ImportError:
        print("[]")
        return

    db_url = os.environ.get("DATABASE_URL_LOCAL") or os.environ.get("DATABASE_URL")
    if not db_url:
        # Try common Pro setup
        db_url = "postgres://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"

    try:
        conn = await asyncpg.connect(db_url, timeout=10)
    except Exception as e:
        print("[]", file=sys.stderr)
        print(f"DB connection failed: {e}", file=sys.stderr)
        return

    try:
        rows = await conn.fetch("""
            SELECT id, query, query_tier, url, canonical_url, title, description, source_domain, observed_at::text
            FROM intel_radar_findings
            WHERE query_tier = 'L1'
              AND observed_at > NOW() - INTERVAL '48 hours'
            ORDER BY observed_at DESC
            LIMIT 10
        """)
        results = [dict(r) for r in rows]
        print(json.dumps(results, default=str))
    finally:
        await conn.close()

asyncio.run(main())
EOF

if [ ! -s "$FINDINGS_JSON" ] || [ "$(cat "$FINDINGS_JSON")" = "[]" ]; then
    log "No L1 findings in last 48h"
    codex_state idle no_findings "No L1 findings in last 48h" "" "$REPO_ROOT"
    exit 0
fi

# Pick the first finding NOT in state file
FINDING_JSON=$(python3 <<EOF
import json, os, sys

with open("$FINDINGS_JSON") as f:
    findings = json.load(f)

state_path = "$STATE_FILE"
processed_ids = set()
if os.path.exists(state_path):
    with open(state_path) as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                processed_ids.add(parts[0])

for fnd in findings:
    if str(fnd["id"]) not in processed_ids:
        print(json.dumps(fnd))
        sys.exit(0)
EOF
)

if [ -z "$FINDING_JSON" ]; then
    log "All recent L1 findings already processed"
    codex_state idle all_processed "All recent L1 findings already processed" "" "$REPO_ROOT"
    exit 0
fi

FINDING_ID=$(echo "$FINDING_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
FINDING_TITLE=$(echo "$FINDING_JSON" | python3 -c "import json,sys; t=json.load(sys.stdin).get('title',''); print(t[:120] if t else 'untitled')")
FINDING_URL=$(echo "$FINDING_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('canonical_url') or json.load(sys.stdin).get('url',''))" 2>/dev/null || echo "")

log "Processing finding $FINDING_ID: $FINDING_TITLE"

# Mark attempted
echo "$FINDING_ID $(date +%s) $FINDING_TITLE" >> "$STATE_FILE"

# ─────────────────────────────────────────────
# Determine domain from query
# ─────────────────────────────────────────────
QUERY=$(echo "$FINDING_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['query'])")

DOMAIN="general"
case "$QUERY" in
    *visa*|*KITAS*|*KITAP*|*imigrasi*|*immigration*) DOMAIN="immigration" ;;
    *tax*|*pajak*|*PPh*|*PPN*|*coretax*|*SPT*|*NPWP*) DOMAIN="tax" ;;
    *KBLI*|*OSS*|*PT\ PMA*|*company*|*business*) DOMAIN="company" ;;
    *property*|*villa*|*HGB*|*PBG*|*SHM*) DOMAIN="property" ;;
    *LKPM*|*compliance*|*BKPM*) DOMAIN="compliance" ;;
esac

log "Inferred domain: $DOMAIN"

# ─────────────────────────────────────────────
# Setup branch + Codex
# ─────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SLUG=$(echo "$FINDING_TITLE" | tr -cd '[:alnum:] -' | tr ' ' '-' | tr 'A-Z' 'a-z' | cut -c1-50)
BRANCH_NAME="codex-research/${DOMAIN}-${SLUG}-${TIMESTAMP}"

cd "$REPO_ROOT"

# Stash dirty work before checkout (cf. cicatrix scar 2026-04-29 untracked-files-loss)
STASH_TAG="codex-research-${TIMESTAMP}"
HAD_STASH=0
if [ -n "$(git status --porcelain)" ]; then
    if [ "${CODEX_RESEARCH_ALLOW_STASH:-0}" != "1" ]; then
        log "Working tree dirty — skipping full run to avoid stashing user/Codex work. Set CODEX_RESEARCH_ALLOW_STASH=1 to override."
        codex_state skipped dirty_worktree "Runtime worktree dirty before branch creation" "$BRANCH_NAME" "$REPO_ROOT"
        notify "⚠️ Codex research-actor: skipped because working tree is dirty"
        exit 0
    fi
    log "Working tree dirty — stashing as $STASH_TAG (CODEX_RESEARCH_ALLOW_STASH=1)"
    git stash push -u -m "$STASH_TAG" 2>&1 | head -3 || true
    HAD_STASH=1
fi

restore_stash() {
    if [ "$HAD_STASH" -eq 1 ]; then
        git checkout main 2>/dev/null || true
        STASH_REF=$(git stash list 2>/dev/null | grep "$STASH_TAG" | head -1 | cut -d: -f1 || echo "")
        if [ -n "$STASH_REF" ]; then
            git stash pop "$STASH_REF" 2>&1 | head -5 || log "stash pop $STASH_REF failed"
        fi
        HAD_STASH=0
    fi
}
trap 'restore_stash; rm -f "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

git checkout main 2>&1 | head -2
git pull origin main --ff-only 2>&1 | head -3 || log "pull failed (continuing with local main HEAD)"
git checkout -b "$BRANCH_NAME" 2>&1 | head -2

CODEX_PROMPT=$(cat <<EOF
You are processing an Indonesian regulatory intelligence finding into a draft regulations update for the Nuzantara/Bali Zero monorepo.

FINDING:
$(echo "$FINDING_JSON" | python3 -m json.tool)

DOMAIN: ${DOMAIN}

Your task:
1. Read the URL to understand the regulatory change (use \`curl\` or fetch tool)
2. If domain is ${DOMAIN}, query the relevant NotebookLM notebook for grounding context (skip if NB tool unavailable):
   - immigration → NB-2 (cff93ab0-813a-42f2-a8de-36987e724271)
   - tax → NB-4 (d4b2eedb-9863-4a1a-81ff-a11b0b45d853)
   - company → NB-3 (933509f9-1561-403d-bd44-4a7a67a36df2)
   - property → NB-5 (d9438180-5e63-4e2a-a473-6061101f6a8d)
   - compliance → NB-6 (85207af3-352f-4554-8d2a-18f42cc541ba)
3. Draft a regulations update file at:
   \`research/regulatory/${DOMAIN}/${TIMESTAMP}-${SLUG}.md\`
4. The draft MUST include:
   - YAML frontmatter: date, domain, source_url, finding_id, sources_consulted
   - Summary of what changed (1 paragraph)
   - Effective date / deadline (if applicable)
   - Who is impacted (Bali Zero client segments)
   - Action required (procedural changes, document updates, notify clients?)
   - Cross-reference to existing Bali Zero knowledge base entries that need update
5. Also add a separate action proposal file at:
   \`research/regulatory/${DOMAIN}/${TIMESTAMP}-${SLUG}.action-proposal.md\`
   The proposal MUST state whether an autonomous overnight follow-up is required.
6. If the proposal says a KB/docs/code follow-up is required, add an overnight task spec at:
   \`research/regulatory/${DOMAIN}/${TIMESTAMP}-${SLUG}.overnight-task.md\`
   The spec must be safe for Codex overnight runner: exact files allowed, exact verification commands, no secrets, no direct production deploy.
7. Commit the draft/proposal/task files with message: "research(${DOMAIN}): draft update from intel finding ${FINDING_ID}"
8. Do NOT modify apps/backend-rag/backend/kb/ directly — only \`research/\` subtree

HARD RULES:
- NO ANTHROPIC_API_KEY anywhere
- NO new OPENAI_API_KEY usage
- ONLY add files in research/regulatory/${DOMAIN}/ subtree
- If you cannot fetch the source URL or generate a useful draft, write reason to /tmp/codex-research-${TIMESTAMP}.txt and exit without committing

Read root AGENTS.md + apps/backend-rag/AGENTS.md for full project context.
EOF
)

log "Launching Codex (timeout ${CODEX_TIMEOUT}s, profile=xhigh)..."
codex_state action attempt_started "Launching Codex for finding $FINDING_ID" "$BRANCH_NAME" "$REPO_ROOT"

if timeout "$CODEX_TIMEOUT" codex --profile xhigh exec "$CODEX_PROMPT" \
    > "${LOG_DIR}/codex-output-${TIMESTAMP}.log" 2>&1; then
    log "Codex completed"
else
    rc=$?
    log "Codex exit $rc"
fi

# ─────────────────────────────────────────────
# Verify + push
# ─────────────────────────────────────────────
COMMITS_AHEAD=$(git rev-list --count "main..${BRANCH_NAME}" 2>/dev/null || echo 0)

if [ "$COMMITS_AHEAD" -eq 0 ]; then
    log "Codex made no commit"
    codex_state skipped no_commit "Codex made no commit for finding $FINDING_ID" "$BRANCH_NAME" "$REPO_ROOT"
    if [ -f "/tmp/codex-research-${TIMESTAMP}.txt" ]; then
        REASON=$(cat "/tmp/codex-research-${TIMESTAMP}.txt" | head -150)
        notify "⚠️ Codex research-actor: declined finding $FINDING_ID — $REASON"
    fi
    git checkout main 2>&1 | head -2
    git branch -D "$BRANCH_NAME" 2>&1 | head -2 || true
    exit 0
fi

# Sanity: only research/regulatory/ files modified
NON_RESEARCH=$(git diff --name-only "main..${BRANCH_NAME}" | grep -v "^research/regulatory/" | wc -l | tr -d ' ')
if [ "$NON_RESEARCH" -gt 0 ]; then
    log "Codex modified files outside research/regulatory/. Rejecting."
    codex_state blocked path_constraint "Codex modified files outside research/regulatory" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex research-actor: violated path constraint on finding $FINDING_ID"
    git checkout main 2>&1 | head -2
    git branch -D "$BRANCH_NAME" 2>&1 | head -2 || true
    exit 1
fi

log "Pushing branch + opening PR..."

if ! git push -u origin "$BRANCH_NAME" 2>&1 | head -10; then
    log "Push failed"
    codex_state blocked push_failed "Push failed for $BRANCH_NAME" "$BRANCH_NAME" "$REPO_ROOT"
    notify "🔴 Codex research-actor: push failed for finding $FINDING_ID"
    exit 1
fi

FOLLOWUP_FILE=$(git diff --name-only "main..${BRANCH_NAME}" | grep -E '\.overnight-task\.md$' | head -1 || true)
if [ -n "$FOLLOWUP_FILE" ] && [ -f "$FOLLOWUP_FILE" ]; then
    FOLLOWUP_TARGET="${OVERNIGHT_BACKLOG_DIR}/research-${FINDING_ID}-${TIMESTAMP}.md"
    cp "$FOLLOWUP_FILE" "$FOLLOWUP_TARGET"
    log "Queued overnight follow-up: $FOLLOWUP_TARGET"
fi

PR_BODY=$(cat <<EOF
## Codex daily research-actor draft

**Finding:** ${FINDING_TITLE}
**Domain:** ${DOMAIN}
**Source:** ${FINDING_URL}
**Intel finding ID:** ${FINDING_ID}

This PR is a DRAFT regulatory update generated from an intel-radar finding (L1 high priority). Review carefully before merging:
- Verify factual accuracy against original source
- Check NotebookLM cross-reference still valid
- Decide which Bali Zero KB entries need follow-up update (separate PR)

### Verification
- [ ] Source URL accessible and content matches summary
- [ ] Tri-LLM panel ≥2/3 green: \`python3 scripts/codex_tri_llm_review.py --branch ${BRANCH_NAME}\`
- [ ] Manual review

🤖 Generated by Codex daily research-actor
EOF
)

if PR_URL=$(gh pr create \
    --repo "$REPO_SLUG" \
    --base main \
    --head "$BRANCH_NAME" \
    --title "research(${DOMAIN}): draft update from intel finding ${FINDING_ID}" \
    --body "$PR_BODY" 2>&1 | tail -5 | grep -E "^https"); then
    log "PR opened: $PR_URL"
    if [ -n "$FOLLOWUP_FILE" ]; then
        codex_state action followup_queued "PR opened and overnight follow-up queued: $PR_URL" "$BRANCH_NAME" "$REPO_ROOT"
    else
        codex_state action pr_opened "PR opened: $PR_URL" "$BRANCH_NAME" "$REPO_ROOT"
    fi
    notify "✅ Codex research-actor: PR opened $PR_URL ($DOMAIN)"
    echo $((PRS_TODAY + 1)) > "$COUNT_FILE"
else
    log "PR creation failed"
    codex_state blocked pr_failed "PR creation failed for finding $FINDING_ID" "$BRANCH_NAME" "$REPO_ROOT"
    notify "⚠️ Codex research-actor: PR failed for finding $FINDING_ID"
fi

git checkout main 2>&1 | head -2 || true
log "Done."
