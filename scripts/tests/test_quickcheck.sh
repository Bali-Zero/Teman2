#!/usr/bin/env bash
# scripts/tests/test_quickcheck.sh — guilt+innocence for scripts/quickcheck.sh's
# R1 heading matcher (cicatrix-superscar.md #3: no guard ships without both).
#
# Sources scripts/quickcheck.sh to get at check_r1_heading() directly, rather
# than shelling out to the whole script — quickcheck.sh's BASH_SOURCE guard at
# its own tail makes this side-effect-free (sourcing only defines functions;
# nothing runs until `main` is explicitly called, which this test never does).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QUICKCHECK="$REPO_ROOT/scripts/quickcheck.sh"

if [ ! -f "$QUICKCHECK" ]; then
    echo "FAIL - $QUICKCHECK not found"
    exit 1
fi

# shellcheck source=/dev/null
source "$QUICKCHECK"

FAILED=0

expect() {
    local desc="$1" want="$2" got="$3"
    if [ "$want" = "$got" ]; then
        echo "  ok   - $desc"
    else
        echo "  FAIL - $desc (want=$want got=$got)"
        FAILED=1
    fi
}

matches() {
    # Prints 1/0 instead of relying on $? across the caller, so callers can't
    # accidentally read the wrong command's exit code (the exact pipe-masks-rc
    # class this repo has scars for).
    if printf '%s' "$1" | check_r1_heading; then
        echo 1
    else
        echo 0
    fi
}

# --- INNOCENCE: the literal heading, exactly as R1 requires, must be accepted ---
BODY_OK="Why/what here.

## Adversarial review

Seat: Sonnet 5. none survived, 2 raised.
"
expect "accepts literal '## Adversarial review'" 1 "$(matches "$BODY_OK")"

# Heading need not be the only content on the line's continuation, and may
# not be the first line of the body — still must match.
BODY_OK_TRAILING_TEXT="# Title

## Adversarial review

none survived, 0 raised
"
expect "accepts heading with body text following" 1 "$(matches "$BODY_OK_TRAILING_TEXT")"

# --- GUILT 1: wrong case must be rejected (case-sensitive by design) ---
BODY_LOWERCASE="# Title

## adversarial review

none.
"
expect "rejects lowercase '## adversarial review'" 0 "$(matches "$BODY_LOWERCASE")"

# --- GUILT 2: no hashes (not a markdown heading at all) must be rejected ---
BODY_NO_HASH="# Title

Adversarial review

none.
"
expect "rejects 'Adversarial review' with no hashes" 0 "$(matches "$BODY_NO_HASH")"

# --- GUILT 3: mere substring 'adversarial' anywhere in the body must be rejected ---
BODY_SUBSTRING="# Title

We reviewed this adversarially before merging and found nothing wrong.
"
expect "rejects mere substring 'adversarial' with no heading" 0 "$(matches "$BODY_SUBSTRING")"

# --- GUILT 4 (bonus — not in the mandate's 3, but the same failure class):
# a heading with the WRONG number of hashes (### not ##) must be rejected —
# quickcheck's matcher is intentionally an exact literal, narrower than the
# real CI gate's `^#{2,}\s+...` regex (see quickcheck.sh's own comment).
BODY_TRIPLE_HASH="# Title

### Adversarial review

none.
"
expect "rejects '### Adversarial review' (wrong hash count)" 0 "$(matches "$BODY_TRIPLE_HASH")"

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "ALL PASS"
    exit 0
else
    echo "SOME FAILED"
    exit 1
fi
