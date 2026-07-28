#!/usr/bin/env bash
# Proof for the failure alert in scripts/cron-runner.sh.
#
# TRAUMA (2026-07-28). cron-state.sh got a voice on 2026-07-27 and the sweep stopped
# there. Censused on Pro the next morning by the `source` field of the receipts,
# `~/.agent/decisions/state` has FIVE producers — cron-runner 36, cron-state 28,
# cron-wrapper 9, launchagent-state-bridge 5, openclaw-bridge 4 — and the one that got
# cured is not the biggest: cron-runner is invoked 30 times (25 crontab + 5 plist)
# against cron-state's 27. Two cron-runner jobs failed in the 24h after that fix
# shipped — garuda_indexer 27/07 20:36, run_ops_briefing 27/07 00:00 — with no
# `cron-fail:` anywhere: 0 in the 239-row P0 archive, 0 in the 54-row digest spool.
# Curing one wrapper of five does not cut the risk by a fifth; it only moves which
# job dies quietly.
#
#   GUILT ×3    — ALL THREE exits must speak, not just the one that bit us: a job that
#                 runs and fails, a script that is missing (armed to nothing, W81), and
#                 the runner invoked with no argument at all — the last writes no
#                 receipt whatsoever, so silence there is total.
#   INNOCENCE   — a succeeding job must NOT alert. An alarm that fires on success is an
#                 alarm someone turns off.
#   FAIL-OPEN   — the alert must never rewrite the job's exit code: that exit code is the
#                 whole contract this wrapper exists to preserve. Asserted with a gateway
#                 that crashes AND with no gateway at all.
#
# No network, no Telegram: the wrapper runs from a tmp copy with a fake tg_notify.py
# beside it, which records argv instead of sending. (The wrapper OVERWRITES $PATH on
# line 11, so shadowing python3 via PATH cannot work — a stub placed there is silently
# outranked. The sibling-first gateway lookup is what makes this testable at all.)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

WRAPPER="$HERE/cron-runner.sh"
[ -f "$WRAPPER" ] || { echo "cron-runner.sh not found at $WRAPPER"; exit 1; }

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
has () { grep -qx -- "$1" "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1; }

run_case () {  # run_case <args...> ; sets RC. STUB_RC / NO_STUB tune the gateway.
    rm -rf "$TMP/run" "$TMP/state" "$TMP/home" "$TMP/gateway.argv"
    mkdir -p "$TMP/run" "$TMP/state" "$TMP/home"
    cp "$WRAPPER" "$TMP/run/cron-runner.sh"
    [ -n "${NO_STUB:-}" ] || mkstub "${STUB_RC:-0}"
    HOME="$TMP/home" CRON_RUNNER_STATE_DIR="$TMP/state" \
        bash "$TMP/run/cron-runner.sh" "$@" >/dev/null 2>&1
    RC=$?
}

echo "GUILT 1 — un job che gira e fallisce deve parlare"
printf '#!/bin/bash\necho "boom sul canale combinato" >&2\nexit 7\n' > "$TMP/job.sh"
chmod +x "$TMP/job.sh"
run_case "$TMP/job.sh"
check "l'exit code del job e' preservato (7)"   "$([ "$RC" = "7" ] && echo 0 || echo 1)"
check "il gateway e' stato invocato"            "$([ -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "tier p0"                                 "$( [ "$(has '--tier')" = 0 ] && [ "$(has 'p0')" = 0 ] && echo 0 || echo 1)"
check "dedup key per-job (cron-fail:job)"       "$(has 'cron-fail:job')"
check "source per-job (cron:job)"               "$(has 'cron:job')"
check "il messaggio porta l'exit code vero"     "$(grep -q 'Exit: 7' "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"
check "il messaggio porta la causa reale"       "$(grep -q 'boom sul canale combinato' "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"
check "la ricevuta e' comunque scritta"         "$([ -f "$TMP/state/job.last.json" ] && echo 0 || echo 1)"

echo "GUILT 2 — script assente (armato a vuoto, W81): la ricevuta c'e', mancava la voce"
run_case "$TMP/does-not-exist.sh"
check "exit 1"                                  "$([ "$RC" = "1" ] && echo 0 || echo 1)"
check "il gateway e' stato invocato"            "$([ -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "dedup key derivata dal nome del job"     "$(has 'cron-fail:does_not_exist')"
check "il messaggio dice che manca lo script"   "$(grep -q 'script not found' "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"

echo "GUILT 3 — invocato senza argomenti: nessuna ricevuta, silenzio totale"
run_case
check "exit 64 preservato"                      "$([ "$RC" = "64" ] && echo 0 || echo 1)"
check "il gateway e' stato invocato lo stesso"  "$([ -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "chiave fissa (nessuna identita' di job)" "$(has 'cron-fail:_cron_runner_usage')"

echo "INNOCENZA — un job che riesce NON deve parlare"
printf '#!/bin/bash\nexit 0\n' > "$TMP/happy.sh"; chmod +x "$TMP/happy.sh"
run_case "$TMP/happy.sh"
check "exit 0 preservato"                       "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "nessuna invocazione del gateway"         "$([ ! -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "ricevuta scritta"                        "$([ -f "$TMP/state/happy.last.json" ] && echo 0 || echo 1)"

echo "FAIL-OPEN — un problema dell'allarme non puo' riscrivere l'exit del job"
STUB_RC=3 run_case "$TMP/job.sh"
check "gateway che crasha (3): l'exit resta 7"  "$([ "$RC" = "7" ] && echo 0 || echo 1)"
NO_STUB=1 run_case "$TMP/job.sh"
check "nessun gateway sul disco: l'exit resta 7" "$([ "$RC" = "7" ] && echo 0 || echo 1)"
unset NO_STUB

echo
printf 'cron-runner alert corpus: %d ok, %d FAIL\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
