#!/bin/bash
# mini.kc_watchdog — tiene giu knowledgeconstructiond sul Mini.
# Born via scripts/organ_birth.py conventions (DNA/GENOME 2026-07-06): genes
# retrofitted 2026-08-19 after the healer's kc-watchdog-canon PR failed the
# organ-conformance gate (G1/G2/G5/G9 missing) — no behavior change, same kill
# logic as the version promoted from ~/scripts/kc-watchdog.sh verbatim.
# Canon: infra/launchagents/wrappers/kc-watchdog.sh
# Live:  ~/scripts/kc-watchdog.sh (declared pair, node=mini)
#
# PERCHE ESISTE (misurato 2026-08-19):
#   knowledgeconstructiond (Apple Intelligence / IntelligencePlatformCore) itera la rubrica
#   UN CONTATTO ALLA VOLTA chiedendo gli avatar a contactsd: ~1.336 richieste/minuto, ognuna
#   respinta con "Skipping: required keys missing". Con ~100.000 contatti non finisce MAI:
#   sfonda il proprio tetto di memoria (ActiveSoft 50 MB, misurato a 145 MB), il kernel lo
#   uccide ("Full corpse enqueued"), lui riparte da zero e ricomincia. Costo: 40% di CPU su
#   se stesso + 85% su contactsd, che e solo il servo che risponde.
#   `launchctl disable` NON basta: rinasce comunque (XPC on-demand + respawn dopo corpse).
#   Su un server headless senza schermo ne Siri, questo servizio non serve a nulla.
#
# DISINSTALLA:  launchctl bootout gui/$(id -u)/com.nuzantara.kc-watchdog
#               rm ~/Library/LaunchAgents/com.nuzantara.kc-watchdog.plist

set -u   # G9_fail_visible: unset vars crash, they do not expand empty

ORGAN_ID="mini.kc_watchdog"
LOG="$HOME/logs/kc-watchdog.log"
SIDECAR_DIR="$HOME/.organism/last_seen"
mkdir -p "$(dirname "$LOG")"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every run)
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

# G5_kill_switch — operator stop without uninstall; disabled heartbeat keeps
# the healer from resurrecting an intentionally-stopped organ. The legacy
# file switch (~/.kc-watchdog-off) is kept for quick console access; the
# _ENABLED env var is the gene the gate + healer contract expect.
if [ -f "$HOME/.kc-watchdog-off" ] || [ "${KC_WATCHDOG_ENABLED:-true}" = "false" ]; then
    echo "$(ts) kill switch active — exiting" >> "$LOG"
    heartbeat "disabled" "kill switch"
    exit 0
fi

killed=0
# ancora di fine riga: senza, il pattern prende anche altri processi (lezione della stessa notte)
for p in $(pgrep -x knowledgeconstructiond 2>/dev/null); do
  rss=$(ps -o rss= -p "$p" 2>/dev/null | tr -d ' ')
  if kill -9 "$p" 2>/dev/null; then
    killed=$((killed+1))
    echo "$(ts) killed pid=$p rss=${rss}KB" >> "$LOG"
  fi
done
# rotazione semplice: il log non deve crescere all infinito su un server
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ]; then
  tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

heartbeat "ok" "killed=$killed"
exit 0
