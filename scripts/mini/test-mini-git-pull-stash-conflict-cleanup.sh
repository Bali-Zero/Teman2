#!/bin/bash
# End-to-end test for the 2026-10-03 hardening: a `git stash pop` conflict
# must leave the working tree CLEAN (restored to HEAD), not mid-merge.
#
# Observed live on Mini: a narrow-self-heal stash pop conflicted on
# shared/escalations_pro.jsonl at 07:15 WITA, the conflicted file was left
# with raw conflict markers (index stage 1/2/3, `git status` reporting
# `UU`), and every 5-min tick since then failed outright at its own
# `git stash push` step ("error: could not write index ... needs merge")
# because `git stash` refuses to run against an already-unmerged index —
# a permanent loop no Telegram alert could break (the alert channel
# itself being the chronically-dead bot token). The fix must (1) restore
# the conflicted path to clean HEAD content after a failed pop, keeping
# the attempted change safe in the stash for human review, and (2) let
# the VERY NEXT invocation stash a *different*, non-conflicting dirty
# edit normally — proving the poison does not propagate tick to tick.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-stash-conflict.XXXXXX")
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

# Base: the shared.jsonl analog, both sides will edit the SAME last line
# differently — the deterministic shape of a real 3-way stash-pop conflict
# (not a plain two-sided-append, which git usually auto-merges cleanly).
printf 'header line\nbase line\n' > "$ORIGIN_WORK/shared.jsonl"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "base"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# Origin moves on: rewrites "base line" (plus an unrelated commit so there
# is something real to pull — COMMITS_BEHIND > 0).
printf 'header line\nbase line upstream-edit\n' > "$ORIGIN_WORK/shared.jsonl"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "upstream edits the shared line"
echo "unrelated upstream change" > "$ORIGIN_WORK/other.txt"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "unrelated upstream commit"
git -C "$ORIGIN_WORK" push --quiet origin main

# Dirty the LOCAL tracked copy with a conflicting edit to the exact same
# line, uncommitted — this is what the happy-path block below stashes
# before the ff-pull, then fails to cleanly pop afterwards.
printf 'header line\nbase line LOCAL-edit\n' > "$LOCAL/shared.jsonl"

set +e
bash "$SCRIPT" >/dev/null 2>&1
RC=$?
set -e

LOG_FILE="$WORK/logs/mini-git-pull.log"
echo "[test] first run exit: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0 (pull succeeds even if the pop conflicts), got $RC"
  exit 1
fi
if ! grep -q "stash pop conflict" "$LOG_FILE"; then
  echo "[test] FAIL: log should record the stash pop conflict (test did not reproduce one)"
  exit 1
fi
if ! grep -q "restored .* unmerged path(s) to clean HEAD after stash pop conflict" "$LOG_FILE"; then
  echo "[test] FAIL: log should confirm the conflicted path was restored to clean HEAD"
  exit 1
fi

# The working tree must NOT be mid-merge: no UU entries, no conflict markers.
UNMERGED=$(git -C "$LOCAL" diff --name-only --diff-filter=U)
if [ -n "$UNMERGED" ]; then
  echo "[test] FAIL: working tree still has unmerged path(s) after the script ran: $UNMERGED"
  exit 1
fi
if grep -q '^<<<<<<<' "$LOCAL/shared.jsonl"; then
  echo "[test] FAIL: conflict markers still present in shared.jsonl"
  exit 1
fi
ACTUAL=$(cat "$LOCAL/shared.jsonl")
EXPECTED=$(printf 'header line\nbase line upstream-edit\n')
if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "[test] FAIL: shared.jsonl should read as clean upstream HEAD content"
  echo "  expected: $EXPECTED"
  echo "  actual:   $ACTUAL"
  exit 1
fi

# The attempted local edit must still be recoverable — stash retained, not dropped.
STASH_COUNT=$(git -C "$LOCAL" stash list | wc -l | tr -d ' ')
if [ "$STASH_COUNT" -ne 1 ]; then
  echo "[test] FAIL: expected exactly 1 retained stash entry, found $STASH_COUNT"
  exit 1
fi
if ! git -C "$LOCAL" stash show -p | grep -q "LOCAL-edit"; then
  echo "[test] FAIL: the retained stash no longer carries the original local edit"
  exit 1
fi

echo "[test] first run PASS — conflicted pop left a clean working tree, stash retained for human review."

# --- second tick: the poison-propagation check ---
# A fresh, NON-conflicting dirty edit plus a fresh upstream commit. If the
# first run's conflict left the index/working tree in any way broken, this
# tick's own `git stash push` would fail outright ("needs merge") exactly
# as observed live on Mini.
echo "fresh unrelated upstream commit" > "$ORIGIN_WORK/second.txt"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "second unrelated upstream commit"
git -C "$ORIGIN_WORK" push --quiet origin main

echo "fresh local pending entry (uncommitted, non-conflicting)" >> "$LOCAL/shared.jsonl"
EXPECTED_MARKER=$(tail -1 "$LOCAL/shared.jsonl")

set +e
bash "$SCRIPT" >/dev/null 2>&1
RC2=$?
set -e

echo "[test] second run exit: $RC2"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC2" -ne 0 ]; then
  echo "[test] FAIL: second tick should succeed, got $RC2"
  exit 1
fi
if grep -q "git stash failed, skip" "$LOG_FILE"; then
  echo "[test] FAIL: the first tick's conflict poisoned the second tick's stash step"
  exit 1
fi
ACTUAL_MARKER=$(tail -1 "$LOCAL/shared.jsonl")
if [ "$ACTUAL_MARKER" != "$EXPECTED_MARKER" ]; then
  echo "[test] FAIL: second tick's non-conflicting dirty edit was lost"
  echo "  expected: $EXPECTED_MARKER"
  echo "  actual:   $ACTUAL_MARKER"
  exit 1
fi
ORIGIN_HEAD=$(git -C "$ORIGIN_WORK" rev-parse main)
LOCAL_HEAD=$(git -C "$LOCAL" rev-parse HEAD)
if [ "$LOCAL_HEAD" != "$ORIGIN_HEAD" ]; then
  echo "[test] FAIL: second tick did not land on origin/main HEAD"
  exit 1
fi

rm -rf "$WORK"
echo "[test] PASS — a stash-pop conflict no longer poisons the next tick's own stash step."
