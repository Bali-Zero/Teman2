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
#   NUZ_PREPUSH_SUITE_LOCK_TIMEOUT=<s>   max wait in seconds before failing
#                                         closed (default 4500 = 75min).
#                                         Test-only override in practice.
#   NUZ_PREPUSH_SUITE_LOCK_POLL=<s>      poll interval in seconds (default 2).
#                                         Test-only override.
#
# Exit code: on success, propagates <command>'s own exit code UNCHANGED
# (including a 128+N signal-death code, so an outer `TEST_RC -ge 128`
# classification still works). On a timed-out lock acquisition, exits 1
# itself with an actionable message — the wrapped command never even starts;
# this NEVER silently skips the lock and runs anyway (cicatrix-superscar.md
# family #2, "esiste != armato" — a guard that can silently disarm itself
# is not a guard).

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
HEARTBEAT_EVERY=30

START_TS=$(date +%s)
LAST_HEARTBEAT=$START_TS

while :; do
    if mkdir "$LOCKFILE" 2>/dev/null; then
        chmod 700 "$LOCKFILE" 2>/dev/null
        echo $$ > "$LOCKFILE/pid" 2>/dev/null
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
        echo "❌ machine saturated — suite lock not acquired in ${TIMEOUT_MIN}m. Do NOT use --no-verify. Either retry later, or land this branch from an idle fleet machine (git bundle + push from pro/mini)." >&2
        exit 1
    fi

    if [ $((NOW - LAST_HEARTBEAT)) -ge "$HEARTBEAT_EVERY" ]; then
        HELD_MIN=$((ELAPSED / 60))
        echo "⏳ waiting for this machine's backend-suite lock (held by PID ${HOLDER_PID:-unknown} for ${HELD_MIN}m)"
        LAST_HEARTBEAT=$NOW
    fi

    sleep "$POLL_INTERVAL"
done

# CHILD_PID starts unset: if this wrapper is killed between acquiring the
# lock and backgrounding the command below, cleanup must only drop the lock,
# not try to signal a child that was never started.
CHILD_PID=""
cleanup() {
    if [ -n "$CHILD_PID" ]; then
        # A signal that targets only THIS wrapper's PID (not the whole
        # foreground process group) must not leave the wrapped suite running
        # as an orphan after the lock is already released underneath it.
        kill -TERM "$CHILD_PID" 2>/dev/null
    fi
    rm -rf "$LOCKFILE" 2>/dev/null
}
trap cleanup EXIT INT TERM

"$@" &
CHILD_PID=$!
wait "$CHILD_PID"
RC=$?
exit "$RC"
