#!/usr/bin/env bash
# Corpus for infra/launchagents/wrappers/voa-probe-wrapper.sh +
# scripts/probes/voa_journey_probe.mjs.
#
# NO NETWORK CALL ANYWHERE IN THIS FILE. Three techniques keep it that way:
#
#   (a) The probe's PURE classifiers (classifyPage / classifyJourney /
#       classifyCleanupVerify / classifyTransportError / assessEligibilityBody
#       / combineVerdict / shouldWriteHeartbeat / sanitizeBaseUrl /
#       sanitizeReasonString) are exercised directly — either via the
#       probe's own `--self-test` flag, or via a `node -e
#       --input-type=module` script that imports the real module by
#       absolute path and calls the classifier with an inline fixture.
#       Neither path touches `fetch`.
#
#   (b) runJourney() is exercised with a FAKE `fetchImpl` (the reason it is
#       exported taking one) that dispatches on method+call-order and never
#       imports `fetch` — see the shared harness written to a temp file
#       below. This proves the real POST->GET->DELETE->verify-GET control
#       flow, the cookie-jar handling, and the cleanup counters, without a
#       single real network call.
#
#   (c) The WRAPPER, and separately the real probe's `main()` in dry-run
#       mode (monkeypatching `globalThis.fetch` with a function that always
#       throws — main() looks up the bare `fetch` identifier at CALL time,
#       so this substitution is visible to it), are exercised in a
#       disposable world — same discipline as test_wa_session_liveness_wrapper.sh.
#
# WHY EXECUTE INSTEAD OF READ (superscar #2 / W107)
# A wrapper's voice — did it pick the right interpreter, did it capture the
# real exit code, did it leave a line behind — is only provable by running
# it. Reading the script proves intent, not behavior; W107's lesson was
# curing one wrapper out of five and calling the disease closed because
# nobody RAN the other four. So: run it, in a disposable world, both on the
# guilty shapes and the innocent one.
#
# mktemp DISCIPLINE (adversarial finding, verified): an unchecked `mktemp`
# failure continues with an empty path, and every subsequent operation on
# "$EMPTY/..." then fails for a completely unrelated reason — a refuter's
# sandbox hit exactly this and misattributed 4 FAILs to the wrapper. Every
# mktemp call in this file goes through require_tmpdir/require_tmpfile,
# which abort the WHOLE corpus loudly on failure rather than let a hollow
# path corrupt every check downstream of it.

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

# --- mktemp discipline: abort loudly, never continue on a hollow path -----
CLEANUP_PATHS=()
cleanup_all() {
    local p
    for p in "${CLEANUP_PATHS[@]:-}"; do
        [ -n "$p" ] && rm -rf "$p"
    done
}
trap cleanup_all EXIT

require_tmpdir() {
    local d
    d="$(mktemp -d)" || { echo "FATAL: mktemp -d failed — cannot run this corpus (adversarial finding: an unchecked mktemp failure misattributes every downstream check to the wrong component)"; exit 1; }
    [ -n "$d" ] && [ -d "$d" ] || { echo "FATAL: mktemp -d returned an unusable path: '$d'"; exit 1; }
    CLEANUP_PATHS+=("$d")
    printf '%s' "$d"
}

require_tmpfile() {
    local f
    f="$(mktemp)" || { echo "FATAL: mktemp failed — cannot run this corpus"; exit 1; }
    [ -n "$f" ] && [ -f "$f" ] || { echo "FATAL: mktemp returned an unusable path: '$f'"; exit 1; }
    CLEANUP_PATHS+=("$f")
    printf '%s' "$f"
}

echo "== 1. probe --self-test exits 0 (drives its own inline classifier fixtures, 0 network calls) =="

selftest_log="$(require_tmpfile)"
"$NODE_BIN" "$PROBE_SRC" --self-test >"$selftest_log" 2>&1
selftest_rc=$?
check "self-test exit 0" "0" "$selftest_rc"
if [ "$selftest_rc" != "0" ]; then
    echo "  --- self-test output ---"
    sed 's/^/  | /' "$selftest_log"
fi

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
echo "== 5. classifyPage F9 redirect guilt/innocence (fetch() follows redirects silently) =="

classify_page_state_with_path() {
    VOA_TEST_STATUS="$1" VOA_TEST_BODY="$2" VOA_TEST_FINALPATH="$3" "$NODE_BIN" --input-type=module -e "
import { classifyPage } from '$PROBE_SRC';
const status = Number(process.env.VOA_TEST_STATUS);
const body = process.env.VOA_TEST_BODY;
const finalPath = process.env.VOA_TEST_FINALPATH;
console.log(classifyPage({ status, body, finalPath }).state);
"
}

state="$(classify_page_state_with_path 200 '<html>...Get a new Visa on Arrival...</html>' '/some/other/page')"
check "guilt (F9): 200 + live marker but landed on the WRONG path -> broken" "broken" "$state"

state="$(classify_page_state_with_path 200 '<html>...Get a new Visa on Arrival...</html>' '/visa/voa')"
check "innocence (F9): 200 + live marker + correct final path -> live" "live" "$state"

echo
echo "== 6. runJourney fake-fetchImpl scenarios (F11 a-g) — POST/GET/DELETE/verify, 0 network =="
echo "         (a shared harness dispatches on method+call-order; each scenario supplies"
echo "          canned responses via a JSON env var, never a live fetch)"

RUNJOURNEY_TMP="$(require_tmpdir)"
HARNESS="$RUNJOURNEY_TMP/runjourney-harness.mjs"

cat > "$HARNESS" <<HARNESSEOF
// Fake-fetchImpl harness for scripts/probes/voa_journey_probe.mjs's runJourney.
// Imports the REAL runJourney/classifyJourney/combineVerdict by absolute
// path — this proves the real control flow, not a re-implementation of it.
import { runJourney, classifyJourney, combineVerdict } from "$PROBE_SRC";

function makeHeaders(map) {
    return {
        get(name) { return map[name.toLowerCase()] ?? null; },
        getSetCookie() { return map.setCookies || []; },
    };
}

function respFromSpec(spec) {
    if (spec.throw) {
        const err = new Error(spec.throwMessage || "synthetic transport failure");
        err.name = spec.throwName || "TypeError";
        throw err;
    }
    return {
        status: spec.status,
        headers: makeHeaders({ location: spec.location, setCookies: spec.setCookies }),
        json: async () => {
            if (!("body" in spec)) throw new Error("no fake body configured");
            return spec.body;
        },
        text: async () => (spec.body === undefined ? "" : JSON.stringify(spec.body)),
    };
}

const scenario = JSON.parse(process.env.VOA_SCENARIO);
const calls = [];

async function fakeFetch(url, init) {
    const method = (init && init.method) || "GET";
    calls.push(method);
    if (method === "POST") return respFromSpec(scenario.post);
    if (method === "DELETE") return respFromSpec(scenario.delete || { status: 204 });
    if (method === "GET") {
        // GET calls are positional, not semantic: the scenario author lists
        // EXACTLY the responses runJourney's real control flow is expected
        // to request, in order (0, 1, ... GET calls). This avoids guessing
        // "is this the api-read GET or the cleanup verify-GET" — a guess
        // that is wrong whenever the api-read GET never fires (e.g. the
        // POST itself failed a contract check) but the verify-GET still
        // does, or vice-versa.
        const idx = calls.filter((m) => m === "GET").length - 1;
        const spec = (scenario.getSequence || [])[idx];
        if (!spec) {
            throw new Error("test harness bug: no fake GET response configured for call #" + (idx + 1));
        }
        return respFromSpec(spec);
    }
    throw new Error("unexpected method " + method);
}

const result = await runJourney({ baseUrl: "https://example.invalid", fetchImpl: fakeFetch });
const journey = classifyJourney(result.legs);
const verdict = combineVerdict({
    page: { state: scenario.pageState || "live" },
    journey,
    cleanup: result.cleanup,
    dryRun: false,
});

console.log("POST_OK=" + (result.legs.post ? result.legs.post.ok : "null"));
console.log("POST_UNKNOWN=" + (result.legs.post ? result.legs.post.unknown === true : false));
console.log("GET_OK=" + (result.legs.get ? result.legs.get.ok : "null"));
console.log("JOURNEY_STATE=" + journey.state);
console.log("CLEANUP_ATTEMPTED=" + result.cleanup.attempted);
console.log("CLEANUP_VERIFIED_GONE=" + result.cleanup.verified_gone);
console.log("CLEANUP_UNVERIFIED=" + result.cleanup.unverified);
console.log("CLEANUP_LEAKED=" + result.cleanup.leaked);
console.log("VERDICT=" + verdict.verdict);
console.log("CALLS=" + calls.join(","));
HARNESSEOF

run_scenario() {
    VOA_SCENARIO="$1" "$NODE_BIN" "$HARNESS" 2>&1
}

field_of() {
    printf '%s\n' "$1" | grep "^$2=" | head -1 | cut -d= -f2-
}

# --- (a) happy path: create -> read -> delete -> verify confirms gone -----
SCENARIO_A='{"post":{"status":201,"location":"/visa/voa/abcdefghijklmnopqrstuv12","setCookies":["garuda_result_session=xyz; HttpOnly; Path=/"],"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},"getSequence":[{"status":200,"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},{"status":404,"body":{"code":"RESULT_NOT_FOUND"}}]}'
out="$(run_scenario "$SCENARIO_A")"
check "(a) happy path: journey ok"                "ok"    "$(field_of "$out" JOURNEY_STATE)"
check "(a) happy path: cleanup verified_gone=1"   "1"     "$(field_of "$out" CLEANUP_VERIFIED_GONE)"
check "(a) happy path: cleanup leaked=0"          "0"     "$(field_of "$out" CLEANUP_LEAKED)"
check "(a) happy path: cleanup unverified=0"      "0"     "$(field_of "$out" CLEANUP_UNVERIFIED)"
check "(a) happy path: overall verdict pass"      "pass"  "$(field_of "$out" VERDICT)"

# --- (b) verify returns 200 (row survived) -> leaked -> overall fail ------
SCENARIO_B='{"post":{"status":201,"location":"/visa/voa/abcdefghijklmnopqrstuv12","setCookies":["garuda_result_session=xyz; HttpOnly; Path=/"],"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},"getSequence":[{"status":200,"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},{"status":200,"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}}]}'
out="$(run_scenario "$SCENARIO_B")"
check "(b) row survived cleanup: leaked=1"        "1"     "$(field_of "$out" CLEANUP_LEAKED)"
check "(b) row survived cleanup: verified_gone=0" "0"     "$(field_of "$out" CLEANUP_VERIFIED_GONE)"
check "(b) row survived cleanup: overall fail"    "fail"  "$(field_of "$out" VERDICT)"

# --- (c) verify 404 GARUDA_PUBLIC_DISABLED -> unverified -> overall unknown
SCENARIO_C='{"post":{"status":201,"location":"/visa/voa/abcdefghijklmnopqrstuv12","setCookies":["garuda_result_session=xyz; HttpOnly; Path=/"],"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},"getSequence":[{"status":200,"body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},{"status":404,"body":{"code":"GARUDA_PUBLIC_DISABLED"}}]}'
out="$(run_scenario "$SCENARIO_C")"
check "(c) flag disabled mid-run: unverified=1"       "1"       "$(field_of "$out" CLEANUP_UNVERIFIED)"
check "(c) flag disabled mid-run: verified_gone=0"    "0"       "$(field_of "$out" CLEANUP_VERIFIED_GONE)"
check "(c) flag disabled mid-run: overall unknown"    "unknown" "$(field_of "$out" VERDICT)"

# --- (d) POST 201 but NO Set-Cookie -> unverified, never verified_gone ----
SCENARIO_D='{"post":{"status":201,"location":"/visa/voa/abcdefghijklmnopqrstuv12","body":{"verdict":"ACCEPT","reason_codes":[],"price_idr":500000,"published_filing_deadline":"2026-09-15"}},"getSequence":[]}'
out="$(run_scenario "$SCENARIO_D")"
check "(d) no cookie: cleanup unverified=1"       "1" "$(field_of "$out" CLEANUP_UNVERIFIED)"
check "(d) no cookie: cleanup verified_gone=0"    "0" "$(field_of "$out" CLEANUP_VERIFIED_GONE)"
check "(d) no cookie: no verify-GET was attempted (calls has no trailing GET after DELETE)" \
    "POST,DELETE" "$(field_of "$out" CALLS)"

# --- (e) POST throws a TimeoutError -> verdict unknown, NOT fail ---------
SCENARIO_E='{"post":{"throw":true,"throwName":"TimeoutError"},"getSequence":[]}'
out="$(run_scenario "$SCENARIO_E")"
check "(e) post transport failure: POST_UNKNOWN=true"     "true"    "$(field_of "$out" POST_UNKNOWN)"
check "(e) post transport failure: journey state unknown" "unknown" "$(field_of "$out" JOURNEY_STATE)"
check "(e) post transport failure: overall unknown, not fail" "unknown" "$(field_of "$out" VERDICT)"
check "(e) post transport failure: no cleanup attempted (resultId never set)" \
    "0" "$(field_of "$out" CLEANUP_ATTEMPTED)"

# --- (f) POST returns a contract-shaped DECLINE -> healthy (not fail) ----
SCENARIO_F='{"post":{"status":201,"location":"/visa/voa/abcdefghijklmnopqrstuv12","setCookies":["garuda_result_session=xyz; HttpOnly; Path=/"],"body":{"verdict":"DECLINE","reason_codes":["ARRIVAL_DATE_UNCONFIRMED"]}},"getSequence":[{"status":200,"body":{"verdict":"DECLINE","reason_codes":["ARRIVAL_DATE_UNCONFIRMED"]}},{"status":404,"body":{"code":"RESULT_NOT_FOUND"}}]}'
out="$(run_scenario "$SCENARIO_F")"
check "(f) contract-shaped DECLINE: journey ok (a decline is a healthy funnel, F6)" \
    "ok" "$(field_of "$out" JOURNEY_STATE)"
check "(f) contract-shaped DECLINE: overall pass" "pass" "$(field_of "$out" VERDICT)"

# --- (g) {"verdict":"ACCEPT"} with no price_idr -> broken -----------------
SCENARIO_G='{"post":{"status":201,"location":"/visa/voa/abcdefghijklmnopqrstuv12","setCookies":["garuda_result_session=xyz; HttpOnly; Path=/"],"body":{"verdict":"ACCEPT","reason_codes":[]}},"getSequence":[{"status":404,"body":{"code":"RESULT_NOT_FOUND"}}]}'
out="$(run_scenario "$SCENARIO_G")"
check "(g) ACCEPT missing price_idr: POST_OK=false"    "false"  "$(field_of "$out" POST_OK)"
check "(g) ACCEPT missing price_idr: journey broken"   "broken" "$(field_of "$out" JOURNEY_STATE)"
check "(g) ACCEPT missing price_idr: overall fail"     "fail"   "$(field_of "$out" VERDICT)"

echo
echo "== 7. F1: --dry-run heartbeat write gating, exercised on the REAL probe main() =="
echo "         (globalThis.fetch is monkeypatched to always throw — main() resolves the"
echo "          bare 'fetch' identifier at CALL time, so this never touches a real socket)"

DRYRUN_HOME="$(require_tmpdir)"

run_dryrun_main() {
    # $1 = heartbeat env var value, or empty string to leave it unset
    if [ -n "$1" ]; then
        VOA_PROBE_HEARTBEAT="$1" HOME="$DRYRUN_HOME" "$NODE_BIN" --input-type=module -e "
import { main } from '$PROBE_SRC';
globalThis.fetch = async () => { throw new Error('no network in tests'); };
await main(['--dry-run']);
" >/dev/null 2>&1
    else
        env -u VOA_PROBE_HEARTBEAT HOME="$DRYRUN_HOME" "$NODE_BIN" --input-type=module -e "
import { main } from '$PROBE_SRC';
globalThis.fetch = async () => { throw new Error('no network in tests'); };
await main(['--dry-run']);
" >/dev/null 2>&1
    fi
}

run_dryrun_main ""
DEFAULT_HB="$DRYRUN_HOME/logs/voa-probe-heartbeat.json"
if [ -f "$DEFAULT_HB" ]; then
    check "(F1) dry-run without an explicit heartbeat path leaves the default UNWRITTEN" "absent" "present"
else
    check "(F1) dry-run without an explicit heartbeat path leaves the default UNWRITTEN" "absent" "absent"
fi

EXPLICIT_HB="$DRYRUN_HOME/explicit-heartbeat.json"
run_dryrun_main "$EXPLICIT_HB"
if [ -f "$EXPLICIT_HB" ]; then
    mode_val="$("$NODE_BIN" -e "console.log(JSON.parse(require('fs').readFileSync('$EXPLICIT_HB','utf8')).mode)" 2>&1)"
    check "(F1) dry-run WITH an explicit heartbeat path writes it, tagged mode=dry_run" "dry_run" "$mode_val"
else
    check "(F1) dry-run WITH an explicit heartbeat path writes it, tagged mode=dry_run" "dry_run" "FILE-MISSING"
fi

echo
echo "== 8/9. wrapper + stubbed probe, in a fake world: rc= line + heartbeat atomicity =="
echo "         (0 network calls — the stub never imports fetch, only the real"
echo "          module's writeHeartbeatAtomic helper)"

TMP="$(require_tmpdir)"

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
    mode: "full",
    ts: new Date().toISOString(),
    ts_epoch: Math.floor(Date.now() / 1000),
    verdict: "pass",
    reason: "stub_probe_run",
    latency_ms: { page: 1, post: 1, get: 1 },
    legs: {},
    cleanup: { attempted: 0, verified_gone: 0, unverified: 0, leaked: 0 },
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
    const need = ['schema', 'probe', 'mode', 'ts', 'verdict', 'cleanup'];
    const missing = need.filter((k) => !(k in obj));
    console.log(missing.length === 0 ? 'ok' : 'missing:' + missing.join(','));
} catch (e) {
    console.log('parse-error:' + e.message);
}
")"
    check "heartbeat file parses as JSON with required keys (incl. mode)" "ok" "$hb_check"
    # No leftover .tmp file — proves the rename actually happened, not just
    # a write with no cleanup. Note: the atomic write now uses a
    # per-process/per-call temp SUFFIX (<path>.<pid>.<random>.tmp), so a
    # glob (not a single fixed name) is the right check here.
    leftover_tmp=""
    for f in "${HEARTBEAT_PATH}".*.tmp; do
        [ -e "$f" ] && leftover_tmp="$f"
    done
    if [ -n "$leftover_tmp" ]; then
        check "no dangling <path>.<pid>.<random>.tmp after atomic write" "gone" "still-present:$leftover_tmp"
    else
        check "no dangling <path>.<pid>.<random>.tmp after atomic write" "gone" "gone"
    fi
else
    check "heartbeat file exists after a run" "yes" "no"
fi

echo
echo "== 10. wrapper: missing probe file -> FATAL exit 2 (not a bare 127) =="

MISSING_PROBE_TMP="$(require_tmpdir)"
mkdir -p "$MISSING_PROBE_TMP/infra/launchagents/wrappers" "$MISSING_PROBE_TMP/logs"
cp "$WRAPPER_SRC" "$MISSING_PROBE_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
chmod +x "$MISSING_PROBE_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
# Deliberately NOT creating scripts/probes/voa_journey_probe.mjs anywhere
# under $MISSING_PROBE_TMP — the wrapper's own signature guard (W105 class)
# must catch this before ever invoking node on a nonexistent file.

HOME="$MISSING_PROBE_TMP" \
    zsh "$MISSING_PROBE_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh" >/dev/null 2>&1
missing_probe_rc=$?
check "wrapper exits 2 when the probe file is absent" "2" "$missing_probe_rc"

echo
echo "== 11. wrapper: a NON-ZERO probe exit code propagates through the wrapper =="

PROBE_FAILS_TMP="$(require_tmpdir)"
mkdir -p "$PROBE_FAILS_TMP/infra/launchagents/wrappers" "$PROBE_FAILS_TMP/scripts/probes" "$PROBE_FAILS_TMP/scripts/lib" "$PROBE_FAILS_TMP/logs"
cp "$WRAPPER_SRC" "$PROBE_FAILS_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
chmod +x "$PROBE_FAILS_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
# The REAL organism heartbeat library, not a stub — sections 12/13 below
# assert what this wrapper actually writes to the ORGANISM (not the probe's
# own heartbeat, which the writeHeartbeatAtomic call further down already
# covers), so the library that call is meant to invoke must genuinely exist
# in this fake world.
cp "$REPO/scripts/lib/heartbeat.sh" "$PROBE_FAILS_TMP/scripts/lib/heartbeat.sh"

cat > "$PROBE_FAILS_TMP/scripts/probes/voa_journey_probe.mjs" <<FAILEOF
// Stub that behaves like a real "fail" verdict run: writes a heartbeat (so
// the F8 "a heartbeat MUST exist" promise still holds) and exits 1. If a
// future wrapper edit ever hardcoded "exit 0" regardless of the probe's own
// exit code, THIS is the test that would catch it — the happy-path stub in
// section 8/9 always exits 0 and could never expose that bug on its own.
import { writeHeartbeatAtomic } from "$PROBE_SRC";
writeHeartbeatAtomic(process.env.VOA_PROBE_HEARTBEAT, {
    schema: 1,
    probe: "voa_journey",
    mode: "full",
    ts: new Date().toISOString(),
    ts_epoch: Math.floor(Date.now() / 1000),
    verdict: "fail",
    reason: "stub_probe_fail",
    latency_ms: { page: 1, post: null, get: null },
    legs: {},
    cleanup: { attempted: 0, verified_gone: 0, unverified: 0, leaked: 0 },
    base_url: "stub://no-network",
    probe_version: 1,
});
process.exit(1);
FAILEOF

HOME="$PROBE_FAILS_TMP" \
    zsh "$PROBE_FAILS_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh" >/dev/null 2>&1
probe_fails_rc=$?
check "wrapper propagates a non-zero probe exit code (1), not a hardcoded 0" "1" "$probe_fails_rc"

FAIL_ORGANISM_HB="$PROBE_FAILS_TMP/.organism/last_seen/mini.voa_probe.json"
if [ -f "$FAIL_ORGANISM_HB" ]; then
    fail_organism_status="$("$NODE_BIN" -e "console.log(JSON.parse(require('fs').readFileSync('$FAIL_ORGANISM_HB','utf8')).status)" 2>&1)"
    check "(verdict=fail) organism status=error (an attributable break, real heartbeat.sh)" "error" "$fail_organism_status"
else
    check "(verdict=fail) organism status=error (an attributable break, real heartbeat.sh)" "error" "FILE-MISSING"
fi

echo
echo "== 12. wrapper: VOA_PROBE_ENABLED=false -> exit 0, probe NEVER invoked, disabled heartbeat =="
echo "         (this is the RUNTIME kill switch, distinct from install_voa_probe.sh's"
echo "          install-time VOA_PROBE_CRON_ENABLED)"

KILLSWITCH_TMP="$(require_tmpdir)"
mkdir -p "$KILLSWITCH_TMP/infra/launchagents/wrappers" "$KILLSWITCH_TMP/scripts/probes" "$KILLSWITCH_TMP/scripts/lib" "$KILLSWITCH_TMP/logs"
cp "$WRAPPER_SRC" "$KILLSWITCH_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
chmod +x "$KILLSWITCH_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
cp "$REPO/scripts/lib/heartbeat.sh" "$KILLSWITCH_TMP/scripts/lib/heartbeat.sh"

KILLSWITCH_RAN_MARKER="$KILLSWITCH_TMP/probe-ran-marker"
cat > "$KILLSWITCH_TMP/scripts/probes/voa_journey_probe.mjs" <<KILLEOF
// If the kill switch works, this file must never even be imported, let
// alone executed. Its only job is to prove that IF it ran, we would know.
import fs from "node:fs";
fs.writeFileSync("$KILLSWITCH_RAN_MARKER", "ran");
process.exit(99);
KILLEOF

VOA_PROBE_ENABLED=false HOME="$KILLSWITCH_TMP" \
    zsh "$KILLSWITCH_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh" >/dev/null 2>&1
killswitch_rc=$?
check "(kill switch) wrapper exits 0 when VOA_PROBE_ENABLED=false" "0" "$killswitch_rc"

if [ -f "$KILLSWITCH_RAN_MARKER" ]; then
    check "(kill switch) the probe itself was NEVER invoked" "not-run" "ran"
else
    check "(kill switch) the probe itself was NEVER invoked" "not-run" "not-run"
fi

KILLSWITCH_ORGANISM_HB="$KILLSWITCH_TMP/.organism/last_seen/mini.voa_probe.json"
if [ -f "$KILLSWITCH_ORGANISM_HB" ]; then
    killswitch_status="$("$NODE_BIN" -e "console.log(JSON.parse(require('fs').readFileSync('$KILLSWITCH_ORGANISM_HB','utf8')).status)" 2>&1)"
    check "(kill switch) organism heartbeat status=disabled (never resurrected by a healer)" "disabled" "$killswitch_status"
else
    check "(kill switch) organism heartbeat status=disabled (never resurrected by a healer)" "disabled" "FILE-MISSING"
fi

echo
echo "== 13. wrapper: verdict=dark maps to organism status=ok (W104: an intentionally-off"
echo "         flag is healthy, not degraded — never nag the organism over it) =="

DARK_TMP="$(require_tmpdir)"
mkdir -p "$DARK_TMP/infra/launchagents/wrappers" "$DARK_TMP/scripts/probes" "$DARK_TMP/scripts/lib" "$DARK_TMP/logs"
cp "$WRAPPER_SRC" "$DARK_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
chmod +x "$DARK_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh"
cp "$REPO/scripts/lib/heartbeat.sh" "$DARK_TMP/scripts/lib/heartbeat.sh"

cat > "$DARK_TMP/scripts/probes/voa_journey_probe.mjs" <<DARKEOF
// Stub that behaves like a real "dark" verdict run (flag deliberately off,
// pre-launch): writes a heartbeat and exits 0, same as the probe's own
// documented exit-code contract for dark/pass/unknown.
import { writeHeartbeatAtomic } from "$PROBE_SRC";
writeHeartbeatAtomic(process.env.VOA_PROBE_HEARTBEAT, {
    schema: 1,
    probe: "voa_journey",
    mode: "full",
    ts: new Date().toISOString(),
    ts_epoch: Math.floor(Date.now() / 1000),
    verdict: "dark",
    reason: "flag_off_next_404_template",
    latency_ms: { page: 1, post: null, get: null },
    legs: {},
    cleanup: { attempted: 0, verified_gone: 0, unverified: 0, leaked: 0 },
    base_url: "stub://no-network",
    probe_version: 1,
});
process.exit(0);
DARKEOF

HOME="$DARK_TMP" \
    zsh "$DARK_TMP/infra/launchagents/wrappers/voa-probe-wrapper.sh" >/dev/null 2>&1
dark_wrapper_rc=$?
check "(verdict=dark) wrapper rc propagates the probe's 0" "0" "$dark_wrapper_rc"

DARK_ORGANISM_HB="$DARK_TMP/.organism/last_seen/mini.voa_probe.json"
if [ -f "$DARK_ORGANISM_HB" ]; then
    dark_organism_status="$("$NODE_BIN" -e "console.log(JSON.parse(require('fs').readFileSync('$DARK_ORGANISM_HB','utf8')).status)" 2>&1)"
    check "(verdict=dark) organism status=ok, not degraded (W104)" "ok" "$dark_organism_status"
else
    check "(verdict=dark) organism status=ok, not degraded (W104)" "ok" "FILE-MISSING"
fi

echo
echo "TOTAL $((PASS + FAIL)) FAILED $FAIL"
[ "$FAIL" -eq 0 ]
