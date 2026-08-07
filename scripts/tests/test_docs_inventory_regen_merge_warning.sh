#!/usr/bin/env bash
# Proof that the "you are mid-merge" advice fires when it should, stays quiet
# when it should, and can never fail its caller.
#
# Measured 2026-08-07 (PR #3750): the docs inventory was regenerated between
# `git merge` and `git commit`, while the merge was still conflicted. HEAD was
# still the branch's own tip, so `git log -1 -- <path>` — where docs_audit.py
# reads `last_touched_date` — walked a history without the commits being merged
# and wrote two rows a day stale. The `inventory-check` gate charged the PR.
#
#   GUILT     — a real conflicted merge is open: the advice must be printed, and
#               it must name the FIX (run again after the commit), not just the
#               symptom. An alarm that says "something is off" costs a reader
#               the same investigation the alarm was supposed to save.
#   INNOCENCE — a clean tree, and a tree with UNCOMMITTED CHANGES that are not a
#               merge: silence. The second is the case that matters — the naive
#               guard is "is the tree dirty?", which would fire on every ordinary
#               edit and be muted within a week.
#   SYMMETRY  — a merge that has been COMMITTED is silent again, because that is
#               precisely the state in which regenerating is correct.
#   CONTRACT  — the function returns 0 in every one of those states. It is
#               advice; a caller must not be able to fail because of it, and a
#               future `set -e` upstream must not turn advice into an abort.
#
# Everything runs in throwaway git repos under a tmp dir; the real repo is only
# ever READ (to source the helper).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
LIB="$REPO_ROOT/lib/git_merge_state.sh"
[ -f "$LIB" ] || { echo "helper not found at $LIB"; exit 1; }
# shellcheck source=/dev/null
. "$LIB"

TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

PASS=0
FAIL=0
check() { # check <label> <expected: fires|silent> <repo>
  local label="$1" expect="$2" repo="$3" out rc
  out="$(warn_if_merge_in_progress "$repo" 2>&1 >/dev/null)"
  rc=$?
  local got="silent"
  [ -n "$out" ] && got="fires"
  if [ "$got" != "$expect" ]; then
    echo "  FAIL $label: expected $expect, got $got"
    FAIL=$((FAIL + 1))
    return
  fi
  if [ "$rc" -ne 0 ]; then
    echo "  FAIL $label: advice returned rc=$rc — it must always be 0"
    FAIL=$((FAIL + 1))
    return
  fi
  echo "  ok   $label ($got, rc=0)"
  PASS=$((PASS + 1))
}

mkrepo() { # mkrepo <dir>  -> a repo with one commit on `main`
  local d="$1"
  mkdir -p "$d"
  git -C "$d" init -q -b main
  git -C "$d" config user.email t@example.com
  git -C "$d" config user.name Test
  printf 'base\n' > "$d/f.txt"
  git -C "$d" add f.txt
  git -C "$d" commit -qm base
}

# --- INNOCENCE 1: clean tree -------------------------------------------------
mkrepo "$TMP/clean"
check "clean tree" silent "$TMP/clean"

# --- INNOCENCE 2: dirty, but NOT a merge ------------------------------------
# The naive guard ("tree is dirty") would fire here on every ordinary edit.
mkrepo "$TMP/dirty"
printf 'edited\n' >> "$TMP/dirty/f.txt"
check "uncommitted edits, no merge" silent "$TMP/dirty"

# --- GUILT: a genuinely conflicted, uncommitted merge ------------------------
mkrepo "$TMP/merging"
git -C "$TMP/merging" checkout -q -b other
printf 'theirs\n' > "$TMP/merging/f.txt"
git -C "$TMP/merging" commit -qam theirs
git -C "$TMP/merging" checkout -q main
printf 'ours\n' > "$TMP/merging/f.txt"
git -C "$TMP/merging" commit -qam ours
git -C "$TMP/merging" merge other >/dev/null 2>&1  # expected to conflict
if ! git -C "$TMP/merging" rev-parse --verify -q MERGE_HEAD >/dev/null 2>&1; then
  echo "  FAIL setup: the fixture did not actually leave a merge open — the"
  echo "             guilt case would have measured its own setup, not the guard"
  FAIL=$((FAIL + 1))
else
  check "conflicted merge in progress" fires "$TMP/merging"
  msg="$(warn_if_merge_in_progress "$TMP/merging" 2>&1 >/dev/null)"
  # shellcheck disable=SC2016  # the literal is the point: this asserts the
  # advice's own wording, so expansion would defeat the assertion.
  if printf '%s' "$msg" | grep -q 'ONCE MORE after `git commit`'; then
    echo "  ok   the advice names the fix, not just the symptom"
    PASS=$((PASS + 1))
  else
    echo "  FAIL the advice fires but never tells the reader what to do"
    FAIL=$((FAIL + 1))
  fi
fi

# --- SYMMETRY: the same repo, once the merge is COMMITTED --------------------
if git -C "$TMP/merging" rev-parse --verify -q MERGE_HEAD >/dev/null 2>&1; then
  printf 'resolved\n' > "$TMP/merging/f.txt"
  git -C "$TMP/merging" add f.txt
  git -C "$TMP/merging" commit -qm merged
  check "merge committed" silent "$TMP/merging"
fi

echo
echo "merge-state advice: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
