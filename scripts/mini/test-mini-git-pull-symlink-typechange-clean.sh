#!/bin/bash
# Innocence test for the W120 hardening of check_type_mismatch() in
# scripts/mini/mini-git-pull.sh.
#
# Companion to test-mini-git-pull-symlink-mismatch.sh (the guilt case: a
# tracked symlink FOREIGN-materialized as a real dir on Mini, which must
# still be refused). This test is the mirror case that must NOT be
# refused: a path that is a real directory tracked EXACTLY as such by
# Mini's own (stale) HEAD, while origin/main has since converted it to a
# symlink via a legitimate commit (e.g. a skills-folder reorg). Local
# content is git-clean — nothing foreign, nothing uncommitted — so
# `git merge --ff-only` can retype it natively with zero risk.
#
# Live incident this mirrors (2026-08-20): Mini's checkout sat 30 commits
# behind main; origin/main had converted .claude/skills/secondhome from a
# tracked directory to a symlink (skills-folder reorg). The pre-W120
# guard flagged every tick as "type-mismatch, refusing pull" — ~9h of
# dead 5-min ticks — even though the local directory was byte-identical
# to what Mini's own HEAD already recorded.
#
# Usage: bash scripts/mini/test-mini-git-pull-symlink-typechange-clean.sh

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-typechange.XXXXXX")
REMOTE="$WORK/remote.git"
LOCAL="$WORK/local"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/mini-git-pull.sh"

echo "[test] workdir: $WORK"
echo "[test] script: $SCRIPT"
[ -f "$SCRIPT" ] || { echo "[test] FAIL: script not found at $SCRIPT"; exit 1; }

export HOME="$WORK"
mkdir -p "$WORK/logs" "$WORK/.agent/decisions/state" "$WORK/Desktop"
ln -sfn "$LOCAL" "$WORK/nuzantara"
export TELEGRAM_BOT_TOKEN=""

echo "[test] step 1: 'remote' with a tracked DIRECTORY at skills/thing"
mkdir -p "$REMOTE"
git -C "$REMOTE" init --quiet --bare
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main
ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"
mkdir -p "$ORIGIN_WORK/skills/thing"
echo "old content" > "$ORIGIN_WORK/skills/thing/SKILL.md"
echo "hello" > "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "initial: tracked dir + README"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

echo "[test] step 2: clone as 'Mini' local, stays on this commit (simulates a stale checkout)"
git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

[ -d "$LOCAL/skills/thing" ] && [ ! -L "$LOCAL/skills/thing" ] || \
  { echo "[test] FAIL: clone did not produce a real directory"; exit 1; }

echo "[test]   confirming local is git-clean (nothing foreign)"
DIRTY=$(git -C "$LOCAL" status --short)
[ -z "$DIRTY" ] || { echo "[test] FAIL: local should be git-clean, got: $DIRTY"; exit 1; }

echo "[test] step 3: 'remote' converts the dir to a symlink (legitimate reorg commit)"
rm -rf "$ORIGIN_WORK/skills/thing"
mkdir -p "$ORIGIN_WORK/.agents/skills"
echo "new content" > "$ORIGIN_WORK/.agents/skills/thing.md"
ln -sfn "../../.agents/skills/thing.md" "$ORIGIN_WORK/skills/thing"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "reorg: skills/thing dir -> symlink"
git -C "$ORIGIN_WORK" push --quiet origin main

echo "[test] step 4: run mini-git-pull.sh on the stale-but-clean local clone"
set +e
bash "$SCRIPT"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test]   exit code: $RC"
echo "[test]   log content:"
sed 's/^/  | /' "$LOG_FILE"

echo "[test] step 5: assertions"
if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0 (clean type-change should NOT be refused), got $RC"
  exit 1
fi
if grep -q "type-mismatch" "$LOG_FILE"; then
  echo "[test] FAIL: log should NOT report a type-mismatch for a HEAD-clean stale path"
  exit 1
fi
if [ ! -L "$LOCAL/skills/thing" ]; then
  echo "[test] FAIL: skills/thing should be a symlink after pull"
  exit 1
fi
NEW_HEAD=$(git -C "$LOCAL" rev-parse --short HEAD)
ORIGIN_HEAD=$(git -C "$ORIGIN_WORK" rev-parse --short HEAD)
if [ "$NEW_HEAD" != "$ORIGIN_HEAD" ]; then
  echo "[test] FAIL: HEAD did not advance (local=$NEW_HEAD, origin=$ORIGIN_HEAD)"
  exit 1
fi

# Cleanup
rm -rf "$WORK"

echo "[test] PASS — HEAD-clean dir->symlink type-change pulled through, no false refusal."
