#!/bin/bash
# Untracked-collision smoke test for scripts/mini/mini-git-pull.sh.
#
# Reproduces the 2026-07-11 incident: a sibling session has an uncommitted
# new file on Mini's main checkout (e.g. a new test file), and origin/main
# advances with a commit that ALSO adds a file at that same path.
#
# 2026-07-17 upgrade (skip → RESOLVE): the puller now backs up + moves the
# colliding untracked file aside (recoverable) and PROCEEDS with the ff, instead
# of stalling the whole tick. This test asserts the resolve: the pull lands, the
# sibling's file is preserved in the backup (not lost), the working tree holds
# origin's version, and an UNRELATED tracked-dirty file survives via stash+pop.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-untracked.XXXXXX")
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

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0 (collision resolved, pull applied), got $RC"
  exit 1
fi
if ! grep -q "moved colliding untracked" "$LOG_FILE"; then
  echo "[test] FAIL: log should name the moved-aside untracked collision"
  exit 1
fi
# The sibling's file must be RECOVERABLE in the backup (moved aside, not deleted).
BK=$(find "$WORK/.git-pull-collision-backup" -name 'new_test.py' 2>/dev/null | head -1)
if [ -z "$BK" ] || [ "$(cat "$BK")" != "sibling WIP draft" ]; then
  echo "[test] FAIL: sibling's untracked file not recoverable in backup (data loss!)"
  exit 1
fi
# The working tree must now hold ORIGIN's version at that path (the ff landed).
if [ "$(cat "$LOCAL/scripts/new_test.py")" != "committed upstream version" ]; then
  echo "[test] FAIL: working tree does not have origin's version after ff"
  exit 1
fi
# The pull must have applied (HEAD advanced to origin).
if [ "$(git -C "$LOCAL" rev-parse HEAD)" != "$(git -C "$ORIGIN_WORK" rev-parse HEAD)" ]; then
  echo "[test] FAIL: local HEAD did NOT advance — pull should have applied after resolve"
  exit 1
fi
# The UNRELATED tracked-dirty file must survive the stash+pop around the ff.
if ! grep -q "unrelated local edit" "$LOCAL/docs.md"; then
  echo "[test] FAIL: unrelated tracked-dirty edit was lost across the pull (stash/pop)"
  exit 1
fi
# No stash should linger (pop succeeded).
if [ -n "$(git -C "$LOCAL" stash list 2>/dev/null)" ]; then
  echo "[test] FAIL: a stash lingered — pop failed"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — untracked-collision RESOLVED: moved aside (recoverable), ff applied, unrelated dirty edit preserved."
