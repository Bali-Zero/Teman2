#!/usr/bin/env bash
# test_cost_breaker_deadman.sh — falsifiable test for the P9 G5 dead-man's
# switch stale-detection logic (P2-5).
#
# FORCE_ALERT short-circuits the real stale logic in cost_breaker_deadman.sh, so
# the MISSING/STALE/FRESH classification had ZERO coverage. The `--classify`
# mode exposes that logic side-effect-free (no telegram, no state write). This
# test drives it through all three states + exit codes + injected `now`.
#
# Run:  bash scripts/test_cost_breaker_deadman.sh
# Exit: 0 all pass, 1 any failure.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEADMAN="$HERE/cost_breaker_deadman.sh"

fail=0
pass=0

# check <desc> <expected_out> <expected_code> -- <classify args...>
check() {
    local desc="$1" exp_out="$2" exp_code="$3"
    shift 4  # drop desc, exp_out, exp_code, and the literal "--"
    local out code
    out="$(bash "$DEADMAN" --classify "$@" 2>/dev/null)"
    code=$?
    if [[ "$out" == "$exp_out" && "$code" == "$exp_code" ]]; then
        pass=$((pass + 1))
        echo "ok   - $desc (out=$out code=$code)"
    else
        fail=$((fail + 1))
        echo "FAIL - $desc: expected out=$exp_out code=$exp_code, got out=$out code=$code"
    fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fresh_file="$tmpdir/fresh.json"
stale_file="$tmpdir/stale.json"
missing_file="$tmpdir/does-not-exist.json"

touch "$fresh_file"
# Make stale_file old (BSD touch -t: 2020-01-01 00:00).
touch -t 202001010000 "$stale_file"

# FRESH: just-touched file, generous threshold.
check "fresh file is FRESH" "FRESH" "0" -- "$fresh_file" 1800

# STALE: file from 2020, small threshold.
check "old file is STALE" "STALE" "1" -- "$stale_file" 60

# MISSING: file does not exist.
check "missing file is MISSING" "MISSING" "2" -- "$missing_file" 60

# Injected now: with now far in the future, even a fresh file is STALE
# (the injected clock is the comparison anchor — proves now is honored).
check "injected future now makes fresh file STALE" "STALE" "1" -- "$fresh_file" 100 9999999999

# Injected now == file mtime → age 0 → FRESH (boundary).
# Portable mtime read: BSD/macOS `stat -f %m`, GNU/Linux `stat -c %Y`.
fresh_mtime="$(stat -f %m "$fresh_file" 2>/dev/null || stat -c %Y "$fresh_file")"
check "injected now == mtime is FRESH (age 0)" "FRESH" "0" -- "$fresh_file" 0 "$fresh_mtime"

echo "----"
echo "passed=$pass failed=$fail"
[[ "$fail" -eq 0 ]]
