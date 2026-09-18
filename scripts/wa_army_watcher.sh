#!/usr/bin/env bash
# wa_army_watcher.sh — sorveglia il log di una sessione-armata e notifica via Telegram.
#
# Lanciato in background da wa_army_launcher.sh. Tail-segue il log della sessione tmux;
# quando vede "ARMY_DONE <NAME> <pr>" (l'armata ha aperto la PR draft) manda un alert
# Telegram e termina. Se la sessione tmux muore senza ARMY_DONE entro il timeout, manda
# un alert di "armata terminata senza PR" (probabile crash/halt).
#
# La sessione cambia pane: il context guard (tmux_jump.sh) sposta claude in una NUOVA
# finestra della stessa sessione e chiude la vecchia. pipe-pane è per-pane, la finestra
# nuova nasce senza pipe e ARMY_DONE non arriva più nel log (2026-09-18: armate finite
# segnalate come "scaduto"/"terminata SENZA PR"). Ogni giro il watcher aggancia i pane
# ancora senza pipe — SOLO quelli: `pipe-pane -o` su un pane già agganciato lo SGANCIA
# (toggle, misurato su tmux 3.7b) e spegnerebbe il log del launcher.
#
# Uso: wa_army_watcher.sh <tmux-session> <army-name> <log-file>

set -euo pipefail

SESSION="${1:?manca tmux-session}"
ARMY="${2:?manca army-name}"
LOG_FILE="${3:?manca log-file}"

# Chat Telegram destinatario degli alert armata (Antonello, @Balizerobot).
TG_CHAT_ID="${WA_ARMY_TG_CHAT_ID:-8865544795}"
# Timeout massimo di sorveglianza (default 6h). Oltre, smette di seguire.
MAX_WATCH_S="${WA_ARMY_MAX_WATCH_S:-21600}"
# Intervallo di polling (default 15s); il tmux da usare (seam per i test).
POLL_S="${WA_ARMY_POLL_S:-15}"
TMUX_BIN="${TMUX_BIN:-tmux}"

# Recupera il bot token dallo stesso modo del resto dell'organismo: dai LaunchAgent plist
# che lo hanno valorizzato (NON in chiaro qui — Law: secret non hardcoded).
get_tg_token() {
  local p t
  for p in "$HOME"/Library/LaunchAgents/com.nuzantara.sentinel.plist \
           "$HOME"/Library/LaunchAgents/com.balizero.*.plist \
           "$HOME"/Library/LaunchAgents/com.nuzantara.*.plist; do
    [ -e "$p" ] || continue
    t="$(plutil -convert json -o - "$p" 2>/dev/null \
         | python3 -c 'import sys,json; print(json.load(sys.stdin).get("EnvironmentVariables",{}).get("TELEGRAM_BOT_TOKEN",""))' 2>/dev/null || true)"
    if [ -n "$t" ] && [[ "$t" == *:* ]]; then echo "$t"; return 0; fi
  done
  # fallback: env esplicito
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && echo "$TELEGRAM_BOT_TOKEN" && return 0
  return 1
}

tg_send() {
  local text="$1" token
  token="$(get_tg_token)" || { echo "watcher: no telegram token" >&2; return 1; }
  curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${TG_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    -d "disable_web_page_preview=true" >/dev/null 2>&1 || true
}

repipe_unpiped_panes() {
  local pane piped
  while read -r pane piped; do
    [ -n "$pane" ] && [ "$piped" = "0" ] || continue
    "$TMUX_BIN" pipe-pane -t "$pane" -o "cat >> '$LOG_FILE'" 2>/dev/null || true
  done < <("$TMUX_BIN" list-panes -s -t "$SESSION" -F '#{pane_id} #{pane_pipe}' 2>/dev/null || true)
}

START_TS=$(date +%s)

# Segui il log finché: (a) troviamo ARMY_DONE, (b) la sessione tmux muore, (c) timeout.
while true; do
  repipe_unpiped_panes

  # (c) timeout
  now=$(date +%s)
  if [ $(( now - START_TS )) -ge "$MAX_WATCH_S" ]; then
    tg_send "⏱️ Armata ${ARMY}: watcher scaduto (${MAX_WATCH_S}s) senza PR. Controlla: tmux attach -t ${SESSION}"
    exit 0
  fi

  # (a) ARMY_DONE nel log?
  if [ -f "$LOG_FILE" ] && grep -qE "ARMY_DONE ${ARMY}\b" "$LOG_FILE" 2>/dev/null; then
    line="$(grep -E "ARMY_DONE ${ARMY}\b" "$LOG_FILE" | tail -1)"
    pr="$(echo "$line" | sed -E "s/.*ARMY_DONE ${ARMY}[[:space:]]*//" | tr -d '\r')"
    tg_send "🎖️ Armata ${ARMY} HA FINITO — PR draft pronta: ${pr:-(vedi log)}
Mergio? Rispondi a mano dopo review.
Log: ${LOG_FILE}
Attach: tmux attach -t ${SESSION}"
    exit 0
  fi

  # (b) sessione morta senza ARMY_DONE?
  if ! "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null; then
    # piccola grazia: l'ARMY_DONE potrebbe essere appena stato scritto prima del kill
    sleep 2
    if [ -f "$LOG_FILE" ] && grep -qE "ARMY_DONE ${ARMY}\b" "$LOG_FILE" 2>/dev/null; then
      line="$(grep -E "ARMY_DONE ${ARMY}\b" "$LOG_FILE" | tail -1)"
      pr="$(echo "$line" | sed -E "s/.*ARMY_DONE ${ARMY}[[:space:]]*//" | tr -d '\r')"
      tg_send "🎖️ Armata ${ARMY} HA FINITO — PR draft: ${pr:-(vedi log)}"
    else
      tail_excerpt="$(tail -8 "$LOG_FILE" 2>/dev/null | tr -d '\r' | cut -c1-400 || true)"
      tg_send "⚠️ Armata ${ARMY}: sessione terminata SENZA PR (probabile halt/crash).
Ultime righe:
${tail_excerpt}
Log: ${LOG_FILE}"
    fi
    exit 0
  fi

  sleep "$POLL_S"
done
