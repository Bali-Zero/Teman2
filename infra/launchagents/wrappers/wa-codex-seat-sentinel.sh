#!/usr/bin/env bash
# wa-codex-seat-sentinel.sh — wrapper cron per scripts/wa_codex_seat_sentinel.py.
#
# Invocato da crontab attraverso `cron-runner.sh`, che scrive la ricevuta e —
# dalla cura W107 — allarma sull'exit non-zero. Questo wrapper esiste solo per
# tre cose che il python non puo fare da se: scegliere l'interprete giusto,
# dire ad alta voce se quell'interprete non c'e, e non mangiarsi il codice di
# uscita per strada. Runs in-place from the repo checkout as `nuzantara` —
# DIFFERENT identity from the probe (Piece A), which runs as zantara-codex.
#
# Le tre trappole che questo file evita, tutte pagate in cicatrici:
#
#   W108 — l'interprete e ASSOLUTO, mai risolto via PATH. Un allarme che gira
#          sull'interprete la cui corruzione e fra le cause del guasto che deve
#          riportare condivide il modo di guasto della cosa che riporta.
#   W101 — nessuna pipeline nuda sotto `set -e`: errexit aborta SULLA pipeline
#          e la cattura del codice diventa codice morto proprio sul percorso
#          per cui esiste. Qui l'errexit e disarmato attorno al job e il codice
#          e catturato, non dedotto dall'essere sopravvissuti.
#   W81  — se il payload non c'e, il cron e armato a vuoto. Lo diciamo con un
#          exit 2 (CANNOT-VERIFY) invece di uscire 0 come se fosse tutto a
#          posto: non-ho-potuto-guardare non e "va tutto bene".
#
# Runs in-place from the repo checkout (like wa-session-liveness.sh) — NO
# declared-pairs entry: there is no separate HOME-fork copy to drift from.
#
# Exit: 0 = ho guardato entrambe le fonti (anche se un verdetto e RED: quel
# verdetto viaggia via Telegram) · 2 = non ho potuto leggere il gauge.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ORGAN="$REPO/scripts/wa_codex_seat_sentinel.py"
PYTHON="$REPO/apps/backend-rag/.venv/bin/python"

# Signature guard: se la root derivata non contiene l'organo, la derivazione e
# sbagliata — e proseguire significherebbe misurare un altro repo (W105).
if [ ! -f "$ORGAN" ]; then
    echo "CANNOT-VERIFY: organo assente a $ORGAN (REPO derivata: $REPO)" >&2
    exit 2
fi

if [ ! -x "$PYTHON" ]; then
    echo "CANNOT-VERIFY: interprete assente a $PYTHON" >&2
    exit 2
fi

set +e
"$PYTHON" "$ORGAN" "$@"
RC=$?
set -e

echo "wa-codex-seat-sentinel rc=$RC"
exit "$RC"
