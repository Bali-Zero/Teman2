#!/usr/bin/env bash
# Guilt + innocence corpus for scripts/ci/tracked_file_present_in_diff.sh,
# the check harness-floor.yml's Step 4 (evidence/brief.yml) and Step 7b
# (evidence/pack.yml) both call.
#
# WHY THIS EXISTS (independent Gear-3 review round 1, 2026-08-21, finding F1
# CRITICAL + F4 MEDIUM, same defect on the pack side): the workflow used to
# test tree PRESENCE only (`git cat-file -e "$HEAD_SHA:evidence/brief.yml"`).
# But evidence/brief.yml is a tracked file at a FIXED repo-root path —
# whatever the last merged Gear-3 PR left there is inherited by every
# subsequent branch, whether or not that branch ever touches it. Under the
# old never-fails Step 7c this was harmless; under the new read-based Step
# 7c it would have turned EVERY PR in the repo (all of which inherit the
# last Gear-3 PR's leftover brief) into a Gear-3-gated PR, repo-wide.
# Verified live during review: `evidence/brief.yml` on origin/main declares
# `gear: 3` for PR #4474's task, and a single-file docs-ledger PR inherits
# it verbatim.
#
# CORRECTED 2026-08-21 (independent Gear-3 review ROUND 2, same PR #4539):
# round 1's fix was two inline `if` conditions in harness-floor.yml, and
# THIS test file pinned them by *reimplementing the same two-line idiom
# itself* (`brief_present()`, a private copy) rather than exercising the
# workflow's actual code. Round 2 verified the gap the hard way: reverting
# BOTH inline conditions in harness-floor.yml left this entire test suite
# green, because nothing here ever imported or ran the code under review —
# a test that never touches the file it claims to pin is not a pin. Fix:
# the check now lives in scripts/ci/tracked_file_present_in_diff.sh (a
# standalone, `run:`-invoked script — same shape as the sibling
# hotzone_changed_files.sh this file's own precedent already used), and
# THIS test invokes that exact file. A mutation to the real script is what
# this corpus now catches; harness-floor.yml calling anything other than
# that script is a change this corpus cannot see (that gap is the workflow
# YAML's own concern — actionlint + the pack-lint step's --changed-files-file
# argument, not this file's job).
#
# GUILT     — evidence/brief.yml exists at HEAD (inherited from a prior
#             merge) but is NOT in this PR's own changed-files list ->
#             "inherited", never "present".
# INNOCENCE — evidence/brief.yml exists at HEAD AND is in the PR's own
#             changed-files list (this PR genuinely authored it) ->
#             "present".
# GUILT-2   — evidence/brief.yml does not exist at HEAD at all -> "absent",
#             regardless of the changed-files list content (a
#             malformed/empty changed-files.txt must never manufacture a
#             false positive).
#
# Runs in any POSIX-ish shell with git. No network, no fixtures on disk.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNDER_TEST="$SCRIPT_DIR/../ci/tracked_file_present_in_diff.sh"
FAILURES=0

fail() { echo "  ✗ $*"; FAILURES=$((FAILURES + 1)); }
pass() { echo "  ✓ $*"; }

if [[ ! -x "$UNDER_TEST" ]]; then
  echo "FATAL: $UNDER_TEST missing or not executable"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --------------------------------------------------------------- fixture repo
# main ──●(has evidence/brief.yml from a PRIOR Gear-3 PR, and an unrelated
#          content.txt)
#          \
#           ●  branch-untouched   (edits ONLY content.txt — never touches
#                                   evidence/brief.yml at all)
#           ●  branch-authored    (edits evidence/brief.yml itself)
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email test@example.com
git config user.name "harness-floor test"
git config commit.gpgsign false

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

run_under_test() {  # run_under_test <head_sha> <changed_files_file>
  bash "$UNDER_TEST" "$1" evidence/brief.yml "$2"
}

# --- GUILT: inherited-but-untouched brief must read "inherited" ---
printf 'content.txt\n' > "$TMP/changed-untouched.txt"
RESULT="$(run_under_test "$UNTOUCHED_SHA" "$TMP/changed-untouched.txt")"
if [[ "$RESULT" == "inherited" ]]; then
  pass "guilt: inherited evidence/brief.yml, NOT in this PR's diff -> inherited"
else
  fail "guilt: inherited evidence/brief.yml, NOT in this PR's diff -> got '$RESULT', expected inherited (F1 regression)"
fi

# --- INNOCENCE: self-authored brief must read "present" ---
printf 'evidence/brief.yml\n' > "$TMP/changed-authored.txt"
RESULT="$(run_under_test "$AUTHORED_SHA" "$TMP/changed-authored.txt")"
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
RESULT="$(run_under_test "$NO_BRIEF_SHA" "$TMP/changed-lying.txt")"
if [[ "$RESULT" == "absent" ]]; then
  pass "guilt: no evidence/brief.yml in the tree at all -> absent regardless of changed-files content"
else
  fail "guilt: no evidence/brief.yml in the tree at all -> got '$RESULT', expected absent"
fi

# --- Whole-line match discipline: grep -x must not partial-match a longer path ---
printf 'evidence/brief.yml.bak\nsome/evidence/brief.yml\n' > "$TMP/changed-similar.txt"
RESULT="$(run_under_test "$AUTHORED_SHA" "$TMP/changed-similar.txt")"
if [[ "$RESULT" == "inherited" ]]; then
  pass "guilt: changed-files list has only near-miss paths (not the exact one) -> inherited (present in tree, not this diff)"
else
  fail "guilt: near-miss paths in changed-files.txt should not satisfy the exact-match -> got '$RESULT'"
fi

# --- SCAR-PIN: the file this test exercises must be the one the workflow
#     actually calls — a rename/relocation of the real script that this
#     test's own $UNDER_TEST path silently kept pointing at a stale copy
#     would defeat the whole point of round 2's fix. Cheap, exact grep on
#     the live workflow YAML, not a semantic parse. ---
WORKFLOW="$SCRIPT_DIR/../../.github/workflows/harness-floor.yml"
if [[ -f "$WORKFLOW" ]] && grep -q "scripts/ci/tracked_file_present_in_diff.sh" "$WORKFLOW"; then
  pass "scar-pin: harness-floor.yml actually calls scripts/ci/tracked_file_present_in_diff.sh"
else
  fail "scar-pin: harness-floor.yml does NOT reference scripts/ci/tracked_file_present_in_diff.sh — this test would be pinning a script the workflow no longer calls"
fi

# --- Second-order regression pin: mutate the REAL script (a copy of it) to
#     the pre-round-2 tree-presence-only behavior and confirm THIS test
#     corpus (run against the mutant) goes red — proves the corpus is not
#     vacuously green the same way round 2 found the old one to be. ---
MUTANT_DIR="$TMP/mutant"
mkdir -p "$MUTANT_DIR"
MUTANT="$MUTANT_DIR/tracked_file_present_in_diff.sh"
cat > "$MUTANT" <<'MUTEOF'
#!/usr/bin/env bash
set -euo pipefail
SHA="$1"; REL_PATH="$2"
if git cat-file -e "${SHA}:${REL_PATH}" 2>/dev/null; then
  echo "present"
else
  echo "absent"
fi
MUTEOF
chmod +x "$MUTANT"
MUTANT_RESULT="$(bash "$MUTANT" "$UNTOUCHED_SHA" evidence/brief.yml "$TMP/changed-untouched.txt" 2>/dev/null || true)"
if [[ "$MUTANT_RESULT" == "present" ]]; then
  pass "scar-pin: the pre-round-2 tree-presence-only mutant DOES misreport inherited-as-present (proves this corpus would catch that regression)"
else
  fail "scar-pin: expected the mutant to misreport 'present' for an inherited-but-untouched brief (got '$MUTANT_RESULT') — the scar-pin itself is broken"
fi

echo ""
if (( FAILURES > 0 )); then
  echo "FAIL: $FAILURES failure(s)"
  exit 1
fi
echo "PASS"
