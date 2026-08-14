#!/bin/sh
# test_army_spark_lane.sh — guilt+innocence corpus for scripts/army/spark_lane.sh
# (Armata H24 lane 1, 2026-08-14). Runs the REAL wrapper against a fake HOME +
# fake repo + a controllable stub `codex` binary, never the network, never a
# live queue. W107 discipline: prove the alarm/behaviour FIRES on the failure
# shapes it exists to catch, not just that the caller survives.
#
# Run:  sh scripts/tests/test_army_spark_lane.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0
note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WRAPPER="$SCRIPT_DIR/army/spark_lane.sh"

if [ ! -f "$WRAPPER" ]; then
    echo "FATAL: $WRAPPER not found"
    exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/test-army-spark.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# ---------------------------------------------------------------------------
# Fake world: a repo dir (with tg_notify stub) + a queue + isolated state.
# ---------------------------------------------------------------------------
setup_world() {
    rm -rf "$WORK/world"
    mkdir -p "$WORK/world/repo/scripts" "$WORK/world/queue" \
        "$WORK/world/reports" "$WORK/world/state" "$WORK/world/logs" \
        "$WORK/world/sidecar" "$WORK/world/bin" "$WORK/world/home"

    cat > "$WORK/world/repo/scripts/tg_notify.py" <<'PY'
#!/usr/bin/env python3
import os
import sys
log = os.environ.get("STUB_TG_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\n")
PY
    chmod +x "$WORK/world/repo/scripts/tg_notify.py"
    : > "$WORK/world/tg.log"

    cat > "$WORK/world/queue/task-one.md" <<'MD'
# Test task one

Read-only analysis prompt body.
MD
}

# codex stub: behaviour selected via STUB_CODEX_MODE (success|quota|fail).
write_codex_stub() {
    mode="$1"
    cat > "$WORK/world/bin/codex" <<SH
#!/bin/sh
case "\$STUB_CODEX_MODE" in
    success) echo "STUB REPORT BODY"; exit 0 ;;
    quota) echo "error: out of extra usage on this weekly bucket"; exit 1 ;;
    fail) echo "boom: synthetic codex crash"; exit 3 ;;
    *) echo "unset STUB_CODEX_MODE"; exit 9 ;;
esac
SH
    chmod +x "$WORK/world/bin/codex"
}

run_wrapper() {
    # Fixed fake-world env, then caller-supplied VAR=val overrides ("$@"),
    # then the command. `env` (not shell prefix-assignment) so the override
    # list can be empty or many words without fragile quoting.
    env \
        STUB_TG_LOG="$WORK/world/tg.log" \
        PATH="$WORK/world/bin:$PATH" \
        ARMY_SPARK_REPO="$WORK/world/repo" \
        ARMY_SPARK_QUEUE_DIR="$WORK/world/queue" \
        ARMY_SPARK_REPORTS_DIR="$WORK/world/reports" \
        ARMY_SPARK_STATE_DIR="$WORK/world/state" \
        ARMY_SPARK_LOG_DIR="$WORK/world/logs" \
        ARMY_SPARK_SIDECAR_DIR="$WORK/world/sidecar" \
        ARMY_SPARK_PIDFILE="$WORK/world/spark.pid" \
        ARMY_SPARK_CODEX_BIN="codex" \
        ARMY_SPARK_SKIP_NODE_GUARD=1 \
        HOME="$WORK/world/home" \
        "$@" \
        /bin/bash "$WRAPPER" > "$WORK/world/wrapper.out" 2>&1
    echo $?
}

sidecar_status() {
    if [ -f "$WORK/world/sidecar/army.spark_lane.json" ]; then
        # crude field extraction, no jq dependency assumed
        grep -o '"status":"[a-z]*"' "$WORK/world/sidecar/army.spark_lane.json" | head -1 | cut -d'"' -f4
    fi
}

# ---------------------------------------------------------------------------
# Case 1 (guilt): kill switch off -> disabled, no codex invocation.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_ENABLED=false STUB_CODEX_MODE=success)"
status="$(sidecar_status)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" = "0" ] && [ "$status" = "disabled" ]; then
    note_pass "kill switch off: exits 0, heartbeat=disabled"
else
    note_fail "kill switch off: rc=$rc status=$status"
fi
if [ "$report_count" = "0" ]; then
    note_pass "kill switch off innocence: no report written"
else
    note_fail "kill switch off: a report was written despite the kill switch"
fi

# ---------------------------------------------------------------------------
# Case 2 (guilt): wrong node -> disabled, no dispatch (node guard fires).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_SKIP_NODE_GUARD=0 ARMY_SPARK_NODE_OVERRIDE=some-other-mac STUB_CODEX_MODE=success)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$status" = "disabled" ]; then
    note_pass "wrong node: exits 0, heartbeat=disabled"
else
    note_fail "wrong node: rc=$rc status=$status"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence): right node override explicitly matches -> proceeds.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_SKIP_NODE_GUARD=0 ARMY_SPARK_NODE_OVERRIDE=nuzantara ARMY_SPARK_REQUIRED_NODE=nuzantara STUB_CODEX_MODE=success)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" = "0" ] && [ "$report_count" = "1" ]; then
    note_pass "right node: dispatch proceeds, report written"
else
    note_fail "right node: rc=$rc report_count=$report_count"
fi

# ---------------------------------------------------------------------------
# Case 4 (innocence): successful dispatch writes report, marks task done,
# heartbeat=ok, and a SECOND tick does not reprocess the same task.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc1="$(run_wrapper STUB_CODEX_MODE=success)"
status1="$(sidecar_status)"
report_file="$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | head -1)"
if [ "$rc1" = "0" ] && [ "$status1" = "ok" ] && [ -n "$report_file" ] && grep -q "STUB REPORT BODY" "$report_file"; then
    note_pass "successful dispatch: report written with codex output, heartbeat=ok"
else
    note_fail "successful dispatch: rc=$rc1 status=$status1 report_file=$report_file"
fi
before_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
rc2="$(run_wrapper STUB_CODEX_MODE=success)"
after_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc2" = "0" ] && [ "$after_count" = "$before_count" ]; then
    note_pass "dedup innocence: second tick does not reprocess the already-done task"
else
    note_fail "dedup innocence: before=$before_count after=$after_count"
fi

# ---------------------------------------------------------------------------
# Case 5 (guilt): quota marker in codex output -> backoff written, task NOT
# marked done, NOT reported as a success report, a digest alert fires.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub quota
rc="$(run_wrapper STUB_CODEX_MODE=quota)"
status="$(sidecar_status)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" = "0" ] && [ "$status" = "degraded" ] && [ "$report_count" = "0" ] && [ -f "$WORK/world/state/backoff-until.txt" ]; then
    note_pass "quota: degraded heartbeat, no report, backoff file written"
else
    note_fail "quota: rc=$rc status=$status report_count=$report_count backoff_exists=$([ -f "$WORK/world/state/backoff-until.txt" ] && echo y || echo n)"
fi
if grep -q "army-spark:quota" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "quota: telegram digest alert fired with the right dedup key"
else
    note_fail "quota: no telegram digest alert found in stub log"
fi
if grep -qxF "task-one.md:$(shasum -a 256 "$WORK/world/queue/task-one.md" 2>/dev/null | awk '{print $1}')" "$WORK/world/state/done-list.txt" 2>/dev/null; then
    note_fail "quota: task was incorrectly marked done despite the quota condition"
else
    note_pass "quota innocence: task NOT marked done (stays eligible for retry after backoff)"
fi

# ---------------------------------------------------------------------------
# Case 6 (guilt): backoff active -> the NEXT tick skips dispatch even with a
# fresh (non-quota) stub, and does not increment the daily run counter.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
mkdir -p "$WORK/world/state"
future_epoch=$(( $(date +%s) + 3600 ))
echo "$future_epoch" > "$WORK/world/state/backoff-until.txt"
rc="$(run_wrapper STUB_CODEX_MODE=success)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$report_count" = "0" ] && [ "$status" = "degraded" ]; then
    note_pass "backoff active: dispatch skipped, no report, degraded heartbeat"
else
    note_fail "backoff active: rc=$rc report_count=$report_count status=$status"
fi

# ---------------------------------------------------------------------------
# Case 7 (guilt): daily cap reached -> dispatch skipped even with a pending
# task and no active backoff, heartbeat stays ok (expected condition).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
mkdir -p "$WORK/world/state"
echo "6" > "$WORK/world/state/run-count-$(date +%Y-%m-%d).txt"
rc="$(run_wrapper ARMY_SPARK_DAILY_CAP=6 STUB_CODEX_MODE=success)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$report_count" = "0" ] && [ "$status" = "ok" ]; then
    note_pass "daily cap reached: dispatch skipped, no report, heartbeat=ok (expected, not an error)"
else
    note_fail "daily cap reached: rc=$rc report_count=$report_count status=$status"
fi

# ---------------------------------------------------------------------------
# Case 8 (guilt): codex exec real failure (non-quota) -> error heartbeat,
# task NOT marked done, a P0 alert fires (distinct dedup key from quota).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub fail
rc="$(run_wrapper STUB_CODEX_MODE=fail)"
status="$(sidecar_status)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" = "0" ] && [ "$status" = "error" ] && [ "$report_count" = "0" ]; then
    note_pass "codex failure: error heartbeat, no report written"
else
    note_fail "codex failure: rc=$rc status=$status report_count=$report_count"
fi
if grep -q "army-spark:codex-failed" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "codex failure: P0 alert fired with the right dedup key"
else
    note_fail "codex failure: no P0 alert found in stub log"
fi

# ---------------------------------------------------------------------------
# Case 9 (guilt): single-instance guard — a live pidfile blocks a second run
# and does not touch the queue.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
echo $$ > "$WORK/world/spark.pid"   # this test process's own pid: guaranteed alive
rc="$(run_wrapper STUB_CODEX_MODE=success)"
report_count=$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" = "0" ] && [ "$report_count" = "0" ]; then
    note_pass "single-instance guard: concurrent run skipped, no dispatch"
else
    note_fail "single-instance guard: rc=$rc report_count=$report_count"
fi
rm -f "$WORK/world/spark.pid"

echo
echo "TOTAL: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
