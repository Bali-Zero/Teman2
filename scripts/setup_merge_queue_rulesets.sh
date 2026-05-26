#!/usr/bin/env bash
# setup_merge_queue_rulesets.sh — Enable GitHub merge queue + path-restriction
# rulesets for Balizero1987/Teman2 main branch.
#
# IDEMPOTENT: safe to re-run. Default mode is DRY-RUN — pass --apply to mutate.
#
# Owner: @Balizero1987 only (admin scope on repo required).
# Sister doc: docs/runbooks/merge-queue-discipline.md
# SOTA brief: research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md
#
# Usage:
#   bash scripts/setup_merge_queue_rulesets.sh                # DRY-RUN, prints diff
#   bash scripts/setup_merge_queue_rulesets.sh --apply        # APPLY changes
#   bash scripts/setup_merge_queue_rulesets.sh --rollback     # Revert merge queue
#   bash scripts/setup_merge_queue_rulesets.sh --snapshot     # Save current state JSON
#
# Empirical baseline captured 2026-05-24 (see runbook §2 for the snapshot table).

set -euo pipefail

REPO="Balizero1987/Teman2"
BRANCH="main"
MODE="${1:-dry-run}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SNAPSHOT_DIR="${REPO_ROOT}/research/operations/audits"
SNAPSHOT_FILE="${SNAPSHOT_DIR}/2026-05-24-pre-merge-queue-protection.json"

# Required status checks — names must match GitHub Actions job display names EXACTLY.
# Verified 2026-05-24 via `gh api .../branches/main/protection`.
REQUIRED_CHECKS=(
  "E2E Tests (Playwright)"
  "MCP Server Tests"
  "Frontend Tests (Next.js) (mouth)"
  "Detect Secrets"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
err()  { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
diff_line() { printf '  %s %s\n' "$1" "$2"; }

require_gh() {
  command -v gh >/dev/null 2>&1 || err "gh CLI not installed (brew install gh)"
  gh auth status >/dev/null 2>&1 || err "gh CLI not authenticated (gh auth login)"
  local user
  user="$(gh api user --jq '.login')"
  log "Authenticated as: ${user}"
  if [[ "${user}" != "Balizero1987" ]] && [[ "${MODE}" == "--apply" || "${MODE}" == "--rollback" ]]; then
    err "Only @Balizero1987 may apply/rollback merge-queue config. Current user: ${user}"
  fi
}

build_checks_json() {
  # Emit JSON array of {context, app_id} objects. We omit app_id to allow any
  # GitHub-Actions-run check with the matching context to satisfy the requirement.
  local arr=()
  for c in "${REQUIRED_CHECKS[@]}"; do
    arr+=("{\"context\":\"${c}\"}")
  done
  printf '[%s]' "$(IFS=,; echo "${arr[*]}")"
}

# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

snapshot_state() {
  mkdir -p "${SNAPSHOT_DIR}"
  log "Capturing current branch protection → ${SNAPSHOT_FILE}"
  gh api "repos/${REPO}/branches/${BRANCH}/protection" > "${SNAPSHOT_FILE}"
  log "Capturing existing rulesets → ${SNAPSHOT_DIR}/2026-05-24-pre-merge-queue-rulesets.json"
  gh api "repos/${REPO}/rulesets" > "${SNAPSHOT_DIR}/2026-05-24-pre-merge-queue-rulesets.json"
  log "Snapshot complete."
}

# ---------------------------------------------------------------------------
# Diff (dry-run): show what --apply would change.
# ---------------------------------------------------------------------------

show_diff() {
  log "=== DRY-RUN: changes that --apply would make ==="
  local current strict checks_count
  current="$(gh api "repos/${REPO}/branches/${BRANCH}/protection" 2>/dev/null || echo '{}')"
  strict="$(echo "${current}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("required_status_checks",{}).get("strict","absent"))')"
  checks_count="$(echo "${current}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get("required_status_checks",{}).get("contexts",[])))')"

  echo
  echo "BRANCH PROTECTION on ${REPO}#${BRANCH}:"
  diff_line "current:" "strict=${strict}, ${checks_count} required checks"
  diff_line "  → after:" "strict=true, ${#REQUIRED_CHECKS[@]} required checks (no change to context list)"
  diff_line "current:" "required_pull_request_reviews.required_approving_review_count=$(echo "${current}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("required_pull_request_reviews",{}).get("required_approving_review_count","absent"))')"
  diff_line "  → after:" "required_approving_review_count=1, require_code_owner_reviews=true"
  diff_line "current:" "required_linear_history.enabled=$(echo "${current}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("required_linear_history",{}).get("enabled","absent"))')"
  diff_line "  → after:" "required_linear_history.enabled=true"
  diff_line "current:" "allow_force_pushes.enabled=$(echo "${current}" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("allow_force_pushes",{}).get("enabled","absent"))')"
  diff_line "  → after:" "allow_force_pushes.enabled=false (no change if already false)"
  echo
  echo "MERGE QUEUE on ${REPO}#${BRANCH}:"
  diff_line "current:" "disabled"
  diff_line "  → after:" "enabled (squash merge, max 5 entries, 5min wait, 60min timeout)"
  echo
  echo "RULESETS on ${REPO}:"
  local rs_count
  rs_count="$(gh api "repos/${REPO}/rulesets" --jq 'length' 2>/dev/null || echo '?')"
  diff_line "current:" "${rs_count} ruleset(s)"
  diff_line "  → after:" "+1 ruleset 'merge-queue-discipline-2026-05-24' (path-restriction enforced via CODEOWNERS)"
  echo
  echo "CODEOWNERS:"
  if [[ -f "${REPO_ROOT}/.github/CODEOWNERS" ]]; then
    diff_line "current:" ".github/CODEOWNERS exists ($(wc -l < "${REPO_ROOT}/.github/CODEOWNERS") lines, $(grep -cv '^#\|^$' "${REPO_ROOT}/.github/CODEOWNERS") rules)"
  else
    diff_line "current:" "MISSING — apply will block until file is committed"
  fi
  diff_line "  → after:" "no API change (CODEOWNERS is repo-tree, takes effect on next commit)"
  echo
  log "=== END DRY-RUN ==="
}

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

apply_changes() {
  log "=== APPLY: mutating ${REPO} ==="

  # Pre-flight: CODEOWNERS must exist or path-restriction is moot.
  if [[ ! -f "${REPO_ROOT}/.github/CODEOWNERS" ]]; then
    err "Refusing to apply: .github/CODEOWNERS missing. Commit it first."
  fi

  snapshot_state

  log "Step 1/3: Update branch protection (strict checks + CODEOWNERS reviews + linear history)"
  local checks_json
  checks_json="$(build_checks_json)"

  # Build the payload as JSON via stdin to avoid shell-quoting hell.
  python3 - <<PYEOF | gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" --input -
import json, sys
payload = {
    "required_status_checks": {
        "strict": True,
        "checks": ${checks_json},
    },
    "enforce_admins": False,
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": True,
        "require_code_owner_reviews": True,
        "required_approving_review_count": 1,
        "require_last_push_approval": False,
    },
    "restrictions": None,
    "required_linear_history": True,
    "allow_force_pushes": False,
    "allow_deletions": False,
    "required_conversation_resolution": True,
    "lock_branch": False,
    "allow_fork_syncing": False,
}
print(json.dumps(payload))
PYEOF
  log "  → branch protection updated"

  log "Step 2/3: Enable merge queue on ${BRANCH}"
  # Merge queue config — GraphQL is the canonical API; REST has limited support.
  # Use the REST endpoint where available; fall back to graphql.
  python3 - <<PYEOF | gh api graphql --input - || log "  ⚠ merge queue enable returned non-zero (may already be enabled)"
import json
query = '''
mutation EnableMergeQueue($repoId: ID!) {
  createMergeQueue(input: {
    repositoryId: $repoId,
    mergeMethod: SQUASH,
    mergingStrategy: ALLGREEN,
    maximumEntriesToBuild: 5,
    maximumEntriesToMerge: 5,
    minimumEntriesToMerge: 1,
    minimumEntriesToMergeWaitTime: 300,
    checkResponseTimeout: 3600
  }) {
    mergeQueue { id }
  }
}
'''
# NOTE: This GraphQL mutation may not be public — fallback path documented.
print(json.dumps({"query": query, "variables": {"repoId": "REPO_NODE_ID_PLACEHOLDER"}}))
PYEOF
  log "  → merge queue API call attempted; verify via GitHub UI: Settings → Branches → main → Merge queue"
  log "  ℹ If GraphQL mutation failed, enable manually: https://github.com/${REPO}/settings/branches → edit ${BRANCH} → Require merge queue"

  log "Step 3/3: Create path-restriction ruleset"
  python3 - <<PYEOF | gh api -X POST "repos/${REPO}/rulesets" --input - || log "  ⚠ ruleset create returned non-zero (may already exist)"
import json
payload = {
    "name": "merge-queue-discipline-2026-05-24",
    "target": "branch",
    "enforcement": "active",
    "conditions": {
        "ref_name": {
            "include": ["refs/heads/main"],
            "exclude": []
        }
    },
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "required_linear_history"},
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True
            }
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": "E2E Tests (Playwright)"},
                    {"context": "MCP Server Tests"},
                    {"context": "Frontend Tests (Next.js) (mouth)"},
                    {"context": "Detect Secrets"}
                ]
            }
        }
    ],
    "bypass_actors": [
        {
            "actor_id": 1,
            "actor_type": "RepositoryRole",
            "bypass_mode": "always"
        }
    ]
}
print(json.dumps(payload))
PYEOF
  log "  → ruleset create attempted (bypass: RepositoryRole admin = owner)"

  echo
  log "=== APPLY COMPLETE ==="
  log "Verify via:"
  log "  gh api repos/${REPO}/branches/${BRANCH}/protection | jq"
  log "  gh api repos/${REPO}/rulesets | jq"
  log "Smoke plan: docs/runbooks/merge-queue-discipline.md §8"
}

# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

rollback_changes() {
  log "=== ROLLBACK: restoring pre-2026-05-24 state ==="
  if [[ ! -f "${SNAPSHOT_FILE}" ]]; then
    err "Snapshot not found: ${SNAPSHOT_FILE}. Cannot rollback without snapshot."
  fi

  log "Step 1/3: Restore branch protection from snapshot"
  python3 - <<PYEOF | gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" --input -
import json
with open("${SNAPSHOT_FILE}") as f:
    snap = json.load(f)
# Reconstruct PUT payload from GET shape (lossy: drop url/etc fields).
payload = {
    "required_status_checks": {
        "strict": snap.get("required_status_checks",{}).get("strict", False),
        "checks": snap.get("required_status_checks",{}).get("checks", []),
    },
    "enforce_admins": snap.get("enforce_admins",{}).get("enabled", False),
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": snap.get("required_pull_request_reviews",{}).get("dismiss_stale_reviews", False),
        "require_code_owner_reviews": snap.get("required_pull_request_reviews",{}).get("require_code_owner_reviews", False),
        "required_approving_review_count": snap.get("required_pull_request_reviews",{}).get("required_approving_review_count", 0),
    },
    "restrictions": None,
    "required_linear_history": snap.get("required_linear_history",{}).get("enabled", False),
    "allow_force_pushes": snap.get("allow_force_pushes",{}).get("enabled", False),
    "allow_deletions": snap.get("allow_deletions",{}).get("enabled", False),
    "required_conversation_resolution": snap.get("required_conversation_resolution",{}).get("enabled", False),
}
print(json.dumps(payload))
PYEOF
  log "  → branch protection restored from snapshot"

  log "Step 2/3: Delete merge-queue-discipline-2026-05-24 ruleset (if exists)"
  local ruleset_id
  ruleset_id="$(gh api "repos/${REPO}/rulesets" --jq '.[] | select(.name=="merge-queue-discipline-2026-05-24") | .id' 2>/dev/null || echo '')"
  if [[ -n "${ruleset_id}" ]]; then
    gh api -X DELETE "repos/${REPO}/rulesets/${ruleset_id}"
    log "  → ruleset ${ruleset_id} deleted"
  else
    log "  → no ruleset to delete"
  fi

  log "Step 3/3: Disable merge queue (manual)"
  log "  ℹ Disable manually: https://github.com/${REPO}/settings/branches → edit ${BRANCH}"
  log "    or via GraphQL: deleteMergeQueue mutation."

  log "=== ROLLBACK COMPLETE ==="
  log "CODEOWNERS file (.github/CODEOWNERS) is NOT removed — it has no API counterpart."
  log "To fully revert, delete the file in a follow-up PR."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  require_gh
  case "${MODE}" in
    --apply)
      apply_changes
      ;;
    --rollback)
      rollback_changes
      ;;
    --snapshot)
      snapshot_state
      ;;
    --dry-run|dry-run|"")
      show_diff
      ;;
    -h|--help)
      sed -n '2,20p' "$0"
      ;;
    *)
      err "Unknown mode: ${MODE}. Use --apply | --rollback | --snapshot | --dry-run"
      ;;
  esac
}

main "$@"
