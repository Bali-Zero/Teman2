#!/usr/bin/env bash
# Proof for scripts/lib/fly_credential.sh — GUILT and INNOCENCE, both worlds.
#
# The resolver exists because a fix pinned to one day's world became the bug on
# another (see the header of fly_credential.sh). A proof that only covered
# today's world would pin it exactly the same way, so every case here is stated
# as a WORLD, and both historical worlds are asserted:
#
#   INNOCENCE — the 2026-06-03 world (stale env token shadowing a valid config
#               token) must STILL be cured: the resolver must not re-export the
#               env token when the config token works.
#   GUILT     — the 2026-07-26 world (dead config token, valid env token) must
#               now be cured: the resolver must fall back and SAY SO.
#   Plus: both-dead and no-env-token must fail loudly, exporting nothing.
#
# No network, no real credential, no file on disk is touched: `fly` is a stub
# that accepts or refuses according to the world under test.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ── the stub: a fly that answers according to the world ──────────────────────
cat > "$TMP/fly" <<'STUB'
#!/bin/sh
# Accepts `auth whoami` per the world: STUB_ENV_OK governs the answer when a
# token is present in the environment, STUB_CONFIG_OK when none is.
if [ "$1" = "auth" ] && [ "$2" = "whoami" ]; then
    if [ -n "${FLY_API_TOKEN:-}${FLY_ACCESS_TOKEN:-}" ]; then
        [ "${STUB_ENV_OK:-0}" = "1" ] && exit 0 || exit 1
    fi
    [ "${STUB_CONFIG_OK:-0}" = "1" ] && exit 0 || exit 1
fi
exit 1
STUB
chmod +x "$TMP/fly"

FAILURES=0
check() { # check <label> <condition-result> [detail]
    if [ "$2" = "0" ]; then printf '  PASS  %s\n' "$1"
    else printf '  FAIL  %s%s\n' "$1" "${3:+  [$3]}"; FAILURES=$((FAILURES + 1)); fi
}

# Run the resolver in a subshell shaped like `world`, and report back the
# outcome plus what was left in the environment.
run_world() { # run_world <config_ok> <env_ok> <env_token>
    (
        export STUB_CONFIG_OK="$1" STUB_ENV_OK="$2"
        if [ -n "$3" ]; then export FLY_API_TOKEN="$3"; else unset FLY_API_TOKEN; fi
        unset FLY_ACCESS_TOKEN
        # shellcheck source=lib/fly_credential.sh
        . "$HERE/lib/fly_credential.sh"
        resolve_fly_credential "$TMP/fly" > "$TMP/log" 2>&1
        rc=$?
        printf 'rc=%s token=%s\n' "$rc" "${FLY_API_TOKEN:-<unset>}"
    )
}

echo "=== INNOCENCE: the 2026-06-03 world — valid config token, STALE env token ==="
out=$(run_world 1 0 "stale-june-token")
check "resolver succeeds" "$([ "${out%% *}" = "rc=0" ] && echo 0 || echo 1)" "$out"
check "the stale env token is NOT re-exported (the 06-03 cure survives)" \
      "$(echo "$out" | grep -q "token=<unset>" && echo 0 || echo 1)" "$out"
check "log names the config file as the source" \
      "$(grep -q "config-file token" "$TMP/log" && echo 0 || echo 1)" "$(cat "$TMP/log")"

echo
echo "=== GUILT: the 2026-07-26 world — DEAD config token, valid env token ==="
out=$(run_world 0 1 "live-july-token")
check "resolver succeeds instead of aborting the backup" \
      "$([ "${out%% *}" = "rc=0" ] && echo 0 || echo 1)" "$out"
check "the working env token IS exported" \
      "$(echo "$out" | grep -q "token=live-july-token" && echo 0 || echo 1)" "$out"
check "the fallback is LOGGED, never silent" \
      "$(grep -q "REFUSED" "$TMP/log" && grep -q "FLY_API_TOKEN" "$TMP/log" && echo 0 || echo 1)" "$(cat "$TMP/log")"

echo
echo "=== INNOCENCE 2: both credentials valid — prefer config, export nothing ==="
out=$(run_world 1 1 "also-valid")
check "resolver succeeds" "$([ "${out%% *}" = "rc=0" ] && echo 0 || echo 1)" "$out"
check "does not gratuitously switch to the env token" \
      "$(echo "$out" | grep -q "token=<unset>" && echo 0 || echo 1)" "$out"

echo
echo "=== BOTH DEAD: must fail loudly and leave nothing exported ==="
out=$(run_world 0 0 "dead-token")
check "resolver fails (caller must abort)" \
      "$([ "${out%% *}" = "rc=1" ] && echo 0 || echo 1)" "$out"
check "no token left exported" \
      "$(echo "$out" | grep -q "token=<unset>" && echo 0 || echo 1)" "$out"
check "the error names BOTH sources" \
      "$(grep -q "BOTH" "$TMP/log" && echo 0 || echo 1)" "$(cat "$TMP/log")"
check "the error states the remedy" \
      "$(grep -q "fly auth login" "$TMP/log" && echo 0 || echo 1)" "$(cat "$TMP/log")"

echo
echo "=== CONFIG DEAD, NO env token at all — distinct, actionable message ==="
out=$(run_world 0 1 "")
check "resolver fails" "$([ "${out%% *}" = "rc=1" ] && echo 0 || echo 1)" "$out"
check "message says there is no FLY_API_TOKEN (not 'both refused')" \
      "$(grep -q "no FLY_API_TOKEN" "$TMP/log" && echo 0 || echo 1)" "$(cat "$TMP/log")"

echo
if [ "$FAILURES" -eq 0 ]; then
    echo "PROOF OK — both historical worlds cured, neither re-opened."
    exit 0
fi
echo "PROOF FAILED: $FAILURES check(s)"
exit 1
