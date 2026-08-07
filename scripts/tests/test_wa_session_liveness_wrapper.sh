#!/usr/bin/env bash
# Corpus per infra/launchagents/wrappers/wa-session-liveness.sh.
#
# Il wrapper si prova ESEGUENDOLO in un mondo finto — repo fasullo, interprete
# fasullo — perche le tre cose che deve fare sono tutte cose che si vedono solo
# girando: scegliere l'interprete assoluto, urlare se non c'e, e non mangiarsi
# il codice di uscita. Leggerlo non distingue "non ha sparato" da "non e
# passato di li" (W107).
#
# Uso: bash scripts/tests/test_wa_session_liveness_wrapper.sh

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER_SRC="$REPO/infra/launchagents/wrappers/wa-session-liveness.sh"

PASS=0
FAIL=0

check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "  ✓ $name"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $name — atteso rc=$expected, ottenuto rc=$actual"
        FAIL=$((FAIL + 1))
    fi
}

# Costruisce un finto repo con la stessa FORMA di quello vero, cosi la
# derivazione script-relative del wrapper atterra dentro il finto.
#
# I tre pezzi si montano SEPARATAMENTE di proposito. La prima stesura toglieva
# organo e interprete insieme, e il mutante che disarmava la guardia
# sull'organo sopravviveva: cadeva nella guardia sull'interprete e usciva 2 lo
# stesso. Il test non stava provando NIENTE sulla prima guardia — misurava solo
# che qualcuna delle due avesse parlato. Per giudicare una guardia bisogna
# essere l'unica cosa rotta.
make_world() {
    local root="$1"
    mkdir -p "$root/infra/launchagents/wrappers" "$root/scripts" \
             "$root/apps/backend-rag/.venv/bin"
    cp "$WRAPPER_SRC" "$root/infra/launchagents/wrappers/wa-session-liveness.sh"
}

add_organ() {
    printf '#!/bin/sh\nexit %s\n' "$2" > "$1/scripts/wa_session_liveness.py"
}

add_python() {
    # NON fare `shift`: il primo argomento E lo script da eseguire, e una shell
    # invocata senza argomenti legge EOF e esce 0 — cioe il finto riporterebbe
    # successo qualunque cosa faccia l'organo, e il test misurerebbe la propria
    # poverta invece del wrapper (W107).
    printf '#!/bin/sh\nexec /bin/sh "$@"\n' > "$1/apps/backend-rag/.venv/bin/python"
    chmod +x "$1/apps/backend-rag/.venv/bin/python"
}

run_wrapper() {
    bash "$1/infra/launchagents/wrappers/wa-session-liveness.sh" >/dev/null 2>&1
    echo $?
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "COLPEVOLEZZA — il cron armato a vuoto deve dirlo (W81)"

# 1. organo assente, interprete PRESENTE: e il caso del cron che gira da mesi
#    su un payload sparito. Senza la guardia, il wrapper eseguirebbe
#    l'interprete su un file inesistente e uscirebbe 127, non 2.
make_world "$TMP/no-organ"; add_python "$TMP/no-organ"
check "organo assente → CANNOT-VERIFY" 2 "$(run_wrapper "$TMP/no-organ")"

# 2. interprete assente, organo PRESENTE: asyncpg vive solo nel venv.
make_world "$TMP/no-python"; add_organ "$TMP/no-python" 0
check "interprete assente → CANNOT-VERIFY" 2 "$(run_wrapper "$TMP/no-python")"

echo
echo "PROPAGAZIONE — il codice va CATTURATO, non dedotto dall'essere vivi (W101)"

# 3. l'organo esce 2 (DB irraggiungibile): il wrapper NON deve appiattirlo a 0,
#    altrimenti cron-runner scrive una ricevuta verde su una cecita.
make_world "$TMP/organ-blind"; add_organ "$TMP/organ-blind" 2; add_python "$TMP/organ-blind"
check "organo esce 2 → wrapper esce 2" 2 "$(run_wrapper "$TMP/organ-blind")"

# 4. l'organo esce 0 con una linea ferma: quel verdetto viaggia via Telegram,
#    non via exit-code. Un wrapper che lo alzasse a 1 farebbe fallire il cron
#    ogni giorno finche un collega e in ferie — e insegnerebbe a ignorarlo.
make_world "$TMP/organ-ok"; add_organ "$TMP/organ-ok" 0; add_python "$TMP/organ-ok"
check "organo esce 0 → wrapper esce 0" 0 "$(run_wrapper "$TMP/organ-ok")"

echo
echo "INNOCENZA — il mondo VERO non deve inciampare nelle due guardie sopra"

# 5. Senza questo, i test 1-2 passerebbero anche con un wrapper cablato a
#    `exit 2`: misurerebbero la poverta del mondo finto, non il wrapper.
real_rc=0
if [ ! -f "$REPO/scripts/wa_session_liveness.py" ]; then
    real_rc=1
elif [ ! -x "$REPO/apps/backend-rag/.venv/bin/python" ]; then
    echo "  ~ venv assente su questa macchina: guardia interprete non provabile qui"
    real_rc=-1
fi
if [ "$real_rc" = "0" ]; then
    out="$(bash "$WRAPPER_SRC" --selftest 2>&1)"; rc=$?
    check "repo reale + venv → l'organo gira davvero (rc 0)" 0 "$rc"
    case "$out" in
        *selftest*) echo "  ✓ l'output viene dall'organo, non dalle guardie" ;
                    PASS=$((PASS + 1)) ;;
        *) echo "  ✗ output inatteso: $out" ; FAIL=$((FAIL + 1)) ;;
    esac
elif [ "$real_rc" = "1" ]; then
    echo "  ✗ scripts/wa_session_liveness.py assente nel repo reale"
    FAIL=$((FAIL + 1))
fi

echo
echo "risultato: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ]
