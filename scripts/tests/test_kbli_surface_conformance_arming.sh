#!/usr/bin/env bash
# Hermetic guilt + innocence corpus for the scheduled KBLI conformance adapter.
# No Telegram, Keychain, Fly, launchctl, crontab, or production Postgres access.
# shellcheck disable=SC2016,SC2319

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER_SRC="$ROOT/infra/launchagents/wrappers/kbli-surface-conformance-run.sh"
RUNNER_SRC="$ROOT/scripts/cron-runner.sh"
PLIST="$ROOT/infra/launchagents/com.nuzantara.kbli-surface-conformance.daily.plist"
INSTALLER="$ROOT/infra/launchagents/install_kbli_surface_conformance.sh"
REGISTRY_FRAGMENT="$ROOT/infra/launchagents/job_registry.kbli_surface_conformance.json"
ORGANS="$ROOT/apps/organism/organism/organs_registry.yaml"
VENV_PY="$ROOT/apps/backend-rag/.venv/bin/python"
TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

check() {
    local name="$1" rc="$2"
    if [ "$rc" -eq 0 ]; then
        PASS=$((PASS + 1)); printf '  ok    %s\n' "$name"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$name"
    fi
}

contains() {
    grep -Fq -- "$1" "$2"
}

json_value() {
    /usr/bin/python3 - "$1" "$2" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(str(value).lower() if isinstance(value, bool) else value)
PY
}

mkdir -p "$TMP/run" "$TMP/stubs"
cp "$RUNNER_SRC" "$TMP/run/cron-runner.sh"
cp "$WRAPPER_SRC" "$TMP/run/kbli-surface-conformance-run.sh"
chmod +x "$TMP/run/cron-runner.sh" "$TMP/run/kbli-surface-conformance-run.sh"

cat > "$TMP/stubs/gtimeout" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_TIMEOUT_LOG"
[ "${1:-}" = "-k" ] && [ "${2:-}" = "30" ] && [ "${3:-}" = "180" ] || exit 98
shift 3
exec "$@"
SH

cat > "$TMP/stubs/detector.sh" <<'SH'
#!/usr/bin/env bash
printf 'called\n' >> "$FAKE_DETECTOR_CALL_LOG"
if [ -n "${SHOULD_NOT_LOAD:-}" ] || [ -n "${DATABASE_URL:-}" ]; then
    printf 'whole-secrets contamination reached detector\n' >&2
    exit 91
fi
if [ -n "${FAKE_PG_STUB:-}" ]; then
    "$FAKE_PG_STUB"
fi
printf '%b\n' "${FAKE_DETECTOR_OUTPUT:-}"
exit "${FAKE_DETECTOR_RC:-0}"
SH

cat > "$TMP/stubs/pg.sh" <<'SH'
#!/usr/bin/env bash
printf 'pg-called\n' >> "$FAKE_PG_CALL_LOG"
SH

cat > "$TMP/stubs/lsof" <<'SH'
#!/usr/bin/env bash
[ "${FAKE_PORT_LISTENING:-1}" = "1" ]
SH

cat > "$TMP/stubs/fly" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_FLY_CALL_LOG"
exit "${FAKE_FLY_RC:-0}"
SH

cat > "$TMP/run/tg_notify.py" <<'PY'
import json
import os
import sys
with open(os.environ["FAKE_GATEWAY_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
print(f"tg_notify: {os.environ.get('FAKE_GATEWAY_VERDICT', 'sent')}", file=sys.stderr)
raise SystemExit(int(os.environ.get("FAKE_GATEWAY_RC", "0")))
PY

cat > "$TMP/stubs/heartbeat.py" <<'PY'
import json
import os
import pathlib
import sys
with open(os.environ["FAKE_HEARTBEAT_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
if int(os.environ.get("FAKE_HEARTBEAT_RC", "0")):
    raise SystemExit(int(os.environ["FAKE_HEARTBEAT_RC"]))
out = pathlib.Path(os.environ["ORGANISM_LAST_SEEN_DIR"])
out.mkdir(parents=True, exist_ok=True)
organ_id, status, note = sys.argv[1:4]
(out / f"{organ_id}.json").write_text(
    json.dumps({"ts": "test", "status": status, "note": note}) + "\n",
    encoding="utf-8",
)
PY

chmod +x "$TMP/stubs/"* "$TMP/run/tg_notify.py"

cat > "$TMP/secrets.env" <<'ENV'
FLY_API_TOKEN=test-fly-token
DATABASE_URL=must-not-be-sourced
SHOULD_NOT_LOAD=must-not-enter-child-env
ENV

CASE_WRAPPER="$TMP/run/kbli-surface-conformance-run.sh"
run_case() {
    local name="$1"
    /bin/rm -rf "$TMP/case"
    /bin/mkdir -p "$TMP/case/home" "$TMP/case/state" "$TMP/case/logs" "$TMP/case/hb" "$TMP/case/locks"
    : > "$TMP/case/gateway.jsonl"
    : > "$TMP/case/heartbeat.jsonl"
    : > "$TMP/case/detector.calls"
    : > "$TMP/case/fly.calls"
    : > "$TMP/case/pg.calls"
    : > "$TMP/case/timeout.calls"
    case "${FAKE_PREPARE_LOCK:-}" in
        live)
            /bin/mkdir -p "$TMP/case/locks/lock"
            printf '%s\n' "$$" > "$TMP/case/locks/lock/pid"
            ;;
        stale)
            /bin/mkdir -p "$TMP/case/locks/lock"
            printf '%s\n' "999999" > "$TMP/case/locks/lock/pid"
            ;;
    esac
    HOME="$TMP/case/home" \
    CRON_RUNNER_STATE_DIR="$TMP/case/state" \
    CRON_RUNNER_JOB_NAME="kbli_surface_conformance" \
    ORGANISM_LAST_SEEN_DIR="$TMP/case/hb" \
    KBLI_SURFACE_CONFORMANCE_HOSTNAME="Nuzantara" \
    KBLI_SURFACE_CONFORMANCE_REPO_ROOT="$ROOT" \
    KBLI_SURFACE_CONFORMANCE_DETECTOR_PY="/bin/bash" \
    KBLI_SURFACE_CONFORMANCE_DETECTOR="$TMP/stubs/detector.sh" \
    KBLI_SURFACE_CONFORMANCE_HEARTBEAT_PY="/usr/bin/python3" \
    KBLI_SURFACE_CONFORMANCE_HEARTBEAT="$TMP/stubs/heartbeat.py" \
    KBLI_SURFACE_CONFORMANCE_GATEWAY_PY="/usr/bin/python3" \
    KBLI_SURFACE_CONFORMANCE_GATEWAY="$TMP/run/tg_notify.py" \
    KBLI_SURFACE_CONFORMANCE_GTIMEOUT="$TMP/stubs/gtimeout" \
    KBLI_SURFACE_CONFORMANCE_LSOF="$TMP/stubs/lsof" \
    KBLI_SURFACE_CONFORMANCE_FLY_BIN="$TMP/stubs/fly" \
    KBLI_SURFACE_CONFORMANCE_FLY_CREDENTIAL_LIB="$ROOT/scripts/lib/fly_credential.sh" \
    KBLI_SURFACE_CONFORMANCE_SECRETS_FILE="$TMP/secrets.env" \
    KBLI_SURFACE_CONFORMANCE_LOG_DIR="$TMP/case/logs" \
    KBLI_SURFACE_CONFORMANCE_LOCK_DIR="$TMP/case/locks/lock" \
    FAKE_GATEWAY_LOG="$TMP/case/gateway.jsonl" \
    FAKE_HEARTBEAT_LOG="$TMP/case/heartbeat.jsonl" \
    FAKE_DETECTOR_CALL_LOG="$TMP/case/detector.calls" \
    FAKE_FLY_CALL_LOG="$TMP/case/fly.calls" \
    FAKE_PG_CALL_LOG="$TMP/case/pg.calls" \
    FAKE_TIMEOUT_LOG="$TMP/case/timeout.calls" \
    /bin/bash "$TMP/run/cron-runner.sh" "$CASE_WRAPPER" > "$TMP/case/output" 2>&1
    RC=$?
    RECEIPT="$TMP/case/state/kbli_surface_conformance.last.json"
    HB_FILE="$TMP/case/hb/pro.kbli_surface_conformance.json"
    RUN_LOG="$(find "$TMP/case/logs" -name 'kbli-surface-conformance-*.log' -type f | head -1)"
    printf 'case=%s rc=%s\n' "$name" "$RC" >> "$TMP/case/output"
}

echo "GUILT — rc 1 + detector report header is a divergence"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=1 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical\n  pma_status disagrees: 1' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case divergence
check "outer runner normalises recognised divergence" "$([ "$RC" -eq 0 ] && echo 0 || echo 1)"
check "exactly one semantic gateway call" "$([ "$(wc -l < "$TMP/case/gateway.jsonl" | tr -d ' ')" = 1 ] && echo 0 || echo 1)"
check "tier p0 + stable divergence key" "$(contains 'kbli-surface:divergence' "$TMP/case/gateway.jsonl" && contains 'p0' "$TMP/case/gateway.jsonl"; echo $?)"
check "divergence headline present" "$(contains 'KBLI SURFACE DIVERGENCE' "$TMP/case/gateway.jsonl"; echo $?)"
check "heartbeat says error with raw rc" "$([ "$(json_value "$HB_FILE" status)" = error ] && contains 'detector_rc=1 result=divergence' "$HB_FILE"; echo $?)"
check "full detector output logged" "$(contains 'pma_status disagrees: 1' "$RUN_LOG"; echo $?)"
check "runner receipt is successful and fresh" "$([ "$(json_value "$RECEIPT" status)" = ok ] && [ -s "$RECEIPT" ]; echo $?)"
check "timeout pins TERM 180s then KILL 30s" "$(contains '-k 30 180 /bin/bash' "$TMP/case/timeout.calls"; echo $?)"

echo "GUILT — rc 1 without report header is detector_failure, never divergence"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=1 FAKE_DETECTOR_OUTPUT='Traceback: ValueError bad rows' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case rc1_crash
check "rc-1 crash is normalised only after honest failure alert" "$([ "$RC" -eq 0 ] && echo 0 || echo 1)"
check "detector-failure key" "$(contains 'kbli-surface:detector-failure' "$TMP/case/gateway.jsonl"; echo $?)"
check "no divergence headline or key" "$(! contains 'KBLI SURFACE DIVERGENCE' "$TMP/case/gateway.jsonl" && ! contains 'kbli-surface:divergence' "$TMP/case/gateway.jsonl"; echo $?)"
check "heartbeat records detector_failure" "$(contains 'result=detector_failure' "$HB_FILE"; echo $?)"

echo "GUILT — rc 4 is cannot-verify, with disjoint language"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=4 FAKE_DETECTOR_OUTPUT='CANNOT VERIFY: offline/no Keychain/no DSN' \
FAKE_GATEWAY_VERDICT=spooled FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case cannot_verify
check "recognised cannot-verify returns outer zero" "$([ "$RC" -eq 0 ] && echo 0 || echo 1)"
check "digest tier + stable key" "$(contains 'digest' "$TMP/case/gateway.jsonl" && contains 'kbli-surface:cannot-verify' "$TMP/case/gateway.jsonl"; echo $?)"
check "NO COMPARISON VERDICT language" "$(contains 'CANNOT VERIFY' "$TMP/case/gateway.jsonl" && contains 'NO COMPARISON VERDICT' "$TMP/case/gateway.jsonl"; echo $?)"
check "cannot-verify does not say drift/divergence" "$(! grep -Eqi 'drift|divergence' "$TMP/case/gateway.jsonl"; echo $?)"
check "warning heartbeat keeps raw rc 4" "$([ "$(json_value "$HB_FILE" status)" = warning ] && contains 'detector_rc=4 result=cannot_verify' "$HB_FILE"; echo $?)"

echo "GUILT — timeout and live overlap are cannot-verify; stale lock gets one retry"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=124 FAKE_DETECTOR_OUTPUT='timeout fixture' \
FAKE_GATEWAY_VERDICT=spooled FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case timeout
check "timeout rc 124 becomes cannot-verify" "$([ "$RC" -eq 0 ] && contains 'detector_rc=124 result=cannot_verify' "$HB_FILE"; echo $?)"

FAKE_PREPARE_LOCK=live FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=0 FAKE_DETECTOR_OUTPUT='should-not-run' \
FAKE_GATEWAY_VERDICT=spooled FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case live_overlap
check "live PID overlap becomes cannot-verify" "$([ "$RC" -eq 0 ] && contains 'result=cannot_verify' "$HB_FILE"; echo $?)"
check "live overlap never invokes detector" "$([ ! -s "$TMP/case/detector.calls" ] && echo 0 || echo 1)"
unset FAKE_PREPARE_LOCK

FAKE_PREPARE_LOCK=stale FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=0 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case stale_lock
check "dead PID lock is cleaned once and detector runs" "$([ "$RC" -eq 0 ] && [ -s "$TMP/case/detector.calls" ]; echo $?)"
unset FAKE_PREPARE_LOCK

echo "INNOCENCE — conformant comparison is healthy silence with two receipts"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=0 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical\n  pma_status disagrees: 0' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case conformant
check "conformant outer rc 0" "$([ "$RC" -eq 0 ] && echo 0 || echo 1)"
check "gateway not invoked" "$([ ! -s "$TMP/case/gateway.jsonl" ] && echo 0 || echo 1)"
check "heartbeat ok" "$([ "$(json_value "$HB_FILE" status)" = ok ] && echo 0 || echo 1)"
check "durable log records rc 0" "$(contains 'detector_rc=0 result=conformant' "$RUN_LOG"; echo $?)"
check "runner receipt advances and says ok" "$([ "$(json_value "$RECEIPT" status)" = ok ] && echo 0 || echo 1)"

echo "INNOCENCE — kill switch writes disabled heartbeat and runs no detector"
KBLI_SURFACE_CONFORMANCE_ENABLED=false FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=0 \
FAKE_DETECTOR_OUTPUT='should-not-run' FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 \
FAKE_HEARTBEAT_RC=0 run_case disabled
check "disabled is an outer success" "$([ "$RC" -eq 0 ] && echo 0 || echo 1)"
check "disabled heartbeat is explicit" "$([ "$(json_value "$HB_FILE" status)" = disabled ] && echo 0 || echo 1)"
check "kill switch invokes neither detector nor gateway" "$([ ! -s "$TMP/case/detector.calls" ] && [ ! -s "$TMP/case/gateway.jsonl" ]; echo $?)"
unset KBLI_SURFACE_CONFORMANCE_ENABLED

echo "GUILT — alert and heartbeat failures stay audible through cron-runner fallback"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=1 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical\n  pma_status disagrees: 1' \
FAKE_GATEWAY_VERDICT='internal error' FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case gateway_failure
check "unaccepted gateway makes runner fail" "$([ "$RC" -ne 0 ] && [ "$(json_value "$RECEIPT" status)" = failed ]; echo $?)"
check "fallback carries truthful CRON_ALERT_P0 sentence" "$(contains 'could not hand its alert to the gateway' "$RECEIPT"; echo $?)"

FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=0 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=9 run_case heartbeat_failure
check "heartbeat failure makes runner fail" "$([ "$RC" -ne 0 ] && [ "$(json_value "$RECEIPT" status)" = failed ]; echo $?)"
check "fallback identifies heartbeat failure" "$(contains 'direct heartbeat failed' "$TMP/case/gateway.jsonl"; echo $?)"

echo "CREDENTIAL GUILT + INNOCENCE — no whole-secrets sourcing"
FAKE_PORT_LISTENING=0 FAKE_FLY_RC=1 FAKE_DETECTOR_RC=0 FAKE_DETECTOR_OUTPUT='should-not-run' \
FAKE_GATEWAY_VERDICT=spooled FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case fly_refused
check "refused app-scoped Fly probe becomes cannot-verify" "$([ "$RC" -eq 0 ] && contains 'cannot_verify' "$HB_FILE"; echo $?)"
check "refused probe never invokes detector" "$([ ! -s "$TMP/case/detector.calls" ] && echo 0 || echo 1)"
check "probe is app-scoped to nuzantara-postgres" "$(contains 'machine list --app nuzantara-postgres' "$TMP/case/fly.calls"; echo $?)"

FAKE_PORT_LISTENING=1 FAKE_FLY_RC=1 FAKE_DETECTOR_RC=0 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case port_listening
check "listening port skips Fly probing" "$([ ! -s "$TMP/case/fly.calls" ] && [ -s "$TMP/case/detector.calls" ]; echo $?)"

DATABASE_URL=must-be-unset FAKE_PORT_LISTENING=0 FAKE_FLY_RC=0 FAKE_PG_STUB="$TMP/stubs/pg.sh" FAKE_DETECTOR_RC=0 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case fly_success
check "successful Fly probe reaches detector/pg stub" "$([ -s "$TMP/case/detector.calls" ] && [ -s "$TMP/case/pg.calls" ]; echo $?)"
check "non-Fly secrets never reach detector" "$(! contains 'whole-secrets contamination' "$TMP/case/output"; echo $?)"
unset FAKE_PG_STUB
check "wrapper never sources the whole secrets file" "$(! grep -Eq '(source|\.)[[:space:]]+"?\$SECRETS_FILE' "$WRAPPER_SRC"; echo $?)"
check "wrapper extracts only Fly token key names" "$(contains 'FLY_API_TOKEN|FLY_ACCESS_TOKEN' "$WRAPPER_SRC"; echo $?)"

echo "NIGHT-CAP NOTE — durable overflow is accepted but recorded distinctly"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=1 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical\n  pma_status disagrees: 1' \
FAKE_GATEWAY_VERDICT=p0_overflow_spooled FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case night_cap
check "overflow-spooled remains accepted" "$([ "$RC" -eq 0 ] && echo 0 || echo 1)"
check "night-cap note is explicit in durable log" "$(contains 'night-cap-note: P0 budget overflowed' "$RUN_LOG"; echo $?)"

echo "MUTATION CHECKS — the guilt corpus kills both rc-capture mutants"
sed '/^[[:space:]]*set +e[[:space:]]*$/d' "$WRAPPER_SRC" > "$TMP/run/mutant-no-set-plus-e.sh"
chmod +x "$TMP/run/mutant-no-set-plus-e.sh"
CASE_WRAPPER="$TMP/run/mutant-no-set-plus-e.sh"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=1 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical\n  pma_status disagrees: 1' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case mutant_no_set_plus_e
check "deleting set +e makes divergence guilt red" "$([ "$RC" -ne 0 ] && echo 0 || echo 1)"

sed 's/detector_rc=\$?/detector_rc=0/' "$WRAPPER_SRC" > "$TMP/run/mutant-rc-zero.sh"
chmod +x "$TMP/run/mutant-rc-zero.sh"
CASE_WRAPPER="$TMP/run/mutant-rc-zero.sh"
FAKE_PORT_LISTENING=1 FAKE_DETECTOR_RC=1 \
FAKE_DETECTOR_OUTPUT='kbli_documents conformance vs canonical\n  pma_status disagrees: 1' \
FAKE_GATEWAY_VERDICT=sent FAKE_GATEWAY_RC=0 FAKE_HEARTBEAT_RC=0 run_case mutant_rc_zero
check "forcing captured rc=0 destroys expected divergence signal" "$([ "$RC" -eq 0 ] && [ ! -s "$TMP/case/gateway.jsonl" ] && [ "$(json_value "$HB_FILE" status)" = ok ]; echo $?)"
CASE_WRAPPER="$TMP/run/kbli-surface-conformance-run.sh"

echo "STATIC ARMS — plist, installer, Sentinel fragment, organ checksum"
/usr/bin/python3 - "$PLIST" <<'PY'
import plistlib, sys
p = plistlib.load(open(sys.argv[1], "rb"))
assert p["StartCalendarInterval"] == {"Hour": 8, "Minute": 20}
assert p["KeepAlive"] is False and p["RunAtLoad"] is False
assert p["EnvironmentVariables"]["CRON_RUNNER_JOB_NAME"] == "kbli_surface_conformance"
assert p["ProgramArguments"] == [
    "/bin/bash",
    "/Users/nuzantara/nuzantara/scripts/cron-runner.sh",
    "/Users/nuzantara/nuzantara/infra/launchagents/wrappers/kbli-surface-conformance-run.sh",
]
flat = repr(p).lower()
assert all(word not in flat for word in ("password", "database_url", "fly_api_token", "pgpassword"))
PY
check "plist schedule/booleans/paths/no-secrets" "$?"
check "Pro-only guard + kill switch present" "$(contains 'EXPECTED_HOST' "$WRAPPER_SRC" && contains 'KBLI_SURFACE_CONFORMANCE_ENABLED' "$WRAPPER_SRC"; echo $?)"
check "installer stages real Sentinel registry merge" "$(contains 'REGISTRY_FILE="$HOME/.agent/decisions/job_registry.json"' "$INSTALLER" && contains 'registry_update add' "$INSTALLER"; echo $?)"
/usr/bin/python3 - "$REGISTRY_FRAGMENT" <<'PY'
import json, sys
f = json.load(open(sys.argv[1], encoding="utf-8"))
assert f["job"] == "kbli_surface_conformance"
e = f["entry"]
assert e["label"] == "com.nuzantara.kbli-surface-conformance.daily"
assert e["schedule_seconds"] == 86400 and e["staleness_threshold_s"] == 90000
assert e["restart_cmd"].startswith("launchctl kickstart")
PY
check "Sentinel job fragment schema" "$?"

PYTHONPATH="$ROOT/apps/organism" "$VENV_PY" -m organism.tools.validate_organs_registry "$ORGANS" > "$TMP/organ-validator.out" 2>&1
check "organ registry schema + checksum" "$?"
check "organ carries direct heartbeat and infra.postgres dependency" "$(contains 'pro.kbli_surface_conformance' "$ORGANS" && contains 'pro.kbli_surface_conformance.json' "$ORGANS"; echo $?)"

echo "DETECTOR REGRESSION — existing rc 0/1/4 corpus"
PYTHONPATH="$ROOT/apps/organism" "$VENV_PY" -m pytest "$ROOT/scripts/kbli_filiera/tests/test_kbli_surface_conformance.py" -q > "$TMP/detector-tests.out" 2>&1
DETECTOR_TEST_RC=$?
check "existing detector suite" "$DETECTOR_TEST_RC"
if [ "$DETECTOR_TEST_RC" -ne 0 ]; then
    tail -n 30 "$TMP/detector-tests.out"
fi

echo
printf 'kbli surface conformance arming corpus: %d ok, %d FAIL\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
