#!/bin/sh
# test_army_spark_lane.sh — guilt+innocence corpus for scripts/army/spark_lane.sh
# (Armata H24 lane 1, 2026-08-14, amended same day after a cross-family Kimi
# K3 refutation of the design closed 12 numbered defects — see the script's
# own header and research/operations/2026-08-14-armata-h24-standing-lanes.md).
# Runs the REAL wrapper against a fake HOME + fake repo + a controllable
# stub `codex` binary, never the network, never a live queue. W107
# discipline: prove the alarm/behaviour FIRES on the failure shapes it
# exists to catch, not just that the caller survives.
#
# Requires a real python3 on PATH (the wrapper itself now depends on one for
# attempts.jsonl state management — this is a deliberate, documented choice,
# not a gap: see select_task()'s comment in spark_lane.sh).
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

wita_today() { TZ=Asia/Makassar date '+%Y-%m-%d'; }

# ---------------------------------------------------------------------------
# Fake world: a repo dir (with tg_notify stub) + a queue + isolated state.
# ---------------------------------------------------------------------------
setup_world() {
    rm -rf "$WORK/world"
    mkdir -p "$WORK/world/repo/scripts/lib" "$WORK/world/queue" \
        "$WORK/world/reports" "$WORK/world/state" "$WORK/world/logs" \
        "$WORK/world/sidecar" "$WORK/world/bin" "$WORK/world/home"

    # The wrapper unconditionally sources the fleet seat door from
    # $ARMY_SPARK_REPO/scripts/lib/codex_seat.sh — copy the REAL library in
    # so that source succeeds exactly as it does against a real checkout,
    # instead of stubbing around it and silently diverging from the
    # guarded contract (test_no_call_site_invokes_codex_without_choosing_a_seat).
    cp "$SCRIPT_DIR/lib/codex_seat.sh" "$WORK/world/repo/scripts/lib/codex_seat.sh"

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

    # A live codex seat for scripts/lib/codex_seat.sh to resolve by default,
    # so the pre-existing cases below keep exercising exactly the same
    # dispatch path they did before the seat-library sourcing landed. Case 12
    # removes this to exercise the seatless path on purpose.
    mkdir -p "$WORK/world/home/.codex-o2"
    echo '{}' > "$WORK/world/home/.codex-o2/auth.json"

    # The real queue dir carries a README.md alongside real tasks (documents
    # the queue format, incl. quota/backoff/429 behavior) — every fake world
    # must reproduce that shape so the README-exclusion fix (defect 1,
    # 2026-08-15) is exercised by every case, not just a dedicated one.
    # Written BEFORE task-one.md on purpose: select_task() without the
    # exclusion picks the earliest-mtime never-attempted candidate, so if
    # README.md were still eligible it would win the race by CREATION ORDER
    # alone — the guilt assertion in Case 13 below must not depend on
    # alphabetical/mtime luck to catch the defect.
    cat > "$WORK/world/queue/README.md" <<'MD'
# Spark queue README

This queue feeds army.spark_lane. If the bucket returns "out of extra usage",
"usage limit", "quota exceeded", or HTTP 429, the lane backs off for 12h.
Rate-limit and weekly limit markers are treated the same way.
MD

    cat > "$WORK/world/queue/task-one.md" <<'MD'
# Test task one

Read-only analysis prompt body.
MD
}

write_task() {  # $1 filename $2 content-line (so distinct tasks hash differently)
    cat > "$WORK/world/queue/$1" <<MD
# $2

Read-only analysis prompt body for $2.
MD
}

# codex stub: behaviour selected via STUB_CODEX_MODE (success|quota|fail).
# Every invocation is logged (never truncated by mode) so a test can assert
# the stub was NEVER called — the only way to prove a guard refused BEFORE
# reaching codex, not just that the outcome happens to look the same as a
# real codex failure (Case 12).
write_codex_stub() {
    mode="$1"
    : > "$WORK/world/codex-invocations.log"
    cat > "$WORK/world/bin/codex" <<SH
#!/bin/sh
echo "invoked \$*" >> "$WORK/world/codex-invocations.log"
case "\$STUB_CODEX_MODE" in
    success) echo "STUB REPORT BODY"; exit 0 ;;
    success_quota_text) echo "Analysis: this queue documents a usage limit and 429 backoff policy."; exit 0 ;;
    quota) echo "error: out of extra usage on this weekly bucket"; exit 1 ;;
    quota_with_reset) echo "ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark. Switch to another model now, or try again at Jan 1st, 2030 8:06 PM."; exit 1 ;;
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
        ARMY_SPARK_CODEX_BIN="codex" \
        ARMY_SPARK_CODEX_HOME="$WORK/world/home/.codex-o2" \
        ARMY_SPARK_SKIP_NODE_GUARD=1 \
        HOME="$WORK/world/home" \
        "$@" \
        /bin/bash "$WRAPPER" > "$WORK/world/wrapper.out" 2>&1
    echo $?
}

sidecar_status() {
    if [ -f "$WORK/world/sidecar/army.spark_lane.json" ]; then
        # crude field extraction, no jq dependency assumed
        grep -o '"status":"[a-z-]*"' "$WORK/world/sidecar/army.spark_lane.json" | head -1 | cut -d'"' -f4
    fi
}

report_count() { find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' '; }

p0_count() { grep -c '"--tier" *"p0"\|army-spark:[a-z-]*-fail\|tg_notify\[army-spark:' "$WORK/world/tg.log" 2>/dev/null || echo 0; }

# ---------------------------------------------------------------------------
# Case 1 (guilt): kill switch off -> disabled, no codex invocation, and the
# digest-check code path still runs (item 11) rather than an early exit.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_ENABLED=false STUB_CODEX_MODE=success ARMY_SPARK_DIGEST_HOUR=99)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$status" = "disabled" ]; then
    note_pass "kill switch off: exits 0, heartbeat=disabled"
else
    note_fail "kill switch off: rc=$rc status=$status"
fi
if [ "$(report_count)" = "0" ]; then
    note_pass "kill switch off innocence: no report written"
else
    note_fail "kill switch off: a report was written despite the kill switch"
fi

# ---------------------------------------------------------------------------
# Case 1b (guilt, item 11): kill switch off AND it's past digest hour ->
# the digest fires and explicitly says the lane is disabled.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_ENABLED=false STUB_CODEX_MODE=success ARMY_SPARK_DIGEST_HOUR=0)"
if [ "$rc" = "0" ] && grep -q "ARMY_SPARK_ENABLED=false" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "kill switch off past digest hour: digest still fires and names the kill switch"
else
    note_fail "kill switch off past digest hour: rc=$rc, tg.log=$(cat "$WORK/world/tg.log" 2>/dev/null)"
fi

# ---------------------------------------------------------------------------
# Case 2 (guilt): wrong node -> disabled, no dispatch, no digest at all
# (not my machine, not my digest to send).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_SKIP_NODE_GUARD=0 ARMY_SPARK_NODE_OVERRIDE=some-other-mac STUB_CODEX_MODE=success ARMY_SPARK_DIGEST_HOUR=0)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$status" = "disabled" ]; then
    note_pass "wrong node: exits 0, heartbeat=disabled"
else
    note_fail "wrong node: rc=$rc status=$status"
fi
if ! grep -q "army-spark:daily-digest" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "wrong node innocence: no digest sent"
else
    note_fail "wrong node: digest was sent despite the node guard"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence): right node override explicitly matches -> proceeds.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper ARMY_SPARK_SKIP_NODE_GUARD=0 ARMY_SPARK_NODE_OVERRIDE=nuzantara ARMY_SPARK_REQUIRED_NODE=nuzantara STUB_CODEX_MODE=success)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "1" ]; then
    note_pass "right node: dispatch proceeds, report written"
else
    note_fail "right node: rc=$rc report_count=$(report_count)"
fi

# ---------------------------------------------------------------------------
# Case 4 (innocence): successful dispatch writes report (with HEAD sha +
# task sha header, item 5), marks the attempt ok, heartbeat=ok, and a
# SECOND tick does not reprocess the same task.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc1="$(run_wrapper STUB_CODEX_MODE=success)"
status1="$(sidecar_status)"
report_file="$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | head -1)"
if [ "$rc1" = "0" ] && [ "$status1" = "ok" ] && [ -n "$report_file" ] \
    && grep -q "STUB REPORT BODY" "$report_file" \
    && grep -q "checkout HEAD:" "$report_file" \
    && grep -q "task sha256:" "$report_file"; then
    note_pass "successful dispatch: report written with codex output + HEAD/task sha header, heartbeat=ok"
else
    note_fail "successful dispatch: rc=$rc1 status=$status1 report_file=$report_file"
fi
if grep -q '"status":"ok"' "$WORK/world/state/attempts.jsonl" 2>/dev/null; then
    note_pass "attempts.jsonl: an ok attempt was recorded"
else
    note_fail "attempts.jsonl: no ok attempt recorded"
fi
before="$(report_count)"
rc2="$(run_wrapper STUB_CODEX_MODE=success)"
after="$(report_count)"
if [ "$rc2" = "0" ] && [ "$after" = "$before" ]; then
    note_pass "dedup innocence: second tick does not reprocess the already-done task"
else
    note_fail "dedup innocence: before=$before after=$after"
fi

# ---------------------------------------------------------------------------
# Case 4b (item 2: content-only dedup survives a rename): a task file
# renamed to a different filename with IDENTICAL content must still be
# recognized as already-done — dedup key is sha256 of content, not
# filename+sha.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
run_wrapper STUB_CODEX_MODE=success > /dev/null
before="$(report_count)"
mv "$WORK/world/queue/task-one.md" "$WORK/world/queue/task-one-renamed.md"
rc="$(run_wrapper STUB_CODEX_MODE=success)"
after="$(report_count)"
if [ "$rc" = "0" ] && [ "$after" = "$before" ]; then
    note_pass "content-only dedup: renamed-but-identical task is not reprocessed"
else
    note_fail "content-only dedup: before=$before after=$after"
fi

# ---------------------------------------------------------------------------
# Case 5 (guilt): quota marker in codex output -> backoff written (fixed
# ${BACKOFF_HOURS}h), task attempt recorded as "quota" (not "ok" — stays
# eligible for retry after backoff), a digest alert fires.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub quota
rc="$(run_wrapper STUB_CODEX_MODE=quota)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$status" = "degraded" ] && [ "$(report_count)" = "0" ] && [ -f "$WORK/world/state/backoff-until.txt" ]; then
    note_pass "quota: degraded heartbeat, no report, backoff file written"
else
    note_fail "quota: rc=$rc status=$status report_count=$(report_count) backoff_exists=$([ -f "$WORK/world/state/backoff-until.txt" ] && echo y || echo n)"
fi
if grep -q "army-spark:quota" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "quota: telegram digest alert fired with the right dedup key"
else
    note_fail "quota: no telegram digest alert found in stub log"
fi
if grep -q '"status":"quota"' "$WORK/world/state/attempts.jsonl" 2>/dev/null \
    && ! grep -q '"status":"ok"' "$WORK/world/state/attempts.jsonl" 2>/dev/null; then
    note_pass "quota innocence: attempt recorded as quota, NOT ok (stays eligible for retry)"
else
    note_fail "quota: attempts.jsonl did not record the expected quota-not-ok shape"
fi
if grep -q "out of extra usage on this weekly bucket" "$WORK/world/logs/run.log" 2>/dev/null; then
    note_pass "quota: run.log carries codex's own quota-message text (2026-08-27 diagnosability fix)"
else
    note_fail "quota: run.log did not carry codex's raw quota-message text"
fi

# ---------------------------------------------------------------------------
# Case 5b (guilt, 2026-08-27 repair): quota output that names a REALISTIC
# reset time (~3 days out — comfortably between the fixed 12h floor and the
# 7-day safety cap) sets the backoff to that parsed time, not the fixed
# ${BACKOFF_HOURS}h default. This is the fix for the measured 2026-08-19..27
# deadlock where the lane blind-retried every 12h against a bucket whose own
# reply said "try again at Aug 31st, 2026 8:06 PM" for 8 straight days.
#
# The fixture date string is built by adding 3 days + the WITA (UTC+8)
# offset to now, then formatting THAT instant in UTC — because the
# implementation reads codex's digits as WITA wall-clock and subtracts 8h,
# round-tripping through UTC-formatted digits of (target + 8h) is what
# makes the parser land back on `target` (epoch math, not a wall-clock
# label a human would write for a specific zone).
# ---------------------------------------------------------------------------
setup_world
now_epoch="$(date +%s)"
target_epoch=$((now_epoch + 3 * 86400))
label_epoch=$((target_epoch + 8 * 3600))
future_str="$(date -u -r "$label_epoch" '+%b %e, %Y %I:%M %p' 2>/dev/null || date -u -d "@$label_epoch" '+%b %e, %Y %I:%M %p' 2>/dev/null)"
cat > "$WORK/world/bin/codex" <<SH
#!/bin/sh
echo "invoked \$*" >> "$WORK/world/codex-invocations.log"
echo "ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark. Switch to another model now, or try again at $future_str."
exit 1
SH
chmod +x "$WORK/world/bin/codex"
rc="$(run_wrapper STUB_CODEX_MODE=irrelevant-custom-stub-above)"
backoff_val="$(cat "$WORK/world/state/backoff-until.txt" 2>/dev/null || echo 0)"
lo=$((now_epoch + 2 * 86400))
hi=$((now_epoch + 5 * 86400))
if [ "$rc" = "0" ] && [ "$backoff_val" -ge "$lo" ] && [ "$backoff_val" -le "$hi" ]; then
    note_pass "quota with a realistic parseable reset ('$future_str'): backoff set near the parsed time, not the fixed 12h"
else
    note_fail "quota with realistic reset: rc=$rc backoff_val=$backoff_val expected within [$lo,$hi] (fixture: '$future_str')"
fi
if grep -q "parsed reset time" "$WORK/world/logs/run.log" 2>/dev/null; then
    note_pass "quota with realistic reset: log names the parsed-reset code path"
else
    note_fail "quota with realistic reset: log did not name the parsed-reset path"
fi

# ---------------------------------------------------------------------------
# Case 5c (guilt, safety cap): a quota message naming an ABSURD reset time
# (years out) must NOT wedge the lane open-endedly on a parser misfire or a
# provider quoting a nonsensical future date — falls back to the fixed
# ${BACKOFF_HOURS}h default instead, same as no reset time at all.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub quota_with_reset
now_epoch="$(date +%s)"
rc="$(run_wrapper STUB_CODEX_MODE=quota_with_reset)"
backoff_val="$(cat "$WORK/world/state/backoff-until.txt" 2>/dev/null || echo 0)"
lower=$((now_epoch + 11 * 3600))
upper=$((now_epoch + 13 * 3600))
if [ "$rc" = "0" ] && [ "$backoff_val" -ge "$lower" ] && [ "$backoff_val" -le "$upper" ]; then
    note_pass "quota with an absurd (years-out) reset time: capped back to the fixed ~12h default"
else
    note_fail "quota with absurd reset time: backoff_val=$backoff_val expected within [$lower,$upper]"
fi

# ---------------------------------------------------------------------------
# Case 5d (innocence, 2026-08-27 repair): quota output WITHOUT a parseable
# reset time still falls back to the fixed ${BACKOFF_HOURS}h default,
# unchanged from before this repair — the parser must only ever EXTEND the
# wait on real evidence, never invent one from silence.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub quota
now_epoch="$(date +%s)"
rc="$(run_wrapper STUB_CODEX_MODE=quota)"
backoff_val="$(cat "$WORK/world/state/backoff-until.txt" 2>/dev/null || echo 0)"
lower=$((now_epoch + 11 * 3600))
upper=$((now_epoch + 13 * 3600))
if [ "$rc" = "0" ] && [ "$backoff_val" -ge "$lower" ] && [ "$backoff_val" -le "$upper" ]; then
    note_pass "quota without a parseable reset: backoff stays at the fixed ~12h default"
else
    note_fail "quota without a parseable reset: backoff_val=$backoff_val expected within [$lower,$upper]"
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
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "0" ] && [ "$status" = "degraded" ]; then
    note_pass "backoff active: dispatch skipped, no report, degraded heartbeat"
else
    note_fail "backoff active: rc=$rc report_count=$(report_count) status=$status"
fi

# ---------------------------------------------------------------------------
# Case 7 (guilt): daily cap reached (WITA calendar day, item 6) -> dispatch
# skipped even with a pending task and no active backoff, heartbeat stays
# ok (expected condition, not an error).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
mkdir -p "$WORK/world/state"
echo "6" > "$WORK/world/state/run-count-$(wita_today).txt"
rc="$(run_wrapper ARMY_SPARK_DAILY_CAP=6 STUB_CODEX_MODE=success)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "0" ] && [ "$status" = "ok" ]; then
    note_pass "daily cap reached (WITA day): dispatch skipped, no report, heartbeat=ok"
else
    note_fail "daily cap reached: rc=$rc report_count=$(report_count) status=$status"
fi

# ---------------------------------------------------------------------------
# Case 8 (guilt): codex exec real failure (non-quota) -> error heartbeat,
# no report, a P0 alert fires (distinct dedup key from quota), and the
# attempt is recorded "failed" (not silently dropped).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub fail
rc="$(run_wrapper STUB_CODEX_MODE=fail)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$status" = "error" ] && [ "$(report_count)" = "0" ]; then
    note_pass "codex failure: error heartbeat, no report written"
else
    note_fail "codex failure: rc=$rc status=$status report_count=$(report_count)"
fi
if grep -q "army-spark:codex-failed" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "codex failure: P0 alert fired with the right dedup key"
else
    note_fail "codex failure: no P0 alert found in stub log"
fi
if grep -q '"status":"failed"' "$WORK/world/state/attempts.jsonl" 2>/dev/null; then
    note_pass "codex failure: attempt recorded as failed in attempts.jsonl"
else
    note_fail "codex failure: no failed attempt recorded"
fi

# ---------------------------------------------------------------------------
# Case 8b (item 3: quarantine after 2 failures — a poisoned task must never
# block the head of the queue nor retry forever). Third tick with the SAME
# always-failing stub must produce NO new P0 alert and NO new report: the
# task is quarantined, the queue reads as empty.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub fail
run_wrapper STUB_CODEX_MODE=fail > /dev/null   # attempt 1: failed (1)
run_wrapper STUB_CODEX_MODE=fail > /dev/null   # attempt 2: failed (2) -> quarantined
p0_before="$(grep -c "army-spark:codex-failed" "$WORK/world/tg.log" 2>/dev/null || echo 0)"
rc="$(run_wrapper STUB_CODEX_MODE=fail)"       # attempt 3: should NOT dispatch at all
status="$(sidecar_status)"
p0_after="$(grep -c "army-spark:codex-failed" "$WORK/world/tg.log" 2>/dev/null || echo 0)"
if [ "$rc" = "0" ] && [ "$p0_after" = "$p0_before" ] && [ "$status" = "ok" ]; then
    note_pass "quarantine after 2 failures: third tick does not retry, no new P0, heartbeat=ok (queue reads empty)"
else
    note_fail "quarantine: rc=$rc p0_before=$p0_before p0_after=$p0_after status=$status"
fi

# ---------------------------------------------------------------------------
# Case 8c (item 4: 3 consecutive NON-quota failures across DIFFERENT tasks
# also trigger the fixed backoff — protects against a silently-changed
# codex output format, not just quota exhaustion on one poisoned task).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub fail
rm -f "$WORK/world/queue/task-one.md"
write_task "task-a.md" "Task A"
write_task "task-b.md" "Task B"
write_task "task-c.md" "Task C"
run_wrapper STUB_CODEX_MODE=fail > /dev/null   # task-a fails, consec=1
run_wrapper STUB_CODEX_MODE=fail > /dev/null   # task-b fails, consec=2
rc="$(run_wrapper STUB_CODEX_MODE=fail)"       # task-c fails, consec=3 -> backoff
if [ "$rc" = "0" ] && [ -f "$WORK/world/state/backoff-until.txt" ] \
    && grep -q "army-spark:consecutive-fail-backoff" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "3 consecutive non-quota failures across distinct tasks: fixed backoff triggered + distinct P0"
else
    note_fail "consecutive-fail backoff: rc=$rc backoff_exists=$([ -f "$WORK/world/state/backoff-until.txt" ] && echo y || echo n)"
fi

# ---------------------------------------------------------------------------
# Case 9 (guilt, item 1): corrupt attempts.jsonl -> the lane HALTS
# (status-corrupt), fires a P0, and does NOT fall open into re-running the
# whole queue (no report written despite a pending task).
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
mkdir -p "$WORK/world/state"
printf '{"sha":"abc","status":"ok"}\nTHIS IS NOT JSON\n' > "$WORK/world/state/attempts.jsonl"
rc="$(run_wrapper STUB_CODEX_MODE=success)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$status" = "error" ] && [ "$(report_count)" = "0" ]; then
    note_pass "corrupt attempts.jsonl: halts (error heartbeat), does not fall open"
else
    note_fail "corrupt attempts.jsonl: rc=$rc status=$status report_count=$(report_count)"
fi
if grep -q "army-spark:state-corrupt" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "corrupt attempts.jsonl: P0 alert fired"
else
    note_fail "corrupt attempts.jsonl: no P0 alert found"
fi

# ---------------------------------------------------------------------------
# Case 10 (guilt, item 1): single-instance guard — a LIVE lock (mkdir'd
# lock dir with this test process's own pid inside, guaranteed alive)
# blocks a second run with status=skipped-overlap, no dispatch.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
mkdir -p "$WORK/world/state/run.lock"
echo $$ > "$WORK/world/state/run.lock/pid"
rc="$(run_wrapper STUB_CODEX_MODE=success)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "0" ]; then
    note_pass "single-instance guard: concurrent run skipped, no dispatch"
else
    note_fail "single-instance guard: rc=$rc report_count=$(report_count)"
fi
rm -rf "$WORK/world/state/run.lock"

# ---------------------------------------------------------------------------
# Case 11 (innocence, item 1): a STALE lock (mkdir'd lock dir with a dead
# pid inside) is reclaimed, not treated as a live overlap — dispatch
# proceeds, and the lock dir does not linger after the run.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
mkdir -p "$WORK/world/state/run.lock"
echo 999999999 > "$WORK/world/state/run.lock/pid"   # almost certainly not alive
rc="$(run_wrapper STUB_CODEX_MODE=success)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "1" ] && [ ! -d "$WORK/world/state/run.lock" ]; then
    note_pass "stale lock: reclaimed, dispatch proceeds, lock dir cleaned up on exit"
else
    note_fail "stale lock: rc=$rc report_count=$(report_count) lock_dir_exists=$([ -d "$WORK/world/state/run.lock" ] && echo y || echo n)"
fi

# ---------------------------------------------------------------------------
# Case 12 (guilt): no codex seat resolves anywhere in the fake HOME (no
# ARMY_SPARK_CODEX_HOME override, no auth.json under $HOME/.codex*) ->
# codex_seat_pick() (sourced from the REAL scripts/lib/codex_seat.sh, see
# setup_world) returns empty, so the dispatch subshell's `[ -n
# "$CODEX_HOME_OVERRIDE" ] || exit 91` guard fires BEFORE codex is ever
# exec'd — never a silent fallback to a dead default ~/.codex. Proven by the
# stub's own invocation log staying empty, not just by the outcome looking
# like a codex failure.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rm -rf "$WORK/world/home/.codex-o2"   # strip setup_world's default seat: seatless HOME
rc="$(run_wrapper ARMY_SPARK_CODEX_HOME="" STUB_CODEX_MODE=success)"
status="$(sidecar_status)"
invocations="$(wc -l < "$WORK/world/codex-invocations.log" 2>/dev/null | tr -d ' ')"
if [ "$rc" = "0" ] && [ "$status" = "error" ] && [ "$(report_count)" = "0" ] && [ "$invocations" = "0" ]; then
    note_pass "no codex seat anywhere: dispatch refuses (rc=91 guard), stub codex never invoked"
else
    note_fail "no codex seat anywhere: rc=$rc status=$status report_count=$(report_count) invocations=$invocations"
fi
if grep -q '"status":"failed"' "$WORK/world/state/attempts.jsonl" 2>/dev/null; then
    note_pass "no codex seat anywhere: attempt recorded as failed (not silently dropped)"
else
    note_fail "no codex seat anywhere: no failed attempt recorded in attempts.jsonl"
fi
if grep -q "army-spark:codex-failed" "$WORK/world/tg.log" 2>/dev/null; then
    note_pass "no codex seat anywhere: P0 alert fired"
else
    note_fail "no codex seat anywhere: no P0 alert found in stub log"
fi

# ---------------------------------------------------------------------------
# Case 13 (guilt+innocence, defect 1 — 2026-08-15 live evidence): the queue
# README must never be dispatched as a task, while a real task file
# alongside it IS. Live symptom on Pro 17:09-17:10 WITA: run.log showed
# "dispatching task=README.md" (select_task()'s *.md glob matched it).
# setup_world's fake queue always has README.md next to task-one.md, so
# every case above already exercises this — this case asserts it directly.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rc="$(run_wrapper STUB_CODEX_MODE=success)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "1" ] \
    && grep -q "dispatching task=task-one.md" "$WORK/world/logs/run.log" 2>/dev/null; then
    note_pass "README exclusion innocence: the real task alongside README.md IS dispatched"
else
    note_fail "README exclusion innocence: rc=$rc report_count=$(report_count)"
fi
if ! grep -q "dispatching task=README.md" "$WORK/world/logs/run.log" 2>/dev/null; then
    note_pass "README exclusion guilt: README.md is never selected as a dispatch target"
else
    note_fail "README exclusion guilt: README.md was dispatched as a task"
fi

# ---------------------------------------------------------------------------
# Case 13b (guilt, defect 1): a queue containing ONLY README.md (no real
# task) reads as EMPTY, not as "one task named README.md" — no dispatch, no
# report, heartbeat=ok.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success
rm -f "$WORK/world/queue/task-one.md"
rc="$(run_wrapper STUB_CODEX_MODE=success)"
status="$(sidecar_status)"
if [ "$rc" = "0" ] && [ "$(report_count)" = "0" ] && [ "$status" = "ok" ] \
    && ! grep -q "dispatching task=README.md" "$WORK/world/logs/run.log" 2>/dev/null; then
    note_pass "README exclusion guilt (queue-only-README): treated as empty queue, never dispatched"
else
    note_fail "README exclusion guilt (queue-only-README): rc=$rc report_count=$(report_count) status=$status"
fi

# ---------------------------------------------------------------------------
# Case 14 (guilt+innocence, defect 2 — 2026-08-15 live evidence): a
# SUCCESSFUL codex run (rc=0) whose output text happens to mention
# quota/usage-limit/429 language must be classified as a normal successful
# report, NOT quota. This is the exact false-positive measured live: the
# dispatched README documents quota/backoff/429 behavior, so codex's
# legitimate analysis of it contained those substrings -> false
# status=quota, false 12h backoff, false P0-class alert; a manual codex
# probe on the same bucket 3 minutes later answered fine (bucket was never
# actually in quota). The pre-existing quota-on-FAILURE case (Case 5) must
# stay green — this case only closes the rc=0 false-positive gap.
# ---------------------------------------------------------------------------
setup_world
write_codex_stub success_quota_text
rc="$(run_wrapper STUB_CODEX_MODE=success_quota_text)"
status="$(sidecar_status)"
report_file="$(find "$WORK/world/reports" -maxdepth 1 -name '*.md' 2>/dev/null | head -1)"
if [ "$rc" = "0" ] && [ "$status" = "ok" ] && [ "$(report_count)" = "1" ] \
    && [ -n "$report_file" ] && grep -q "usage limit" "$report_file"; then
    note_pass "quota over-match fix: rc=0 output mentioning 'usage limit' classified as a normal report, not quota"
else
    note_fail "quota over-match fix: rc=$rc status=$status report_count=$(report_count)"
fi
if [ ! -f "$WORK/world/state/backoff-until.txt" ]; then
    note_pass "quota over-match fix innocence: no backoff file written on a successful run"
else
    note_fail "quota over-match fix innocence: a backoff file was written despite rc=0 success"
fi
if grep -q '"status":"ok"' "$WORK/world/state/attempts.jsonl" 2>/dev/null \
    && ! grep -q '"status":"quota"' "$WORK/world/state/attempts.jsonl" 2>/dev/null; then
    note_pass "quota over-match fix: attempt recorded as ok, not quota"
else
    note_fail "quota over-match fix: attempts.jsonl did not record ok-not-quota"
fi

echo
echo "TOTAL: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
