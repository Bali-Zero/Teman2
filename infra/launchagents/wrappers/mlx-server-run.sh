#!/bin/bash
# mlx-server-run.sh — keep mlx_lm.server alive as a real blocking supervisor loop.
# Deliberately NOT a one-shot under launchd KeepAlive (cicatrix #7: KeepAlive on a
# transient exec = restart storm). This wrapper IS the long-running process; launchd
# only restarts it if the whole supervisor dies. Lives in ~/scripts, NOT ~/Desktop
# (cicatrix W84: launchd loses TCC grant to ~/Desktop and dies green-but-dead).
set -u

MLX_BIN="$HOME/mlx-env/bin/mlx_lm.server"
MODEL="mlx-community/Qwen3-8B-4bit"
# Speculative decoding: small draft model proposes tokens, the 8B verifies in batch.
# Tuned 2026-06-20 via clean serial sweep: num-draft=2 is the sweet spot (+26% on code),
# beats 3 (+12%) and 5 (-5%, too many rejected drafts). +~0.37GB RAM (24GB host has room).
DRAFT_MODEL="mlx-community/Qwen3-0.6B-4bit"
NUM_DRAFT="2"
HOST="127.0.0.1"
PORT="8080"
LOG="$HOME/mlx-server.log"

log() { echo "[$(/bin/date '+%Y-%m-%dT%H:%M:%S')] supervisor: $*" >> "$LOG"; }

if [ ! -x "$MLX_BIN" ]; then
  log "FATAL: $MLX_BIN not found/executable — exiting so launchd surfaces it"
  exit 78  # EX_CONFIG: honest hard-fail, not a silent green
fi

log "starting supervisor for $MODEL on $HOST:$PORT"
while true; do
  log "launching mlx_lm.server (model=$MODEL draft=$DRAFT_MODEL num-draft=$NUM_DRAFT)"
  # Foreground (no &) so this loop blocks on the server's lifetime.
  "$MLX_BIN" --model "$MODEL" --host "$HOST" --port "$PORT" \
    --draft-model "$DRAFT_MODEL" --num-draft-tokens "$NUM_DRAFT" >> "$LOG" 2>&1
  code=$?
  log "mlx_lm.server exited code=$code — restarting in 5s"
  sleep 5
done
