#!/bin/bash
# Smoke test for scripts/mini/mini-git-pull.sh symlink-vs-dir mismatch detection.
#
# Simulates the 2026-05-06 incident in /tmp:
#   1. Create a "remote" repo with a tracked symlink at apps/backend-rag/.venv
#   2. Clone it as "Mini" working repo
#   3. Replace the symlink with a real directory locally on the clone
#   4. Add a new commit to "remote"
#   5. Run mini-git-pull.sh against the clone — must SKIP with exit 1
#   6. Confirm log contains "type-mismatch" detection.
#
# Usage: bash scripts/mini/test-mini-git-pull-symlink-mismatch.sh

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-test.XXXXXX")
REMOTE="$WORK/remote.git"
LOCAL="$WORK/local"
LOG_BASE="$WORK/logs"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/mini-git-pull.sh"

echo "[test] workdir: $WORK"
echo "[test] script: $SCRIPT"
[ -f "$SCRIPT" ] || { echo "[test] FAIL: script not found at $SCRIPT"; exit 1; }

# Stub HOME so the script logs to our isolated dir.
export HOME="$WORK"
mkdir -p "$LOG_BASE" "$WORK/.agent/decisions/state" "$WORK/Desktop"
ln -sfn "$LOCAL" "$WORK/Desktop/nuzantara"

# Disable Telegram during test.
export TELEGRAM_BOT_TOKEN=""

echo "[test] step 1: bare 'remote' with tracked symlink"
mkdir -p "$REMOTE"
git -C "$REMOTE" init --quiet --bare
ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"
mkdir -p "$ORIGIN_WORK/apps/backend-rag"
ln -sfn "/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv" \
  "$ORIGIN_WORK/apps/backend-rag/.venv"
echo "hello" > "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "initial: tracked symlink + README"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

echo "[test] step 2: clone as 'Mini' local"
git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Confirm symlink survived clone.
[ -L "$LOCAL/apps/backend-rag/.venv" ] || \
  { echo "[test] FAIL: clone did not preserve symlink"; exit 1; }

echo "[test] step 3: simulate Mini materializing the symlink as a real dir"
rm "$LOCAL/apps/backend-rag/.venv"
mkdir -p "$LOCAL/apps/backend-rag/.venv/bin"
echo "fake activate script" > "$LOCAL/apps/backend-rag/.venv/bin/activate"
echo "[test]   .venv is now: $(file "$LOCAL/apps/backend-rag/.venv" | cut -d: -f2)"

echo "[test] step 4: add new commit to remote (so behind=1)"
echo "second" >> "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" commit --quiet -am "second commit"
git -C "$ORIGIN_WORK" push --quiet origin main

echo "[test] step 5: run mini-git-pull.sh on local clone"
set +e
bash "$SCRIPT"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test]   exit code: $RC"
echo "[test]   log content:"
sed 's/^/  | /' "$LOG_FILE"

echo "[test] step 6: assertions"
if [ "$RC" -ne 1 ]; then
  echo "[test] FAIL: expected exit 1 (type-mismatch refusal), got $RC"
  exit 1
fi
if ! grep -q "type-mismatch" "$LOG_FILE"; then
  echo "[test] FAIL: log should mention 'type-mismatch'"
  exit 1
fi
if ! grep -q "origin=symlink, local=dir" "$LOG_FILE"; then
  echo "[test] FAIL: log should identify the specific mismatch direction"
  exit 1
fi

# Cleanup
rm -rf "$WORK"

echo "[test] PASS — symlink↔dir mismatch detected, pull refused, no destructive stash."
