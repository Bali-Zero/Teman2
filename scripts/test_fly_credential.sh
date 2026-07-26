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
# The last three worlds were added after an adversarial review of the first
# draft, which found two real defects the original corpus could not see:
#   - a valid FLY_ACCESS_TOKEN was destroyed whenever a stale FLY_API_TOKEN sat
#     beside it (the original corpus unset FLY_ACCESS_TOKEN in every world, so
#     it could never have caught this);
#   - `auth whoami` passes for a token scoped to a DIFFERENT app, so a caller
#     was handed a credential that could not do its job — the same silent-wrong-
#     answer shape, one stage later.
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
# Credential acceptance:
#   STUB_GOOD_TOKEN set  -> an env token is accepted iff it equals that value
#   otherwise            -> STUB_ENV_OK governs any env token
#   no env token         -> STUB_CONFIG_OK governs (i.e. the config-file path)
# Scope:
#   STUB_APP_SCOPE_FAILS=1 -> `machine list ...` is refused even when the
#   credential is otherwise accepted, mimicking a token scoped to another app.
tok="${FLY_API_TOKEN:-}"
if [ -n "$tok" ]; then
    if [ -n "${STUB_GOOD_TOKEN:-}" ]; then
        [ "$tok" = "$STUB_GOOD_TOKEN" ] && ok=1 || ok=0
    else
        ok="${STUB_ENV_OK:-0}"
    fi
else
    ok="${STUB_CONFIG_OK:-0}"
fi
if [ "$1" = "machine" ] && [ "${STUB_APP_SCOPE_FAILS:-0}" = "1" ]; then
    echo 'Could not find App "nuzantara-rag"' >&2
    exit 1
fi
if [ "$ok" = "1" ]; then
    [ "$1" = "auth" ] && echo "someone@tokens.fly.io"
    exit 0
fi
echo "no access token available. Please login with 'flyctl auth login'" >&2
exit 1
STUB
chmod +x "$TMP/fly"

FAILURES=0
check() { # check <label> <condition-result> [detail]
    if [ "$2" = "0" ]; then printf '  PASS  %s\n' "$1"
    else printf '  FAIL  %s%s\n' "$1" "${3:+  [$3]}"; FAILURES=$((FAILURES + 1)); fi
}
is() { [ "$1" = "$2" ] && echo 0 || echo 1; }
has() { grep -q -- "$1" "$TMP/log" && echo 0 || echo 1; }

# Run the resolver in a subshell shaped like `world`, and report back the
# outcome plus what was left in the environment.
# run_world <config_ok> <env_ok> <FLY_API_TOKEN> [FLY_ACCESS_TOKEN] [probe args...]
run_world() {
    local cfg="$1" envok="$2" apitok="$3" acctok="${4:-}"; shift 4 2>/dev/null || shift 3
    (
        export STUB_CONFIG_OK="$cfg" STUB_ENV_OK="$envok"
        if [ -n "$apitok" ]; then export FLY_API_TOKEN="$apitok"; else unset FLY_API_TOKEN; fi
        if [ -n "$acctok" ]; then export FLY_ACCESS_TOKEN="$acctok"; else unset FLY_ACCESS_TOKEN; fi
        # shellcheck source=lib/fly_credential.sh
        . "$HERE/lib/fly_credential.sh"
        resolve_fly_credential "$TMP/fly" "$@" > "$TMP/log" 2>&1
        rc=$?
        printf 'rc=%s token=%s source=%s\n' "$rc" "${FLY_API_TOKEN:-<unset>}" "${FLY_CREDENTIAL_SOURCE:-<none>}"
    )
}
field() { echo "$1" | tr ' ' '\n' | grep "^$2=" | cut -d= -f2-; }

echo "=== INNOCENCE: the 2026-06-03 world — valid config token, STALE env token ==="
out=$(run_world 1 0 "stale-june-token")
check "resolver succeeds" "$(is "$(field "$out" rc)" 0)" "$out"
check "the stale env token is NOT re-exported (the 06-03 cure survives)" \
      "$(is "$(field "$out" token)" "<unset>")" "$out"
check "source reported as config" "$(is "$(field "$out" source)" config)" "$out"
check "log names the config file as the source" "$(has 'config-file token')" "$(cat "$TMP/log")"

echo
echo "=== GUILT: the 2026-07-26 world — DEAD config token, valid env token ==="
out=$(run_world 0 1 "live-july-token")
check "resolver succeeds instead of aborting the backup" "$(is "$(field "$out" rc)" 0)" "$out"
check "the working env token IS exported" "$(is "$(field "$out" token)" live-july-token)" "$out"
check "source reported as env (a caller can see it is degraded)" \
      "$(is "$(field "$out" source)" env)" "$out"
check "the fallback is LOGGED, never silent" "$(has 'REFUSED')" "$(cat "$TMP/log")"

echo
echo "=== INNOCENCE 2: both credentials valid — prefer config, export nothing ==="
out=$(run_world 1 1 "also-valid")
check "resolver succeeds" "$(is "$(field "$out" rc)" 0)" "$out"
check "does not gratuitously switch to the env token" \
      "$(is "$(field "$out" token)" "<unset>")" "$out"

echo
echo "=== BOTH DEAD: must fail loudly and leave nothing exported ==="
out=$(run_world 0 0 "dead-token")
check "resolver fails (caller must abort)" "$(is "$(field "$out" rc)" 1)" "$out"
check "no token left exported" "$(is "$(field "$out" token)" "<unset>")" "$out"
check "the error says every source was refused" "$(has 'every fly credential')" "$(cat "$TMP/log")"
check "the probe's OWN words are surfaced (not a guess)" \
      "$(has 'no access token available')" "$(cat "$TMP/log")"
check "the error states the remedy" "$(has 'fly auth login')" "$(cat "$TMP/log")"

echo
echo "=== CONFIG DEAD, NO env token at all — distinct, actionable message ==="
out=$(run_world 0 1 "")
check "resolver fails" "$(is "$(field "$out" rc)" 1)" "$out"
check "message says there is no FLY_API_TOKEN (not 'every source')" \
      "$(has 'no FLY_API_TOKEN is set')" "$(cat "$TMP/log")"

echo
echo "=== REGRESSION (found by adversarial review): stale FLY_API_TOKEN next to a VALID FLY_ACCESS_TOKEN ==="
# Only "the-good-one" is accepted, and it arrives via FLY_ACCESS_TOKEN while a
# stale value occupies FLY_API_TOKEN. The first draft took the stale one, wiped
# both, and declared everything refused — destroying a working credential.
out=$( (export STUB_GOOD_TOKEN="the-good-one"; run_world 0 0 "stale-one" "the-good-one") )
check "the valid FLY_ACCESS_TOKEN is found, not destroyed" "$(is "$(field "$out" rc)" 0)" "$out"
check "it is the one exported" "$(is "$(field "$out" token)" the-good-one)" "$out"

echo
echo "=== REGRESSION: same value in both env names — tried once, not twice ==="
out=$( (export STUB_GOOD_TOKEN="same-token"; run_world 0 0 "same-token" "same-token") )
check "still resolves" "$(is "$(field "$out" rc)" 0)" "$out"
check "reported as a single candidate" "$(has 'candidate 1/1')" "$(cat "$TMP/log")"

echo
echo "=== SCOPE: a credential that passes 'auth whoami' but CANNOT do the job ==="
# Pro's real token is scoped to nuzantara-postgres only, so a caller targeting
# nuzantara-rag must probe with its own app or be handed a useless credential.
out=$( (export STUB_APP_SCOPE_FAILS=1; run_world 0 1 "wrong-scope-token" "" machine list --app nuzantara-rag) )
check "app-scoped probe REFUSES it (no useless credential handed back)" \
      "$(is "$(field "$out" rc)" 1)" "$out"
check "nothing exported after refusal" "$(is "$(field "$out" token)" "<unset>")" "$out"
check "the wrong-scope reason is surfaced, not 'token rotted'" \
      "$(has 'Could not find App')" "$(cat "$TMP/log")"
out=$( (export STUB_APP_SCOPE_FAILS=1; run_world 0 1 "wrong-scope-token") )
check "INNOCENCE: the same credential still passes the default whoami probe" \
      "$(is "$(field "$out" rc)" 0)" "$out"

echo
if [ "$FAILURES" -eq 0 ]; then
    echo "PROOF OK — both historical worlds cured, neither re-opened; scope and"
    echo "multi-candidate regressions pinned."
    exit 0
fi
echo "PROOF FAILED: $FAILURES check(s)"
exit 1
