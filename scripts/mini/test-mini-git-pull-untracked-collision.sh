#!/bin/bash
# Untracked-collision smoke test for scripts/mini/mini-git-pull.sh.
#
# Reproduces the 2026-07-11 incident: a sibling session has an uncommitted
# new file on Mini's main checkout (e.g. a new test file), and origin/main
# advances with a commit that ALSO adds a file at that same path. The old
# script stashed tracked changes, attempted `git merge --ff-only`, failed
# on the untracked-path collision, restored the stash, and repeated the
# whole cycle every 5 minutes forever. The fix detects the collision
# BEFORE stashing and skips cleanly with one targeted alert.
#
# This test also has an unrelated tracked-dirty file present, to prove the
# collision check runs — and skips — before the stash step even fires.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-untracked.XXXXXX")
REMOTE="$WORK/remote.git"
LOCAL="$WORK/local"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/mini-git-pull.sh"

echo "[test] workdir: $WORK"

export HOME="$WORK"
mkdir -p "$WORK/logs" "$WORK/.agent/decisions/state" "$WORK/Desktop"
ln -sfn "$LOCAL" "$WORK/Desktop/nuzantara"
export TELEGRAM_BOT_TOKEN=""

mkdir -p "$REMOTE"
git -C "$REMOTE" init --quiet --bare
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main  # portable regardless of ambient init.defaultBranch
ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"
echo "v1 doc" > "$ORIGIN_WORK/docs.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "v1"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Unrelated tracked file, dirty (a normal Mini-local modification) — proves
# the collision check pre-empts the stash step even when one would
# otherwise be triggered.
echo "unrelated local edit" >> "$LOCAL/docs.md"

# Sibling session's uncommitted WIP: a brand-new untracked file.
mkdir -p "$LOCAL/scripts"
echo "sibling WIP draft" > "$LOCAL/scripts/new_test.py"

# Origin advances with a commit that introduces a file at the SAME path
# (this is the actual collision — same path, different content).
mkdir -p "$ORIGIN_WORK/scripts"
echo "committed upstream version" > "$ORIGIN_WORK/scripts/new_test.py"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "add scripts/new_test.py upstream"
git -C "$ORIGIN_WORK" push --quiet origin main

set +e
bash "$SCRIPT"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test] exit: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 1 ]; then
  echo "[test] FAIL: expected exit 1 (collision, needs sibling to resolve), got $RC"
  exit 1
fi
if ! grep -q "untracked file(s) collide" "$LOG_FILE"; then
  echo "[test] FAIL: log should name the untracked-collision detection"
  exit 1
fi
if grep -q "Stashed tracked changes" "$LOG_FILE"; then
  echo "[test] FAIL: script stashed before checking for the collision — should skip pre-stash"
  exit 1
fi
if ! git -C "$LOCAL" stash list | grep -q "^$"; then
  : # stash list empty is expected — no assertion needed beyond the grep below
fi
if [ -n "$(git -C "$LOCAL" stash list 2>/dev/null)" ]; then
  echo "[test] FAIL: a stash was created — sibling's tracked-dirty file should not have been touched"
  exit 1
fi
if [ "$(cat "$LOCAL/scripts/new_test.py")" != "sibling WIP draft" ]; then
  echo "[test] FAIL: sibling's untracked WIP file was modified — must be left alone"
  exit 1
fi
if [ "$(git -C "$LOCAL" rev-parse HEAD)" = "$(git -C "$ORIGIN_WORK" rev-parse HEAD)" ]; then
  echo "[test] FAIL: local HEAD advanced despite the collision — pull should have been skipped"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — untracked-collision: skipped pre-stash, sibling WIP untouched, no pull applied."
