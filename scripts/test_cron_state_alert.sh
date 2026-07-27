#!/usr/bin/env bash
# Proof for the failure alert in scripts/cron-state.sh.
#
# The wrapper wrote a receipt and nothing else. A receipt is evidence, not a voice: the
# 03:00 Postgres backup runs under this wrapper, so its 2026-07-26 failure was silent
# while the 03:20 run — which uses cron-wrapper.sh — alerted. Four other cron-state jobs
# were sitting in a failed receipt nobody had seen.
#
#   GUILT     — a failing job MUST invoke the gateway, with the p0 tier and the per-job
#               dedup key, carrying the real exit code.
#   INNOCENCE — a succeeding job must NOT alert (an alarm that fires on success is an
#               alarm someone turns off), and the receipt must still be written.
#   FAIL-OPEN — the alert path must never rewrite the job's exit code: that exit code is
#               the whole contract this wrapper exists to preserve. Asserted twice, with a
#               gateway that crashes and with no gateway at all.
#
# No network and no Telegram: the wrapper runs from a tmp copy with a fake tg_notify.py
# beside it, which records argv instead of sending anything.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

WRAPPER="$HERE/cron-state.sh"
[ -f "$WRAPPER" ] || { echo "cron-state.sh not found at $WRAPPER"; exit 1; }

# The wrapper OVERWRITES $PATH on its second line, so shadowing `python3` cannot work —
# a stub placed on PATH is silently outranked. Instead we run a COPY of the wrapper from
# a tmp dir and drop a fake tg_notify.py beside it: the sibling-first lookup finds ours,
# and the real python3 executes it. (Finding this was the corpus earning its keep.)
mkstub () {  # mkstub <exit-code>
    cat > "$TMP/run/tg_notify.py" <<STUB
import sys
with open("$TMP/gateway.argv", "a") as fh:
    fh.write("\n".join(sys.argv[1:]) + "\n")
raise SystemExit($1)
STUB
}

PASS=0; FAIL=0
check () {  # check <name> <condition-result>
    if [ "$2" = "0" ]; then PASS=$((PASS+1)); printf '  ok    %s\n' "$1"
    else FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; fi
}

run_case () {  # run_case <job> <cmd...> ; sets RC
    rm -rf "$TMP/run" "$TMP/state" "$TMP/home" "$TMP/gateway.argv"
    mkdir -p "$TMP/run" "$TMP/state" "$TMP/home"
    cp "$WRAPPER" "$TMP/run/cron-state.sh"
    mkstub "${STUB_RC:-0}"
    HOME="$TMP/home" CRON_STATE_DIR="$TMP/state" \
        bash "$TMP/run/cron-state.sh" "$@" >/dev/null 2>&1
    RC=$?
}

echo "GUILT — un job che fallisce deve parlare"
run_case failing-job sh -c 'echo boom >&2; exit 7'
check "l'exit code del job e' preservato (7)" "$([ "$RC" = "7" ] && echo 0 || echo 1)"
check "il gateway e' stato invocato" "$([ -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "tier p0" "$(grep -qx -- '--tier' "$TMP/gateway.argv" 2>/dev/null && grep -qx -- 'p0' "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"
check "dedup key per-job" "$(grep -qx -- 'cron-fail:failing_job' "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"
check "il messaggio porta l'exit code vero" "$(grep -q 'Exit: 7' "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"
check "la ricevuta e' comunque scritta" "$([ -f "$TMP/state/failing_job.last.json" ] && echo 0 || echo 1)"

echo "INNOCENZA — un job che riesce NON deve parlare"
run_case happy-job sh -c 'exit 0'
check "exit 0 preservato" "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "nessuna invocazione del gateway" "$([ ! -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "ricevuta scritta" "$([ -f "$TMP/state/happy_job.last.json" ] && echo 0 || echo 1)"

echo "FAIL-OPEN — un allarme rotto non puo' riscrivere l'esito del job"
STUB_RC=1 run_case crashing-gateway sh -c 'exit 3'
check "exit 3 preservato anche se il gateway esplode" "$([ "$RC" = "3" ] && echo 0 || echo 1)"

# ...e senza alcun gateway sul disco (nessun tg_notify.py né accanto né sotto HOME)
rm -rf "$TMP/run" "$TMP/state" "$TMP/home"
mkdir -p "$TMP/run" "$TMP/state" "$TMP/home"
cp "$WRAPPER" "$TMP/run/cron-state.sh"
HOME="$TMP/home" CRON_STATE_DIR="$TMP/state" \
    bash "$TMP/run/cron-state.sh" no-gateway sh -c 'exit 5' >/dev/null 2>&1
NOGW_RC=$?
check "exit 5 preservato senza gateway sul disco" "$([ "$NOGW_RC" = "5" ] && echo 0 || echo 1)"

echo
echo "pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
