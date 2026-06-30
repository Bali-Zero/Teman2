#!/bin/zsh
# Mata Garuda Classifier Worker — classifies garuda:enriched via Ollama qwen3:8b
# Invoked by com.matagaruda.classifier.adaptive.plist every 5 minutes.
#
# W9 cicatrix 2026-05-22: classifier consumer group on garuda:enriched had been
# stuck 32 days (consumer classifier-1 idle=2760607955ms), lag=1570 + pending=0.
# Library existed (classifier_worker.py with qwen3:8b + keyword fallback) but
# never had a runner script + LaunchAgent. Mirror of W6 NER recovery.
#
# W7 lesson applied from day 1: flock(1) semaphore prevents concurrent-cron
# stacking. qwen3:8b is faster than qwen3.5:9b NER (~3-8s vs 5-15s) so 5min
# cadence is comfortable for 200-msg batch, but lock is cheap insurance.
#
# TCC-safe: calls venv python directly.

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Self-locating from THIS script's path (cicatrix #1: no hardcoded HOME-fork).
REPO="${MATA_GARUDA_REPO:-${0:A:h:h}}"
VENV_PY="$REPO/.venv/bin/python"
LOCK="/tmp/matagaruda-classifier-worker.lock"
FLOCK="/opt/homebrew/bin/flock"

if [ ! -x "$VENV_PY" ]; then
    echo "[classifier-worker] venv python not found at $VENV_PY" >&2
    exit 1
fi

if [ ! -x "$FLOCK" ]; then
    echo "[classifier-worker] flock not found at $FLOCK — running without dedup" >&2
    cd "$REPO"
    PYTHONPATH="$REPO" "$VENV_PY" scripts/run_classifier_worker.py
    exit $?
fi

set +e
"$FLOCK" --nonblock --exclusive --conflict-exit-code 75 "$LOCK" -c "cd '$REPO' && PYTHONPATH='$REPO' '$VENV_PY' scripts/run_classifier_worker.py"
RC=$?
set -e

if [ "$RC" -eq 75 ]; then
    echo "[classifier-worker] previous run still active — skipped this tick" >&2
    exit 0
fi
exit $RC
