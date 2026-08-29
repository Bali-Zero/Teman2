#!/usr/bin/env bash
# Corpus for infra/launchagents/wrappers/voa-probe-wrapper.sh +
# scripts/probes/voa_journey_probe.mjs.
#
# NO NETWORK CALL ANYWHERE IN THIS FILE. Two techniques keep it that way:
#
#   (a) The probe's PURE classifiers (classifyPage / classifyJourney) are
#       exercised directly — either via the probe's own `--self-test` flag,
#       or via a `node -e --input-type=module` script that imports the real
#       module by absolute path and calls the classifier with an inline
#       fixture. Neither path touches `fetch`.
#
#   (b) The WRAPPER is exercised in a fake world (temp dir mirroring the real
#       repo's relative layout) against a STUB probe file, not the real one
#       — same discipline as test_wa_session_liveness_wrapper.sh. The stub
#       reuses the REAL module's exported `writeHeartbeatAtomic` (imported by
#       absolute path) so the heartbeat-atomicity assertion below proves the
#       real write mechanism, not a hand-rolled double of it.
#
# WHY EXECUTE INSTEAD OF READ (superscar #2 / W107)
# A wrapper's voice — did it pick the right interpreter, did it capture the
# real exit code, did it leave a line behind — is only provable by running
# it. Reading the script proves intent, not behavior; W107's lesson was
# curing one wrapper out of five and calling the disease closed because
# nobody RAN the other four. So: run it, in a disposable world, both on the
# guilty shapes and the innocent one.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROBE_SRC="$REPO/scripts/probes/voa_journey_probe.mjs"
WRAPPER_SRC="$REPO/infra/launchagents/wrappers/voa-probe-wrapper.sh"

PASS=0
FAIL=0

check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        printf '  PASS  %s\n' "$name"
        PASS=$((PASS + 1))
    else
        printf '  FAIL  %s — expected [%s], got [%s]\n' "$name" "$expected" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

[ -f "$PROBE_SRC" ] || { echo "FATAL: probe not found at $PROBE_SRC"; exit 1; }
[ -f "$WRAPPER_SRC" ] || { echo "FATAL: wrapper not found at $WRAPPER_SRC"; exit 1; }

NODE_BIN="$(command -v node 2>/dev/null || true)"
[ -n "$NODE_BIN" ] || { echo "FATAL: no node interpreter on PATH — cannot run this corpus"; exit 1; }

command -v zsh >/dev/null 2>&1 || { echo "FATAL: no zsh on PATH — the wrapper is #!/bin/zsh"; exit 1; }

echo "== 1. probe --self-test exits 0 (drives its own inline classifier fixtures, 0 network calls) =="

selftest_log="$(mktemp)"
"$NODE_BIN" "$PROBE_SRC" --self-test >"$selftest_log" 2>&1
selftest_rc=$?
check "self-test exit 0" "0" "$selftest_rc"
if [ "$selftest_rc" != "0" ]; then
    echo "  --- self-test output ---"
    sed 's/^/  | /' "$selftest_log"
fi
rm -f "$selftest_log"

echo
echo "== 2/3/4. classifyPage guilt/innocence via a node -e import of the real module =="

# Fixture bodies travel via env vars, never string-interpolated into the JS
# source — sidesteps quoting entirely and matches the module's own
# --self-test discipline of testing the function directly, not a shell
# reconstruction of it.
classify_page_state() {
    VOA_TEST_STATUS="$1" VOA_TEST_BODY="$2" "$NODE_BIN" --input-type=module -e "
import { classifyPage } from '$PROBE_SRC';
const status = Number(process.env.VOA_TEST_STATUS);
const body = process.env.VOA_TEST_BODY;
console.log(classifyPage({ status, body }).state);
"
}

state="$(classify_page_state 200 'blah blah NEXT_HTTP_ERROR_FALLBACK blah')"
check "guilt: fallback-template marker -> dark (never pass, never fail)" "dark" "$state"

state="$(classify_page_state 200 '<html><body>nothing relevant here</body></html>')"
check "guilt: 200 OK but missing the funnel marker -> broken" "broken" "$state"

state="$(classify_page_state 200 '<html>...card label: Get a new Visa on Arrival...</html>')"
check "innocence: live funnel marker present, no fallback marker -> live" "live" "$state"

echo
echo "== 5/6. wrapper + stubbed probe, in a fake world: rc= line + heartbeat atomicity =="
echo "         (0 network calls — the stub never imports fetch, only the real"
echo "          module's writeHeartbeatAtomic helper)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/infra/launchagents/wrappers" "$TMP/scripts/probes" "$TMP/logs"
cp "$WRAPPER_SRC" "$TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
chmod +x "$TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"

HEARTBEAT_PATH="$TMP/heartbeat.json"

cat > "$TMP/scripts/probes/voa_journey_probe.mjs" <<STUBEOF
// Stub standing in for the real probe (fake-world layout only — this file
// never ships). Reuses the REAL module's atomic-write helper by absolute
// import so the heartbeat-atomicity assertion below exercises real code,
// not a re-implementation of it. Zero network calls: no fetch anywhere.
import { writeHeartbeatAtomic } from "$PROBE_SRC";

writeHeartbeatAtomic(process.env.VOA_PROBE_HEARTBEAT, {
    schema: 1,
    probe: "voa_journey",
    ts: new Date().toISOString(),
    ts_epoch: Math.floor(Date.now() / 1000),
    verdict: "pass",
    reason: "stub_probe_run",
    latency_ms: { page: 1, post: 1, get: 1 },
    legs: {},
    cleanup: { attempted: 0, verified_gone: 0, leaked: 0 },
    base_url: "stub://no-network",
    probe_version: 1,
});
console.log("stub-probe-ran");
process.exit(0);
STUBEOF

VOA_PROBE_HEARTBEAT="$HEARTBEAT_PATH" HOME="$TMP" \
    zsh "$TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh" >/dev/null 2>&1
wrapper_rc=$?

check "wrapper propagates the stub probe's exit code (0)" "0" "$wrapper_rc"

RUN_LOG="$TMP/logs/voa-probe.log"
if [ -f "$RUN_LOG" ] && grep -q '^\[voa-probe\] rc=' "$RUN_LOG"; then
    check "wrapper log contains an 'rc=' line" "yes" "yes"
else
    check "wrapper log contains an 'rc=' line" "yes" "no"
    [ -f "$RUN_LOG" ] && { echo "  --- $RUN_LOG ---"; sed 's/^/  | /' "$RUN_LOG"; }
fi

if [ -f "$HEARTBEAT_PATH" ]; then
    hb_check="$("$NODE_BIN" -e "
const fs = require('fs');
try {
    const raw = fs.readFileSync('$HEARTBEAT_PATH', 'utf8');
    const obj = JSON.parse(raw);
    const need = ['schema', 'probe', 'ts', 'verdict', 'cleanup'];
    const missing = need.filter((k) => !(k in obj));
    console.log(missing.length === 0 ? 'ok' : 'missing:' + missing.join(','));
} catch (e) {
    console.log('parse-error:' + e.message);
}
")"
    check "heartbeat file parses as JSON with required keys" "ok" "$hb_check"
    # No leftover .tmp file — proves the rename actually happened, not just
    # a write with no cleanup.
    if [ -f "${HEARTBEAT_PATH}.tmp" ]; then
        check "no dangling <path>.tmp after atomic write" "gone" "still-present"
    else
        check "no dangling <path>.tmp after atomic write" "gone" "gone"
    fi
else
    check "heartbeat file exists after a run" "yes" "no"
fi

echo
echo "TOTAL $((PASS + FAIL)) FAILED $FAIL"
[ "$FAIL" -eq 0 ]
