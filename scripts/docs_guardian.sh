#!/bin/bash
# docs-guardian — weekly docs hygiene cron
# Sun 05:00 WITA (Sat 21:00 UTC)
#
# Two-layer automation:
#   L0 (always)    : regenerate DOCS_INVENTORY.md, Telegram on any delta.
#   L1+L2 (auto-PR): if orphans OR broken-links detected, open a PR that
#                    already contains the orphan archive moves (L1) and
#                    a review-required checklist for broken links (L2).
#                    Never pushes directly to main.
#
# Safety gates:
#   - Requires `gh` CLI authenticated for PR creation.
#   - Working tree must be clean (except for inventory) before running.
#   - --dry-run flag for audit-only mode.

set -euo pipefail

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift;;
    *) echo "Unknown flag: $1" >&2; exit 2;;
  esac
done

# Default to the repo root this script lives in, so cron runs work in-place
# and manual invocations from any worktree also work.
if [[ -n "${REPO:-}" ]]; then
  cd "$REPO"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$SCRIPT_DIR/.."
fi

notify() {
  local subject="$1" body="$2"
  if [[ -x "$HOME/.claude/scripts/hotfix-notify.sh" ]]; then
    "$HOME/.claude/scripts/hotfix-notify.sh" "$subject" "$body" || true
  else
    echo "[$subject] $body" >&2
  fi
}

# Cluster + whitelist config — kept identical to .github/workflows/docs-guardian.yml
WHITELIST_ARGS=(
  --whitelist "docs/ARCHITECTURE_DECISION_RECORDS.md"
  --whitelist "docs/API_REFERENCE.md"
  --whitelist "AUTONOMOUS_OPS.md"
  --whitelist "docs/PRO_AIR_CONNECTION.md"
)

CLUSTER_ARGS=(
  --cluster "automation-autonomy:docs/archive/autonomy-history/AUTOMATION_AUTONOMY_PLAN_v3_1.md,docs/archive/autonomy-history/AUTOMATION_AUTONOMY_SYSTEM_V3_2.md,docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md,docs/archive/autonomy-history/AUTOMATION_AUTONOMY_NB1_SUBMISSION.md:docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md"
  --cluster "automations-catalog:docs/archive/ACTIVE_AUTOMATIONS.md,docs/archive/AUTOMATION_MODEL_MAP.md,docs/AUTOMATIONS.md:docs/AUTOMATIONS.md"
  --cluster "system-map:docs/archive/system-map-history/SYSTEM_MAP_4D.md,docs/archive/system-map-history/SYSTEM_OVERVIEW.md,docs/archive/system-map-history/CODEBASE_THEMATIC_AREAS.md,docs/LIVING_ARCHITECTURE.md:docs/LIVING_ARCHITECTURE.md"
  --cluster "system-audit:docs/archive/SYSTEM_AUDIT_2026-04-03.md,docs/SYSTEM_AUDIT_FINAL_2026-04-03.md:docs/SYSTEM_AUDIT_FINAL_2026-04-03.md"
)

# Sync DOCSYNC markers; tolerate failure.
python scripts/docs_sync.py --quiet || true

# Collect stats (single JSON read; also triggers inventory write as side-effect)
STATS=$(python scripts/docs_audit.py --json --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" 2>/dev/null || echo '{}')
STATS_LINE=$(echo "$STATS" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('stale', 0), d.get('broken', 0), d.get('orphans', 0))
except Exception:
    print('0 0 0')
" 2>/dev/null || echo "0 0 0")
STALE=$(echo "$STATS_LINE" | awk '{print $1}')
BROKEN=$(echo "$STATS_LINE" | awk '{print $2}')
ORPHANS=$(echo "$STATS_LINE" | awk '{print $3}')

# Regenerate inventory (persistent file output)
python scripts/docs_audit.py --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" || true

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[dry-run] stale=$STALE broken=$BROKEN orphans=$ORPHANS"
  exit 0
fi

# Nothing actionable? (STALE counts canonical cluster keepers — irreducible, ignored.)
if [[ "$ORPHANS" == "0" && "$BROKEN" == "0" ]]; then
  # Discard inventory drift so the repo stays clean.
  if ! git diff --quiet docs/DOCS_INVENTORY.md 2>/dev/null; then
    git checkout -- docs/DOCS_INVENTORY.md 2>/dev/null || true
  fi
  exit 0
fi

# --- Preconditions for auto-PR ---
if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
  notify "docs-guardian" "Delta detected ($ORPHANS orphans, $BROKEN broken) but gh CLI unavailable. Manual review. See docs/DOCS_INVENTORY.md."
  exit 0
fi

# Working tree sanity (ignore inventory file)
if ! git diff --quiet HEAD -- . ':(exclude)docs/DOCS_INVENTORY.md' 2>/dev/null; then
  notify "docs-guardian" "Delta detected but working tree is dirty. Auto-PR skipped. $ORPHANS orphans, $BROKEN broken."
  exit 0
fi

# --- Build PR branch from origin/main ---
DATE_SLUG=$(date +%Y-%m-%d)
BRANCH="docs-guardian/weekly-${DATE_SLUG}"

git fetch origin main --quiet 2>&1 || {
  notify "docs-guardian" "Failed to fetch origin/main. Auto-PR skipped."
  exit 1
}
git checkout -B "$BRANCH" origin/main >/dev/null 2>&1

# Extract orphan list + broken detail from the captured STATS (before branch switch)
ORPHAN_LIST=$(echo "$STATS" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for f in d.get('files', []):
        if f.get('action', '').startswith('archive: orphan'):
            print(f['path'])
except Exception:
    pass
")
BROKEN_DETAIL=$(echo "$STATS" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for f in d.get('files', []):
        if f.get('broken', 0) > 0:
            print(f\"- \`{f['path']}\`: {f['broken']} broken link(s)\")
except Exception:
    pass
")

L1_COMMITTED=0
if [[ "$ORPHANS" != "0" ]]; then
  python scripts/docs_audit.py --apply --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" || {
    notify "docs-guardian" "--apply failed. Working tree partially modified. Manual cleanup required."
    git checkout main >/dev/null 2>&1 || true
    exit 1
  }
  python scripts/docs_audit.py --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" || true
  git add -A docs/
  if ! git diff --cached --quiet 2>/dev/null; then
    git -c commit.gpgsign=false commit -q -m "chore(docs): auto-archive $ORPHANS orphan docs

Orphan criteria: mtime>90d AND refs_in=0 AND not in whitelist.
Destination: docs/archive/$(date +%Y-%m)-orphans/
Inventory refreshed post-move.

Archived files:
$ORPHAN_LIST

Reversible with git mv <path> docs/<basename>.md if needed.

Co-Authored-By: docs-guardian <noreply@balizero.com>"
    L1_COMMITTED=1
  fi
fi

# If nothing to ship and no broken links to report, abort.
if [[ "$L1_COMMITTED" == "0" && "$BROKEN" == "0" ]]; then
  git checkout main >/dev/null 2>&1 || true
  exit 0
fi

# Push branch
git push origin "$BRANCH" --force-with-lease >/dev/null 2>&1 || {
  notify "docs-guardian" "Failed to push $BRANCH. Auto-PR skipped."
  git checkout main >/dev/null 2>&1 || true
  exit 1
}

# Build PR body
PR_BODY_FILE=$(mktemp)
{
  echo "## Docs Guardian — Weekly Report"
  echo
  echo "**Auto-generated by weekly cron on $(date -u +'%Y-%m-%d %H:%M UTC').**"
  echo
  echo "### Summary"
  echo "- Orphans auto-archived (L1): **$ORPHANS**"
  echo "- Broken links flagged for manual fix (L2): **$BROKEN file(s)**"
  echo
  if [[ "$ORPHANS" != "0" ]]; then
    echo "### L1 — Orphans auto-archived"
    echo
    echo "Criteria: \`mtime>90d AND refs_in=0 AND not in whitelist\`. Already moved in this branch."
    echo
    echo '```'
    echo "$ORPHAN_LIST"
    echo '```'
    echo
    echo "Each move is reversible via \`git mv docs/archive/<YYYY-MM>-orphans/<file>.md docs/<file>.md\`."
    echo
  fi
  if [[ "$BROKEN" != "0" ]]; then
    echo "### L2 — Broken links (manual fix required)"
    echo
    echo "$BROKEN_DETAIL"
    echo
    echo "For each file:"
    echo "1. Locate the broken link."
    echo "2. Apply one of: update path (moved) / remove link syntax (deleted) / fix anchor."
    echo "3. After fixes, run \`./scripts/docs_guardian.sh --dry-run\` locally. Expected: broken=0."
    echo "4. Commit + push to this branch."
    echo
  fi
  echo "### Inventory"
  echo
  echo "\`docs/DOCS_INVENTORY.md\` has been refreshed and reflects state AFTER L1 auto-archive."
  echo
  echo "---"
  echo "🤖 Auto-generated by \`scripts/docs_guardian.sh\` · weekly cron."
} > "$PR_BODY_FILE"

PR_TITLE="docs-guardian: weekly report ($ORPHANS orphans, $BROKEN broken-link file(s))"

PR_URL=$(gh pr create --base main --head "$BRANCH" \
  --title "$PR_TITLE" \
  --body-file "$PR_BODY_FILE" 2>&1 | tail -1 || echo "")
rm -f "$PR_BODY_FILE"

# Enable auto-merge only if there's no manual work pending
if [[ "$BROKEN" == "0" && -n "$PR_URL" && "$PR_URL" =~ ^https://github.com/.+/pull/[0-9]+$ ]]; then
  PR_NUM=$(echo "$PR_URL" | awk -F'/' '{print $NF}')
  gh pr merge "$PR_NUM" --auto --squash >/dev/null 2>&1 || true
fi

# Return to main branch for clean state
git checkout main >/dev/null 2>&1 || true

# --- Final Telegram notification ---
SUMMARY=()
[[ "$L1_COMMITTED" == "1" ]] && SUMMARY+=("L1: $ORPHANS orphans auto-archived")
[[ "$BROKEN" != "0" ]] && SUMMARY+=("L2: $BROKEN broken-link file(s) need manual fix")
[[ -n "$PR_URL" ]] && SUMMARY+=("PR: $PR_URL")

if [[ ${#SUMMARY[@]} -gt 0 ]]; then
  MSG="docs-guardian weekly run"
  for s in "${SUMMARY[@]}"; do MSG="$MSG | $s"; done
  notify "docs-guardian" "$MSG"
fi
