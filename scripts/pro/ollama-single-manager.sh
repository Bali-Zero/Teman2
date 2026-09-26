#!/bin/bash
# ollama-single-manager.sh — the ONE Ollama manager on Pro, with memory caps.
# Genesis 2026-08-18: kernel panic post-mortem found TWO managers fighting —
# Raycast-owned `ollama serve` held :11434 while homebrew.mxcl.ollama crash-looped
# on "address already in use"; the uncapped instance kept 2 models resident (18GB).
# Canon note: replaces homebrew.mxcl.ollama (brew services stays stopped).
# If a foreign serve holds the port (Raycast until its extension is disabled),
# stand by visibly and take over at the next tick once the port frees.
set -u

ORGAN_ID="pro.ollama_single_manager"
LOG_DIR="$HOME/logs"
LOG="$LOG_DIR/ollama-single-manager.log"
SIDECAR_DIR="$HOME/.organism/last_seen"
mkdir -p "$LOG_DIR"

hb() { # $1 status, $2 note — heartbeat sidecar on EVERY exit path
    mkdir -p "$SIDECAR_DIR"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "nuzantara" ]; then
    hb "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

if [ "${OLLAMA_SINGLE_MANAGER_ENABLED:-true}" = "false" ]; then
    hb "disabled" "kill switch"
    exit 0
fi

if curl -sf -m 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] :11434 busy (foreign serve) — standing by" >> "$LOG"
    hb "blocked" "foreign serve on 11434"
    exit 0
fi

hb "ok" "starting serve (capped)"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MAX_LOADED_MODELS=2
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_KEEP_ALIVE=30m
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
# Memory budget, measured 2026-09-26 while swap sat at 7.2/8 GB and jetsam LOWSWAP
# was killing daemons. The qwen3.5:9b runner's footprint was 17 GB, of which the
# KV cache at 32768 ctx was only 544 MiB: 8.1 GiB was llama-server's host-RAM
# prompt cache (default --cache-ram 8192, which Ollama never passes), full with
# 42 prompts of ~90 MiB each. The runner inherits this env, so cap it here.
export LLAMA_ARG_CACHE_RAM=1024
# Pinned, not left to the VRAM-tier default (4k/32k/256k): 36 of 827 articles
# need more than 16384 tokens (prompt + translation) in translate-articles.py.
export OLLAMA_CONTEXT_LENGTH=32768
echo "[$(date '+%Y-%m-%d %H:%M:%S')] starting capped serve" >> "$LOG"
exec /opt/homebrew/bin/ollama serve >> "$LOG" 2>&1
