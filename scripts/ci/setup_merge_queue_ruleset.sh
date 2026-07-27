#!/usr/bin/env bash
# setup_merge_queue_ruleset.sh — idempotent IaC for the `merge-queue-main` GitHub
# Ruleset that gates the merge queue on `main`.
#
# CONTEXT: a prior script of nearly this name (`setup_merge_queue_rulesets.sh`,
# plural) was deleted 2026-07-17 as dead automation — GitHub Rulesets are not
# available on repos owned by a personal User account, and this repo was one.
# The repo moved to org `Bali-Zero` on 2026-07-27 (verified live:
# `gh api repos/{owner}/{repo} --jq .owner.type` → `Organization`), which
# unlocks Rulesets. The `merge-queue-main` ruleset this script manages already
# exists (id 19779175, created 2026-07-27 via API, `enforcement: disabled`) —
# this script is the reconciler/toggle for it going forward, not a first-apply.
#
# WHY WHOLE-OBJECT PUT: GitHub's ruleset PUT endpoint replaces the entire
# ruleset body — there is no per-field PATCH. `--enable`/`--disable` therefore
# resend the full canonical body below with only `enforcement` varying.
# Rollback purity depends on this: the body sent by `--disable` must be
# byte-for-byte the same rule set `--enable` sent, so flipping enforcement
# never silently drops or alters a rule as a side effect.
#
# Repo slug is NEVER hardcoded — always resolved live via `gh repo view`
# (the historical `Balizero1987/Teman2` slug now only works as a GitHub
# redirect; hardcoding it would silently keep working today and silently
# break the day the redirect is retired).
#
# Reference: docs/runbooks/merge-queue-discipline.md (activation sequence,
# canary plan, rollback procedure this script implements).
set -euo pipefail

RULESET_NAME="merge-queue-main"

usage() {
  cat <<'USAGE'
Usage: setup_merge_queue_ruleset.sh --status | --enable | --disable | --apply

  --status    Print the current ruleset (if any) + effective branch rules on
              main (drift check). Read-only, always exits 0 once the repo
              slug and ruleset list are fetched successfully.
  --enable    PUT the canonical ruleset body with enforcement=active.
              Requires the ruleset to already exist (run --apply first).
  --disable   PUT the canonical ruleset body with enforcement=disabled.
              This is the documented rollback: one PUT, re-opens the
              pre-queue window. Requires the ruleset to already exist.
  --apply     Create the ruleset if missing (POST, enforcement=disabled by
              default — activation is a deliberate separate --enable step,
              never a side effect of reconciling drift), else reconcile its
              rule content via PUT while preserving current enforcement.

Every subcommand resolves the repo slug live via `gh repo view` and never
echoes a secret. Any real GitHub API error (as opposed to "ruleset not found
by name", which is a valid state, not an error) propagates as a non-zero
exit via `set -e`.
USAGE
}

repo_slug() {
  gh repo view --json nameWithOwner --jq '.nameWithOwner'
}

# $1 = enforcement value ("active" | "disabled")
canonical_body() {
  local enforcement="$1"
  cat <<JSON
{
  "name": "${RULESET_NAME}",
  "target": "branch",
  "enforcement": "${enforcement}",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "merge_queue",
      "parameters": {
        "check_response_timeout_minutes": 90,
        "grouping_strategy": "ALLGREEN",
        "max_entries_to_build": 1,
        "max_entries_to_merge": 4,
        "merge_method": "SQUASH",
        "min_entries_to_merge": 1,
        "min_entries_to_merge_wait_minutes": 2
      }
    }
  ],
  "bypass_actors": []
}
JSON
}

# Prints the id of the ruleset named $RULESET_NAME in repo $1, or empty
# string if the list call succeeded but found no match. A genuine API
# failure of the underlying `gh api` call propagates via `set -e` — this
# function does not swallow it.
find_ruleset_id() {
  local repo="$1"
  gh api "repos/${repo}/rulesets" --jq ".[] | select(.name==\"${RULESET_NAME}\") | .id"
}

print_effective_rules() {
  local repo="$1"
  echo "--- Effective rules: repos/${repo}/rules/branches/main ---"
  gh api "repos/${repo}/rules/branches/main"
}

# Returns 1 (without treating it as a script-fatal error at the call site)
# if no ruleset with this name exists yet — that is a legitimate status to
# report for --status, and the precondition --enable/--disable check on.
print_ruleset() {
  local repo="$1" id="$2"
  if [[ -z "$id" ]]; then
    echo "Ruleset '${RULESET_NAME}' not found in ${repo}."
    return 1
  fi
  echo "--- Ruleset ${id} (${RULESET_NAME}) ---"
  gh api "repos/${repo}/rulesets/${id}" --jq '{id, name, enforcement, target, conditions, rules, bypass_actors}'
}

cmd_status() {
  local repo id
  repo="$(repo_slug)"
  echo "Repo: ${repo}"
  id="$(find_ruleset_id "$repo")"
  print_ruleset "$repo" "$id" || true
  print_effective_rules "$repo"
}

# $1 = target enforcement ("active" | "disabled")
cmd_set_enforcement() {
  local enforcement="$1"
  local repo id
  repo="$(repo_slug)"
  id="$(find_ruleset_id "$repo")"
  if [[ -z "$id" ]]; then
    echo "ERROR: ruleset '${RULESET_NAME}' not found in ${repo}. Run --apply first." >&2
    exit 1
  fi

  echo "=== BEFORE ==="
  print_effective_rules "$repo"

  echo "Setting enforcement=${enforcement} on ruleset ${id}..."
  canonical_body "$enforcement" | gh api --method PUT "repos/${repo}/rulesets/${id}" --input - >/dev/null

  echo "=== AFTER ==="
  print_effective_rules "$repo"
  echo "OK: ruleset ${id} enforcement=${enforcement}"
}

cmd_apply() {
  local repo id
  repo="$(repo_slug)"
  id="$(find_ruleset_id "$repo")"

  if [[ -z "$id" ]]; then
    echo "Ruleset '${RULESET_NAME}' not found in ${repo} — creating (enforcement=disabled by default)..."
    canonical_body "disabled" | gh api --method POST "repos/${repo}/rulesets" --input - >/dev/null
    echo "OK: created."
  else
    local current_enforcement
    current_enforcement="$(gh api "repos/${repo}/rulesets/${id}" --jq '.enforcement')"
    echo "Ruleset '${RULESET_NAME}' exists (id ${id}, enforcement=${current_enforcement}) — reconciling rule content via PUT, enforcement unchanged..."
    canonical_body "$current_enforcement" | gh api --method PUT "repos/${repo}/rulesets/${id}" --input - >/dev/null
    echo "OK: reconciled (enforcement unchanged: ${current_enforcement})."
  fi

  print_ruleset "$repo" "$(find_ruleset_id "$repo")"
}

case "${1:-}" in
  --status)
    cmd_status
    ;;
  --enable)
    cmd_set_enforcement "active"
    ;;
  --disable)
    cmd_set_enforcement "disabled"
    ;;
  --apply)
    cmd_apply
    ;;
  -h|--help|"")
    usage
    exit 0
    ;;
  *)
    echo "Unknown argument: $1" >&2
    usage
    exit 1
    ;;
esac
