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
# exists (id 19779175, created 2026-07-27 via API) and enforcement was flipped
# to `active` the same day (~01:00Z; proof: first queue-merged SHA 7aab65b1ee,
# 25/25 required contexts SUCCESS) — this script is the reconciler/toggle for
# it going forward, not a first-apply.
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

# S5 ARM-half additions (scripts/ci/check_base_protected.py is the CHECK-half).
# A separate ruleset name/purpose from $RULESET_NAME above: that one governs
# merge_group queue MECHANICS for main (grouping/batching) and carries no
# required_status_checks rule at all — main's actual required checks live in
# CLASSIC branch protection, which cannot glob-match a branch that doesn't
# exist yet. This ruleset instead protects a *pattern* of integration branch
# (e.g. refs/heads/feature/*) with a required_status_checks rule, since that's
# the one mechanism that auto-applies to a branch created after the ruleset.
INTEGRATION_RULESET_NAME="integration-branch-protection"
MIN_CONTEXTS_JSON="infra/required.d/integration-branch-minimum-contexts.json"

usage() {
  cat <<'USAGE'
Usage: setup_merge_queue_ruleset.sh --status | --enable | --disable | --apply
       setup_merge_queue_ruleset.sh --branch-pattern <pattern> [--apply]

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

  --branch-pattern <pattern>
              S5 ARM-half (scripts/ci/check_base_protected.py is the CHECK-
              half): create/reconcile a SEPARATE ruleset named
              "integration-branch-protection", scoped to
              refs/heads/<pattern> (e.g. 'feature/*'), carrying a
              required_status_checks rule seeded from
              infra/required.d/integration-branch-minimum-contexts.json.
              WITHOUT --apply this only PRINTS the `gh api` body + command it
              would run — no mutation, safe to call from a CI check or a
              read-only session. WITH --apply it actually creates it
              (enforcement=disabled, same "activation is a separate step"
              posture as --apply above — there is no --branch-pattern
              --enable in this version; flip enforcement by hand once ready:
              reconcile with --apply again after editing this script's
              INTEGRATION_RULESET_NAME lookup, or extend cmd_set_enforcement
              to take a ruleset name). One pattern per invocation — running
              it again with a different pattern REPLACES the include list
              (whole-object PUT, see the canonical_body() comment above).
              This is a repo-settings mutation: --apply is operator[control-
              plane], never run by the CI check itself.

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
#
# NOTE — `max_entries_to_build` (do not lower it back to 1 without reading this).
# It is how many queue entries GitHub builds — creates a merge-group ref for and
# runs checks on — CONCURRENTLY. At 1 the queue is strictly SERIAL: entry N's ~20
# minutes of checks begin only after N-1 merges or is ejected, which caps the repo
# at roughly 3 PRs/hour no matter how fast everything upstream is. Measured live
# 2026-07-27: 6 entries waiting, nothing merged for 51 minutes, one entry
# AWAITING_CHECKS and five idle. Raised to 5 and five went AWAITING_CHECKS at once.
#
# Raising it is safe here for one specific reason, which is a precondition and not
# a property of the number: every workflow triggering on `merge_group` keys its
# concurrency group on `github.ref`, which for a queue entry is the unique
# `refs/gh-readonly-queue/main/pr-N-<sha>`, and sets `cancel-in-progress` false for
# merge_group (PR #3285). With a SHARED group key instead, parallel builds would
# cancel each other and the queue would eat its own verdicts — silently, since a
# cancelled run reports no failure. Re-check that invariant before raising further.
# Cost is only rebuilds when an early entry is ejected, and GitHub-hosted runners
# are free on a public repo.
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
        "max_entries_to_build": 5,
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

# $1 = branch pattern (e.g. "feature/*"), $2 = enforcement ("active"|"disabled").
# Builds the S5 ARM-half ruleset body via python3 (not jq — `gh --jq` embeds
# gojq, no standalone `jq` binary is guaranteed on every runner/machine this
# script targets, and python3 already is a hard dependency across this repo's
# scripts/ci/*.py siblings). Reads the pinned minimum contexts from
# $MIN_CONTEXTS_JSON so this script and check_base_protected.py never drift —
# one SSOT, not two hand-maintained lists.
integration_body() {
  local pattern="$1" enforcement="$2"
  BRANCH_PATTERN="$pattern" ENFORCEMENT="$enforcement" MIN_CONTEXTS_JSON="$MIN_CONTEXTS_JSON" \
    python3 - <<'PYEOF'
import json
import os

with open(os.environ["MIN_CONTEXTS_JSON"], encoding="utf-8") as fh:
    minimum_contexts = json.load(fh)["minimum_contexts"]

body = {
    "name": "integration-branch-protection",
    "target": "branch",
    "enforcement": os.environ["ENFORCEMENT"],
    "conditions": {
        "ref_name": {
            "include": [f"refs/heads/{os.environ['BRANCH_PATTERN']}"],
            "exclude": [],
        }
    },
    "rules": [
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [
                    {"context": c, "integration_id": None} for c in minimum_contexts
                ],
            },
        }
    ],
    "bypass_actors": [],
}
print(json.dumps(body, indent=2))
PYEOF
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

# $1 = branch pattern, $2 = "true"|"false" (--apply given or not).
# Print-only by default (no `gh api --method POST/PUT` call at all unless
# apply="true") — this is what lets check_base_protected.py's failure message
# safely print the equivalent command line for an operator to run, and what
# lets THIS script itself be invoked read-only from a CI job without risking
# a repo-settings mutation from an unattended context.
cmd_branch_pattern() {
  local pattern="$1" apply="$2"
  local repo id enforcement body

  if [[ -z "$pattern" ]]; then
    echo "ERROR: --branch-pattern requires a value, e.g. --branch-pattern 'feature/*'" >&2
    exit 1
  fi

  repo="$(repo_slug)"
  id="$(gh api "repos/${repo}/rulesets" --jq ".[] | select(.name==\"${INTEGRATION_RULESET_NAME}\") | .id")"

  if [[ "$apply" != "true" ]]; then
    echo "DRY RUN — nothing executed. Add --apply to actually create/reconcile this ruleset."
    echo
    if [[ -z "$id" ]]; then
      body="$(integration_body "$pattern" "disabled")"
      echo "Would run (ruleset does not exist yet):"
      echo "  gh api --method POST repos/${repo}/rulesets --input - <<'JSON'"
      echo "$body"
      echo "JSON"
    else
      enforcement="$(gh api "repos/${repo}/rulesets/${id}" --jq '.enforcement')"
      body="$(integration_body "$pattern" "$enforcement")"
      echo "Ruleset '${INTEGRATION_RULESET_NAME}' already exists (id ${id}, enforcement=${enforcement}). Would run:"
      echo "  gh api --method PUT repos/${repo}/rulesets/${id} --input - <<'JSON'"
      echo "$body"
      echo "JSON"
    fi
    return 0
  fi

  # --apply: mirrors cmd_apply()'s idempotent create-or-reconcile posture —
  # a NEW ruleset is created with enforcement=disabled (activation stays a
  # deliberate, separate, manual step: edit the enforcement value by hand and
  # re-run --apply, or extend cmd_set_enforcement to take a ruleset name —
  # not built here, out of this PR's scope).
  if [[ -z "$id" ]]; then
    echo "Ruleset '${INTEGRATION_RULESET_NAME}' not found in ${repo} — creating (enforcement=disabled by default)..."
    integration_body "$pattern" "disabled" | gh api --method POST "repos/${repo}/rulesets" --input - >/dev/null
    echo "OK: created, enforcement=disabled. Flip it active only once ready (deliberate, manual)."
  else
    enforcement="$(gh api "repos/${repo}/rulesets/${id}" --jq '.enforcement')"
    echo "Ruleset '${INTEGRATION_RULESET_NAME}' exists (id ${id}, enforcement=${enforcement}) — reconciling rule content via PUT, enforcement unchanged..."
    integration_body "$pattern" "$enforcement" | gh api --method PUT "repos/${repo}/rulesets/${id}" --input - >/dev/null
    echo "OK: reconciled (enforcement unchanged: ${enforcement})."
  fi
  id="$(gh api "repos/${repo}/rulesets" --jq ".[] | select(.name==\"${INTEGRATION_RULESET_NAME}\") | .id")"
  print_ruleset "$repo" "$id"
}

if [[ "${1:-}" == "--branch-pattern" ]]; then
  _pattern="${2:-}"
  _apply="false"
  case "${3:-}" in
    --apply) _apply="true" ;;
    "") ;;
    *)
      echo "Unknown argument after --branch-pattern <pattern>: $3" >&2
      usage
      exit 1
      ;;
  esac
  cmd_branch_pattern "$_pattern" "$_apply"
  exit 0
fi

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
