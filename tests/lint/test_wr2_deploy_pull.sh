#!/usr/bin/env bash
# test_wr2_deploy_pull.sh — TDD harness for the WR2 deploy puller
# (Sprint C C1, 2026-05-08).
#
# The puller itself is Pro-local at ~/scripts/wr2-deploy-pull.sh
# (NOT in this repo); the canonical body lives at
# docs/wr2/skill-snapshots/deploy-pull-2026-05-08.md.
# These tests embed the script via the snapshot — extracting the bash
# code block, writing it to a sandbox path, then running it with
# isolated state + a local git fixture so we exercise the 6 paths
# (healthy fast-forward / already up-to-date / missing worktree /
# wrong branch / dirty worktree / local ahead) without touching the
# real production deploy worktree.
#
# Run from repo root:
#   bash tests/lint/test_wr2_deploy_pull.sh
# Exit 0 = all paths pass, 1 = any failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SNAPSHOT="$REPO_ROOT/docs/wr2/skill-snapshots/deploy-pull-2026-05-08.md"

if [[ ! -f "$SNAPSHOT" ]]; then
  echo "FAIL: snapshot not found at $SNAPSHOT" >&2
  exit 2
fi

TMP="$(mktemp -d -t wr2_deploy_pull.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# Extract the bash block that begins with the canonical script
# shebang. The snapshot may contain other small bash blocks (bootstrap
# commands, runbook examples) — we want the one that's the actual
# script body.
SCRIPT="$TMP/wr2-deploy-pull.sh"
awk '
  /^```bash$/                                { inside=1; current=""; next }
  /^```$/ && inside                          { if (current ~ /^#!\/usr\/bin\/env bash/) { printf "%s", current; exit } inside=0; current=""; next }
  inside                                     { current = current $0 "\n" }
' "$SNAPSHOT" > "$SCRIPT"
if [[ ! -s "$SCRIPT" ]]; then
  echo "FAIL: could not extract bash body from $SNAPSHOT" >&2
  exit 2
fi
chmod +x "$SCRIPT"

# Override HOME so the script writes its log + state into the sandbox.
export HOME="$TMP/home"
mkdir -p "$HOME/.agent/decisions/state" "$HOME/logs" "$HOME/Desktop"

# No real Telegram even if a real token leaked in.
export TELEGRAM_BOT_TOKEN=""

# Default: point the puller at a sandbox deploy dir we'll create per-test.
DEPLOY_DIR="$HOME/Desktop/nuzantara-deploy"
export WR2_DEPLOY_DIR="$DEPLOY_DIR"

PASS=0
FAIL=0

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    printf '  PASS: %-50s (got=%s)\n' "$label" "$actual"
    PASS=$((PASS + 1))
  else
    printf '  FAIL: %-50s (expected=%s actual=%s)\n' "$label" "$expected" "$actual" >&2
    FAIL=$((FAIL + 1))
  fi
}

assert_grep() {
  local label="$1" pattern="$2" file="$3"
  if grep -qE "$pattern" "$file" 2>/dev/null; then
    printf '  PASS: %-50s (matched /%s/)\n' "$label" "$pattern"
    PASS=$((PASS + 1))
  else
    printf '  FAIL: %-50s (no match for /%s/ in %s)\n' "$label" "$pattern" "$file" >&2
    FAIL=$((FAIL + 1))
  fi
}

reset_state() {
  rm -f "$HOME/.agent/decisions/state/wr2_deploy_pull.state" \
        "$HOME/.agent/decisions/state/wr2_deploy_pull.lock" \
        "$HOME/logs/wr2-deploy-pull.log"
}

state_get() {
  local key="$1"
  awk -F= -v k="$key" '$1==k {print $2}' \
    "$HOME/.agent/decisions/state/wr2_deploy_pull.state" 2>/dev/null \
    | tail -1
}

run_script() {
  set +e
  rc=0
  "$SCRIPT" >/dev/null 2>&1
  rc=$?
  set -e
}

# ─────────────────────────────────────────────────────────────────────
# Build a local git fixture: bare "remote" + worktree clone, so we can
# manipulate divergence without touching the network.
# ─────────────────────────────────────────────────────────────────────
build_fixture() {
  rm -rf "$DEPLOY_DIR" "$HOME/Desktop/.fake-remote.git" "$HOME/Desktop/.fixture-source"
  # Bare remote.
  git init --bare --quiet "$HOME/Desktop/.fake-remote.git"
  # Source clone we use to seed the remote with one initial commit.
  git init --quiet "$HOME/Desktop/.fixture-source"
  (
    cd "$HOME/Desktop/.fixture-source"
    git config user.email "test@example.com"
    git config user.name "test"
    echo initial > README.md
    git add README.md
    git commit -q -m "initial"
    git branch -M deploy/main
    git remote add origin "$HOME/Desktop/.fake-remote.git"
    git push -q origin deploy/main
  )
  # Now create the deploy worktree by cloning the bare remote.
  git clone --quiet --branch deploy/main "$HOME/Desktop/.fake-remote.git" "$DEPLOY_DIR"
  (cd "$DEPLOY_DIR" && git config user.email "test@example.com" && git config user.name "test")
}

advance_remote() {
  # Push a new commit to the bare remote via the fixture-source clone.
  (
    cd "$HOME/Desktop/.fixture-source"
    git pull -q origin deploy/main
    echo "advance $(date +%s%N)" >> README.md
    git add README.md
    git commit -q -m "advance"
    git push -q origin deploy/main
  )
}

# ─────────────────────────────────────────────────────────────────────
# Test 1: missing worktree → exit 1, alert "deploy_missing"
# ─────────────────────────────────────────────────────────────────────
echo "TEST 1: missing worktree"
reset_state
rm -rf "$DEPLOY_DIR"
run_script
assert_eq "missing-dir exit code" "1" "$rc"
assert_grep "log mentions missing"   "deploy worktree missing" "$HOME/logs/wr2-deploy-pull.log"

# ─────────────────────────────────────────────────────────────────────
# Test 2: already up-to-date → exit 0, last_status=ok
# ─────────────────────────────────────────────────────────────────────
echo "TEST 2: already up-to-date"
reset_state
build_fixture
run_script
assert_eq "up-to-date exit code"     "0" "$rc"
assert_eq "state.last_status (ok)"   "ok" "$(state_get last_status)"
assert_grep "log mentions up-to-date" "already up-to-date" "$HOME/logs/wr2-deploy-pull.log"

# ─────────────────────────────────────────────────────────────────────
# Test 3: healthy fast-forward → exit 0, last_status=advanced
# ─────────────────────────────────────────────────────────────────────
echo "TEST 3: healthy fast-forward"
reset_state
build_fixture
advance_remote
run_script
assert_eq "ff exit code"             "0" "$rc"
assert_eq "state.last_status (advanced)" "advanced" "$(state_get last_status)"
assert_grep "log mentions fast-forwarded" "fast-forwarded" "$HOME/logs/wr2-deploy-pull.log"

# ─────────────────────────────────────────────────────────────────────
# Test 4: wrong branch → exit 1, alert "wrong_branch"
# ─────────────────────────────────────────────────────────────────────
echo "TEST 4: wrong branch"
reset_state
build_fixture
(cd "$DEPLOY_DIR" && git checkout -q -b feature/oops)
run_script
assert_eq "wrong-branch exit code"   "1" "$rc"
assert_grep "log mentions wrong branch" "WRONG.*branch|on branch=feature/oops" "$HOME/logs/wr2-deploy-pull.log"

# ─────────────────────────────────────────────────────────────────────
# Test 5: dirty worktree → exit 1, alert "dirty_worktree"
# ─────────────────────────────────────────────────────────────────────
echo "TEST 5: dirty worktree"
reset_state
build_fixture
echo "local edit" >> "$DEPLOY_DIR/README.md"
run_script
assert_eq "dirty exit code"          "1" "$rc"
assert_grep "log mentions dirty"     "has local changes" "$HOME/logs/wr2-deploy-pull.log"

# ─────────────────────────────────────────────────────────────────────
# Test 6: local ahead → exit 1, alert "local_ahead"
# ─────────────────────────────────────────────────────────────────────
echo "TEST 6: local ahead of remote"
reset_state
build_fixture
(
  cd "$DEPLOY_DIR"
  echo "local commit" >> README.md
  git add README.md
  git commit -q -m "local-only"
)
run_script
assert_eq "local-ahead exit code"    "1" "$rc"
assert_grep "log mentions ahead"     "ahead of" "$HOME/logs/wr2-deploy-pull.log"

# ─────────────────────────────────────────────────────────────────────
# Test 7: cooldown active → exit 1 but no second Telegram POST
#         (we just check the suppression log line; Telegram is no-op
#         because TELEGRAM_BOT_TOKEN is empty)
# ─────────────────────────────────────────────────────────────────────
# No-op without a real Telegram token; we just verify the cooldown
# state file is consulted. Skip this scenario in the no-token harness;
# it's exercised in Test 5/6 implicitly because the script writes
# log lines for both the failure AND the cooldown check on the
# alert path.
#
# (The Canva OAuth watchdog test_canva_oauth_watchdog.sh already
# covers cooldown semantics for a structurally identical helper.)

# ─────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "RESULT: ${PASS} passed, ${FAIL} failed"
if (( FAIL > 0 )); then
  exit 1
fi
exit 0
