#!/usr/bin/env bash
# Guilt + innocence for scripts/hooks/injected_surface_sessionstart.sh.
#
# The receptor's ONE promise is that it is never silent while armed: silence
# must mean exactly "not registered", never "ran and had nothing to say". That
# promise is the whole reason it exists — the injected surface grew from ~150 KB
# to 783,444 B with nothing printing it, so nobody could miss the growth. A
# receptor that can be quiet is indistinguishable from an absent one.
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/hooks/injected_surface_sessionstart.sh"
FAIL=0
check() { if [ "$1" = "1" ]; then echo "  ok   — $2"; else echo "  FAIL — $2"; FAIL=1; fi; }

echo "innocence:"
OUT="$(bash "$HOOK" 2>&1)"; RC=$?
check "$([ $RC -eq 0 ] && echo 1 || echo 0)" "exits 0 (a receptor that can block session boot gets disarmed)"
check "$([ -n "$OUT" ] && echo 1 || echo 0)" "is NOT silent on a healthy repo"
check "$(printf '%s' "$OUT" | grep -q 'INJECTED SURFACE' && echo 1 || echo 0)" "names the surface it measured"
check "$(printf '%s' "$OUT" | grep -qE '[0-9],?[0-9]* B' && echo 1 || echo 0)" "reports a byte figure, not just a verdict"

echo "guilt:"
# The attestation script missing is the deployment fault most likely to happen
# (the hook is a HOME-fork copy; the script it calls is not). It must SAY so.
TMP="$(mktemp -d)"; mkdir -p "$TMP/scripts/hooks"
sed 's|/scripts/injected_surface_attest.py|/scripts/DOES_NOT_EXIST.py|' "$HOOK" > "$TMP/scripts/hooks/h.sh"
OUT2="$(bash "$TMP/scripts/hooks/h.sh" 2>&1)"; RC2=$?
check "$([ $RC2 -eq 0 ] && echo 1 || echo 0)" "still exits 0 when its own dependency is missing"
check "$([ -n "$OUT2" ] && echo 1 || echo 0)" "still speaks when its own dependency is missing"
check "$(printf '%s' "$OUT2" | grep -qi 'missing' && echo 1 || echo 0)" "says the measurement did NOT happen, rather than reporting a clean number"
check "$(printf '%s' "$OUT2" | grep -q 'INJECTED SURFACE [0-9]' && echo 0 || echo 1)" "does NOT emit a byte figure it could not have measured"

# The kill switch is the ONE case where silence is correct, and it must be exact.
OUT3="$(INJECTED_SURFACE_RECEPTOR_ENABLED=false bash "$HOOK" 2>&1)"
check "$([ -z "$OUT3" ] && echo 1 || echo 0)" "kill switch silences it completely"
OUT4="$(INJECTED_SURFACE_RECEPTOR_ENABLED=maybe bash "$HOOK" 2>&1)"
check "$([ -n "$OUT4" ] && echo 1 || echo 0)" "any value OTHER than 'false' leaves it armed (fail-safe, not fail-quiet)"
rm -rf "$TMP"

[ $FAIL -eq 0 ] && echo "PASS" || echo "FAILURES"
exit $FAIL
