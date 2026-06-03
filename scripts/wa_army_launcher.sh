#!/usr/bin/env bash
# wa_army_launcher.sh — lancia una sessione-armata Claude Code in tmux da un comando WhatsApp.
#
# Registro estendibile: ogni armata è un file <NAME>.txt in docs/army-prompts/.
# Per aggiungere un'armata non serve toccare questo script — basta creare il .txt.
#
# Comandi (chiamati dal bridge OpenClaw WhatsApp):
#   wa_army_launcher.sh list                 → elenca le armate disponibili (un nome per riga)
#   wa_army_launcher.sh status               → elenca le armate IN CORSO (sessioni tmux army-*)
#   wa_army_launcher.sh launch <NAME>        → lancia l'armata <NAME>
#   wa_army_launcher.sh kill <NAME>          → termina l'armata <NAME>
#
# launch stdout: "LAUNCHED <tmux-session> <log-path>" oppure "ERROR <motivo>" (exit !=0).
# Il bridge legge questa riga per rispondere su WhatsApp.
#
# Flusso di launch:
#   1. valida che <NAME>.txt esista
#   2. apre tmux detached, dentro gira `claude` interattivo in autonomia col prompt-armata
#      (la sessione fa il proprio PASSO 0 = crea il suo worktree isolato)
#   3. pipe-pane cattura l'output su un log
#   4. lancia wa_army_watcher.sh in background → su "ARMY_DONE" manda alert Telegram

set -euo pipefail

# SECURITY: questo script è invocato da un handler remoto (WhatsApp bridge) e lancia claude
# in autonomia. I path NON sono env-overridable, così un'eventuale env-injection non può
# dirottare QUALE script/prompt/binario viene eseguito. Solo LOG_DIR/MODEL restano regolabili
# (innocui: una dir di log o il nome modello non cambiano cosa-viene-eseguito).
REPO_ROOT="$HOME/Desktop/nuzantara"
PROMPTS_DIR="$REPO_ROOT/docs/army-prompts"
CLAUDE_BIN="$HOME/.local/bin/claude"
WATCHER="$REPO_ROOT/scripts/wa_army_watcher.sh"
CLAUDE_MODEL="${WA_ARMY_MODEL:-claude-opus-4-8}"
LOG_DIR="${WA_ARMY_LOG_DIR:-$HOME/Library/Logs/wa-army}"

# Solo nomi-armata che sono basename puri [A-Za-z0-9._-]: niente path traversal, niente
# argomenti che escono da docs/army-prompts/. (resolve_name + questo guard = doppio fondo.)
_valid_army_name() { [[ "$1" =~ ^[A-Za-z0-9._-]+$ ]]; }

err()  { echo "ERROR $*"; exit 1; }

# Normalizza un nome armata: "spec-1" / "SPEC1" / "1" → cerca il file giusto.
# Ritorna il NOME canonico (basename senza .txt) o vuoto se non trovato.
resolve_name() {
  local raw="$1" f
  # match esatto
  if [ -f "$PROMPTS_DIR/${raw}.txt" ]; then echo "$raw"; return 0; fi
  # match case-insensitive su basename
  for f in "$PROMPTS_DIR"/*.txt; do
    [ -e "$f" ] || continue
    local base; base="$(basename "$f" .txt)"
    if [ "$(echo "$base" | tr '[:upper:]' '[:lower:]')" = "$(echo "$raw" | tr '[:upper:]' '[:lower:]')" ]; then
      echo "$base"; return 0
    fi
  done
  # se è solo un numero, prova SPEC-N e S<N>
  local num; num="$(echo "$raw" | grep -oE '[0-9]+' | head -1 || true)"
  if [ -n "$num" ]; then
    for cand in "SPEC-${num}" "S${num}"; do
      if [ -f "$PROMPTS_DIR/${cand}.txt" ]; then echo "$cand"; return 0; fi
    done
  fi
  return 1
}

cmd_list() {
  local f any=0
  for f in "$PROMPTS_DIR"/*.txt; do
    [ -e "$f" ] || continue
    any=1
    local base; base="$(basename "$f" .txt)"
    # descrizione: riga "# DESC: ..." se presente, altrimenti prima riga di testo
    local desc; desc="$(grep -m1 -E '^# DESC:' "$f" 2>/dev/null | sed -E 's/^# DESC:[[:space:]]*//' || true)"
    [ -n "$desc" ] || desc="$(grep -m1 -E '^[A-Za-z]' "$f" 2>/dev/null | cut -c1-70 || true)"
    echo "${base} — ${desc}"
  done
  [ "$any" = "1" ] || echo "(nessuna armata in $PROMPTS_DIR)"
}

cmd_status() {
  local sessions; sessions="$(tmux list-sessions 2>/dev/null | grep -oE '^army-[^:]+' || true)"
  if [ -z "$sessions" ]; then echo "(nessuna armata in corso)"; return 0; fi
  echo "$sessions"
}

cmd_kill() {
  local name="$1" canon
  _valid_army_name "$name" || err "nome armata non valido: '$name'"
  canon="$(resolve_name "$name")" || err "armata sconosciuta: '$name'"
  local killed=0 s
  for s in $(tmux list-sessions 2>/dev/null | grep -oE '^army-[^:]+' || true); do
    # le sessioni sono army-<slug>-<timestamp>; matcha sullo slug
    if echo "$s" | grep -qiE "^army-$(slug "$canon")-"; then
      tmux kill-session -t "$s" 2>/dev/null && killed=1 && echo "KILLED $s"
    fi
  done
  [ "$killed" = "1" ] || echo "(nessuna sessione in corso per $canon)"
}

# slug: nome armata → token tmux-safe (no maiuscole, no caratteri strani)
slug() { echo "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-|-$//g'; }

cmd_launch() {
  local raw="$1" canon
  [ -n "$raw" ] || err "manca il nome. Uso: /lancia <NOME>  (vedi /armate per la lista)"
  _valid_army_name "$raw" || err "nome armata non valido: '$raw' (solo lettere/numeri/.-_)"
  canon="$(resolve_name "$raw")" || err "armata '$raw' non trovata. Scrivi /armate per la lista."
  _valid_army_name "$canon" || err "nome armata risolto non valido: '$canon'"

  local prompt_file="$PROMPTS_DIR/${canon}.txt"
  [ -f "$prompt_file" ]            || err "prompt non trovato: $prompt_file"
  [ -x "$CLAUDE_BIN" ]             || err "claude CLI non eseguibile: $CLAUDE_BIN"
  command -v tmux >/dev/null 2>&1  || err "tmux non installato"

  local sl; sl="$(slug "$canon")"

  # Una sola istanza per armata alla volta.
  if tmux list-sessions 2>/dev/null | grep -qE "^army-${sl}-"; then
    err "armata ${canon} già in corso. Vedi /armate-status, o killa con /ferma ${canon}"
  fi

  mkdir -p "$LOG_DIR"
  local ts session log_file prompt_tmp
  ts="$(date +%Y%m%d-%H%M%S)"
  session="army-${sl}-${ts}"
  log_file="$LOG_DIR/${session}.log"
  prompt_tmp="$LOG_DIR/${session}.prompt"

  cp "$prompt_file" "$prompt_tmp"

  # tmux detached, working dir = repo root (la sessione fa il proprio PASSO 0).
  tmux new-session -d -s "$session" -c "$REPO_ROOT" -x 220 -y 50
  tmux pipe-pane -t "$session" -o "cat >> '$log_file'"

  # claude interattivo in autonomia piena col prompt-armata come messaggio iniziale.
  tmux send-keys -t "$session" \
    "export ORCHESTRATE_GATE_OFF=1 AGENT_BROKER_ENABLED=true CLAUDE_CONFIG_DIR=\$HOME/.claude; '$CLAUDE_BIN' --model '$CLAUDE_MODEL' --dangerously-skip-permissions \"\$(cat '$prompt_tmp')\"" \
    Enter

  # watcher → Telegram su ARMY_DONE.
  if [ -x "$WATCHER" ]; then
    nohup "$WATCHER" "$session" "$canon" "$log_file" >/dev/null 2>&1 &
  fi

  echo "LAUNCHED $session $log_file"
}

ACTION="${1:-}"; shift || true
case "$ACTION" in
  list)    cmd_list ;;
  status)  cmd_status ;;
  launch)  cmd_launch "${1:-}" ;;
  kill)    cmd_kill "${1:-}" ;;
  *)       err "azione sconosciuta: '$ACTION' (list|status|launch|kill)" ;;
esac
