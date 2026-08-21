#!/usr/bin/env bash
# Guilt + innocence corpus for harness-floor.yml's Step 4 / Step 7b "does THIS
# PR'S OWN DIFF carry evidence/brief.yml (and pack.yml)" check.
#
# WHY THIS EXISTS (independent Gear-3 review, 2026-08-21, finding F1 CRITICAL
# + F4 MEDIUM, same defect on the pack side): the workflow used to test tree
# PRESENCE only (`git cat-file -e "$HEAD_SHA:evidence/brief.yml"`). But
# evidence/brief.yml is a tracked file at a FIXED repo-root path — whatever
# the last merged Gear-3 PR left there is inherited by every subsequent
# branch, whether or not that branch ever touches it. Under the old
# never-fails Step 7c this was harmless; under the new read-based Step 7c it
# would have turned EVERY PR in the repo (all of which inherit the last
# Gear-3 PR's leftover brief) into a Gear-3-gated PR, repo-wide. Verified
# live during review: `evidence/brief.yml` on origin/main declares
# `gear: 3` for PR #4474's task, and a single-file docs-ledger PR inherits
# it verbatim.
#
# THE FIX this pins: `brief.present` (and, symmetrically, the pack.yml
# validation gate) requires BOTH tree presence AND membership in the PR's
# own merge-base-anchored changed-files set — exactly the two-line shell
# idiom this test exercises directly, isolated from the surrounding
# workflow YAML so it can be guilt/innocence-tested without a live Actions
# run.
#
# GUILT     — evidence/brief.yml exists at HEAD (inherited from a prior
#             merge) but is NOT in this PR's own changed-files list -> the
#             combined check reports "not this PR's brief".
# INNOCENCE — evidence/brief.yml exists at HEAD AND is in the PR's own
#             changed-files list (this PR genuinely authored it) -> reports
#             "present".
# GUILT-2   — evidence/brief.yml does not exist at HEAD at all -> reports
#             "not present", regardless of the changed-files list content
#             (a malformed/empty changed-files.txt must never manufacture a
#             false positive).
#
# Runs in any POSIX-ish shell with git. No network, no fixtures on disk.
set -uo pipefail

FAILURES=0
fail() { echo "  ✗ $*"; FAILURES=$((FAILURES + 1)); }
pass() { echo "  ✓ $*"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email test@example.com
git config user.name "harness-floor test"
git config commit.gpgsign false

# --------------------------------------------------------------- fixture repo
# main ──●(has evidence/brief.yml from a PRIOR Gear-3 PR, and an unrelated
#          content.txt)
#          \
#           ●  branch-untouched   (edits ONLY content.txt — never touches
#                                   evidence/brief.yml at all)
#           ●  branch-authored    (edits evidence/brief.yml itself)
mkdir -p evidence
printf 'task_id: prior-pr\ngear: 3\n' > evidence/brief.yml
printf 'unrelated content\n' > content.txt
git add -A && git commit -qm "main: prior Gear-3 PR leaves its brief in the tree"
MAIN_SHA="$(git rev-parse HEAD)"

git checkout -qb branch-untouched "$MAIN_SHA"
printf 'unrelated content, v2\n' > content.txt
git add -A && git commit -qm "branch-untouched: only touches content.txt"
UNTOUCHED_SHA="$(git rev-parse HEAD)"

git checkout -qb branch-authored "$MAIN_SHA"
printf 'task_id: this-pr\ngear: 3\n' > evidence/brief.yml
git add -A && git commit -qm "branch-authored: writes its own brief"
AUTHORED_SHA="$(git rev-parse HEAD)"

# THE CHECK UNDER TEST — verbatim two-line shape from harness-floor.yml Step 4
# (and, with the filename swapped, Step 7b). CHANGED_FILES_FILE stands in for
# /tmp/changed-files.txt, produced upstream by the merge-base-anchored
# enumerator (scripts/ci/hotzone_changed_files.sh) — this test does not
# re-derive it (that enumerator has its own corpus,
# scripts/ci/test_hotzone_changed_files.sh), it consumes a hand-built one, the
# same way the workflow step consumes the enumerator's real output.
brief_present() {  # brief_present <head_sha> <changed_files_file>
  local sha="$1" cf="$2"
  if git cat-file -e "$sha:evidence/brief.yml" 2>/dev/null && grep -qxF "evidence/brief.yml" "$cf"; then
    echo "present"
  else
    echo "absent"
  fi
}

# --- GUILT: inherited-but-untouched brief must read absent ---
printf 'content.txt\n' > "$TMP/changed-untouched.txt"
RESULT="$(brief_present "$UNTOUCHED_SHA" "$TMP/changed-untouched.txt")"
if [[ "$RESULT" == "absent" ]]; then
  pass "guilt: inherited evidence/brief.yml, NOT in this PR's diff -> absent"
else
  fail "guilt: inherited evidence/brief.yml, NOT in this PR's diff -> got '$RESULT', expected absent (F1 regression)"
fi

# --- INNOCENCE: self-authored brief must read present ---
printf 'evidence/brief.yml\n' > "$TMP/changed-authored.txt"
RESULT="$(brief_present "$AUTHORED_SHA" "$TMP/changed-authored.txt")"
if [[ "$RESULT" == "present" ]]; then
  pass "innocence: this PR's own diff touches evidence/brief.yml -> present"
else
  fail "innocence: this PR's own diff touches evidence/brief.yml -> got '$RESULT', expected present"
fi

# --- GUILT-2: no brief in tree at all, even if changed-files.txt lies ---
git checkout -qb branch-no-brief "$MAIN_SHA"
git rm -q evidence/brief.yml
git commit -qm "branch-no-brief: removes the inherited brief entirely"
NO_BRIEF_SHA="$(git rev-parse HEAD)"
printf 'evidence/brief.yml\n' > "$TMP/changed-lying.txt" # malformed/adversarial input
RESULT="$(brief_present "$NO_BRIEF_SHA" "$TMP/changed-lying.txt")"
if [[ "$RESULT" == "absent" ]]; then
  pass "guilt: no evidence/brief.yml in the tree at all -> absent regardless of changed-files content"
else
  fail "guilt: no evidence/brief.yml in the tree at all -> got '$RESULT', expected absent"
fi

# --- Whole-line match discipline: grep -x must not partial-match a longer path ---
printf 'evidence/brief.yml.bak\nsome/evidence/brief.yml\n' > "$TMP/changed-similar.txt"
RESULT="$(brief_present "$AUTHORED_SHA" "$TMP/changed-similar.txt")"
if [[ "$RESULT" == "absent" ]]; then
  pass "guilt: changed-files list has only near-miss paths (not the exact one) -> absent"
else
  fail "guilt: near-miss paths in changed-files.txt should not satisfy the exact-match -> got '$RESULT'"
fi

echo ""
if (( FAILURES > 0 )); then
  echo "FAIL: $FAILURES failure(s)"
  exit 1
fi
echo "PASS"
