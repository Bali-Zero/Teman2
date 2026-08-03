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

run_wrapper() {
    # $1 = value for MAIL_LOOP_DRY_RUN; empty/absent leaves it UNSET, which is
    # the live shape (and the one that fails).
    : > "$ALERTS"
    if [ -n "${1:-}" ]; then
        MAIL_LOOP_REPO_ROOT="$ROOT" MAIL_LOOP_LOG_DIR="$ROOT/logs" HOME="$ROOT" \
            MAIL_LOOP_DRY_RUN="$1" \
            "$INTERP" "$ROOT/scripts/zoho-mail-loop.sh" >/dev/null 2>&1
    else
        MAIL_LOOP_REPO_ROOT="$ROOT" MAIL_LOOP_LOG_DIR="$ROOT/logs" HOME="$ROOT" \
            "$INTERP" "$ROOT/scripts/zoho-mail-loop.sh" >/dev/null 2>&1
    fi
    echo $?
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
for rc in 0 1 2 3; do
    fake_python "$rc"
    check "job rc=$rc, no gateway [live]" "$rc" "$(run_wrapper)"
    check "job rc=$rc, no gateway [DRY_RUN=1]" "$rc" "$(run_wrapper 1)"
done
check "undeliverable alarm is loud in the log" "yes" \
    "$([ "$(grep -c 'ALARM UNDELIVERABLE' "$ROOT/logs/zoho-mail-loop.log")" -gt 0 ] && echo yes || echo no)"

echo "== alert tier: degraded and failed are p0, a clean run is not =="
gateway_present
fake_python 0 && run_wrapper >/dev/null
check "rc=0 -> tier log" "log" "$(awk '{print $2}' "$ALERTS" | head -1)"
fake_python 1 && run_wrapper >/dev/null
check "rc=1 -> tier p0" "p0" "$(awk '{print $2}' "$ALERTS" | head -1)"
check "rc=1 -> dedup key degraded" "mail-loop-degraded" \
    "$(grep -o 'mail-loop-degraded' "$ALERTS" | head -1)"

echo "== a skeleton venv (interpreter present, site-packages gone) is caught =="
fake_python 0 1   # the import probe fails
check "skeleton venv -> rc=2" "2" "$(run_wrapper)"
check "skeleton venv -> alerts" "mail-loop-venv-broken" \
    "$(grep -o 'mail-loop-venv-broken' "$ALERTS" | head -1)"

echo "== a missing venv is caught before anything else =="
rm -f "$ROOT/apps/backend-rag/.venv/bin/python"
check "missing venv -> rc=2" "2" "$(run_wrapper)"
check "missing venv -> alerts" "mail-loop-venv" \
    "$(grep -o 'mail-loop-venv' "$ALERTS" | head -1)"

echo
if [ "$FAILURES" -eq 0 ]; then
    echo "$CHECKS checks, all passed"
    exit 0
fi
echo "$CHECKS checks, $FAILURES FAILED"
exit 1
