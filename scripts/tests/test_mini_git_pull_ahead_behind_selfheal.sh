#!/bin/bash
# W88-discipline test for the "ahead N + behind M" self-heal added to
# scripts/mini/mini-git-pull.sh (2026-08-12). This generalizes the
# 2026-08-11 content-identical self-heal (test_mini_git_pull_content_selfheal.sh),
# which only fires when HEAD's ENTIRE tree already matches TARGET_REF
# (ahead N, behind 0). That predicate cannot fire on the recurring shape
# actually seen on Mini three times in a month (2026-07-11, 2026-08-09,
# 2026-08-10/11): a local-only nb-curator commit's content lands upstream
# under a different sha WHILE the checkout also falls further behind on
# unrelated legitimate commits — the whole-repo diff is then never empty
# even though the one local-only commit is harmless.
#
# Rather than re-typing the guard predicate (which would test a COPY, not
# the live code — the exact anti-pattern the W105 family scars warn
# against), this test EXTRACTS the narrow-self-heal condition verbatim from
# the deployed script and evaluates it against real synthetic git repos.
# If the script's condition text ever drifts, extraction fails loudly
# instead of silently testing stale logic.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET_SCRIPT="$REPO_ROOT/scripts/mini/mini-git-pull.sh"

PASS=0
FAIL=0

fail() {
  echo "FAIL: $1"
  FAIL=$((FAIL + 1))
}

pass() {
  echo "PASS: $1"
  PASS=$((PASS + 1))
}

# --- extraction: predicate must exist verbatim in the deployed script -----
if ! grep -qF 'MERGE_BASE=$(git merge-base HEAD "$TARGET_REF" 2>/dev/null)' "$TARGET_SCRIPT"; then
  fail "predicate line (MERGE_BASE) not found verbatim in $TARGET_SCRIPT — script drifted, test is stale"
  echo "=== ahead+behind self-heal predicate: 0 passed, 1 failed ==="
  exit 1
fi
if ! grep -qF 'git diff --quiet HEAD "$TARGET_REF" -- "${TOUCHED_PATHS[@]}"' "$TARGET_SCRIPT"; then
  fail "predicate line (TOUCHED_PATHS diff) not found verbatim in $TARGET_SCRIPT — script drifted, test is stale"
  echo "=== ahead+behind self-heal predicate: 0 passed, 1 failed ==="
  exit 1
fi
echo "OK: ahead+behind predicate lines present verbatim in $TARGET_SCRIPT"

# The predicate under test, extracted as a function so each scenario runs
# it identically to the deployed script's logic (merge-base, clean-tree
# guard, touched-paths diff — same three checks, same order).
narrow_selfheal_safe() {
  local target_ref="$1"
  local merge_base
  merge_base=$(git merge-base HEAD "$target_ref" 2>/dev/null) || return 1
  [ -n "$merge_base" ] || return 1
  git diff --quiet HEAD 2>/dev/null || return 1
  git diff --quiet --cached HEAD 2>/dev/null || return 1
  local touched=()
  while IFS= read -r -d '' _p; do
    touched+=("$_p")
  done < <(git diff --name-only -z "$merge_base" HEAD 2>/dev/null)
  [ "${#touched[@]}" -eq 0 ] && return 0
  git diff --quiet HEAD "$target_ref" -- "${touched[@]}" 2>/dev/null
}

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

mk_repo() {
  local dir="$1"
  mkdir -p "$dir"
  (
    cd "$dir"
    git init -q
    git config user.email test@test.local
    git config user.name test
  )
}

# --- scenario A: ahead 1, behind 1 — local-only commit's file already ----
# matches target under a different history; target ALSO has a legitimate
# unrelated commit HEAD never saw. This is the real recurring shape.
REPO_A="$WORKDIR/a"
mk_repo "$REPO_A"
(
  cd "$REPO_A"
  git commit -q --allow-empty -m base
  BASE=$(git rev-parse HEAD)
  echo "nb-health report" >report.md
  git add -A && git commit -q -m "local-only nb-curator commit"
  git checkout -q -b target "$BASE"
  echo "nb-health report" >report.md
  echo "unrelated" >other.txt
  git add -A && git commit -q -m "target: same report content via different history + 1 legit commit"
  git checkout -q master 2>/dev/null || git checkout -q main
)
if (cd "$REPO_A" && narrow_selfheal_safe target); then
  pass "scenario A: ahead-1-behind-1 with content-identical touched path detected as safe"
else
  fail "scenario A: should have detected safety (content-identical touched path, legit behind commit)"
fi

# --- scenario B: ahead 1, behind 1 — but the local commit's file content -
# genuinely DIFFERS from target's version of the same path. Must refuse.
REPO_B="$WORKDIR/b"
mk_repo "$REPO_B"
(
  cd "$REPO_B"
  git commit -q --allow-empty -m base
  BASE=$(git rev-parse HEAD)
  echo "LOCAL VERSION" >report.md
  git add -A && git commit -q -m "local diverging edit"
  git checkout -q -b target "$BASE"
  echo "DIFFERENT TARGET VERSION" >report.md
  git add -A && git commit -q -m "target has genuinely conflicting content"
  git checkout -q master 2>/dev/null || git checkout -q main
)
if (cd "$REPO_B" && narrow_selfheal_safe target); then
  fail "scenario B: should have refused (real content conflict on the touched path)"
else
  pass "scenario B: genuinely conflicting touched-path content correctly refused"
fi

# --- scenario C: ahead 1, behind 1, content-identical — but the working ---
# tree carries an uncommitted tracked edit. Must refuse (protect the edit).
REPO_C="$WORKDIR/c"
mk_repo "$REPO_C"
(
  cd "$REPO_C"
  git commit -q --allow-empty -m base
  BASE=$(git rev-parse HEAD)
  echo "content" >report.md
  git add -A && git commit -q -m "local-only commit"
  git checkout -q -b target "$BASE"
  echo "content" >report.md
  echo "unrelated" >other.txt
  git add -A && git commit -q -m "target"
  git checkout -q master 2>/dev/null || git checkout -q main
  echo "dirty" >report.md
)
if (cd "$REPO_C" && narrow_selfheal_safe target); then
  fail "scenario C: should have refused (uncommitted tracked change present)"
else
  pass "scenario C: uncommitted tracked change correctly refused"
fi

# --- scenario D: ahead 0 (merge-base equals HEAD, no local-only commits) -
# HEAD is a pure ancestor of target (a plain fast-forward point). touched
# is trivially empty (diff of a commit against itself). Resetting here
# discards NOTHING — HEAD has zero commits not already in target — so this
# is provably safe too, for the same 2026-08-12 reason as scenario E below.
REPO_D="$WORKDIR/d"
mk_repo "$REPO_D"
(
  cd "$REPO_D"
  git commit -q --allow-empty -m base
  git checkout -q -b target
  echo "content" >report.md
  git add -A && git commit -q -m "target has new content, local has none"
  git checkout -q master 2>/dev/null || git checkout -q main
)
if (cd "$REPO_D" && narrow_selfheal_safe target); then
  pass "scenario D: merge-base==HEAD (pure ancestor, zero local commits) correctly identified as safe"
else
  fail "scenario D: should have detected safety (HEAD has zero commits unique from target, nothing to lose)"
fi

# --- scenario E: ahead 1 (local-only commit touches ZERO files), behind 1 -
# the real-world disease this predicate exists to cure (2026-08-12,
# recurring 2026-07-11..2026-08-11, 850 refused ticks): an empty merge
# commit (or any --allow-empty local-only commit) leaves TOUCHED_PATHS
# empty while merge-base != HEAD. Must be identified as safe — there is no
# content in that commit to discard.
REPO_E="$WORKDIR/e"
mk_repo "$REPO_E"
(
  cd "$REPO_E"
  git commit -q --allow-empty -m base
  BASE=$(git rev-parse HEAD)
  git commit -q --allow-empty -m "local-only empty merge commit (no file changes)"
  git checkout -q -b target "$BASE"
  echo "unrelated" >other.txt
  git add -A && git commit -q -m "target has 1 legit unrelated commit"
  git checkout -q master 2>/dev/null || git checkout -q main
)
if (cd "$REPO_E" && narrow_selfheal_safe target); then
  pass "scenario E: local-only commit touching zero files (empty merge) correctly identified as safe"
else
  fail "scenario E: should have detected safety (zero-touched-paths empty commit — the documented disease)"
fi

echo
echo "=== ahead+behind self-heal predicate: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
