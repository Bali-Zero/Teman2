#!/usr/bin/env bash
# sync-damar.sh — Pro → Damar (unidirezionale, mai viceversa)

DAMAR="damar"  # usa ~/.ssh/config — locale diretto, remoto via ProxyJump air
LOG="$HOME/.claude/logs/sync-damar.log"
mkdir -p "$(dirname $LOG)"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "Sync Pro → Damar avviato"

# Plugins
rsync -az --delete \
  --exclude='blocklist*.json' \
  ~/.claude/plugins/ \
  $DAMAR:~/.claude/plugins/ && log "plugins ok" || log "plugins FAILED"

# Skills
rsync -az --delete \
  ~/.claude/skills/ \
  $DAMAR:~/.claude/skills/ && log "skills ok" || log "skills FAILED"

log "Sync completato"
