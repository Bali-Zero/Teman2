#!/bin/bash
# End-to-end test for the 2026-10-03 follow-up hardening: a stash-pop
# conflict that happened BEFORE this script ever ran (e.g. left by the
# pre-#7823 script version, or by any other process) must not permanently
# poison every future tick.
#
# #7823 added resolve_stash_pop_conflict_to_clean_tree() and called it from
# the three POP-failure branches, so a conflict THIS SCRIPT causes cleans
# itself up before the next tick. It left one gap, reproduced live on
# Mini: if the unmerged path already exists when the script STARTS (i.e.
# the poisoning run has already finished and exited), the very next
# `git stash push` fails outright with "needs merge" — git refuses to
# stash against an already-unmerged index — and the script gave up
# without ever calling the cleanup helper, looping "ERROR: git stash
# failed, skip" forever. This test manufactures that exact pre-existing
# state OUTSIDE the script (mirroring an inherited mess, not one this run
# causes) and asserts a single invocation recovers and completes the pull.

set -e

WORK=$(mktemp -d "${TMPDIR:-/tmp}/mini-git-pull-poisoned.XXXXXX")
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

printf 'header line\nbase line\n' > "$ORIGIN_WORK/shared.jsonl"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "base"
git -C "$ORIGIN_WORK" branch -M main
git -C "$ORIGIN_WORK" push --quiet origin main

# LOCAL clones at the base commit, BEFORE upstream's conflicting commit
# exists — it must stay a clean ancestor of origin throughout (real
# ahead/behind divergence is a different, already-covered code path).
git clone --quiet "$REMOTE" "$LOCAL"
git -C "$LOCAL" config user.email "test@test"
git -C "$LOCAL" config user.name "test"

# --- manufacture a pre-existing "needs merge" index, OUTSIDE the script,
# mirroring a mess some earlier (unpatched) run already left behind: a
# stash whose base predates an upstream commit that touched the SAME
# line, reset onto that upstream commit (exactly what the self-heal
# blocks below do), then popped — this is the one sequence that makes
# git attempt a real 3-way merge (not a "would be overwritten, stash
# first" refusal) and leaves genuine conflict markers. ---
printf 'header line\nbase line LOCAL-edit\n' > "$LOCAL/shared.jsonl"
git -C "$LOCAL" stash push --quiet -m "poison-setup"

printf 'header line\nbase line UPSTREAM-edit\n' > "$ORIGIN_WORK/shared.jsonl"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "upstream edits the same line"
git -C "$ORIGIN_WORK" push --quiet origin main

git -C "$LOCAL" fetch --quiet origin
git -C "$LOCAL" reset --hard --quiet origin/main

set +e
git -C "$LOCAL" stash pop --quiet >/dev/null 2>&1
POP_RC=$?
set -e
if [ "$POP_RC" -eq 0 ]; then
  echo "[test] SETUP FAIL: expected the manual pop to conflict, it didn't"
  exit 1
fi
UNMERGED_SETUP=$(git -C "$LOCAL" diff --name-only --diff-filter=U)
if [ "$UNMERGED_SETUP" != "shared.jsonl" ]; then
  echo "[test] SETUP FAIL: expected shared.jsonl unmerged, got: $UNMERGED_SETUP"
  exit 1
fi
# Confirm a plain `git stash push` on this poisoned index fails exactly as
# observed live on Mini, BEFORE we ever invoke the script under test.
set +e
git -C "$LOCAL" stash push --quiet -m "probe" >/dev/null 2>&1
PROBE_RC=$?
set -e
if [ "$PROBE_RC" -eq 0 ]; then
  echo "[test] SETUP FAIL: expected stash push to fail against a poisoned index"
  exit 1
fi
echo "[test] setup confirmed: poisoned index reproduces 'git stash push' failure, same as live Mini"

# Advance origin further so there's a real pull for the script to perform.
echo "unrelated upstream commit" > "$ORIGIN_WORK/other.txt"
git -C "$ORIGIN_WORK" add -A
git -C "$ORIGIN_WORK" commit --quiet -m "unrelated upstream commit"
git -C "$ORIGIN_WORK" push --quiet origin main

LOG_FILE="$WORK/logs/mini-git-pull.log"

set +e
bash "$SCRIPT" >/dev/null 2>&1
RC=$?
set -e

echo "[test] run exit: $RC"
sed 's/^/  | /' "$LOG_FILE"

if [ "$RC" -ne 0 ]; then
  echo "[test] FAIL: expected exit 0 (one run clears the inherited poison and completes the pull), got $RC"
  exit 1
fi
if grep -q "ERROR: git stash failed, skip" "$LOG_FILE"; then
  echo "[test] FAIL: the script gave up on the inherited poison instead of clearing and retrying"
  exit 1
fi
if ! grep -q "restored .* unmerged path(s) to clean HEAD after stash pop conflict" "$LOG_FILE"; then
  echo "[test] FAIL: log should confirm the inherited unmerged path was cleared"
  exit 1
fi

UNMERGED=$(git -C "$LOCAL" diff --name-only --diff-filter=U)
if [ -n "$UNMERGED" ]; then
  echo "[test] FAIL: working tree still has unmerged path(s) after the script ran: $UNMERGED"
  exit 1
fi

ORIGIN_HEAD=$(git -C "$ORIGIN_WORK" rev-parse main)
LOCAL_HEAD=$(git -C "$LOCAL" rev-parse HEAD)
if [ "$LOCAL_HEAD" != "$ORIGIN_HEAD" ]; then
  echo "[test] FAIL: did not land on origin/main HEAD ($LOCAL_HEAD != $ORIGIN_HEAD)"
  exit 1
fi

# The original attempted LOCAL-edit stays recoverable (the earlier,
# already-conflicted stash is cleared to clean HEAD content by the
# resolver — not re-created — so there is nothing further to pop; the
# resolver's own existing contract already covers "preserve in the
# stash list", asserted by test-mini-git-pull-stash-conflict-cleanup.sh).

rm -rf "$WORK"
echo "[test] PASS — a pre-existing poisoned index (inherited, not caused by this run) no longer loops forever."
