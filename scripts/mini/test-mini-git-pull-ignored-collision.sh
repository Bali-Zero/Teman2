#!/bin/bash
# Ignored-file collision test for scripts/mini/mini-git-pull.sh (scar H, Mini analog).
#
# The pre-2026-07-17 detection used `git ls-files --others --exclude-standard`, which
# EXCLUDES ignored files. So a locally-IGNORED untracked file whose path origin/main now
# TRACKS was never detected — and `git merge --ff-only` SILENTLY OVERWRITES it (verified on
# Pro, scar H). This proves the resolve path now catches it: the ignored local file is moved
# aside to a recoverable backup (not silently clobbered), and the ff still lands.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-ignored.XXXXXX")
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
# Base: a .gitignore that ignores runtime/ (so runtime/x.json is ignored locally).
printf 'runtime/\n' > "$ORIGIN_WORK/.gitignore"
echo "v1 doc" > "$ORIGIN_WORK/docs.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "v1 + gitignore"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Local IGNORED untracked file (matches runtime/ in .gitignore).
mkdir -p "$LOCAL/runtime"
echo "LOCAL-ONLY runtime output" > "$LOCAL/runtime/x.json"

# Origin force-adds runtime/x.json (now TRACKED upstream) → the collision that silently
# clobbered the local ignored file pre-fix.
mkdir -p "$ORIGIN_WORK/runtime"
echo "committed upstream version" > "$ORIGIN_WORK/runtime/x.json"
git -C "$ORIGIN_WORK" add -f runtime/x.json
git -C "$ORIGIN_WORK" commit --quiet -m "force-add runtime/x.json upstream"
git -C "$ORIGIN_WORK" push --quiet origin main

set +e
bash "$SCRIPT"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test] exit: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0 (ignored collision resolved, pull applied), got $RC"
  exit 1
fi
# The ignored local file must be RECOVERABLE in the backup — NOT silently clobbered (scar H).
BK=$(find "$WORK/.git-pull-collision-backup" -name 'x.json' 2>/dev/null | head -1)
if [ -z "$BK" ] || [ "$(cat "$BK")" != "LOCAL-ONLY runtime output" ]; then
  echo "[test] FAIL: ignored local file was NOT backed up (scar H silent clobber regressed!)"
  exit 1
fi
# Working tree now holds origin's tracked version.
if [ "$(cat "$LOCAL/runtime/x.json")" != "committed upstream version" ]; then
  echo "[test] FAIL: working tree does not have origin's version after ff"
  exit 1
fi
if [ "$(git -C "$LOCAL" rev-parse HEAD)" != "$(git -C "$ORIGIN_WORK" rev-parse HEAD)" ]; then
  echo "[test] FAIL: local HEAD did NOT advance — pull should have applied after resolve"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — ignored-collision (scar H): moved aside (recoverable, not clobbered), ff applied."
