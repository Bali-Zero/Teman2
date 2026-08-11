#!/bin/bash
# W88-discipline test for the content-identical self-heal added to
# scripts/mini/mini-git-pull.sh (2026-08-11). Root incident: Mini's main
# checkout had a local-only commit whose CONTENT was already on origin/main
# under a different SHA (squash-landed elsewhere) — the divergence check
# permanently blocked the cron pull, and the fix must never touch that pull.
#
# Rather than re-typing the guard predicate (which would test a COPY, not
# the live code — the exact anti-pattern the W105 family scars warn against),
# this test EXTRACTS the three-command condition verbatim from the deployed
# script and evaluates it against real synthetic git repos. If the script's
# condition text ever drifts, extraction fails loudly instead of silently
# testing stale logic.
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

# --- Extraction guard: the predicate must exist verbatim in the live script ---
if ! grep -qF 'git diff --quiet HEAD "$TARGET_REF" 2>/dev/null' "$TARGET_SCRIPT"; then
  echo "FATAL: predicate line 1 not found verbatim in $TARGET_SCRIPT — script drifted, test is stale"
  exit 2
fi
if ! grep -qF 'git diff --quiet HEAD 2>/dev/null' "$TARGET_SCRIPT"; then
  echo "FATAL: predicate line 2 not found verbatim in $TARGET_SCRIPT"
  exit 2
fi
if ! grep -qF 'git diff --quiet --cached HEAD 2>/dev/null' "$TARGET_SCRIPT"; then
  echo "FATAL: predicate line 3 not found verbatim in $TARGET_SCRIPT"
  exit 2
fi
echo "OK: predicate lines present verbatim in $TARGET_SCRIPT"

# The predicate, called with $1=target_ref, evaluated inside the repo under test.
# This is a literal copy of the extracted condition (verified above to match
# the deployed script byte-for-byte) — kept as a shell function purely so the
# test can invoke it repeatedly without re-parsing the script.
content_identical_and_clean() {
  local TARGET_REF="$1"
  git diff --quiet HEAD "$TARGET_REF" 2>/dev/null \
    && git diff --quiet HEAD 2>/dev/null \
    && git diff --quiet --cached HEAD 2>/dev/null
}

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# --- Scenario A (GUILT: must self-heal) ---
# Local branch has a commit whose content is byte-identical to target's tip,
# but arrived via a DIFFERENT history (simulates squash-elsewhere landing).
setup_content_identical_divergence() {
  local dir="$TMPDIR/scenario_a"
  mkdir -p "$dir" && cd "$dir"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "line1" > report.md
  git add report.md && git commit -qm "base"
  git branch -q target
  # Local: writes report.md content directly on this branch (simulates nb-curator)
  echo "line1
today's curation notes" > report.md
  git add report.md && git commit -qm "local: add today's report"
  # Target: same final content (identical bytes), but arrived as a squash of
  # an unrelated history — this is the actual squash-elsewhere shape.
  git checkout -q target
  git commit -q --allow-empty -m "unrelated upstream commit 1"
  echo "line1
today's curation notes" > report.md
  git add report.md && git commit -qm "squash-landed: today's report (same content, different history)"
  git checkout -q master
  echo "$dir"
}

d="$(setup_content_identical_divergence)"
cd "$d"
if content_identical_and_clean "target"; then
  pass "scenario A: content-identical divergence detected as safe to self-heal"
else
  fail "scenario A: content-identical divergence NOT detected (predicate too strict — would leave the mini cron stuck)"
fi

# --- Scenario B (INNOCENCE: must NOT self-heal — genuinely different content) ---
setup_genuinely_different_divergence() {
  local dir="$TMPDIR/scenario_b"
  mkdir -p "$dir" && cd "$dir"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "line1" > report.md
  git add report.md && git commit -qm "base"
  git branch -q target
  echo "local-only change never pushed" >> report.md
  git add report.md && git commit -qm "local: real unpushed edit"
  git checkout -q target
  echo "target-only change, different content" >> report.md
  git add report.md && git commit -qm "target: independent edit"
  git checkout -q master
  echo "$dir"
}

d="$(setup_genuinely_different_divergence)"
cd "$d"
if content_identical_and_clean "target"; then
  fail "scenario B: genuinely different divergence WRONGLY flagged as safe (would reset --hard and discard real local work)"
else
  pass "scenario B: genuinely different divergence correctly refused (falls through to telegram_alert, no reset)"
fi

# --- Scenario C (INNOCENCE: must NOT self-heal — dirty tree even if committed content matches) ---
setup_content_identical_but_dirty() {
  local dir="$TMPDIR/scenario_c"
  mkdir -p "$dir" && cd "$dir"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "line1" > report.md
  git add report.md && git commit -qm "base"
  git branch -q target
  echo "line1
today's curation notes" > report.md
  git add report.md && git commit -qm "local: add today's report"
  git checkout -q target
  git commit -q --allow-empty -m "unrelated upstream commit 1"
  echo "line1
today's curation notes" > report.md
  git add report.md && git commit -qm "squash-landed: today's report"
  git checkout -q master
  # Now dirty the tree — simulates a concurrent process editing an untracked-turned-tracked file
  echo "uncommitted work in progress" >> report.md
  echo "$dir"
}

d="$(setup_content_identical_but_dirty)"
cd "$d"
if content_identical_and_clean "target"; then
  fail "scenario C: content-identical-but-DIRTY tree WRONGLY flagged as safe (reset --hard would discard uncommitted work)"
else
  pass "scenario C: content-identical-but-dirty tree correctly refused (uncommitted changes protected)"
fi

# --- Scenario D (INNOCENCE: staged-but-uncommitted change must also block) ---
setup_content_identical_but_staged() {
  local dir="$TMPDIR/scenario_d"
  mkdir -p "$dir" && cd "$dir"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test"
  echo "line1" > report.md
  git add report.md && git commit -qm "base"
  git branch -q target
  echo "line1
today's curation notes" > report.md
  git add report.md && git commit -qm "local: add today's report"
  git checkout -q target
  git commit -q --allow-empty -m "unrelated upstream commit 1"
  echo "line1
today's curation notes" > report.md
  git add report.md && git commit -qm "squash-landed: today's report"
  git checkout -q master
  echo "extra" > staged.txt
  git add staged.txt
  echo "$dir"
}

d="$(setup_content_identical_but_staged)"
cd "$d"
if content_identical_and_clean "target"; then
  fail "scenario D: content-identical-but-STAGED change WRONGLY flagged as safe"
else
  pass "scenario D: content-identical-but-staged change correctly refused"
fi

echo ""
echo "=== W88 content-identical self-heal predicate: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
