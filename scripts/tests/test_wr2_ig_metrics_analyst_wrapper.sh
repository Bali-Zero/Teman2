#!/usr/bin/env bash
# Corpus per infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh.
#
# Il wrapper si prova ESEGUENDOLO in un mondo finto — HOME finta, agy finto,
# claude finto, gateway finto — perche le due cose che deve fare sono cose che si
# vedono solo girando:
#
#   1. SOPRAVVIVERE all'health-check di agy. La sonda vive in un sottoshell, e un
#      sottoshell EREDITA errexit; entrambe le sue uscite sono non-zero per
#      costruzione (agy giu -> il codice di agy; agy su -> 143, il watchdog che
#      abbiamo ucciso noi). Fino al 2026-08-08 quel blocco abortiva l'intero
#      script SEMPRE: sul log vivo di Pro i run del 19/26 luglio e 2 agosto si
#      fermano tra il conteggio e il verdetto, zero righe dopo. Il ramo DOWN — il
#      suggerimento di fallback locale, l'unica ragione per cui la sonda esiste —
#      era irraggiungibile esattamente sul percorso per cui era stato scritto.
#
#   2. PARLARE quando fallisce. launchd lo invoca DIRETTAMENTE (nessun
#      cron-runner, nessun wr2-cron-wrapper): niente ricevuta, nessuno legge
#      l'exit code, `missed_runs_alerter` guarda righe WarRoom e non label
#      launchd. Tre run morti e nessuna superficie in grado di accorgersene.
#
# Leggerlo non distingue "non ha sparato" da "non e passato di li" (W107), e su
# M5 il default `/Users/nuzantara/.local/bin/agy` non esiste — senza
# WR2_IG_AGY_BIN questa macchina e strutturalmente incapace di riprodurre il
# rosso (W108 GOTCHA). Per questo il binario della sonda e overridabile.
#
# Uso: bash scripts/tests/test_wr2_ig_metrics_analyst_wrapper.sh

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER_SRC="$REPO/infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh"

PASS=0
FAIL=0

ok() {
    echo "  ✓ $1"
    PASS=$((PASS + 1))
}
ko() {
    echo "  ✗ $1"
    FAIL=$((FAIL + 1))
}
check() {
    local name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then ok "$name"; else ko "$name — atteso [$expected], ottenuto [$actual]"; fi
}
has() {
    local name="$1" needle="$2" file="$3"
    if [ -f "$file" ] && grep -qF -- "$needle" "$file"; then ok "$name"; else ko "$name — '$needle' assente da $file"; fi
}
hasnt() {
    local name="$1" needle="$2" file="$3"
    if [ ! -f "$file" ] || ! grep -qF -- "$needle" "$file"; then ok "$name"; else ko "$name — '$needle' presente in $file e non doveva"; fi
}

# Monta un mondo finto: HOME propria (il wrapper scrive log, legge la coda e
# risolve il gateway sotto $HOME), agy finto con l'esito richiesto, claude finto
# che registra il prompt ricevuto, gateway finto che registra di essere stato
# chiamato.
#
# I pezzi si montano SEPARATAMENTE di proposito: il gateway si puo omettere, cosi
# la guardia "gateway assente" e giudicabile essendo l'unica cosa rotta.
make_world() {
    local root="$1" agy_rc="$2" agy_answer="$3" claude_rc="$4" want_gateway="$5"
    mkdir -p "$root/bin" "$root/nuzantara/apps/war-room/output/queue" \
             "$root/nuzantara/scripts" "$root/logs" \
             "$root/.claude/skills/bali-zero-brand/_proposed-amendments"

    # 12 caroselli pubblicati CON metriche: sopra la soglia di 10, cosi il
    # pre-flight non esce 0 prima di arrivare all'health-check.
    python3 - "$root/nuzantara/apps/war-room/output/queue/human-review-queue.json" <<'PY'
import json, sys
items = [{"state": "published", "engagement_metrics": {"likes": 10 + i}} for i in range(12)]
json.dump({"items": items}, open(sys.argv[1], "w"))
PY

    cat > "$root/bin/agy" <<EOF
#!/bin/bash
cat > /dev/null
[ -n "$agy_answer" ] && echo "$agy_answer"
exit $agy_rc
EOF

    # Il finto claude scrive il prompt ricevuto su disco: e l'unico modo di
    # provare che il GEMINI_HINT viaggia davvero fino all'agente invece di
    # essere solo calcolato.
    cat > "$root/bin/claude" <<EOF
#!/bin/bash
for a in "\$@"; do printf '%s\n' "\$a"; done > "$root/claude-argv.txt"
echo "fake claude answer"
exit $claude_rc
EOF

    if [ "$want_gateway" = "yes" ]; then
        cat > "$root/nuzantara/scripts/tg_notify.py" <<EOF
import sys
open("$root/gateway-called.txt", "w").write(" ".join(sys.argv[1:]))
print("fake gateway ok")
EOF
    fi

    chmod +x "$root/bin/agy" "$root/bin/claude"
}

run_wrapper() {
    local root="$1" wrapper="${2:-$WRAPPER_SRC}"
    env -i \
        HOME="$root" \
        PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin" \
        TMPDIR="$root/tmp" \
        WR2_IG_AGY_BIN="$root/bin/agy" \
        WR2_IG_CLAUDE_BIN="$root/bin/claude" \
        CLAUDE_CODE_OAUTH_TOKEN_1=faketoken \
        WR2_IG_METRICS_TIMEOUT_SECS=70 \
        WR2_IG_METRICS_POLL_SECS=1 \
        WR2_IG_METRICS_KILL_GRACE_SECS=1 \
        /bin/bash "$wrapper" >/dev/null 2>&1
}

TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/wr2-ig-corpus.XXXXXX")"
trap 'rm -rf "$TMPROOT"' EXIT

# ---------------------------------------------------------------- COLPEVOLEZZA 1
# agy GIU: la sonda esce non-zero. Il wrapper deve SOPRAVVIVERE, scrivere il
# verdetto DOWN e arrivare in fondo. Prima della cura moriva qui.
echo "[1] agy DOWN — il wrapper sopravvive e il ramo DOWN e raggiungibile"
W="$TMPROOT/down"; mkdir -p "$W/tmp"
make_world "$W" 1 "" 0 yes
run_wrapper "$W"; rc=$?
LOG="$W/logs/wr2-ig-metrics-analyst.log"
check "rc del wrapper" 0 "$rc"
has "verdetto DOWN scritto" "gemini health-check: DOWN" "$LOG"
has "arriva in fondo (done)" "wr2-ig-metrics-analyst done" "$LOG"
has "probe_rc e quello di AGY, non i 143 del watchdog" "probe_rc=1" "$LOG"
has "il suggerimento di fallback VIAGGIA fino all'agente" "DO NOT call agy" "$W/claude-argv.txt"

# ---------------------------------------------------------------- COLPEVOLEZZA 2
# Lo stesso, con un codice d'uscita diverso: pinna l'`exit "$AGY_RC"` esplicito.
# Senza quello il rc catturato e sempre il reap del watchdog e non dice nulla
# sulla cosa sondata.
echo "[2] agy DOWN con rc=7 — il rc catturato e di agy"
W="$TMPROOT/down7"; mkdir -p "$W/tmp"
make_world "$W" 7 "" 0 yes
run_wrapper "$W" >/dev/null
has "probe_rc=7" "probe_rc=7" "$W/logs/wr2-ig-metrics-analyst.log"

# ------------------------------------------------------------------- INNOCENZA 1
# agy SU: nessun suggerimento, verdetto UP, e comunque nessun allarme.
echo "[3] agy UP — verdetto UP, nessun hint, nessun allarme"
W="$TMPROOT/up"; mkdir -p "$W/tmp"
make_world "$W" 0 "AGYUP" 0 yes
run_wrapper "$W"; rc=$?
LOG="$W/logs/wr2-ig-metrics-analyst.log"
check "rc del wrapper" 0 "$rc"
has "verdetto UP scritto" "gemini health-check: UP" "$LOG"
hasnt "nessun hint di fallback nel prompt" "DO NOT call agy" "$W/claude-argv.txt"
hasnt "nessuna telefonata al gateway su successo" "telegram notify" "$LOG"
if [ -f "$W/gateway-called.txt" ]; then ko "il gateway e stato chiamato su un run riuscito"; else ok "gateway non chiamato su un run riuscito"; fi

# ---------------------------------------------------------------- COLPEVOLEZZA 3
# claude fallisce: il wrapper deve PARLARE, e il rc del gateway va loggato.
echo "[4] claude exit=3 — il wrapper parla e logga l'rc"
W="$TMPROOT/fail"; mkdir -p "$W/tmp"
make_world "$W" 0 "AGYUP" 3 yes
run_wrapper "$W"; rc=$?
LOG="$W/logs/wr2-ig-metrics-analyst.log"
check "il rc del job non viene mangiato dall'allarme" 3 "$rc"
has "l'rc del gateway e loggato" "telegram notify rc=0" "$LOG"
has "l'interprete e assoluto" "python=/" "$LOG"
if [ -f "$W/gateway-called.txt" ]; then
    ok "il gateway e stato invocato davvero"
    has "tier p0" "--tier p0" "$W/gateway-called.txt"
    has "source nominato" "--source wr2-ig-metrics-analyst" "$W/gateway-called.txt"
else
    ko "il gateway NON e stato invocato su un run fallito"
fi

# ---------------------------------------------------------------- COLPEVOLEZZA 4
# Gateway assente: "armato a vuoto" deve essere LOGGATO, non silenzioso, e non
# deve cambiare l'esito del job.
echo "[5] gateway assente — lo dice, e non altera l'esito"
W="$TMPROOT/nogw"; mkdir -p "$W/tmp"
make_world "$W" 0 "AGYUP" 3 no
run_wrapper "$W"; rc=$?
check "il rc del job resta il suo" 3 "$rc"
has "l'assenza del gateway e loggata" "gateway MISSING" "$W/logs/wr2-ig-metrics-analyst.err.log"

# ---------------------------------------------------------------- COLPEVOLEZZA 5
# Coda illeggibile: il pre-flight stampava 0 su QUALSIASI eccezione, quindi "il
# file non c'e" era indistinguibile da "meno di 10 pubblicati" — e il secondo esce
# 0 in silenzio dopo aver scritto uno stub. Deve nominare la causa e allarmare.
echo "[6] coda illeggibile — 'nessuna misura' non e 'nessun dato'"
W="$TMPROOT/noqueue"; mkdir -p "$W/tmp"
make_world "$W" 0 "AGYUP" 0 yes
rm -f "$W/nuzantara/apps/war-room/output/queue/human-review-queue.json"
run_wrapper "$W"; rc=$?
check "esce 66, non 0" 66 "$rc"
has "la causa e nominata nel log" "ERR:FileNotFoundError" "$W/logs/wr2-ig-metrics-analyst.log"
has "l'ERR distingue le due cose" "it is 'no measurement'" "$W/logs/wr2-ig-metrics-analyst.err.log"
if [ -f "$W/gateway-called.txt" ] && grep -qF "UNREADABLE" "$W/gateway-called.txt"; then
    ok "il gateway e stato invocato e il messaggio dice UNREADABLE"
else
    ko "coda illeggibile: nessun allarme (o allarme senza causa)"
fi
if ls "$W/.claude/skills/bali-zero-brand/_proposed-amendments/"*insufficient-data* >/dev/null 2>&1; then
    ko "ha scritto lo stub 'insufficient data' su un guasto di lettura"
else
    ok "nessuno stub 'insufficient data' su un guasto di lettura"
fi

# ---------------------------------------------------------------- COLPEVOLEZZA 6
# Morte NON diagnosticata: TMPDIR inesistente fa fallire il primo `mktemp`, che
# sta fuori dalla regione con errexit disarmato. Prima di oggi lo script moriva
# li in totale silenzio, come nell'errexit bug che questo commit cura: nominare
# solo le uscite a cui ho pensato e l'errore W107 alla scala di un solo organo.
echo "[7] morte non diagnosticata — la voce di ultima istanza parla"
W="$TMPROOT/nodiag"
make_world "$W" 0 "AGYUP" 0 yes   # NOTA: $W/tmp deliberatamente NON creata
run_wrapper "$W"; rc=$?
if [ "$rc" -eq 0 ]; then ko "atteso un rc non-zero, ottenuto 0"; else ok "esce non-zero (rc=$rc)"; fi
has "arriva oltre il pre-flight prima di morire" "published-with-metrics count: 12" "$W/logs/wr2-ig-metrics-analyst.log"
if [ -f "$W/gateway-called.txt" ] && grep -qF "NO diagnosis" "$W/gateway-called.txt"; then
    ok "il gateway dice che e morto SENZA diagnosi (fatto diverso da un guasto nominato)"
else
    ko "morte fuori da ogni percorso noto: nessuna voce"
fi

# ------------------------------------------------------------------- MUTAZIONE
# Rimette errexit dentro e attorno alla sonda — cioe ESATTAMENTE il codice di
# prima — e pretende che il caso [1] diventi rosso. Un corpus che resta verde
# con la cura disattivata non prova nulla (W116).
echo "[mutazione] senza il disarmo di errexit, il caso [1] deve fallire"
# Il mutante va COSTRUITO e va provato che sia costruito: la prima stesura di
# questo blocco falliva la mutazione (rimuoveva 2 righe dove ne pretendeva 3),
# quindi il file non veniva scritto e il wrapper "moriva" con rc=127 perche non
# esisteva — verde su premessa vacua, la malattia stessa che il corpus previene
# (W116). Ora la costruzione fallita e un FAIL, non un pass gratuito.
MUT="$TMPROOT/mutant.sh"
if python3 - "$WRAPPER_SRC" "$MUT" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
lines = open(src).read().splitlines(keepends=True)
start = next(i for i, l in enumerate(lines) if 'AGY="${WR2_IG_AGY_BIN' in l)
end = next(i for i, l in enumerate(lines) if i > start and 'AGY_OUT="$(cat' in l)
out = [l for i, l in enumerate(lines)
       if not (start <= i <= end and l.strip() in ("set +e", "set -e"))]
removed = len(lines) - len(out)
assert removed == 3, f"mutazione inattesa: rimosse {removed} righe (attese 3)"
open(dst, "w").write("".join(out))
PY
then
    ok "mutante costruito (3 righe di disarmo errexit rimosse)"
else
    ko "la MUTAZIONE non e stata costruita — il controllo sotto sarebbe vacuo"
fi
if [ -s "$MUT" ] && bash -n "$MUT" 2>/dev/null; then
    ok "il mutante e uno script valido (non un file assente)"
    W="$TMPROOT/mut"; mkdir -p "$W/tmp"
    make_world "$W" 1 "" 0 yes
    run_wrapper "$W" "$MUT"; mut_rc=$?
    MUTLOG="$W/logs/wr2-ig-metrics-analyst.log"
    if [ "$mut_rc" -eq 0 ] && grep -qF "wr2-ig-metrics-analyst done" "$MUTLOG" 2>/dev/null; then
        ko "il mutante sopravvive: il corpus non sta provando il disarmo di errexit"
    elif [ ! -f "$MUTLOG" ] || ! grep -qF "published-with-metrics count" "$MUTLOG" 2>/dev/null; then
        ko "il mutante e morto PRIMA dell'health-check (rc=$mut_rc): sta misurando la poverta del mondo finto, non la cura"
    else
        ok "il mutante arriva al conteggio e muore nell'health-check (rc=$mut_rc, nessun 'done') — e la cura a tenere in vita il run"
    fi
else
    ko "mutante assente o non valido — controllo di mutazione non eseguito"
fi

echo
echo "risultato: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ]
