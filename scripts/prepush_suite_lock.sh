#!/bin/sh
# prepush_suite_lock.sh — serialize a heavy command to at most ONE runner per
# machine, fail-closed with an actionable message on timeout.
#
# WHY THIS EXISTS (measured live on M5, 2026-07-27 09:31->09:57 WITA): load
# average 68, 12 concurrent `python -m pytest backend/tests/` processes from
# 12 different agent worktrees' pre-push hooks, ~124MB free memory. Nine
# near-identical ~17k-test suites contending for the same CPU/memory made
# each run ~3x slower (40-60min instead of ~12), and pushes were being
# SIGTERM-killed mid-suite as a result — silent work loss (a killed push
# leaves committed work that never becomes a PR, invisible to `gh pr list`).
# This wrapper makes the backend suite single-flight per machine: a second
# concurrent pusher waits for the first to finish rather than racing it for
# the same CPU.
#
# PRIMITIVE CHOICE (verified empirically on Air-M5, Darwin 27.0.0, 2026-07-27):
#   - `flock(1)` is ABSENT on stock macOS (`command -v flock` exits 1 — it's a
#     Linux util-linux tool, never shipped in the BSD userland macOS uses).
#   - `shlock(1)` IS present (/usr/bin/shlock) but its own man page flags it
#     DEPRECATED in favor of lockf(1), and it exits immediately on a held
#     lock (verify-then-report) with no poll point of our own to hook a
#     heartbeat into.
#   - `lockf(1)` IS present and would work, but `lockf -t N` blocks SILENTLY
#     for up to N seconds — no visibility while waiting. This hook's own
#     pre-push comment block already documents silence-during-a-long-wait as
#     indistinguishable from a hang, and a hang is exactly what gets a push
#     killed (the failure this wrapper exists to stop).
#   - `mkdir` is POSIX-guaranteed atomic (EEXIST on collision, no TOCTOU
#     window) and, because WE own the poll loop, gives a heartbeat for free.
#     Chosen primitive: `mkdir` for the lock itself + a PID file inside it
#     for stale-holder detection via `kill -0` (POSIX, universally available,
#     the same mechanism shlock uses internally).
#
# STALE-LOCK SAFETY (the single most important correctness property here):
# the PID recorded in the lock is THIS wrapper process's own PID, and this
# process stays alive for the full duration of the wrapped command (it backgrounds
# the command and `wait`s on it — never a detached/forked "acquire and exit").
# If the holder dies for ANY reason (including the exact SIGTERM this fleet
# is seeing today), `kill -0 <holder_pid>` starts failing immediately, and
# the NEXT waiter reclaims the lock on its very next poll — a killed suite
# does not wedge the machine. Known residual risk: PID reuse after a reboot
# could in theory make a dead holder look alive to `kill -0`; the bounded
# wait + fail-closed timeout below is the backstop for that case (and for
# the ordinary case of more than one predecessor queued) — either way this
# wrapper degrades to a bounded wait with a message, never an infinite wedge.
#
# Usage:  prepush_suite_lock.sh <lockfile> <command> [args...]
#
# Env:
#   NUZ_PREPUSH_SUITE_LOCK=0             kill switch — bypass locking
#                                         entirely, run <command> directly
#                                         (documented escape hatch).
#   NUZ_PREPUSH_SUITE_FIFO=0             disable ONLY the fairness layer
#                                         (2026-08-11): waiters go back to
#                                         racing for the lock on every poll,
#                                         which is correct but starvable. The
#                                         lock itself stays on. Separate from
#                                         the switch above on purpose — losing
#                                         fairness must never require losing
#                                         serialization.
#   NUZ_PREPUSH_SUITE_LOCK_TIMEOUT=<s>   max wait in seconds before failing
#                                         closed (default 4500 = 75min).
#                                         Test-only override in practice.
#   NUZ_PREPUSH_SUITE_LOCK_POLL=<s>      poll interval in seconds (default 2).
#                                         Test-only override.
#   NUZ_PREPUSH_SUITE_LOCK_HEARTBEAT=<s> seconds between "still waiting"
#                                         heartbeats (default 30). Test-only
#                                         override — the corpus needs a
#                                         heartbeat inside a 3s window.
#
# Exit code: on success, propagates <command>'s own exit code UNCHANGED
# (including a 128+N signal-death code, so an outer `TEST_RC -ge 128`
# classification still works). On a timed-out lock acquisition, exits
# LOCK_TIMEOUT_RC (75) itself with an actionable message — the wrapped command
# never even starts; this NEVER silently skips the lock and runs anyway
# (cicatrix-superscar.md family #2, "esiste != armato" — a guard that can
# silently disarm itself is not a guard).
#
# Why 75 and not 1 (2026-07-29, measured): it used to exit 1, which is also
# pytest's "tests failed". The caller could not tell the two apart, so a
# saturation timeout — with the suite NEVER STARTED — printed
# "❌ Python tests FAILED — push blocked" plus a pytest reproduce command.
# Observed live twice the same evening on a 9-waiter M5. Anyone reading that
# line had grounds to hunt a regression that does not exist, and the reproduce
# command then passes, which reads as flakiness. Exactly the defect #45 fixed
# for signal-death (128+N) one class over: the exit code is the reply, and
# collapsing two replies into one value throws away the bit that tells the
# truth. 75 is EX_TEMPFAIL from sysexits.h — "temporary failure, the user is
# invited to retry" — which is precisely this condition.
#
# LIMITATION, stated rather than hidden: this steals one value out of the
# wrapped command's own exit space. A <command> that itself exits 75 will be
# misread by a caller as a lock timeout. Safe for the only caller in the tree
# (.husky/pre-push wraps pytest, whose codes are 0-5 and are pinned as
# pass-through by scripts/tests/test_prepush_suite_lock.sh); re-check this
# line before wrapping anything else.

set -u

LOCKFILE="${1:?prepush_suite_lock.sh: missing <lockfile> argument}"
shift

if [ "$#" -eq 0 ]; then
    echo "prepush_suite_lock.sh: missing <command> argument" >&2
    exit 2
fi

if [ "${NUZ_PREPUSH_SUITE_LOCK:-1}" = "0" ]; then
    echo "🔓 NUZ_PREPUSH_SUITE_LOCK=0 — backend-suite lock disabled, running directly."
    "$@"
    exit $?
fi

TIMEOUT="${NUZ_PREPUSH_SUITE_LOCK_TIMEOUT:-4500}"
POLL_INTERVAL="${NUZ_PREPUSH_SUITE_LOCK_POLL:-2}"
HEARTBEAT_EVERY="${NUZ_PREPUSH_SUITE_LOCK_HEARTBEAT:-30}"
# EX_TEMPFAIL. Distinct from anything pytest returns (0-5) so the caller can
# tell "never acquired the lock" from "the suite ran and failed". See the
# Exit code block in the header.
LOCK_TIMEOUT_RC=75

START_TS=$(date +%s)
LAST_HEARTBEAT=$START_TS

# ---------------------------------------------------------------------------
# FIFO fairness layer (2026-08-11). MEASURED motivation, one push:
# a waiter sat 75 minutes and timed out with the suite never starting, while
# a wrapper born 35 MINUTES LATER took the lock ahead of it — twice in a row,
# same branch. `mkdir` is atomic but says nothing about ORDER: every poll is
# an independent race, so a long waiter has no advantage over an arrival that
# happens to knock at the instant of release. The bounded wait then fires on
# the politest process while the machine is perfectly healthy.
#
# Each wrapper drops a ticket named `<epoch>.<pid>` and only races for the
# lock once no OLDER live ticket remains. That is approximate FIFO — arrival
# order at one-second granularity, ties broken by pid — which is all the
# property needs; it does not have to be a total order, it has to stop a
# newcomer from lapping a 75-minute waiter.
#
# EVERY uncertainty fails OPEN to the pre-FIFO behaviour, because the failure
# this layer could introduce (a stuck queue stalling every push on the
# machine) is far worse than the one it fixes (one push waiting too long):
#   - queue dir not creatable / ticket not writable -> no ticket -> plain race
#   - ticket owner dead (`kill -0`)                 -> reaped, does not block
#   - ticket older than the whole TIMEOUT           -> reaped: it cannot
#     legitimately still be waiting, so it is residue, not a queue position
#   - malformed ticket name                         -> reaped, never parsed
#   - NUZ_PREPUSH_SUITE_FIFO=0                      -> layer off entirely
# The lock itself is unchanged: acquisition is still the same atomic `mkdir`,
# and the stale-holder reclamation below still runs on every poll.
# ---------------------------------------------------------------------------
QUEUE_DIR="${LOCKFILE}.q"
MY_TICKET=""
if [ "${NUZ_PREPUSH_SUITE_FIFO:-1}" != "0" ] && mkdir -p "$QUEUE_DIR" 2>/dev/null; then
    MY_TICKET="$QUEUE_DIR/$START_TS.$$"
    : > "$MY_TICKET" 2>/dev/null || MY_TICKET=""
fi

# Is any OTHER live, unexpired ticket older than mine? Reaps what it rejects,
# so a dead/expired/malformed ticket is removed by the first waiter to see it
# rather than accumulating.
older_ticket_waiting() {
    [ -n "$MY_TICKET" ] || return 1   # no ticket -> never yield (pre-FIFO path)
    _mine="${MY_TICKET##*/}"
    _mine_ts="${_mine%.*}"
    _mine_pid="${_mine##*.}"
    _now=$(date +%s)
    for _t in "$QUEUE_DIR"/*; do
        [ -e "$_t" ] || continue      # unmatched glob
        _n="${_t##*/}"
        [ "$_n" = "$_mine" ] && continue
        _ts="${_n%.*}"
        _pid="${_n##*.}"
        case "$_ts$_pid" in
            ''|*[!0-9]*) rm -f "$_t" 2>/dev/null; continue ;;
        esac
        if [ $((_now - _ts)) -gt "$TIMEOUT" ]; then
            rm -f "$_t" 2>/dev/null
            continue
        fi
        if ! kill -0 "$_pid" 2>/dev/null; then
            rm -f "$_t" 2>/dev/null
            continue
        fi
        if [ "$_ts" -lt "$_mine_ts" ]; then
            return 0
        fi
        if [ "$_ts" -eq "$_mine_ts" ] && [ "$_pid" -lt "$_mine_pid" ]; then
            return 0
        fi
    done
    return 1
}

# The trap is installed BEFORE the wait loop so a ticket never outlives its
# waiter (an orphan ticket is exactly the stall this layer must not cause).
# `I_HOLD_LOCK` is what makes that safe: without it, a WAITER killed or timed
# out mid-queue would run `rm -rf "$LOCKFILE"` and delete the LIVE HOLDER's
# lock — the pre-FIFO code could install the trap late precisely because it
# only ever ran as the holder. Pinned by the "waiter timing out does not
# delete the holder's lock" case in the corpus.
I_HOLD_LOCK=0
CHILD_PID=""
cleanup() {
    if [ -n "$CHILD_PID" ]; then
        # A signal that targets only THIS wrapper's PID (not the whole
        # foreground process group) must not leave the wrapped suite running
        # as an orphan after the lock is already released underneath it.
        kill -TERM "$CHILD_PID" 2>/dev/null
    fi
    if [ "$I_HOLD_LOCK" = "1" ]; then
        rm -rf "$LOCKFILE" 2>/dev/null
    fi
    if [ -n "$MY_TICKET" ]; then
        rm -f "$MY_TICKET" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

while :; do
    if ! older_ticket_waiting && mkdir "$LOCKFILE" 2>/dev/null; then
        chmod 700 "$LOCKFILE" 2>/dev/null
        echo $$ > "$LOCKFILE/pid" 2>/dev/null
        I_HOLD_LOCK=1
        break
    fi

    HOLDER_PID="$(cat "$LOCKFILE/pid" 2>/dev/null || true)"
    if [ -n "$HOLDER_PID" ] && ! kill -0 "$HOLDER_PID" 2>/dev/null; then
        # Holder is dead (SIGTERM'd suite, crashed shell, etc.) — reclaim
        # immediately rather than waiting out the clock behind a corpse.
        echo "♻️  backend-suite lock: holder PID $HOLDER_PID is dead — reclaiming stale lock."
        rm -rf "$LOCKFILE" 2>/dev/null
        continue
    fi

    NOW=$(date +%s)
    ELAPSED=$((NOW - START_TS))

    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        TIMEOUT_MIN=$((TIMEOUT / 60))
        echo "❌ machine saturated — suite lock not acquired in ${TIMEOUT_MIN}m. The suite NEVER RAN: this is not a verdict on your diff." >&2
        echo "   Do NOT use --no-verify, and do NOT set NUZ_PREPUSH_SUITE_LOCK=0 — the wait is the queue working, not a fault." >&2
        echo "   Retry later, or land from an idle fleet machine — but ONLY into a worktree made by scripts/agent_start.py." >&2
        echo "   A worktree from a bare 'git worktree add' has no .husky/_ (it is gitignored and install-generated)," >&2
        echo "   so its push runs NO pre-push hook at all: 2 seconds, exit 0, no output. Landing there is the --no-verify" >&2
        echo "   this message just forbade, with extra steps. Measured 2026-07-29; see agent_start.py's SYMLINK_TARGETS." >&2
        exit "$LOCK_TIMEOUT_RC"
    fi

    if [ $((NOW - LAST_HEARTBEAT)) -ge "$HEARTBEAT_EVERY" ]; then
        # Two DIFFERENT quantities, so say which is which. The old line read
        # "held by PID X for Nm" while N was ELAPSED — the WAITER's own wait.
        # Measured 2026-07-29: one waiter said "held ... for 38m" and another,
        # same holder same minute, said "for 1m", while `ps` put the holder at
        # 20m. A healthy sibling suite reads as hung, and "that lock is stale,
        # kill it" is the action that reading invites — onto live work.
        WAITED_MIN=$((ELAPSED / 60))
        HOLDER_AGE="$(ps -o etime= -p "${HOLDER_PID:-0}" 2>/dev/null | tr -d ' ')"
        echo "⏳ waited ${WAITED_MIN}m for this machine's backend-suite lock (holder PID ${HOLDER_PID:-unknown}, alive ${HOLDER_AGE:-unknown})"
        LAST_HEARTBEAT=$NOW
    fi

    sleep "$POLL_INTERVAL"
done

# The lock is held from here. `cleanup`/`trap` are installed above, before the
# wait loop (see the FIFO block): CHILD_PID still starts unset, so a wrapper
# killed between acquiring the lock and backgrounding the command below drops
# the lock and its ticket without signalling a child that never started.
# The ticket is dropped now rather than at exit: this wrapper is no longer
# queueing, and leaving it in place would make every later waiter yield to a
# position that has already been served.
if [ -n "$MY_TICKET" ]; then
    rm -f "$MY_TICKET" 2>/dev/null
    MY_TICKET=""
fi

"$@" &
CHILD_PID=$!
wait "$CHILD_PID"
RC=$?
exit "$RC"
