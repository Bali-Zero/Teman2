#!/bin/bash
# =============================================================================
# test_zoho_mail_loop_wrapper.sh — the wrapper's exit code must be the job's.
#
# Why this file exists. The first version of zoho-mail-loop.sh wrapped the job in
# `set +e` / `set -e`. That pair does not restore a previous state: the script
# opens with `set -uo pipefail` and no `-e`, so the trailing `set -e` ENABLED
# errexit for the reporting section below it. `alert` returned 1 when the
# Telegram gateway was absent, errexit aborted on it, and the script exited 1
# while the job had actually exited 2. The real verdict, masked by the path whose
# only job is to report the verdict — W101/W97 reappearing inside the cure
# written against them.
#
# It was found by RUNNING the wrapper against a fake job, not by reading it:
# `bash -n` passed, and one of the earlier checks passed for the wrong reason
# (job rc=1 and the masked exit were both 1, so the two were indistinguishable
# until a case with rc=2 was tried).
#
# So: every rc the CLI can return is asserted here, with the gateway both present
# and absent, because the gateway's absence is what perturbs the control flow.
#
# Usage: bash scripts/test_zoho_mail_loop_wrapper.sh
# =============================================================================

set -uo pipefail

WRAPPER_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/zoho-mail-loop.sh"
if [ ! -f "$WRAPPER_SRC" ]; then
    echo "FATAL: wrapper not found at $WRAPPER_SRC" >&2
    exit 2
fi

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/apps/backend-rag/.venv/bin" "$ROOT/scripts" "$ROOT/logs"
cp "$WRAPPER_SRC" "$ROOT/scripts/"
ALERTS="$ROOT/alerts.txt"

FAILURES=0
CHECKS=0

# A fake interpreter: $1 is the exit code for the job invocation (`-m`), $2 the
# exit code for the import probe (`-c`).
fake_python() {
    cat > "$ROOT/apps/backend-rag/.venv/bin/python" <<PY
#!/bin/bash
for a in "\$@"; do [ "\$a" = "-c" ] && exit ${2:-0}; done
exit ${1:-0}
PY
    chmod +x "$ROOT/apps/backend-rag/.venv/bin/python"
}

gateway_present() {
    cat > "$ROOT/scripts/tg_notify.py" <<PY
import sys, pathlib
pathlib.Path("$ALERTS").open("a").write(" ".join(sys.argv[1:]) + "\n")
PY
}

gateway_absent() { rm -f "$ROOT/scripts/tg_notify.py"; }

# The wrapper runs under the interpreter the PLIST names — /bin/bash — never
# under whatever `bash` PATH happens to resolve to.
#
# This is not pedantry, it is the reason this corpus caught anything. macOS ships
# bash 3.2.57 and launchd executes /bin/bash; in 3.2, expanding an EMPTY array
# under `set -u` is a fatal "unbound variable", and in bash 5 it is perfectly
# legal. The wrapper's ARGS array is empty exactly when MAIL_LOOP_DRY_RUN is 0 —
# the live configuration. So the same corpus reports 16/16 green under a bash 5
# and 10 failures under the interpreter that will actually run the job. A test
# free to pick an interpreter the target never uses is not a test of the target.
INTERP="${MAIL_LOOP_TEST_BASH:-/bin/bash}"

# Extra environment is a PARAMETER of run_wrapper, never a global the callee
# clears.
#
# The first version used a `RUN_EXTRA` global that run_wrapper reset after
# reading it. That cannot work, and this corpus caught it on the first run:
# run_wrapper is invoked inside `$( )`, so the reset happens in a SUBSHELL and
# never reaches the caller. The kill-switch setting from one check stayed applied
# to the next, which then reported the organ as stopped while proving nothing.
# (A reviewer reading the same code concluded it worked — it does not; the
# difference is running it.) A fixture that leaks into the following check is the
# same disease as a guard that leaks state.
#
# The lock lives inside the fake world, never at its real default under /tmp.
# Otherwise a genuine 07:30 run holding the real lock would make every check here
# exit 0 early and report all-green — a corpus passing because the thing it tests
# never ran.
HB_LOG="$ROOT/heartbeats.txt"

run_wrapper() {
    # $1 = value for MAIL_LOOP_DRY_RUN; empty/absent leaves it UNSET, which is
    # the live shape (and the one that fails).
    # $2 = extra KEY=VAL environment for this run only.
    : > "$ALERTS"
    local extra="${2:-}"
    if [ -n "${1:-}" ]; then
        env MAIL_LOOP_REPO_ROOT="$ROOT" MAIL_LOOP_LOG_DIR="$ROOT/logs" HOME="$ROOT" \
            MAIL_LOOP_LOCK_DIR="$ROOT/lock" HEARTBEAT_BIN="$ROOT/hb.sh" \
            MAIL_LOOP_DRY_RUN="$1" $extra \
            "$INTERP" "$ROOT/scripts/zoho-mail-loop.sh" >/dev/null 2>&1
    else
        env MAIL_LOOP_REPO_ROOT="$ROOT" MAIL_LOOP_LOG_DIR="$ROOT/logs" HOME="$ROOT" \
            MAIL_LOOP_LOCK_DIR="$ROOT/lock" HEARTBEAT_BIN="$ROOT/hb.sh" \
            $extra \
            "$INTERP" "$ROOT/scripts/zoho-mail-loop.sh" >/dev/null 2>&1
    fi
    echo $?
}

# A fake heartbeat binary: records "<state>" per call so the corpus can assert
# the organ reported the SAME verdict it exited with.
cat > "$ROOT/hb.sh" <<'HB'
#!/bin/bash
echo "$2" >> "$HB_LOG_TARGET"
HB
chmod +x "$ROOT/hb.sh"
export HB_LOG_TARGET="$HB_LOG"

# The dedup key of the first alert, as a WHOLE token.
#
# `grep -o mail-loop-venv` also matches inside `mail-loop-venv-broken`, so the
# missing-venv check used to pass when the skeleton-venv alert fired instead —
# a substring standing in for an entity, which is the exact shape of the
# over-match family this repo keeps paying for.
dedup_key() {
    awk '{for (i = 1; i < NF; i++) if ($i == "--dedup-key") { print $(i + 1); exit }}' "$ALERTS"
}

check() {
    # $1 = label, $2 = expected, $3 = actual
    CHECKS=$((CHECKS + 1))
    if [ "$2" = "$3" ]; then
        printf '  ok    %-58s %s\n' "$1" "$3"
    else
        printf '  FAIL  %-58s expected=%s actual=%s\n' "$1" "$2" "$3"
        FAILURES=$((FAILURES + 1))
    fi
}

echo "interpreter under test: $INTERP ($("$INTERP" --version | head -1))"
case "$("$INTERP" -c 'echo ${BASH_VERSINFO[0]}')" in
    [0-3]) echo "  (bash 3.x: the empty-array-under-set-u fatal is reproducible here)" ;;
    *) echo "  !! bash >= 4: this interpreter CANNOT reproduce the empty-array fatal." \
            "Green here is not evidence about the launchd target (macOS /bin/bash 3.2)." ;;
esac
echo

echo "== the job's exit code must reach the caller, gateway PRESENT =="
gateway_present
for rc in 0 1 2 3; do
    fake_python "$rc"
    # Both flag states, every time. DRY_RUN=1 is what the plist ships; unset is
    # what it becomes the day it goes live, and only the second one has an empty
    # ARGS array. Testing one of the two is testing half the configurations the
    # organ will actually be run in.
    check "job rc=$rc [DRY_RUN unset = live]" "$rc" "$(run_wrapper)"
    check "job rc=$rc [DRY_RUN=1 = shipped]" "$rc" "$(run_wrapper 1)"
done

echo "== and with the gateway ABSENT: the messenger must not change the verdict =="
gateway_absent
# Truncate first and assert an EXACT count below. "at least one line somewhere in
# the accumulated log" would still pass if 7 of the 8 alerts were silently
# swallowed — a threshold standing in for a tally.
: > "$ROOT/logs/zoho-mail-loop.log"
for rc in 0 1 2 3; do
    fake_python "$rc"
    check "job rc=$rc, no gateway [live]" "$rc" "$(run_wrapper)"
    check "job rc=$rc, no gateway [DRY_RUN=1]" "$rc" "$(run_wrapper 1)"
done
check "every undeliverable alarm is loud in the log (8 runs)" "8" \
    "$(grep -c 'ALARM UNDELIVERABLE' "$ROOT/logs/zoho-mail-loop.log" | tr -d ' ')"

echo "== alert tier: degraded and failed are p0, a clean run is not =="
gateway_present
fake_python 0 && run_wrapper >/dev/null
check "rc=0 -> tier log" "log" "$(awk '{print $2}' "$ALERTS" | head -1)"
fake_python 1 && run_wrapper >/dev/null
check "rc=1 -> tier p0" "p0" "$(awk '{print $2}' "$ALERTS" | head -1)"
check "rc=1 -> dedup key degraded" "mail-loop-degraded" "$(dedup_key)"

echo "== a skeleton venv (interpreter present, site-packages gone) is caught =="
fake_python 0 1   # the import probe fails
check "skeleton venv -> rc=2" "2" "$(run_wrapper)"
check "skeleton venv -> alerts" "mail-loop-venv-broken" "$(dedup_key)"

echo "== a missing venv is caught before anything else =="
rm -f "$ROOT/apps/backend-rag/.venv/bin/python"
check "missing venv -> rc=2" "2" "$(run_wrapper)"
check "missing venv -> alerts" "mail-loop-venv" "$(dedup_key)"

echo "== G5 kill switch: it must stop the organ, and ONLY when asked =="
gateway_present
fake_python 3          # the job would fail loudly if it ever ran
check "MAIL_LOOP_ENABLED=false -> rc 0" "0" "$(run_wrapper "" "MAIL_LOOP_ENABLED=false")"
# innocence: the switch must not fire on its own, or the organ is dead and the
# corpus above would still be green — the switch would be indistinguishable from
# a broken loop.
check "switch unset -> the job still runs" "3" "$(run_wrapper)"
check "MAIL_LOOP_ENABLED=true -> the job still runs" "3" "$(run_wrapper "" "MAIL_LOOP_ENABLED=true")"

echo "== G10 single instance: obey a LIVE lock, reclaim a dead one =="
fake_python 3
# a lock held by a process that is genuinely alive: use this shell's own pid.
mkdir -p "$ROOT/lock" && echo $$ > "$ROOT/lock/pid"
check "live lock -> skip, rc 0" "0" "$(run_wrapper)"
check "live lock -> the lock survives" "yes" \
    "$([ -d "$ROOT/lock" ] && echo yes || echo no)"
# a lock left by a dead process must NOT silence the organ forever.
rm -rf "$ROOT/lock"; mkdir -p "$ROOT/lock"
# pid 99999 is not running here; if it ever were, the check would read as a live
# lock and fail loudly rather than pass quietly.
echo 99999 > "$ROOT/lock/pid"
check "stale lock -> reclaimed, job runs" "3" "$(run_wrapper)"
check "lock released on exit" "no" \
    "$([ -d "$ROOT/lock" ] && echo yes || echo no)"

echo "== G2 heartbeat: the organ reports the verdict it exited with =="
for pair in "0:ok" "1:degraded" "2:error"; do
    rc="${pair%%:*}"; want="${pair##*:}"
    : > "$HB_LOG"
    fake_python "$rc"
    run_wrapper >/dev/null
    check "rc=$rc -> heartbeat $want" "$want" "$(tail -1 "$HB_LOG" 2>/dev/null)"
done

# =============================================================================
# The claude CLI must be resolved by the WRAPPER, not discovered per message.
#
# Measured on the first non-dry-run run (2026-08-05): 1 message routed, 0 drafts
# written, every one failing "claude CLI not on PATH". The plist ships a
# deliberately minimal PATH and the CLI lives in ~/.local/bin, which launchd has
# no reason to inherit. `draft.py` had predicted the failure in its own error
# text; the other half was never armed.
#
# PATH is pinned to the plist's OWN value in every check below. Leaving the real
# PATH in place would let `command -v claude` find the developer's install and
# report green for a machine that has one — the corpus would then be measuring
# this laptop, not the launchd environment (the W108 shape: a dev box
# structurally unable to reproduce the red).
# =============================================================================

echo
echo "== the claude CLI is resolved once, by the wrapper =="
PLIST_PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
gateway_present
fake_python 0

plant_fake_cli() {
    mkdir -p "$(dirname "$1")"
    printf '#!/bin/bash
exit 0
' > "$1"
    chmod +x "$1"
}

# The wrapper's own log is zoho-mail-loop.log ($LOG_DIR/zoho-mail-loop.log,
# wrapper line 44). `.out.log` is launchd's stdout capture and does not exist
# in this fake world — reading it returned empty and every grep below counted
# 0, which is a probe measuring its own mistake, not the target.
wrapper_log() { cat "$ROOT/logs/zoho-mail-loop.log" 2>/dev/null; }

# GUILT: nothing to find anywhere -> say so, name where you looked, alert, and
# STILL run. Routing without drafting is worth doing; exiting here would throw
# away the half that works.
rm -f "$ROOT/.local/bin/claude"
: > "$ROOT/logs/zoho-mail-loop.log"
rc="$(run_wrapper "" "PATH=$PLIST_PATH")"
check "no CLI anywhere -> wrapper still exits with the job's rc" "0" "$rc"
check "no CLI anywhere -> warned" "1" "$(wrapper_log | grep -c 'no claude CLI found')"
check "no CLI anywhere -> alerted" "mail-loop-no-cli" "$(dedup_key)"

# INNOCENCE: the real install location is found and EXPORTED, so draft.py — which
# reads CLAUDE_CLI_PATH first — never has to search.
plant_fake_cli "$ROOT/.local/bin/claude"
: > "$ROOT/logs/zoho-mail-loop.log"
rc="$(run_wrapper "" "PATH=$PLIST_PATH")"
check "CLI in ~/.local/bin -> found" "1" "$(wrapper_log | grep -c "claude CLI: $ROOT/.local/bin/claude")"
check "CLI in ~/.local/bin -> no warning" "0" "$(wrapper_log | grep -c 'no claude CLI found')"
# A clean run legitimately alerts `mail-loop-ok`; the assertion is that the
# CLI-missing alarm did NOT fire, not that nothing fired at all.
check "CLI in ~/.local/bin -> no CLI alarm" "0" "$(grep -c mail-loop-no-cli "$ALERTS")"

# INNOCENCE: an explicit CLAUDE_CLI_PATH wins and is not second-guessed.
plant_fake_cli "$ROOT/elsewhere/claude"
: > "$ROOT/logs/zoho-mail-loop.log"
rc="$(run_wrapper "" "PATH=$PLIST_PATH CLAUDE_CLI_PATH=$ROOT/elsewhere/claude")"
check "explicit CLAUDE_CLI_PATH is honoured" "1" "$(wrapper_log | grep -c "claude CLI: $ROOT/elsewhere/claude")"

# GUILT: an explicit path pointing at nothing must NOT be trusted silently —
# fall back and keep looking, because a stale pin is how this organ would go
# quiet after a reinstall moves the binary.
rm -f "$ROOT/elsewhere/claude"
plant_fake_cli "$ROOT/.local/bin/claude"
: > "$ROOT/logs/zoho-mail-loop.log"
rc="$(run_wrapper "" "PATH=$PLIST_PATH CLAUDE_CLI_PATH=$ROOT/elsewhere/claude")"
check "stale CLAUDE_CLI_PATH falls back" "1" "$(wrapper_log | grep -c "claude CLI: $ROOT/.local/bin/claude")"

echo
if [ "$FAILURES" -eq 0 ]; then
    echo "$CHECKS checks, all passed"
    exit 0
fi
echo "$CHECKS checks, $FAILURES FAILED"
exit 1
