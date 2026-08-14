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
# HIGH-5 (red-team 2026-08-14): `git diff` was followed by an UNCONDITIONAL
#   `exit 0` — if git printed a partial list of files and then died partway
#   (killed, corrupt pack, whatever), the caller still saw exit 0 and treated
#   the partial list as complete: a silently-truncated PR file set, which is
#   exactly the "blind pass" this script's own header promises never to do.
#   Fix: capture git diff's own exit status via `if`, and only exit 0 when it
#   actually succeeded; otherwise fall through to the PR-files-API fallback
#   (and eventually the fail-loud exit 3 below) instead of trusting a partial
#   stdout. Deliberately not `set -e` for this (see file-level `set -uo
#   pipefail` and W101 in cicatrix-superscar.md — several fetches above are
#   intentionally non-fatal via `|| true`; a blanket `-e` would break those).
# HIGH-6 (red-team 2026-08-14, same line): `git diff --name-only` without
#   `--no-renames` can collapse a rename to just the destination path,
#   depending on the runner's `diff.renames` config — a hot-zone gate keyed
#   on the OLD path (e.g. a CODEOWNERS-protected file moved out from under
#   review) would then miss it. `--no-renames` makes every rename emit both
#   the deleted source and the added destination, deterministically,
#   independent of ambient git config.
if [[ -n "$merge_base" ]]; then
  log "merge-base $merge_base (base $BASE_SHA, head $HEAD_SHA)"
  if git diff --no-renames --name-only "$merge_base" "$HEAD_SHA"; then
    exit 0
  fi
  log "git diff failed after merge-base resolution — refusing partial output as a blind pass"
fi

# --- 4. Fallback: ask GitHub for the authoritative PR file list -------------
# HIGH-6: the API fallback emitted only `.filename`, which for a renamed file
#   is the DESTINATION only — dropping `.previous_filename` loses the same
#   old-path information the --no-renames fix above restores on the git path.
#   `// empty` on jq means a non-renamed file (no `.previous_filename` field)
#   contributes nothing extra; a renamed file contributes both paths.
# MEDIUM-11: GitHub's PR-files REST endpoint has a documented hard cap of
#   3000 files, even with `--paginate` — a PR that touches exactly 3000 files
#   is indistinguishable from one truncated AT the cap. Trusting an
#   exactly-3000-entry result as "complete" could silently drop files past
#   the cap from every downstream hot-zone/change-map decision. Count FILE
#   ENTRIES, not output lines — a rename emits two lines (old + new path) for
#   one entry, so a naive line count would need 1500 renames to false-trigger
#   at 3000 and would false-negative a genuine 3000-entry all-renames PR at
#   6000 lines. Capture one compact JSON object per line first (`--jq '.[]'`,
#   gh's default compact-per-line output), slurp with `jq -s length` for the
#   true entry count, THEN re-derive filename/previous_filename from the same
#   captured stream — one API call, two local jq passes.
if [[ -n "$PR_NUMBER" && -n "${GITHUB_REPOSITORY:-}" ]] && command -v gh >/dev/null 2>&1; then
  log "merge-base unresolvable — falling back to PR files API for #$PR_NUMBER"
  if api_entries="$(gh api --paginate \
        "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/files" \
        --jq '.[]' 2>/dev/null)"; then
    api_entry_count="$(printf '%s\n' "$api_entries" | jq -s 'length')"
    if [[ "$api_entry_count" -eq 3000 ]]; then
      log "PR files API returned exactly 3000 entries — indistinguishable from GitHub's documented per-PR cap, refusing to trust it as complete"
    else
      printf '%s\n' "$api_entries" | jq -r '(.filename, (.previous_filename // empty))'
      exit 0
    fi
  else
    log "PR files API call failed"
  fi
fi

log "FATAL: cannot determine changed files — refusing to emit a blind-empty list"
exit 3
