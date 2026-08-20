#!/bin/bash
# Regression test for W120b: mini-git-pull.sh must not corrupt its own
# execution when it re-syncs ~/scripts/mini-git-pull.sh from $REPO after a
# successful pull, in the exact situation where that self-update fires:
# the deployed copy differs from the repo copy at invocation time (e.g.
# the tick right after a PR touching this file merges).
#
# Live incident this mirrors (2026-08-20): an in-place `cp` onto the
# currently-executing script file truncated+rewrote the open inode mid-read,
# producing a torn parse ("syntax error near unexpected token" on a line
# that reads fine once inspected afterward — the write had already
# completed by then). This is very likely the same mechanism behind the
# original "line 524: syntax error" symptom seen once on 2026-08-13.
#
# This test can't reproduce the byte-level TOCTOU race deterministically
# (it depends on stdio buffering internals), so it asserts the STRUCTURAL
# fix instead: the self-update step must go temp-file + atomic rename, not
# an in-place overwrite of the live path. Guilt: grep would have caught the
# vulnerable pattern in the pre-fix script. Innocence: the fixed script still
# performs a real self-update (content ends up correct) when repo != live.
#
# Usage: bash scripts/mini/test-mini-git-pull-self-update-atomic.sh

set -e

SCRIPT="$(cd "$(dirname "$0")" && pwd)/mini-git-pull.sh"
echo "[test] script: $SCRIPT"
[ -f "$SCRIPT" ] || { echo "[test] FAIL: script not found at $SCRIPT"; exit 1; }

echo "[test] guilt check: the vulnerable in-place-cp-onto-self pattern must be gone"
if grep -nE '^\s*cp "\$REPO/scripts/mini/mini-git-pull\.sh" "\$HOME/scripts/mini-git-pull\.sh"' "$SCRIPT"; then
  echo "[test] FAIL: found an in-place cp overwriting the live/executing script path"
  exit 1
fi

echo "[test] innocence check: the self-update step still exists and uses atomic rename"
if ! grep -q 'mv -f "\$SELF_UPDATE_TMP" "\$HOME/scripts/mini-git-pull.sh"' "$SCRIPT"; then
  echo "[test] FAIL: expected an atomic mv-based self-update step, not found"
  exit 1
fi
if ! grep -q 'mktemp "\$HOME/scripts/.mini-git-pull.sh.XXXXXX"' "$SCRIPT"; then
  echo "[test] FAIL: expected the self-update to stage into a tmpfile via mktemp first"
  exit 1
fi

echo "[test] functional check: end-to-end self-update via a real tick (repo != live)"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-selfupdate.XXXXXX")
REMOTE="$WORK/remote.git"
LOCAL="$WORK/local"
echo "[test] workdir: $WORK"

export HOME="$WORK"
mkdir -p "$WORK/logs" "$WORK/.agent/decisions/state" "$WORK/Desktop" "$WORK/scripts"
ln -sfn "$LOCAL" "$WORK/nuzantara"
export TELEGRAM_BOT_TOKEN=""

mkdir -p "$REMOTE"
git -C "$REMOTE" init --quiet --bare
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main
ORIGIN_WORK="$WORK/origin-work"
git clone --quiet "$REMOTE" "$ORIGIN_WORK"
git -C "$ORIGIN_WORK" config user.email "test@test"
git -C "$ORIGIN_WORK" config user.name "test"
mkdir -p "$ORIGIN_WORK/scripts/mini"
# The repo's copy of the script itself, one commit ahead — a fixture
# marker line lets us confirm the self-update actually ran.
cp "$SCRIPT" "$ORIGIN_WORK/scripts/mini/mini-git-pull.sh"
echo "# SELF-UPDATE-FIXTURE-MARKER" >> "$ORIGIN_WORK/scripts/mini/mini-git-pull.sh"
echo "hello" > "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "initial: repo copy of the script + marker"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Deployed ("live") copy is the OLD script content — deliberately WITHOUT
# the marker, so it differs from $REPO's copy at invocation time (this is
# exactly the window where the corruption used to fire).
cp "$SCRIPT" "$WORK/scripts/mini-git-pull.sh"
chmod 755 "$WORK/scripts/mini-git-pull.sh"

echo "v2" >> "$ORIGIN_WORK/README.md"
git -C "$ORIGIN_WORK" commit --quiet -am "v2"
git -C "$ORIGIN_WORK" push --quiet origin main

set +e
bash "$WORK/scripts/mini-git-pull.sh"
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test]   exit code: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0, self-update must not break the tick, got $RC"
  exit 1
fi
if ! grep -q "atomic rename" "$LOG_FILE"; then
  echo "[test] FAIL: log should confirm the atomic-rename self-update path ran"
  exit 1
fi
if ! grep -q "SELF-UPDATE-FIXTURE-MARKER" "$WORK/scripts/mini-git-pull.sh"; then
  echo "[test] FAIL: deployed copy should now carry the repo's marker (self-update took effect)"
  exit 1
fi
# No leftover tmpfiles from the mktemp staging step.
LEFTOVER=$(find "$WORK/scripts" -maxdepth 1 -name '.mini-git-pull.sh.*' 2>/dev/null)
if [ -n "$LEFTOVER" ]; then
  echo "[test] FAIL: leftover self-update tmpfile(s): $LEFTOVER"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — self-update stages via tmpfile + atomic rename, no in-place self-overwrite."
