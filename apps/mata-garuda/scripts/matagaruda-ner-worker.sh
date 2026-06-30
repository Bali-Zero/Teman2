#!/bin/zsh
# Mata Garuda NER Worker — extracts entities from garuda:enriched via Ollama qwen3.5:9b
# Invoked by com.matagaruda.ner.adaptive.plist every 5 minutes.
#
# W6 cicatrix 2026-05-22: runner existed (scripts/run_ner_worker.py) but no
# LaunchAgent triggered it. NER consumer group on garuda:enriched had been
# stuck for 31 days, 45 pending + lag=1403.
#
# W7 cicatrix 2026-05-22: NER batch (cap 200 msgs, qwen3.5:9b ~5-15s each =
# up to 30min) outlasts the 5min cron interval. Without a lock, concurrent
# cron invocations stack: observed 2 concurrent run_ner_worker.py processes
# (PIDs 8616 + 18302). Add flock(1) semaphore — concurrent cron skips
# silently (exit 0) if previous still active, so launchd doesn't see false
# failures.
#
# TCC-safe: calls venv python directly (adhoc-signed binaries bypass TCC).

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Load secrets (no quoting trap here — NER needs only OLLAMA_HOST, no FLY tokens)
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Self-locating from THIS script's path (cicatrix #1: no hardcoded HOME-fork).
REPO="${MATA_GARUDA_REPO:-${0:A:h:h}}"
VENV_PY="$REPO/.venv/bin/python"
LOCK="/tmp/matagaruda-ner-worker.lock"
FLOCK="/opt/homebrew/bin/flock"

if [ ! -x "$VENV_PY" ]; then
    echo "[ner-worker] venv python not found at $VENV_PY" >&2
    exit 1
fi

run_worker() {
    cd "$REPO"
    PYTHONPATH="$REPO" "$VENV_PY" scripts/run_ner_worker.py
}

if [ ! -x "$FLOCK" ]; then
    echo "[ner-worker] flock not found at $FLOCK — running without dedup (risk overlapping)" >&2
    run_worker
    exit $?
fi

# Acquire exclusive non-blocking lock. If another run holds it, exit 0
# (silent) so launchd does not treat it as failure. Otherwise execute.
set +e
"$FLOCK" --nonblock --exclusive --conflict-exit-code 75 "$LOCK" -c "cd '$REPO' && PYTHONPATH='$REPO' '$VENV_PY' scripts/run_ner_worker.py"
RC=$?
set -e

if [ "$RC" -eq 75 ]; then
    # Conflict — previous run still active. This is expected behavior, not an error.
    echo "[ner-worker] previous run still active — skipped this tick" >&2
    exit 0
fi

exit $RC
