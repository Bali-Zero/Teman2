#!/usr/bin/env bash
# test_pii_gate_merge_scope.sh — guilt + innocence for the `.husky/pre-commit`
# Law-2 PII gate's FILE ENUMERATION on merge commits.
#
# THE DEFECT (measured 2026-07-30): the gate enumerated with a bare
# `git diff --cached --name-only`, which compares the index against the FIRST
# parent. On a merge commit that reports every file the OTHER side changed since
# the merge base — files this commit did not author — and then reads each one IN
# FULL via `git show ":$f"`. A synthetic 12-file merge made the gate enumerate 12
# while the commit authored 0. On a real merge of a weeks-old main that is
# hundreds of files, any one of which tripping the regex blocks the merge under a
# message that says "staged path/content": naming work the committer never wrote,
# which — coming from origin/main — is already public anyway.
#
# The block under test is EXTRACTED VERBATIM from the live hook between its
# PII_ENUMERATE_BEGIN/END markers, so this test breaks the moment the hook drifts
# from what is pinned here, and it is run under `sh -e` — the same shell husky
# uses (`.husky/_/h`: `sh -e "$s"`), so an errexit-sensitive construct fails here
# exactly as it would in production. Same discipline as
# test_husky_pii_pass_overmatch.py, which extracts the regex rather than
# re-typing it.
#
# Run:  bash scripts/tests/test_pii_gate_merge_scope.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO_ROOT/.husky/pre-commit"
PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1"; }

BLOCK="$(sed -n '/PII_ENUMERATE_BEGIN/,/PII_ENUMERATE_END/p' "$HOOK")"
if [ -z "$BLOCK" ]; then
    echo "❌ could not extract the PII_ENUMERATE block from $HOOK"
    echo "   The markers are load-bearing: without them this test silently tests nothing."
    exit 1
fi
# Guard against the marker surviving while the logic behind it is gutted.
case "$BLOCK" in
    *MERGE_HEAD*) : ;;
    *) echo "❌ extracted block no longer mentions MERGE_HEAD — the merge arm is gone"; exit 1 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Run the extracted enumeration in $1 and echo the resulting PII_FILES.
enumerate() {
    ( cd "$1" && sh -e -c "$BLOCK
printf '%s\n' \"\$PII_FILES\"" 2>&1 )
}

new_repo() {
    d="$WORK/$1"
    rm -rf "$d"; mkdir -p "$d"
    git -C "$d" init -q -b main .
    git -C "$d" config user.email t@t
    git -C "$d" config user.name t
    echo "$d"
}

echo "── PII gate merge-scope corpus ─────────────────────────────────────────"

# ── Case 1 (INNOCENCE, non-merge): ordinary commit still sees its own files ──
R="$(new_repo plain)"
echo hello > "$R/a.txt"; echo hello > "$R/b.txt"
git -C "$R" add -A
OUT="$(enumerate "$R")"
if printf '%s' "$OUT" | grep -qx "a.txt" && printf '%s' "$OUT" | grep -qx "b.txt"; then
    ok "case 1 — non-merge commit enumerates its own staged files (no regression)"
else
    bad "case 1 — non-merge enumeration lost files. got: $(printf '%s' "$OUT" | tr '\n' ' ')"
fi

# ── Case 2 (the defect): clean merge must NOT enumerate the other side's files ──
R="$(new_repo cleanmerge)"
for i in 1 2 3; do echo "base $i" > "$R/f$i.txt"; done
git -C "$R" add -A; git -C "$R" commit -qm base
git -C "$R" checkout -qb feature
echo "mine" > "$R/mine.txt"; git -C "$R" add -A; git -C "$R" commit -qm feature
git -C "$R" checkout -q main
for i in 1 2 3; do echo "main moved $i" > "$R/f$i.txt"; done
echo "new on main" > "$R/n1.txt"
git -C "$R" add -A; git -C "$R" commit -qm "main moves ahead"
git -C "$R" checkout -q feature
git -C "$R" merge --no-commit --no-ff main >/dev/null 2>&1 || true
OUT="$(enumerate "$R")"
LEAKED="$(printf '%s\n' "$OUT" | grep -E '^(f1|f2|f3|n1)\.txt$' || true)"
if [ -z "$LEAKED" ]; then
    ok "case 2 — clean merge does not attribute the other parent's files to this commit"
else
    bad "case 2 — merge still enumerates files it did not author: $(printf '%s' "$LEAKED" | tr '\n' ' ')"
fi

# ── Case 3 (GUILT): a resolved conflict IS this commit's work and must be seen ──
# Without this case, "enumerate nothing on a merge" would pass case 2 and be a
# fail-open gate. This is the innocence/guilt pair that keeps the narrowing honest.
R="$(new_repo conflict)"
echo "base" > "$R/c.txt"; git -C "$R" add -A; git -C "$R" commit -qm base
git -C "$R" checkout -qb feature
echo "feature side" > "$R/c.txt"; git -C "$R" add -A; git -C "$R" commit -qm feature
git -C "$R" checkout -q main
echo "main side" > "$R/c.txt"; git -C "$R" add -A; git -C "$R" commit -qm main
git -C "$R" checkout -q feature
git -C "$R" merge --no-commit --no-ff main >/dev/null 2>&1 || true
printf 'resolved by a human\n' > "$R/c.txt"       # differs from BOTH parents
git -C "$R" add c.txt
OUT="$(enumerate "$R")"
if printf '%s' "$OUT" | grep -qx "c.txt"; then
    ok "case 3 — a human-resolved conflict is still enumerated (narrowing is not fail-open)"
else
    bad "case 3 — resolved conflict went UNSEEN. got: $(printf '%s' "$OUT" | tr '\n' ' ')"
fi

# ── Case 4 (FAIL-VISIBLE): unusable MERGE_HEAD ⇒ full set + a loud warning ─────
# W84 discipline: a scan that cannot see is not clean. Narrowing must never
# happen blind — the safe direction is over-inclusive, and it must say so.
R="$(new_repo blindmerge)"
for i in 1 2 3; do echo "base $i" > "$R/f$i.txt"; done
git -C "$R" add -A; git -C "$R" commit -qm base
git -C "$R" checkout -qb feature
echo "mine" > "$R/mine.txt"; git -C "$R" add -A; git -C "$R" commit -qm feature
git -C "$R" checkout -q main
for i in 1 2 3; do echo "main moved $i" > "$R/f$i.txt"; done
git -C "$R" add -A; git -C "$R" commit -qm "main moves"
git -C "$R" checkout -q feature
git -C "$R" merge --no-commit --no-ff main >/dev/null 2>&1 || true
printf '%s\n' "0000000000000000000000000000000000000000" > "$R/.git/MERGE_HEAD"
OUT="$(enumerate "$R")"
if printf '%s' "$OUT" | grep -q "FULL staged set" && printf '%s\n' "$OUT" | grep -qx "f1.txt"; then
    ok "case 4 — unusable MERGE_HEAD falls back to the full set AND says so"
else
    bad "case 4 — blind narrowing or silent fallback. got: $(printf '%s' "$OUT" | tr '\n' ' ')"
fi

# ── Case 5 (errexit): the block must survive `sh -e` on every path ─────────────
# W101 lives here: a bare `VAR=$(failing)` under `sh -e` aborts the hook before
# any fallback branch can run. Case 4 already drives the failure path; this
# asserts the block did not die on the way (it produced output at all).
if [ -n "$OUT" ]; then
    ok "case 5 — block completes under sh -e on the failure path (no W101 decapitation)"
else
    bad "case 5 — block produced NOTHING under sh -e: it aborted mid-way"
fi

echo "────────────────────────────────────────────────────────────────────────"
echo "${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ]
