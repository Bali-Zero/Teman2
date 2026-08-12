#!/usr/bin/env bash
# Proof that ONE cron failure produces ONE Telegram, carrying the job's own words.
#
# TRAUMA (2026-08-07). Giving the cron wrappers a voice (W107, 2026-07-28) closed a
# real silence and opened a smaller one at the other end: the payloads in
# apps/evaluator/nlm_deep_research/scripts already alarmed for themselves, and 19 of
# the 20 run under a wrapper that alarms too. One failure, two P0s ~2s apart.
# Measured on the archived pair for run_nb2_pipeline (2026-08-06 02:10), they carry
# DIFFERENT information and neither contains the other:
#
#   script:  "🚨 NB2 Immigration pipeline FAILED (exit 1) — check <log path>"
#   wrapper: "CRON FAIL … Job: … Exit: 1 Duration: 3s" + 600 bytes of raw stdout —
#            registry counts, a HALTED state line, a JSON run blob. No log path.
#
# So "silence the script" loses the path and "silence the wrapper" reopens W107.
# The wrapper carries the job's sentence instead: it exports CRON_ALARM_OWNER, the
# payload prints CRON_ALERT_P0: <text> rather than sending, and the wrapper prefers
# that line over its raw tail.
#
#   GUILT ×2      — under EACH alarming wrapper (cron-runner, cron-wrapper): exactly
#                   ONE send, and it carries the job's sentence including the log path.
#   INNOCENCE ×4  — a payload with no wrapper must still send (run_peraturan_ingestion.sh
#                   is invoked from crontab bare; an unconditional deferral would have
#                   made it mute); a non-p0 tier is never deferred; a payload that names
#                   no sentence still gets the raw tail; success still says nothing.
#   RETRIES       — cron-wrapper retries a failing job, and the payload's own alarm
#                   carries NO dedup key, so before this the retries multiplied the
#                   messages. One failure must stay one message.
#   AGREEMENT     — the marker literal is duplicated in three files on purpose (the
#                   alarm path must not gain a dependency that fails the way the thing
#                   it reports fails, W108). Duplication is only safe if something
#                   pins it: this does.
#
# No network. The wrappers run from a tmp tree shaped like the repo, with a fake
# tg_notify.py where BOTH the wrapper and _alert.sh resolve it — so the count below is
# every message that would have been sent, from either mouth.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
TMP="$(mktemp -d)"
trap '/bin/rm -rf "${TMP:?}"' EXIT

RUNNER="$HERE/cron-runner.sh"
WRAPPER="$HERE/cron-wrapper.sh"
ALERTLIB="$REPO/apps/evaluator/nlm_deep_research/scripts/_alert.sh"
for f in "$RUNNER" "$WRAPPER" "$ALERTLIB"; do
    [ -f "$f" ] || { echo "missing: $f"; exit 1; }
done

PASS=0; FAIL=0
check () {  # check <name> <0|1>
    if [ "$2" = "0" ]; then PASS=$((PASS+1)); printf '  ok    %s\n' "$1"
    else FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; fi
}
yes_if () { [ "$1" = "$2" ] && echo 0 || echo 1; }
sends () { grep -c '^=== SEND ===$' "$TMP/gateway.log" 2>/dev/null || echo 0; }
body_has () { grep -q -- "$1" "$TMP/gateway.log" 2>/dev/null && echo 0 || echo 1; }

SENTENCE='NB-X pipeline FAILED — check /tmp/nbx-run.log'
NOISE='raw stdout noise the wrapper would otherwise quote'

build_world () {  # build_world ; payload behaviour tuned by PAYLOAD_BODY
    rm -rf "${TMP:?}/repo" "${TMP:?}/home" "${TMP:?}/gateway.log"
    mkdir -p "$TMP/repo/scripts" "$TMP/repo/apps/evaluator/nlm_deep_research/scripts" \
             "$TMP/home/.agent/decisions/state" "$TMP/home/logs/cron"
    cp "$RUNNER"   "$TMP/repo/scripts/cron-runner.sh"
    cp "$WRAPPER"  "$TMP/repo/scripts/cron-wrapper.sh"
    cp "$ALERTLIB" "$TMP/repo/apps/evaluator/nlm_deep_research/scripts/_alert.sh"

    # One fake gateway at the single path BOTH mouths resolve to:
    #   cron-runner/cron-wrapper -> $(dirname $0)/tg_notify.py
    #   _alert.sh                -> <four levels up>/scripts/tg_notify.py
    cat > "$TMP/repo/scripts/tg_notify.py" <<STUB
import sys
with open("$TMP/gateway.log", "a") as fh:
    fh.write("=== SEND ===\n" + "\n".join(sys.argv[1:]) + "\n")
STUB

    cat > "$TMP/repo/apps/evaluator/nlm_deep_research/scripts/job.sh" <<PAYLOAD
#!/bin/bash
set -uo pipefail
. "\$(dirname "\$0")/_alert.sh"
echo "$NOISE"
${PAYLOAD_BODY:-alert p0 "🚨 $SENTENCE"}
exit \${JOB_EXIT:-5}
PAYLOAD
    chmod +x "$TMP/repo/apps/evaluator/nlm_deep_research/scripts/job.sh"
}

run_under_runner () {
    HOME="$TMP/home" CRON_RUNNER_STATE_DIR="$TMP/home/.agent/decisions/state" \
        bash "$TMP/repo/scripts/cron-runner.sh" \
        "$TMP/repo/apps/evaluator/nlm_deep_research/scripts/job.sh" >/dev/null 2>&1
    RC=$?
}

run_under_wrapper () {  # run_under_wrapper [retries]
    HOME="$TMP/home" CRON_MAX_RETRIES="${1:-0}" CRON_LOG_DIR="$TMP/home/logs/cron" \
        bash "$TMP/repo/scripts/cron-wrapper.sh" "singlevoice-probe-$$" \
        /bin/bash "$TMP/repo/apps/evaluator/nlm_deep_research/scripts/job.sh" >/dev/null 2>&1
    RC=$?
}

echo "GUILT 1 — sotto cron-runner: UN messaggio, e porta la frase del job"
PAYLOAD_BODY="" build_world
run_under_runner
check "l'exit del job e' preservato (5)"        "$(yes_if "$RC" 5)"
check "esattamente UN invio (era 2)"            "$(yes_if "$(sends)" 1)"
check "il messaggio porta la frase del job"     "$(body_has "$SENTENCE")"
check "…quindi porta il path del log"           "$(body_has '/tmp/nbx-run.log')"
check "l'intestazione strutturata resta"        "$(body_has 'Exit: 5')"
check "la coda grezza non e' piu' il corpo"     "$([ "$(body_has "$NOISE")" = 1 ] && echo 0 || echo 1)"
check "il marcatore e' stato spogliato"         "$([ "$(body_has 'CRON_ALERT_P0:')" = 1 ] && echo 0 || echo 1)"
check "la ricevuta e' comunque scritta"         "$([ -f "$TMP/home/.agent/decisions/state/job.last.json" ] && echo 0 || echo 1)"
check "la ricevuta conserva la causa grezza"    "$(grep -q "$NOISE" "$TMP/home/.agent/decisions/state/job.last.json" 2>/dev/null && echo 0 || echo 1)"

echo "GUILT 2 — sotto cron-wrapper: stessa cura (curarne uno su cinque e' W107)"
PAYLOAD_BODY="" build_world
run_under_wrapper 0
check "esattamente UN invio (era 2)"            "$(yes_if "$(sends)" 1)"
check "il messaggio porta la frase del job"     "$(body_has "$SENTENCE")"
check "l'intestazione strutturata resta"        "$(body_has 'Exit: 5')"
# Senza queste due, "porta la frase" passa anche col fallback alla coda grezza:
# la coda CONTIENE la riga-marcatore, quindi contiene la frase. Un mutante che
# spegneva la preferenza qui e' sopravvissuto esattamente cosi'.
check "la coda grezza non e' piu' il corpo"     "$([ "$(body_has "$NOISE")" = 1 ] && echo 0 || echo 1)"
check "il marcatore e' stato spogliato"         "$([ "$(body_has 'CRON_ALERT_P0:')" = 1 ] && echo 0 || echo 1)"

echo "RETRIES — il ritentativo non moltiplica i messaggi"
PAYLOAD_BODY="" build_world
run_under_wrapper 1
check "2 tentativi falliti => 1 solo invio"     "$(yes_if "$(sends)" 1)"

echo "MULTI-RIGA — una frase su piu' righe arriva INTERA"
# Il marcatore si rilegge con un grep ancorato a riga: senza il collasso dei
# newline la seconda meta' resterebbe fuori dal messaggio, in silenzio. Oggi
# nessuno dei 20 payload manda multi-riga — il contratto deve reggerlo lo stesso.
PAYLOAD_BODY='alert p0 "prima meta della frase
seconda meta della frase"' build_world
run_under_runner
check "un invio"                                "$(yes_if "$(sends)" 1)"
check "la prima meta' c'e'"                     "$(body_has 'prima meta della frase')"
check "e la seconda anche"                      "$(body_has 'seconda meta della frase')"
check "…sulla stessa riga (newline collassati)" "$(body_has 'prima meta della frase seconda meta della frase')"

echo "INNOCENZA 1 — nessun wrapper: il payload DEVE parlare da se'"
# run_peraturan_ingestion.sh gira da crontab senza wrapper: se il rinvio fosse
# incondizionato, questo caso sarebbe muto.
PAYLOAD_BODY="" build_world
( cd "$TMP" && HOME="$TMP/home" \
    bash "$TMP/repo/apps/evaluator/nlm_deep_research/scripts/job.sh" >/dev/null 2>&1 )
check "un invio (il payload non e' ammutolito)" "$(yes_if "$(sends)" 1)"
check "e porta la sua frase"                    "$(body_has "$SENTENCE")"

echo "INNOCENZA 2 — un tier diverso da p0 non viene mai rinviato"
PAYLOAD_BODY='alert digest "riepilogo che non e un allarme"' build_world
JOB_EXIT=0 run_under_runner
check "il digest e' partito subito"             "$(body_has 'riepilogo che non e un allarme')"
check "…e il job riuscito non ha aggiunto P0"   "$(yes_if "$(sends)" 1)"

echo "INNOCENZA 3 — un payload che non nomina nulla: resta la coda grezza"
PAYLOAD_BODY=':' build_world
run_under_runner
check "un invio"                                "$(yes_if "$(sends)" 1)"
check "il corpo e' la coda grezza (fallback)"   "$(body_has "$NOISE")"

echo "SIMMETRIA — lo stesso payload muto, ma sotto cron-wrapper (W101, 2026-08-12)"
# INNOCENZA 3 qui sopra gira SOLO sotto cron-runner, che ha `set -uo pipefail`.
# cron-wrapper ha `set -euo pipefail`, e la riga che rilegge il marcatore e' una
# pipeline NUDA: senza marcatore `grep` esce 1, pipefail lo propaga, errexit aborta
# lo script PRIMA di send_telegram. Il ramo di fallback alla coda grezza esisteva,
# non poteva scattare.
#
# Misurato vivo su Mini prima della cura: visa-oracle-retention e' fallito 31 volte
# di fila in ~8h (exit 75 dal suo shim, che non stampa il marcatore) e nello spool
# Telegram della macchina compare ZERO volte — mentre 8 altre sorgenti ci arrivavano,
# quindi il gateway funzionava. Il caso-che-funziona (col marcatore) era gia' provato
# sotto ENTRAMBI i wrapper; il caso-che-rompe sotto uno solo. Un corpus asimmetrico
# copre la forma, non la classe: e' la lezione W107 ripetuta dentro il test scritto
# per chiuderla.
PAYLOAD_BODY=':' build_world
run_under_wrapper 0
check "un invio anche senza marcatore"          "$(yes_if "$(sends)" 1)"
check "il corpo e' la coda grezza (fallback)"   "$(body_has "$NOISE")"

echo "INNOCENZA 4 — un job che riesce non dice niente"
PAYLOAD_BODY=':' build_world
JOB_EXIT=0 run_under_runner
check "exit 0 preservato"                       "$(yes_if "$RC" 0)"
check "nessun invio"                            "$(yes_if "$(sends)" 0)"

echo "NESSUN BYPASS — i payload devono parlare SOLO tramite alert()"
# Il rinvio vive dentro _alert.sh: un payload che invoca il gateway da se'
# aggira la cura e la doppia voce ricresce, senza che niente diventi rosso
# (W82 — la guardia sorveglia una superficie ed e' cieca all'altra).
# "Invoca" != "nomina": run_nb5_t4_monitor.sh cita tg_notify in un COMMENTO ed e'
# innocente, quindi i commenti si tolgono prima di guardare (over-match, #3).
PAYLOADS="$REPO/apps/evaluator/nlm_deep_research/scripts"
bypass=""
for f in "$PAYLOADS"/run_*.sh; do
    [ -f "$f" ] || continue
    if sed 's/[[:space:]]*#.*$//' "$f" | grep -qE 'tg_notify|sendMessage'; then
        bypass="$bypass $(basename "$f")"
    fi
done
n_payloads=$(find "$PAYLOADS" -maxdepth 1 -name 'run_*.sh' | wc -l | tr -d ' ')
check "i payload censiti sono >= 20 (non ho guardato una dir vuota)" \
      "$([ "$n_payloads" -ge 20 ] && echo 0 || echo 1)"
check "nessun payload invoca il gateway da se'" \
      "$([ -z "$bypass" ] && echo 0 || { echo "     bypass:$bypass" >&2; echo 1; })"
# innocenza del rilevatore: una menzione in commento NON e' un bypass
probe_ok=$(printf '#!/bin/bash\n# see tg_notify for the dedup key\nalert p0 "x"\n' \
    | sed 's/[[:space:]]*#.*$//' | grep -cE 'tg_notify|sendMessage')
probe_guilt=$(printf '#!/bin/bash\npython3 scripts/tg_notify.py --tier p0 -- "x"\n' \
    | sed 's/[[:space:]]*#.*$//' | grep -cE 'tg_notify|sendMessage')
check "il rilevatore assolve una menzione in commento"   "$(yes_if "$probe_ok" 0)"
check "…e condanna una invocazione vera"                 "$(yes_if "$probe_guilt" 1)"

echo "ACCORDO — il marcatore duplicato nei tre file deve coincidere"
mk () { grep -h '^CRON_ALERT_MARKER=' "$1" | head -1 | cut -d= -f2- | tr -d '"'; }
M_RUN="$(mk "$RUNNER")"; M_WRAP="$(mk "$WRAPPER")"; M_LIB="$(mk "$ALERTLIB")"
check "cron-runner dichiara un marcatore"       "$([ -n "$M_RUN" ] && echo 0 || echo 1)"
check "cron-wrapper concorda"                   "$(yes_if "$M_WRAP" "$M_RUN")"
check "_alert.sh concorda"                      "$(yes_if "$M_LIB" "$M_RUN")"

echo
printf 'cron single-voice corpus: %d ok, %d FAIL\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
