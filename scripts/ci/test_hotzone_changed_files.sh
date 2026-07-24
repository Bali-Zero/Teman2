#!/usr/bin/env bash
# Guilt + innocence corpus for scripts/ci/hotzone_changed_files.sh
# (superscar #3 antidote: "nessuna guardia mergiata senza un test di innocenza
#  E di colpevolezza" — here the guard is the gate's INPUT, which is where the
#  2026-07-24 false-block actually came from).
#
# GUILT     — a branch that really edits .github/CODEOWNERS is still reported.
# INNOCENCE — a branch that edits only content, while MAIN moved ahead and
#             touched .github/CODEOWNERS, is NOT reported as touching it.
# SCAR-PIN  — the old two-dot implementation IS shown to fail the innocence case,
#             so the test can never go vacuously green after a refactor.
#
# Runs in any POSIX-ish shell with git. No network, no fixtures on disk.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNDER_TEST="$SCRIPT_DIR/hotzone_changed_files.sh"
FAILURES=0

fail() { echo "  ✗ $*"; FAILURES=$((FAILURES + 1)); }
pass() { echo "  ✓ $*"; }

if [[ ! -x "$UNDER_TEST" ]]; then
  echo "FATAL: $UNDER_TEST missing or not executable"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --------------------------------------------------------------- fixture repo
# initial ──● main ──● (main edits CODEOWNERS: the "innocent bystander" commit)
#            \
#             ●  feature-content   (edits only an article)
#             ●  feature-codeowners (edits CODEOWNERS for real)
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email test@example.com
git config user.name "hotzone test"
git config commit.gpgsign false

mkdir -p .github apps/mouth/src/content/articles/tax
printf 'apps/** @Balizero1987\n' > .github/CODEOWNERS
printf 'original article\n' > apps/mouth/src/content/articles/tax/a.mdx
git add -A && git commit -qm "initial"
INITIAL="$(git rev-parse HEAD)"

# main moves ahead and touches the hot-zone file
printf 'apps/** @Balizero1987\ndocs/** @Balizero1987\n' > .github/CODEOWNERS
git add -A && git commit -qm "main: extend CODEOWNERS"
MAIN_TIP="$(git rev-parse HEAD)"

# innocent branch, forked BEFORE main's CODEOWNERS commit
git checkout -q -b feature-content "$INITIAL"
printf 'corrected article\n' > apps/mouth/src/content/articles/tax/a.mdx
git add -A && git commit -qm "content: fix article"
CONTENT_HEAD="$(git rev-parse HEAD)"

# guilty branch, also forked before, that really edits CODEOWNERS
git checkout -q -b feature-codeowners "$INITIAL"
printf 'apps/** @someone-else\n' > .github/CODEOWNERS
git add -A && git commit -qm "chore: self-mod CODEOWNERS"
CODEOWNERS_HEAD="$(git rev-parse HEAD)"

git checkout -q "$MAIN_TIP"

echo "TEST hotzone_changed_files.sh"

# ------------------------------------------------------------------- GUILT
out="$("$UNDER_TEST" "$MAIN_TIP" "$CODEOWNERS_HEAD" 2>/dev/null)"
if grep -qx '\.github/CODEOWNERS' <<< "$out"; then
  pass "guilt: real CODEOWNERS edit is reported"
else
  fail "guilt: real CODEOWNERS edit MISSED (output: ${out//$'\n'/, })"
fi

# --------------------------------------------------------------- INNOCENCE
out="$("$UNDER_TEST" "$MAIN_TIP" "$CONTENT_HEAD" 2>/dev/null)"
if grep -qx '\.github/CODEOWNERS' <<< "$out"; then
  fail "innocence: content-only branch falsely reported as touching CODEOWNERS"
else
  pass "innocence: content-only branch behind main does not touch CODEOWNERS"
fi
if grep -qx 'apps/mouth/src/content/articles/tax/a\.mdx' <<< "$out"; then
  pass "innocence: the branch's own file IS still reported"
else
  fail "innocence: the branch's own file went missing (output: ${out//$'\n'/, })"
fi

# ---------------------------------------------------------------- SCAR PIN
# The pre-fix implementation must demonstrably fail the innocence case,
# otherwise this test proves nothing.
old_out="$(git diff --name-only "$MAIN_TIP" "$CONTENT_HEAD")"
if grep -qx '\.github/CODEOWNERS' <<< "$old_out"; then
  pass "scar-pin: the old two-dot diff DOES produce the false positive"
else
  fail "scar-pin: two-dot no longer reproduces the scar — test is vacuous, revisit it"
fi

# ------------------------------------------------------- FAIL-LOUD, NOT BLIND
# An unresolvable pair must exit non-zero, never print an empty pass.
if out="$("$UNDER_TEST" "$MAIN_TIP" 0000000000000000000000000000000000000000 2>/dev/null)"; then
  fail "fail-loud: unresolvable head exited 0 (blind-empty pass) — output: '$out'"
else
  pass "fail-loud: unresolvable head exits non-zero instead of passing blind"
fi

echo
if [[ "$FAILURES" -gt 0 ]]; then
  echo "FAIL — $FAILURES assertion(s) failed"
  exit 1
fi
echo "PASS — guilt + innocence + scar-pin + fail-loud"
