#!/usr/bin/env bash
# hotzone_changed_files.sh — enumerate the files a PR *itself* changed.
#
# WHY THIS EXISTS (scar 2026-07-24, superscar #9 "il proxy mente sullo stato"):
#   hot-zone-pr-gate.yml used `git diff --name-only "$BASE_SHA" "$HEAD_SHA"` —
#   a TWO-DOT diff between the two tips. `github.event.pull_request.base.sha` is
#   the CURRENT tip of main, so for any branch that is behind main the two-dot
#   diff also lists, as "changed", every file MAIN gained since the branch point
#   (in reverse). PR #3057 (2 content MDX files, author SubBZ2026) was therefore
#   reported as touching `.github/CODEOWNERS` + 3 workflows + a migration, and the
#   CODEOWNERS self-mod gate hard-blocked an innocent PR. The gate was not wrong
#   about its rule — its INPUT was a lying proxy.
#
# THE FIX: anchor on the merge-base (three-dot semantics), which is exactly what
#   GitHub's own "Files changed" tab shows: "what did this branch author since it
#   diverged", never "how does this branch differ from main's tip".
#
#   NB for future readers: cicatrix W88 warns that `git diff main...branch` lies —
#   that warning is about a DIFFERENT question ("is this content already on main
#   after a squash?"), where the merge-base is stale by construction. Here the
#   question is "what did this PR author?", and merge-base anchoring is the
#   correct answer. Do not "fix" this back to two-dot.
#
# FAIL-LOUD, NEVER BLIND (superscar #2): if the merge-base cannot be resolved we
#   deepen the fetch, then fall back to the PR files API, and only then exit
#   non-zero. We never emit an empty list on failure — an empty list would make
#   every downstream hot-zone check silently pass (a disarmed gate that still
#   reports green).
#
# Usage:  hotzone_changed_files.sh <BASE_SHA> <HEAD_SHA> [PR_NUMBER]
# Output: one path per line on stdout; diagnostics on stderr.
# Exit:   0 = list produced (possibly empty because the PR is genuinely empty)
#         3 = could not determine the changed set (caller MUST treat as failure)
set -uo pipefail

BASE_SHA="${1:-}"
HEAD_SHA="${2:-}"
PR_NUMBER="${3:-}"

if [[ -z "$BASE_SHA" || -z "$HEAD_SHA" ]]; then
  echo "hotzone_changed_files: BASE_SHA and HEAD_SHA are required" >&2
  exit 3
fi

log() { echo "hotzone_changed_files: $*" >&2; }

# --- 1. Make sure both endpoints are present locally ------------------------
if ! git cat-file -e "${HEAD_SHA}^{commit}" 2>/dev/null; then
  git fetch --no-tags --depth=200 origin "$HEAD_SHA" >/dev/null 2>&1 || true
fi
if ! git cat-file -e "${BASE_SHA}^{commit}" 2>/dev/null; then
  git fetch --no-tags origin "$BASE_SHA" >/dev/null 2>&1 || true
fi

# --- 2. Resolve the merge-base, deepening if the history is shallow ---------
merge_base=""
resolve_merge_base() {
  git merge-base "$BASE_SHA" "$HEAD_SHA" 2>/dev/null
}
merge_base="$(resolve_merge_base)"

if [[ -z "$merge_base" ]]; then
  log "merge-base not reachable — deepening history"
  if [[ -f "$(git rev-parse --git-dir)/shallow" ]]; then
    git fetch --unshallow --no-tags origin >/dev/null 2>&1 \
      || git fetch --deepen=1000 --no-tags origin >/dev/null 2>&1 \
      || true
  else
    git fetch --no-tags origin >/dev/null 2>&1 || true
  fi
  merge_base="$(resolve_merge_base)"
fi

# --- 3. Emit the branch-authored file set -----------------------------------
if [[ -n "$merge_base" ]]; then
  log "merge-base $merge_base (base $BASE_SHA, head $HEAD_SHA)"
  git diff --name-only "$merge_base" "$HEAD_SHA"
  exit 0
fi

# --- 4. Fallback: ask GitHub for the authoritative PR file list -------------
if [[ -n "$PR_NUMBER" && -n "${GITHUB_REPOSITORY:-}" ]] && command -v gh >/dev/null 2>&1; then
  log "merge-base unresolvable — falling back to PR files API for #$PR_NUMBER"
  if api_out="$(gh api --paginate \
        "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/files" \
        --jq '.[].filename' 2>/dev/null)"; then
    printf '%s\n' "$api_out"
    exit 0
  fi
  log "PR files API call failed"
fi

log "FATAL: cannot determine changed files — refusing to emit a blind-empty list"
exit 3
