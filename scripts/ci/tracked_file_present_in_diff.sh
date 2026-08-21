#!/usr/bin/env bash
# tracked_file_present_in_diff.sh <head_sha> <relative_path> <changed_files_file>
#
# Prints exactly one of: present | inherited | absent — never anything else,
# never a trailing newline variant, so a caller can safely do
# `case "$(tracked_file_present_in_diff.sh ...)" in present) ... esac`.
#
#   present   — the file exists in the tree at <head_sha> AND is a whole-line
#               match in <changed_files_file> (this diff genuinely authored
#               or edited it in this commit range).
#   inherited — the file exists in the tree at <head_sha> but is NOT in
#               <changed_files_file> — it is a tracked file at a fixed path
#               that a PRIOR merge left there, and this branch never touched
#               it. Distinct from "present" on purpose: a caller that treats
#               "exists in the tree" as "this PR's own" inherits whatever the
#               last PR to touch that path declared, repo-wide, forever.
#   absent    — the file does not exist in the tree at <head_sha> at all.
#               <changed_files_file>'s content is irrelevant in this case —
#               even a changed-files list that (falsely) claims the path was
#               touched cannot manufacture a file that isn't in the tree.
#
# Exit status is 0 on all three outcomes (each is a valid, expected state —
# "absent" is not a script failure). Exit 2 is a usage error (wrong argc) or
# an unreadable <changed_files_file>. This script never touches network — the
# caller is responsible for having already fetched <head_sha> into the local
# object store; an unresolvable SHA is the caller's fail-closed concern (see
# harness-floor.yml Step 4's own commit-resolution guard), not this script's.
#
# WHY THIS EXISTS AS A STANDALONE FILE, not inline in harness-floor.yml
# (independent Gear-3 review round 2, 2026-08-21, finding on PR #4539): round
# 1 fixed the tree-presence-vs-diff-membership defect (F1/F4) but left the fix
# living ONLY as two inline `if` conditions duplicated in the YAML (Step 4 for
# evidence/brief.yml, Step 7b for evidence/pack.yml), pinned by a *test that
# reimplemented the same two-line idiom itself* rather than exercising the
# real workflow code. Round 2 verified this the hard way: reverting BOTH
# inline conditions in harness-floor.yml left every test in this repo green —
# the test file's own private copy of the logic was the only thing being
# tested. A test that never imports the code it claims to pin is not a pin
# (cicatrix-superscar.md #6, "phantom citations" — here the phantom is not a
# file, it's a claimed coverage relationship). Fix: extract the check into
# THIS script (same shape as scripts/ci/hotzone_changed_files.sh /
# vercel_should_build.sh, both already `run:`-invoked from workflow YAML
# rather than reimplemented inline), have harness-floor.yml's Step 4 and Step
# 7b call it, and have the test corpus invoke this exact file — so a mutation
# HERE, and only here, is what the workflow and the test both see.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: tracked_file_present_in_diff.sh <head_sha> <relative_path> <changed_files_file>" >&2
  exit 2
fi

SHA="$1"
REL_PATH="$2"
CHANGED_FILES_FILE="$3"

if [[ ! -r "$CHANGED_FILES_FILE" ]]; then
  echo "tracked_file_present_in_diff.sh: cannot read changed-files file: $CHANGED_FILES_FILE" >&2
  exit 2
fi

if git cat-file -e "${SHA}:${REL_PATH}" 2>/dev/null; then
  if grep -qxF "$REL_PATH" "$CHANGED_FILES_FILE"; then
    echo "present"
  else
    echo "inherited"
  fi
else
  echo "absent"
fi
