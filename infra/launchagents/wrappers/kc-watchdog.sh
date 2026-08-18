#!/bin/bash
# kc-watchdog.sh — tiene giu knowledgeconstructiond sul Mini.
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
# KILL SWITCH:  touch ~/.kc-watchdog-off     (il watchdog esce senza fare nulla)
# DISINSTALLA:  launchctl bootout gui/$(id -u)/com.nuzantara.kc-watchdog
#               rm ~/Library/LaunchAgents/com.nuzantara.kc-watchdog.plist
[ -f "$HOME/.kc-watchdog-off" ] && exit 0
LOG="$HOME/logs/kc-watchdog.log"
mkdir -p "$(dirname "$LOG")"
killed=0
# ancora di fine riga: senza, il pattern prende anche altri processi (lezione della stessa notte)
for p in $(pgrep -x knowledgeconstructiond 2>/dev/null); do
  rss=$(ps -o rss= -p "$p" 2>/dev/null | tr -d ' ')
  if kill -9 "$p" 2>/dev/null; then
    killed=$((killed+1))
    echo "$(date '+%Y-%m-%d %H:%M:%S') killed pid=$p rss=${rss}KB" >> "$LOG"
  fi
done
# rotazione semplice: il log non deve crescere all infinito su un server
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ]; then
  tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit 0
