#!/bin/sh
# test_prepush_suite_lock.sh — regression test for scripts/prepush_suite_lock.sh,
# the machine-wide backend-suite serialization wrapper wired into
# .husky/pre-push (2026-07-27).
#
# Measured live on M5, 2026-07-27 09:31->09:57 WITA: load average 68, 12
# concurrent `python -m pytest backend/tests/` processes, ~124MB free memory,
# pushes SIGTERM-killed mid-suite. This wrapper makes the backend suite
# single-flight per machine. Its own header (scripts/prepush_suite_lock.sh)
# documents the primitive choice (mkdir, not flock/shlock/lockf — verified
# empirically absent/deprecated/silent-while-waiting respectively) and why
# stale-lock reclamation is the single most important correctness property:
# a lock must never outlive its holder, or a killed suite wedges the machine
# forever instead of just failing that one push.
#
# Cases mirror the brief's guilt/innocence/stale/timeout/kill-switch split and
# this repo's own test_prepush_failclosed.sh style (real kills and real dead
# PIDs over synthetic conditions wherever the property under test is about a
# REAL process's fate, not just arithmetic).
#
# 2026-07-29 added the exit-code and heartbeat honesty cases. Both pin the same
# property from opposite sides: a message must not name a quantity it did not
# measure. The timeout used to exit 1 (pytest's "tests failed") so saturation
# printed "❌ Python tests FAILED" for a suite that never started, and the
# heartbeat printed the WAITER's elapsed time as the HOLDER's hold. Each cure
# is mutation-verified — revert it and a named case goes red.
#
# Run:  sh scripts/tests/test_prepush_suite_lock.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/prepush_suite_lock.sh"

if [ ! -x "$SCRIPT" ]; then
    note_fail "setup — $SCRIPT not found or not executable, cannot run any case"
    echo "---"
    echo "$pass passed, $fail failed"
    exit 1
fi

WORKDIR="$(mktemp -d 2>/dev/null)"
if [ -z "$WORKDIR" ]; then
    note_fail "setup — mktemp -d failed, cannot run any case"
    echo "---"
    echo "$pass passed, $fail failed"
    exit 1
fi
cleanup_workdir() { rm -rf "$WORKDIR"; }
trap cleanup_workdir EXIT INT TERM

# ---------------------------------------------------------------------------
# Case 1 (innocence): a single acquirer with no contender must run
# essentially immediately — no added latency beyond process-spawn noise.
# ---------------------------------------------------------------------------
LOCK1="$WORKDIR/innocence.lock"
T0=$(date +%s)
OUT1="$("$SCRIPT" "$LOCK1" sh -c 'echo ran')"
RC1=$?
T1=$(date +%s)
ELAPSED1=$((T1 - T0))
if [ "$OUT1" = "ran" ] && [ "$RC1" -eq 0 ] && [ "$ELAPSED1" -le 3 ]; then
    note_pass "innocence — single acquirer ran immediately (${ELAPSED1}s, rc=$RC1, out='$OUT1')"
else
    note_fail "innocence — expected immediate run + rc=0 + out=ran, got elapsed=${ELAPSED1}s rc=$RC1 out='$OUT1'"
fi
if [ -e "$LOCK1" ]; then
    note_fail "innocence — lock directory not cleaned up after a normal exit ($LOCK1 still exists)"
else
    note_pass "innocence — lock directory cleaned up after a normal exit"
fi

# ---------------------------------------------------------------------------
# Case 2 (guilt): two concurrent acquirers on the SAME lockfile — the second
# must wait for the first to release, never run in parallel. Proved
# observably via timestamps written to a shared marker file by each holder
# itself (not by reading the wrapper's code): holder A records its start
# time then holds the lock for 3s; holder B (launched 0.5s later, well
# inside A's hold) records its own start time the moment IT acquires. If
# serialization holds, B's start must land at least ~2s after A's (allowing
# margin below A's full 3s hold for scheduling/poll-interval noise) — b
# starting anywhere near A's own start would mean they ran concurrently.
# ---------------------------------------------------------------------------
LOCK2="$WORKDIR/guilt.lock"
MARKER2="$WORKDIR/guilt.marker"
: > "$MARKER2"

"$SCRIPT" "$LOCK2" sh -c "echo \"A \$(date +%s)\" >> \"$MARKER2\"; sleep 3" &
PID_A=$!
sleep 0.5
"$SCRIPT" "$LOCK2" sh -c "echo \"B \$(date +%s)\" >> \"$MARKER2\"" &
PID_B=$!
wait "$PID_A"
wait "$PID_B"

A_TS="$(grep '^A ' "$MARKER2" | awk '{print $2}')"
B_TS="$(grep '^B ' "$MARKER2" | awk '{print $2}')"
if [ -n "$A_TS" ] && [ -n "$B_TS" ]; then
    DIFF=$((B_TS - A_TS))
else
    DIFF=-1
fi
if [ "$DIFF" -ge 2 ]; then
    note_pass "guilt — second acquirer waited for the first (B started ${DIFF}s after A, holder A slept 3s)"
else
    note_fail "guilt — expected B to start >=2s after A (serialized), got diff=${DIFF}s (marker: $(cat "$MARKER2" 2>/dev/null))"
fi

# ---------------------------------------------------------------------------
# Case 3 (stale): a lock whose recorded PID is dead must be reclaimed, not
# waited out. Uses a REAL PID that is GUARANTEED dead — a child process
# started and explicitly waited-for to completion (same discipline as
# test_prepush_failclosed.sh Case 8: a real process's fate, not a magic
# number that merely looks plausible) — pre-seeded as the lock's holder
# before the wrapper is ever invoked.
# ---------------------------------------------------------------------------
LOCK3="$WORKDIR/stale.lock"
sh -c 'exit 0' &
DEAD_PID=$!
wait "$DEAD_PID" 2>/dev/null
mkdir -p "$LOCK3"
echo "$DEAD_PID" > "$LOCK3/pid"

T0=$(date +%s)
OUT3="$("$SCRIPT" "$LOCK3" sh -c 'echo reclaimed' 2>&1)"
RC3=$?
T1=$(date +%s)
ELAPSED3=$((T1 - T0))

if printf '%s' "$OUT3" | grep -q 'reclaimed' \
   && printf '%s' "$OUT3" | grep -qi 'stale' \
   && [ "$RC3" -eq 0 ] \
   && [ "$ELAPSED3" -le 5 ]; then
    note_pass "stale — dead-PID lock ($DEAD_PID) reclaimed and command ran (${ELAPSED3}s, rc=$RC3)"
else
    note_fail "stale — expected fast reclaim + 'reclaimed' output + a stale-lock message, got elapsed=${ELAPSED3}s rc=$RC3 out='$OUT3'"
fi

# ---------------------------------------------------------------------------
# Case 4 (timeout): a lock held by a LIVE PID, with the wait capped to ~1s
# (NUZ_PREPUSH_SUITE_LOCK_TIMEOUT), must produce a NON-ZERO exit and an
# actionable message naming the fleet-machine alternative — never silently
# skip the suite and run anyway (that would disarm the guard, cicatrix
# family #2). The holder PID is a real long-running `sleep` so `kill -0`
# genuinely reports it alive throughout the test.
# ---------------------------------------------------------------------------
LOCK4="$WORKDIR/timeout.lock"
sleep 30 &
LIVE_PID=$!
mkdir -p "$LOCK4"
echo "$LIVE_PID" > "$LOCK4/pid"

OUT4="$(NUZ_PREPUSH_SUITE_LOCK_TIMEOUT=1 NUZ_PREPUSH_SUITE_LOCK_POLL=0.3 "$SCRIPT" "$LOCK4" sh -c 'echo SHOULD_NOT_RUN' 2>&1)"
RC4=$?
kill "$LIVE_PID" 2>/dev/null

# rc is asserted as exactly 75 (EX_TEMPFAIL), not merely non-zero: the whole
# point of 2026-07-29's change is that "never acquired the lock" stopped
# sharing a value with pytest's "tests failed" (1). `-ne 0` would pass again
# the day someone reverts it to 1.
#
# The guidance is asserted by INTENT, not by the old literal 'pro/mini'. That
# advice is now qualified — landing from another machine is only safe into a
# worktree the broker made, since a bare `git worktree add` has no .husky/_
# and pushes with no gate at all — so pinning the bare string would have
# locked in the version of the sentence that was dangerous.
if [ "$RC4" -eq 75 ] \
   && ! printf '%s' "$OUT4" | grep -q 'SHOULD_NOT_RUN' \
   && printf '%s' "$OUT4" | grep -q -- '--no-verify' \
   && printf '%s' "$OUT4" | grep -q 'NEVER RAN' \
   && printf '%s' "$OUT4" | grep -q 'agent_start.py'; then
    note_pass "timeout — held lock + capped wait exited 75 with never-ran + broker-qualified guidance, wrapped command never ran"
else
    note_fail "timeout — expected rc=75 + 'NEVER RAN' + agent_start.py guidance + command never running, got rc=$RC4 out='$OUT4'"
fi

# ---------------------------------------------------------------------------
# Case 5 (kill switch): NUZ_PREPUSH_SUITE_LOCK=0 must bypass locking
# entirely — proved by pre-seeding a lock that is BOTH held (a live PID)
# AND would time out almost instantly if the wrapper touched it at all, then
# confirming the command still runs immediately and the pre-seeded lock is
# left completely untouched (still exists, PID file unchanged) — evidence
# the wrapper never even looked at it.
# ---------------------------------------------------------------------------
LOCK5="$WORKDIR/killswitch.lock"
sleep 30 &
LIVE_PID5=$!
mkdir -p "$LOCK5"
echo "$LIVE_PID5" > "$LOCK5/pid"
BEFORE_PID_CONTENT="$(cat "$LOCK5/pid")"

T0=$(date +%s)
OUT5="$(NUZ_PREPUSH_SUITE_LOCK=0 NUZ_PREPUSH_SUITE_LOCK_TIMEOUT=1 "$SCRIPT" "$LOCK5" sh -c 'echo bypassed')"
RC5=$?
T1=$(date +%s)
ELAPSED5=$((T1 - T0))
AFTER_PID_CONTENT="$(cat "$LOCK5/pid" 2>/dev/null)"
kill "$LIVE_PID5" 2>/dev/null

if printf '%s' "$OUT5" | grep -q '^bypassed$' && [ "$RC5" -eq 0 ] && [ "$ELAPSED5" -le 3 ] \
   && [ "$AFTER_PID_CONTENT" = "$BEFORE_PID_CONTENT" ]; then
    note_pass "kill switch — NUZ_PREPUSH_SUITE_LOCK=0 ran immediately (${ELAPSED5}s) despite a held+would-timeout lock, and left it untouched"
else
    note_fail "kill switch — expected immediate bypass + untouched lock, got elapsed=${ELAPSED5}s rc=$RC5 out='$OUT5' before='$BEFORE_PID_CONTENT' after='$AFTER_PID_CONTENT'"
fi
rm -rf "$LOCK5"

# ---------------------------------------------------------------------------
# Case 6 (tripwire): the LIVE hook must actually call the wrapper around the
# pytest invocation — a correct standalone script that nobody wires in
# protects nothing (cicatrix family #2, "esiste != armato").
# ---------------------------------------------------------------------------
HOOK_FILE="$REPO_ROOT/.husky/pre-push"
if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire — $HOOK_FILE not found (cannot verify it's wired in)"
else
    if grep -q 'PREPUSH_SUITE_LOCK_SCRIPT' "$HOOK_FILE" \
       && grep -q 'PREPUSH_SUITE_LOCKFILE' "$HOOK_FILE" \
       && grep -q '"\$PREPUSH_SUITE_LOCK_SCRIPT" "\$PREPUSH_SUITE_LOCKFILE"' "$HOOK_FILE" \
       && grep -q 'python -m pytest backend/tests/' "$HOOK_FILE"; then
        note_pass "tripwire — .husky/pre-push wires the lock wrapper around the pytest invocation"
    else
        note_fail "tripwire — .husky/pre-push does not reference the lock wrapper as expected"
    fi
fi

# ---------------------------------------------------------------------------
# Case 8 (innocence): the 75 must mean ONLY "never acquired the lock". Every
# code pytest can actually return has to survive the wrapper untouched —
# otherwise fixing the false FAILED just invents the mirror-image lie.
# ---------------------------------------------------------------------------
INNOCENT_OK=1
for code in 0 1 2 3 4 5; do
    LOCK8="$WORKDIR/passthru-$code.lock"
    "$SCRIPT" "$LOCK8" sh -c "exit $code" >/dev/null 2>&1 && GOT=0 || GOT=$?
    if [ "$GOT" -ne "$code" ]; then
        note_fail "innocence — wrapped command exiting $code was reported as $GOT"
        INNOCENT_OK=0
    fi
    rm -rf "$LOCK8"
done
if [ "$INNOCENT_OK" -eq 1 ]; then
    note_pass "innocence — pytest's whole exit range (0-5) passes through unchanged; 1 is still 'tests failed'"
fi

# ---------------------------------------------------------------------------
# Case 9 (innocence): signal death must still surface as 128+N, so the
# caller's existing `-ge 128` NO-VERDICT branch keeps working alongside 75.
# ---------------------------------------------------------------------------
LOCK9="$WORKDIR/signal.lock"
"$SCRIPT" "$LOCK9" sh -c 'kill -TERM $$' >/dev/null 2>&1 && RC9=0 || RC9=$?
if [ "$RC9" -ge 128 ]; then
    note_pass "innocence — signal death still propagates as 128+N (rc=$RC9), not flattened into 75"
else
    note_fail "innocence — expected 128+N from a signal-killed command, got rc=$RC9"
fi
rm -rf "$LOCK9"

# ---------------------------------------------------------------------------
# Case 10 (guilt): the heartbeat must not report the waiter's own wait as the
# holder's. Measured 2026-07-29: two waiters on ONE holder printed "for 38m"
# and "for 1m" while ps put the holder at 20m — and "that lock is stale, kill
# it" is the action a 38m reading invites, onto a live sibling's suite.
# ---------------------------------------------------------------------------
LOCK10="$WORKDIR/heartbeat.lock"
( "$SCRIPT" "$LOCK10" sh -c 'sleep 6' >/dev/null 2>&1 ) &
HOLDER_JOB=$!
sleep 2
OUT10="$(NUZ_PREPUSH_SUITE_LOCK_TIMEOUT=3 NUZ_PREPUSH_SUITE_LOCK_POLL=1 \
         NUZ_PREPUSH_SUITE_LOCK_HEARTBEAT=1 \
         "$SCRIPT" "$LOCK10" sh -c 'echo late' 2>&1)" || true
wait "$HOLDER_JOB" 2>/dev/null || true
if echo "$OUT10" | grep -q "waited"; then
    note_pass "guilt — heartbeat labels the number as the WAITER's wait"
else
    note_fail "guilt — heartbeat does not say 'waited'; the old wording blamed the holder: '$OUT10'"
fi
if echo "$OUT10" | grep -qE "held by PID [0-9]+ for"; then
    note_fail "guilt — heartbeat still claims the holder HELD it for the waiter's elapsed time"
else
    note_pass "guilt — heartbeat no longer attributes the waiter's elapsed time to the holder"
fi
rm -rf "$LOCK10"

# ---------------------------------------------------------------------------
# Case 11 (tripwire): the caller must classify 75 separately. A distinct exit
# code that nobody branches on is a rename, not a fix (family #2).
# ---------------------------------------------------------------------------
if [ ! -f "$HOOK_FILE" ]; then
    note_fail "tripwire — $HOOK_FILE not found (cannot verify the 75 branch)"
elif grep -q 'TEST_RC" -eq 75' "$HOOK_FILE" && grep -q 'NEVER RAN' "$HOOK_FILE"; then
    note_pass "tripwire — .husky/pre-push branches on 75 and reports NO VERDICT"
else
    note_fail "tripwire — .husky/pre-push does not classify rc=75; saturation still reads as 'tests FAILED'"
fi


# ===========================================================================
# FIFO fairness layer (2026-08-11). Measured trigger: one waiter sat 75
# minutes, timed out with the suite never starting, and a wrapper born 35
# MINUTES LATER took the lock ahead of it — twice on the same branch. mkdir is
# atomic but says nothing about order.
#
# The cases below split the same way as the rest of this file: the fairness
# property itself (guilt), then every fail-open path, because the failure this
# layer could introduce — a stuck queue stalling every push on the machine —
# is worse than the one it fixes.
# ===========================================================================

# ---------------------------------------------------------------------------
# Case F1 (guilt, THE fairness property): the lock is FREE, but an older LIVE
# ticket is queued. A younger wrapper must YIELD — under the pre-FIFO code it
# would take the free lock instantly, which is exactly the lapping that cost a
# real push 75 minutes.
#
# The older ticket's owner is a REAL live process (a `sleep` we spawn and
# later kill), not a plausible-looking number: `kill -0` is what the layer
# actually asks, so the test must give it a real answer.
# ---------------------------------------------------------------------------
LOCKF1="$WORKDIR/fifo-yield.lock"
QF1="$LOCKF1.q"
mkdir -p "$QF1"
sleep 30 &
OLD_OWNER=$!
OLD_TS=$(( $(date +%s) - 60 ))
: > "$QF1/$OLD_TS.$OLD_OWNER"

"$SCRIPT" "$LOCKF1" sh -c 'echo jumped' > "$WORKDIR/f1.out" 2>&1 &
YOUNGER=$!
sleep 4
if kill -0 "$YOUNGER" 2>/dev/null && ! grep -q jumped "$WORKDIR/f1.out" 2>/dev/null; then
    note_pass "fifo guilt — younger waiter yielded to an older live ticket even with the lock FREE"
else
    note_fail "fifo guilt — younger waiter took a free lock ahead of an older live ticket (out: $(cat "$WORKDIR/f1.out" 2>/dev/null))"
fi

# ...and once the older ticket's owner dies, the younger one must proceed —
# the yield is a queue position, not a wedge.
kill "$OLD_OWNER" 2>/dev/null
wait "$OLD_OWNER" 2>/dev/null
sleep 5
if grep -q jumped "$WORKDIR/f1.out" 2>/dev/null; then
    note_pass "fifo guilt — younger waiter proceeded once the older ticket's owner died"
else
    note_fail "fifo guilt — younger waiter still blocked after the older ticket's owner died (WEDGE)"
fi
wait "$YOUNGER" 2>/dev/null

# ---------------------------------------------------------------------------
# Case F2 (innocence): with the layer ON and no contender, a single acquirer
# must still run immediately. A fairness layer that adds latency to the
# uncontended path would be paid on every push on every machine.
# ---------------------------------------------------------------------------
LOCKF2="$WORKDIR/fifo-solo.lock"
T0=$(date +%s)
OUTF2="$("$SCRIPT" "$LOCKF2" sh -c 'echo solo')"
RCF2=$?
ELAPSEDF2=$(( $(date +%s) - T0 ))
if [ "$OUTF2" = "solo" ] && [ "$RCF2" -eq 0 ] && [ "$ELAPSEDF2" -le 3 ]; then
    note_pass "fifo innocence — uncontended acquirer still immediate (${ELAPSEDF2}s)"
else
    note_fail "fifo innocence — uncontended acquirer delayed/broken (${ELAPSEDF2}s, rc=$RCF2, out='$OUTF2')"
fi
if [ -d "$LOCKF2.q" ] && [ -n "$(ls -A "$LOCKF2.q" 2>/dev/null)" ]; then
    note_fail "fifo innocence — ticket left behind after a normal exit: $(ls -A "$LOCKF2.q")"
else
    note_pass "fifo innocence — no ticket left behind after a normal exit"
fi

# ---------------------------------------------------------------------------
# Case F3 (fail-open, dead owner): a ticket whose owner is dead must be reaped,
# not obeyed. Same guaranteed-dead-PID discipline as Case 3.
# ---------------------------------------------------------------------------
LOCKF3="$WORKDIR/fifo-deadticket.lock"
QF3="$LOCKF3.q"
mkdir -p "$QF3"
sh -c 'exit 0' &
DEAD_T=$!
wait "$DEAD_T" 2>/dev/null
: > "$QF3/$(( $(date +%s) - 60 )).$DEAD_T"
T0=$(date +%s)
OUTF3="$("$SCRIPT" "$LOCKF3" sh -c 'echo past-dead' 2>&1)"
ELAPSEDF3=$(( $(date +%s) - T0 ))
if printf '%s' "$OUTF3" | grep -q 'past-dead' && [ "$ELAPSEDF3" -le 5 ]; then
    note_pass "fifo fail-open — dead-owner ticket reaped, waiter proceeded (${ELAPSEDF3}s)"
else
    note_fail "fifo fail-open — dead-owner ticket blocked the waiter (${ELAPSEDF3}s, out='$OUTF3')"
fi

# ---------------------------------------------------------------------------
# Case F4 (fail-open, expired): a ticket older than the whole timeout cannot
# legitimately still be waiting — it is residue. It must not block even though
# its owner IS alive.
# ---------------------------------------------------------------------------
LOCKF4="$WORKDIR/fifo-expired.lock"
QF4="$LOCKF4.q"
mkdir -p "$QF4"
sleep 30 &
LIVE_OLD=$!
: > "$QF4/$(( $(date +%s) - 99999 )).$LIVE_OLD"
T0=$(date +%s)
OUTF4="$("$SCRIPT" "$LOCKF4" sh -c 'echo past-expired' 2>&1)"
ELAPSEDF4=$(( $(date +%s) - T0 ))
kill "$LIVE_OLD" 2>/dev/null
wait "$LIVE_OLD" 2>/dev/null
if printf '%s' "$OUTF4" | grep -q 'past-expired' && [ "$ELAPSEDF4" -le 5 ]; then
    note_pass "fifo fail-open — expired ticket (live owner) reaped, waiter proceeded (${ELAPSEDF4}s)"
else
    note_fail "fifo fail-open — expired ticket blocked the waiter (${ELAPSEDF4}s, out='$OUTF4')"
fi

# ---------------------------------------------------------------------------
# Case F5 (fail-open, malformed): a ticket name that does not parse must be
# reaped, never interpreted. Arithmetic on a non-numeric field would abort the
# wrapper under some shells — a queue that can be poisoned by one bad filename
# is worse than no queue.
# ---------------------------------------------------------------------------
LOCKF5="$WORKDIR/fifo-malformed.lock"
QF5="$LOCKF5.q"
mkdir -p "$QF5"
: > "$QF5/not-a-ticket"
: > "$QF5/abc.def"
T0=$(date +%s)
OUTF5="$("$SCRIPT" "$LOCKF5" sh -c 'echo past-malformed' 2>&1)"
ELAPSEDF5=$(( $(date +%s) - T0 ))
if printf '%s' "$OUTF5" | grep -q 'past-malformed' && [ "$ELAPSEDF5" -le 5 ]; then
    note_pass "fifo fail-open — malformed tickets reaped, waiter proceeded (${ELAPSEDF5}s)"
else
    note_fail "fifo fail-open — malformed ticket blocked the waiter (${ELAPSEDF5}s, out='$OUTF5')"
fi

# ---------------------------------------------------------------------------
# Case F6 (kill switch): NUZ_PREPUSH_SUITE_FIFO=0 turns the fairness layer off
# WITHOUT turning the lock off — losing fairness must never require losing
# serialization. With the layer off, the older live ticket of F1 is ignored.
# ---------------------------------------------------------------------------
LOCKF6="$WORKDIR/fifo-killswitch.lock"
QF6="$LOCKF6.q"
mkdir -p "$QF6"
sleep 30 &
BLOCKER=$!
: > "$QF6/$(( $(date +%s) - 60 )).$BLOCKER"
T0=$(date +%s)
OUTF6="$(NUZ_PREPUSH_SUITE_FIFO=0 "$SCRIPT" "$LOCKF6" sh -c 'echo fifo-off' 2>&1)"
ELAPSEDF6=$(( $(date +%s) - T0 ))
kill "$BLOCKER" 2>/dev/null
wait "$BLOCKER" 2>/dev/null
if printf '%s' "$OUTF6" | grep -q 'fifo-off' && [ "$ELAPSEDF6" -le 5 ]; then
    note_pass "fifo kill switch — NUZ_PREPUSH_SUITE_FIFO=0 ignores the queue (${ELAPSEDF6}s)"
else
    note_fail "fifo kill switch — layer still active with NUZ_PREPUSH_SUITE_FIFO=0 (${ELAPSEDF6}s, out='$OUTF6')"
fi

# ---------------------------------------------------------------------------
# Case F7 (SAFETY — the bug this layer could have introduced): the trap now
# runs in WAITERS too, because a ticket must never outlive its waiter. A
# waiter that gives up must therefore NOT delete the live HOLDER's lock. Drop
# the `I_HOLD_LOCK` guard from cleanup() and this case goes red while every
# other case stays green.
#
# Driven through a real timeout (1s) against a real live holder.
# ---------------------------------------------------------------------------
LOCKF7="$WORKDIR/fifo-holdersafety.lock"
mkdir -p "$LOCKF7"
sleep 30 &
HOLDER7=$!
echo "$HOLDER7" > "$LOCKF7/pid"
NUZ_PREPUSH_SUITE_LOCK_TIMEOUT=1 NUZ_PREPUSH_SUITE_LOCK_POLL=1 \
    "$SCRIPT" "$LOCKF7" sh -c 'echo should-not-run' > "$WORKDIR/f7.out" 2>&1
RCF7=$?
if [ "$RCF7" -eq 75 ] && [ -d "$LOCKF7" ] && [ "$(cat "$LOCKF7/pid" 2>/dev/null)" = "$HOLDER7" ]; then
    note_pass "fifo safety — a timing-out WAITER left the live holder's lock intact (rc=$RCF7)"
else
    note_fail "fifo safety — waiter destroyed or altered the holder's lock (rc=$RCF7, lock exists: $([ -d "$LOCKF7" ] && echo yes || echo NO), pid file: '$(cat "$LOCKF7/pid" 2>/dev/null)')"
fi
if [ -d "$LOCKF7.q" ] && [ -n "$(ls -A "$LOCKF7.q" 2>/dev/null)" ]; then
    note_fail "fifo safety — timing-out waiter left its ticket behind: $(ls -A "$LOCKF7.q")"
else
    note_pass "fifo safety — timing-out waiter removed its own ticket"
fi
kill "$HOLDER7" 2>/dev/null
wait "$HOLDER7" 2>/dev/null

echo "---"
echo "$pass passed, $fail failed"

if [ "$fail" -eq 0 ]; then
    exit 0
else
    exit 1
fi
