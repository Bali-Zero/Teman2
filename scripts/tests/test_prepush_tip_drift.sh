#!/bin/sh
# Guilt + innocence corpus for scripts/ci/prepush_tip_drift.sh.
#
# A guard merged without BOTH halves is half a guard (superscar #3). The guilt
# cases prove it still bites the drift it was written for; the innocence cases
# prove it does not bite the ordinary push, the deletion, or the ref it simply
# cannot see — the three shapes where accusing would be an over-match.
#
# Each case builds a REAL throwaway git repo and drives the checker with a real
# pre-push protocol file. Nothing is mocked: the thing under test resolves refs
# with `git rev-parse`, so a fake would only prove the fake.
#
# Run:  sh scripts/tests/test_prepush_tip_drift.sh

set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
CHECK="$HERE/scripts/ci/prepush_tip_drift.sh"

[ -x "$CHECK" ] || { echo "FATAL: $CHECK missing or not executable"; exit 1; }

PASS=0
FAIL=0

# Every assertion prints the observed rc, so a wrong-reason pass is visible.
expect_rc() {
    _want=$1; _got=$2; _what=$3
    if [ "$_want" = "$_got" ]; then
        PASS=$((PASS + 1)); echo "  ok   $_what (rc=$_got)"
    else
        FAIL=$((FAIL + 1)); echo "  FAIL $_what — wanted rc=$_want, got rc=$_got"
    fi
}

expect_mentions() {
    _needle=$1; _out=$2; _what=$3
    case "$_out" in
        *"$_needle"*) PASS=$((PASS + 1)); echo "  ok   $_what" ;;
        *) FAIL=$((FAIL + 1)); echo "  FAIL $_what — output never mentions '$_needle'" ;;
    esac
}

WORK=$(mktemp -d) || exit 1
trap 'rm -rf "$WORK"' EXIT INT TERM

# --- a real repo with two commits on one branch ----------------------------
REPO="$WORK/repo"
mkdir -p "$REPO"
cd "$REPO" || exit 1
git init -q -b work .
git config user.email t@t.t
git config user.name t
echo one > f && git add f && git commit -qm one
SHA_OLD=$(git rev-parse HEAD)
echo two > f && git add f && git commit -qm two
SHA_NEW=$(git rev-parse HEAD)
ZERO="0000000000000000000000000000000000000000"

# ---------------------------------------------------------------------------
# GUILT — the gate judged SHA_OLD, the branch now sits at SHA_NEW
# ---------------------------------------------------------------------------
printf 'refs/heads/work %s refs/heads/work %s\n' "$SHA_OLD" "$ZERO" > "$WORK/drift.txt"
OUT=$(sh "$CHECK" "$WORK/drift.txt" 2>&1); RC=$?
expect_rc 1 "$RC" "guilt: a commit landed while the gate ran"
expect_mentions "refs/heads/work" "$OUT" "guilt: names the ref that drifted"
expect_mentions "$SHA_NEW" "$OUT" "guilt: reports the sha that will actually land"

# GUILT-2 — drift on ONE ref out of two must still refuse
printf 'refs/heads/work %s refs/heads/work %s\nrefs/heads/other %s refs/heads/other %s\n' \
    "$SHA_NEW" "$ZERO" "$SHA_OLD" "$ZERO" > "$WORK/mixed.txt"
git branch -q other "$SHA_NEW"   # 'other' resolves, but to a different sha
OUT=$(sh "$CHECK" "$WORK/mixed.txt" 2>&1); RC=$?
expect_rc 1 "$RC" "guilt: one clean ref does not excuse a drifted sibling"

# ---------------------------------------------------------------------------
# INNOCENCE — the ordinary push, and the two shapes that must not be accused
# ---------------------------------------------------------------------------
printf 'refs/heads/work %s refs/heads/work %s\n' "$SHA_NEW" "$SHA_OLD" > "$WORK/clean.txt"
OUT=$(sh "$CHECK" "$WORK/clean.txt" 2>&1); RC=$?
expect_rc 0 "$RC" "innocence: nothing moved — the ordinary push"
expect_mentions "1 ref(s) still at the sha" "$OUT" "innocence: says what it verified"

# A branch DELETION carries the all-zero local sha: no commit to compare. It is
# legitimate, so it must not be called drift — and with nothing else in the push
# there is also nothing verified, which is exit 2, not a silent 0 (W84).
printf 'refs/heads/work %s refs/heads/work %s\n' "$ZERO" "$SHA_NEW" > "$WORK/del.txt"
OUT=$(sh "$CHECK" "$WORK/del.txt" 2>&1); RC=$?
expect_rc 2 "$RC" "innocence: a delete-only push is unverifiable, not drifted"

# A ref that no longer resolves locally is absence, not evidence. Accusing on it
# would be the over-match twin of the bug this guard exists for.
printf 'refs/heads/ghost %s refs/heads/ghost %s\n' "$SHA_OLD" "$ZERO" > "$WORK/ghost.txt"
OUT=$(sh "$CHECK" "$WORK/ghost.txt" 2>&1); RC=$?
expect_rc 2 "$RC" "innocence: a vanished ref is not verified and not accused"
expect_mentions "no longer resolves" "$OUT" "innocence: says WHY it could not verify"

# Deletion + a genuinely clean ref: the clean one is comparable, so verdict 0.
printf 'refs/heads/gone %s refs/heads/gone %s\nrefs/heads/work %s refs/heads/work %s\n' \
    "$ZERO" "$SHA_OLD" "$SHA_NEW" "$SHA_OLD" > "$WORK/mixdel.txt"
OUT=$(sh "$CHECK" "$WORK/mixdel.txt" 2>&1); RC=$?
expect_rc 0 "$RC" "innocence: a deletion alongside an unmoved ref still passes"

# ---------------------------------------------------------------------------
# W84 — an empty read is never a clean read
# ---------------------------------------------------------------------------
: > "$WORK/empty.txt"
OUT=$(sh "$CHECK" "$WORK/empty.txt" 2>&1); RC=$?
expect_rc 2 "$RC" "blind: an EMPTY ref file is 'cannot verify', never 'clean'"

OUT=$(sh "$CHECK" "$WORK/does-not-exist.txt" 2>&1); RC=$?
expect_rc 2 "$RC" "blind: a MISSING ref file is 'cannot verify'"

OUT=$(sh "$CHECK" 2>&1); RC=$?
expect_rc 2 "$RC" "blind: no argument at all is 'cannot verify'"

# ---------------------------------------------------------------------------
# W101 — the guard must not decapitate itself under errexit
# ---------------------------------------------------------------------------
# The ghost case makes `git rev-parse` exit non-zero INSIDE the loop. Under a
# caller running `sh -e`, a bare assignment there would abort the script before
# its own verdict — the precise scar this check ships beside. Running it with
# -e must still produce the honest exit 2, not a silent death.
OUT=$(sh -e "$CHECK" "$WORK/ghost.txt" 2>&1); RC=$?
expect_rc 2 "$RC" "W101: survives a failing rev-parse under 'sh -e'"

echo ""
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
