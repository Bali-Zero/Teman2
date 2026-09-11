#!/usr/bin/env bash
# test_sentry_quota_probe.sh — guilt + innocence for the quota probe's verdict logic.
#
# DERIVES the logic from the real script instead of restating it: it extracts the
# PROBE_CODE/PROBE_LIMITS parsing and the `case` block from sentry-quota-check.sh
# and executes THAT. A test that transcribed the branches by hand would stay green
# after someone edited the script, which is precisely the failure being guarded.
set -uo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/sentry-quota-check.sh"
[[ -f "$SCRIPT" ]] || { echo "FAIL: cannot find $SCRIPT"; exit 1; }

LOGIC="$(sed -n '/^PROBE_CODE=/,/^esac$/p' "$SCRIPT")"
if [[ -z "$LOGIC" ]]; then
    echo "FAIL: could not extract verdict logic from $SCRIPT (did the shape change?)"
    exit 1
fi
# Anti-false-negative: prove the extraction actually caught the branches.
for needle in 'PROBE_CODE=' 'PROBE_LIMITS=' '429)' 'exit 4' 'exit 5' 'usage_exceeded'; do
    grep -q -- "$needle" <<<"$LOGIC" || { echo "FAIL: extracted logic missing '$needle' — extraction is blind"; exit 1; }
done
echo "extraction: $(wc -l <<<"$LOGIC" | tr -d ' ') lines, all 6 markers present"

run_case() {
    (
        PROBE_OUT="$1"
        alert() { :; }
        eval "$LOGIC"
        exit 0
    ) >/dev/null 2>&1
    echo $?
}

fails=0
assert() {
    local got; got="$(run_case "$2")"
    if [[ "$got" == "$3" ]]; then
        echo "  ok   $1 -> exit $got"
    else
        echo "  FAIL $1 -> exit $got (expected $3)"; fails=$((fails+1))
    fi
}

echo "GUILT (must be caught):"
assert "quota exhausted"     "429 60:default;error;security;attachment:organization:error_usage_exceeded" 4
assert "rate-limited other"  "429 60:default;error:project:something_else" 4
assert "shape unparsed"      "SHAPE_UNPARSED" 5
assert "network error"       "NETERR URLError" 5
assert "empty output"        "" 5
assert "unexpected status"   "503 " 5

echo "INNOCENCE (must NOT be caught):"
assert "bucket accepting"    "200 " 0

if (( fails )); then echo "FAILED: $fails case(s)"; exit 1; fi
echo "PASS: 7/7"
