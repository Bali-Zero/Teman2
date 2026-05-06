#!/bin/bash
# Tracked-dirty smoke test for scripts/mini/mini-git-pull.sh.
#
# Mini cron 23:15 modifies docs/AUTOMATIONS_REFERENCE.md (auto-gen).
# That file is tracked by git, so on next pull tick the working tree
# is dirty. The script must stash → pull → pop, preserving the local
# modification on top of the new HEAD.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-dirty.XXXXXX")
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
ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"
mkdir -p "$ORIGIN_WORK/docs"
echo "v1 doc" > "$ORIGIN_WORK/docs/AUTOMATIONS_REFERENCE.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "v1 doc"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Mini auto-gen modified the doc locally (uncommitted)
echo "Mini-local addition $(date)" >> "$LOCAL/docs/AUTOMATIONS_REFERENCE.md"
EXPECTED_MARKER=$(tail -1 "$LOCAL/docs/AUTOMATIONS_REFERENCE.md")

# Origin advances — with a different file, so no merge conflict expected
echo "unrelated" > "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "unrelated change"
git -C "$ORIGIN_WORK" push --quiet origin main

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
if ! grep -q "Stashed tracked changes" "$LOG_FILE"; then
  echo "[test] FAIL: log should mention 'Stashed tracked changes'"
  exit 1
fi
if ! grep -q "OK pulled" "$LOG_FILE"; then
  echo "[test] FAIL: log should mention 'OK pulled'"
  exit 1
fi
if ! grep -q "stash restored cleanly" "$LOG_FILE"; then
  echo "[test] FAIL: log should mention 'stash restored cleanly'"
  exit 1
fi
ACTUAL_MARKER=$(tail -1 "$LOCAL/docs/AUTOMATIONS_REFERENCE.md")
if [ "$ACTUAL_MARKER" != "$EXPECTED_MARKER" ]; then
  echo "[test] FAIL: local Mini auto-gen modification was lost"
  echo "  expected: $EXPECTED_MARKER"
  echo "  actual:   $ACTUAL_MARKER"
  exit 1
fi
if ! grep -q "unrelated" "$LOCAL/README.md"; then
  echo "[test] FAIL: pull did not bring in upstream README.md change"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — tracked-dirty: stashed, pulled, popped, both changes preserved."
