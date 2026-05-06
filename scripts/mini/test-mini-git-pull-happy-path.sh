#!/bin/bash
# Happy-path smoke test for scripts/mini/mini-git-pull.sh.
#
# Verifies that on a clean Mini-side repo (no type mismatches, no dirty
# tracked files, no exotic stash state), the script pulls behind commits
# without any false-positive refusals.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-happy.XXXXXX")
REMOTE="$WORK/remote.git"
LOCAL="$WORK/local"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/mini-git-pull.sh"

echo "[test] workdir: $WORK"

export HOME="$WORK"
mkdir -p "$WORK/logs" "$WORK/.agent/decisions/state" "$WORK/Desktop"
ln -sfn "$LOCAL" "$WORK/Desktop/nuzantara"
export TELEGRAM_BOT_TOKEN=""

# Setup origin
mkdir -p "$REMOTE"
git -C "$REMOTE" init --quiet --bare
ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"
echo "v1" > "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "v1"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

echo "v2" >> "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" commit --quiet -am "v2"
git -C "$ORIGIN_WORK" push --quiet origin main

echo "mini-only" > "$LOCAL/mini-only.txt"

set +e
bash "$SCRIPT"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test] exit: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0 on happy path, got $RC"
  exit 1
fi
if ! grep -q "OK pulled" "$LOG_FILE"; then
  echo "[test] FAIL: log should mention 'OK pulled'"
  exit 1
fi
NEW_HEAD=$(git -C "$LOCAL" rev-parse --short HEAD)
ORIGIN_HEAD=$(git -C "$ORIGIN_WORK" rev-parse --short HEAD)
if [ "$NEW_HEAD" != "$ORIGIN_HEAD" ]; then
  echo "[test] FAIL: HEAD did not advance (local=$NEW_HEAD, origin=$ORIGIN_HEAD)"
  exit 1
fi
if [ ! -f "$LOCAL/mini-only.txt" ]; then
  echo "[test] FAIL: untracked file 'mini-only.txt' was lost"
  exit 1
fi
if [ "$(cat "$LOCAL/mini-only.txt")" != "mini-only" ]; then
  echo "[test] FAIL: untracked file content was modified"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — happy path: pulled, HEAD advanced, untracked preserved."
