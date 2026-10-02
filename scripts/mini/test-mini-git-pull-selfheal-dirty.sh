#!/bin/bash
# End-to-end test for the 2026-10-02 hardening: the narrow (ahead+behind)
# self-heal in scripts/mini/mini-git-pull.sh must still fire when the
# working tree has an UNRELATED dirty tracked file — the real-world shape
# found on Mini (shared/escalations_pro.jsonl, written directly by
# concurrent producers and only periodically promoted via PR, blocked the
# self-heal's old clean-tree requirement for 2.5+ days on a genuinely
# content-identical divergence: local commit 53f448edd5, 2026-09-30..10-02).
#
# Runs the REAL script against real git repos (not a predicate copy — see
# scripts/tests/test_mini_git_pull_ahead_behind_selfheal.sh for the gate-only
# predicate test). Asserts: exit 0, narrow self-heal fires, HEAD lands on
# target, AND the dirty file's uncommitted content survives the stash/pop.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-selfheal-dirty.XXXXXX")
REMOTE="$WORK/remote.git"
LOCAL="$WORK/local"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/mini-git-pull.sh"

echo "[test] workdir: $WORK"

export HOME="$WORK"
mkdir -p "$WORK/logs" "$WORK/.agent/decisions/state" "$WORK/Desktop"
ln -sfn "$LOCAL" "$WORK/nuzantara"
export TELEGRAM_BOT_TOKEN=""

mkdir -p "$REMOTE"
git -C "$REMOTE" init --quiet --bare
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main

ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"

# Base: a shared file (the escalations_pro.jsonl analog) that neither side's
# upcoming commits touch.
echo "base line" > "$ORIGIN_WORK/shared.jsonl"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "base"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Local-only commit: a report file, never pushed (the stranded GSC-report shape).
echo "daily report content" > "$LOCAL/report.json"
git -C "$LOCAL" add -A
git -C "$LOCAL" commit --quiet -m "chore: local-only daily report"

# Origin: the SAME report content lands via a different history (recovered
# in a separate PR), PLUS legitimate unrelated commits the local checkout
# hasn't seen — the real ahead+behind shape.
echo "daily report content" > "$ORIGIN_WORK/report.json"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "chore: recover stranded daily report"
echo "unrelated upstream change" > "$ORIGIN_WORK/other.txt"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "unrelated upstream commit"
git -C "$ORIGIN_WORK" push --quiet origin main

# Dirty the shared file locally — uncommitted, untouched by either side's
# new commits. This is what blocked the self-heal before this hardening.
echo "live pending entry (uncommitted)" >> "$LOCAL/shared.jsonl"
EXPECTED_MARKER=$(tail -1 "$LOCAL/shared.jsonl")

set +e
bash "$SCRIPT"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test] exit: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0, got $RC"
  exit 1
fi
if ! grep -q "attempting narrow self-heal" "$LOG_FILE"; then
  echo "[test] FAIL: log should mention narrow self-heal was attempted"
  exit 1
fi
if ! grep -q "ahead+behind divergence resolved" "$LOG_FILE"; then
  echo "[test] FAIL: log should confirm the self-heal resolved the divergence"
  exit 1
fi
if ! grep -q "stash restored cleanly after narrow self-heal" "$LOG_FILE"; then
  echo "[test] FAIL: log should confirm the dirty-file stash was restored"
  exit 1
fi

ORIGIN_HEAD=$(git -C "$ORIGIN_WORK" rev-parse main)
LOCAL_HEAD=$(git -C "$LOCAL" rev-parse HEAD)
if [ "$LOCAL_HEAD" != "$ORIGIN_HEAD" ]; then
  echo "[test] FAIL: local HEAD ($LOCAL_HEAD) did not land on origin/main ($ORIGIN_HEAD)"
  exit 1
fi

ACTUAL_MARKER=$(tail -1 "$LOCAL/shared.jsonl")
if [ "$ACTUAL_MARKER" != "$EXPECTED_MARKER" ]; then
  echo "[test] FAIL: the uncommitted shared.jsonl entry was lost across the self-heal"
  echo "  expected: $EXPECTED_MARKER"
  echo "  actual:   $ACTUAL_MARKER"
  exit 1
fi
if ! grep -q "unrelated upstream change" "$LOCAL/other.txt"; then
  echo "[test] FAIL: self-heal did not bring in the legitimate upstream commit"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — narrow self-heal with an unrelated dirty tracked file: stashed, reset, popped, both preserved."
