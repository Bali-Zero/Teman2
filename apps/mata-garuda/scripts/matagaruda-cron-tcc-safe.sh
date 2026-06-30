#!/bin/zsh
# Mata Garuda generic cron wrapper — TCC-safe (W19+W20 pattern)
#
# Usage:
#   matagaruda-cron-tcc-safe.sh [OPTIONS] <entry> [log_label]
#
# <entry> is a .py file path (default) OR, with --module, a python module name.
# OPTIONS (all optional — without them this behaves EXACTLY as the original
# <entry.py> [label] form, so the 10 existing repo crons are unaffected):
#   --module <m>     run `python -m <m>` instead of `python <entry.py>`
#                    (entry then names the module, e.g. mata_garuda.bridge.nerve)
#   --flock <name>   single-instance gate via flock(1); a second concurrent run
#                    exits 75 and is skipped (W7 anti-stacking lesson)
#   --window <a>-<b> only run when local hour is in [a, b); outside → exit 0
#                    (gap_consumer operating window 06-22 WITA)
#   --source-env <f> additionally source <f> (relative to $HOME or absolute)
#                    before exec (e.g. .cell-bridge-state/wa-media.env, Mythos-P3)
#
# Why this wrapper exists at all: under launchd's TCC sandbox, /bin/zsh cannot
# OPEN a script living under ~/Desktop (macOS TCC) — a bare shell wrapper there
# dies "/bin/zsh: can't open input file" (exit 127). This wrapper is itself a
# shell script under ~/Desktop, BUT launchd execs it and it immediately execs
# the venv PYTHON (adhoc-signed → TCC-bypassing) on the real work. The shell
# never opens a second ~/Desktop file, so TCC never bites. That is the ONLY
# TCC-safe shape for repo-resident mata_garuda crons — promoting per-cron shell
# wrappers into the repo does NOT work (verified 2026-06-30, A/B: ~/Desktop=127,
# /tmp=runs). This wrapper absorbs the per-cron logic (flock/window/module/env)
# the 7 HOME-fork shell wrappers used to carry, so they can converge here.
#
# Eliminates the /bin/bash -lc + source .venv/bin/activate failure that launchd
# TCC sandbox produced as false-noise in .error.log (W20 cicatrix 2026-05-22).

set -e
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# ── option parse (additive; defaults preserve the original behavior) ────────
MODULE=""
FLOCK_NAME=""
WINDOW=""
EXTRA_ENV=""
while [ $# -gt 0 ]; do
    case "$1" in
        --module)     MODULE="$2"; shift 2 ;;
        --flock)      FLOCK_NAME="$2"; shift 2 ;;
        --window)     WINDOW="$2"; shift 2 ;;
        --source-env) EXTRA_ENV="$2"; shift 2 ;;
        --) shift; break ;;
        -*) echo "[ERROR] unknown option: $1" >&2; exit 2 ;;
        *) break ;;
    esac
done

if [ $# -lt 1 ] && [ -z "$MODULE" ]; then
    echo "[ERROR] usage: $0 [--module m|--flock n|--window a-b|--source-env f] <entry_or_module> [log_label]" >&2
    exit 2
fi

ENTRY="$1"
LABEL="${2:-$(basename "$ENTRY" .py)}"

# ── operating window (exit 0 outside, so launchd records a clean skip) ───────
if [ -n "$WINDOW" ]; then
    WIN_START="${WINDOW%-*}"
    WIN_END="${WINDOW#*-}"
    HOUR=$(date +%H)
    # strip leading zero so 08 isn't read as octal
    HOUR=$((10#$HOUR))
    if [ "$HOUR" -lt "$WIN_START" ] || [ "$HOUR" -ge "$WIN_END" ]; then
        echo "[$LABEL] outside operating window ${WIN_START}-${WIN_END} (hour=$HOUR) — skipping"
        exit 0
    fi
fi

# Path-aware: derive repo root from THIS script's location
# (<repo>/apps/mata-garuda/scripts/matagaruda-cron-tcc-safe.sh).
SCRIPT_DIR="${0:A:h}"            # zsh: absolute dir of this script
REPO_ROOT="${REPO_ROOT:-${SCRIPT_DIR:h:h:h}}"   # up 3: scripts→mata-garuda→apps→repo
APP_ROOT="$REPO_ROOT/apps/mata-garuda"
VENV_PY="$APP_ROOT/.venv/bin/python"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Optional extra env file (e.g. cell-bridge-state/wa-media.env, Mythos-P3 —
# BRIDGE_API_KEY lives there, 0600, not in .nuzantara-secrets.env).
if [ -n "$EXTRA_ENV" ]; then
    case "$EXTRA_ENV" in /*) EF="$EXTRA_ENV" ;; *) EF="$HOME/$EXTRA_ENV" ;; esac
    if [ -f "$EF" ]; then
        set -a
        . "$EF"
        set +a
    fi
fi

# Canonical Redis = Pro (127.0.0.1). Was 100.93.236.6 (Mini) → caused
# the live split-brain: 10 crons read Mini while monitor/archiver/rollup
# read Pro, and 982 alerts sat unsent. Fixed canonical to Pro 2026-06-30.
export GARUDA_REDIS_HOST="${GARUDA_REDIS_HOST:-127.0.0.1}"  # canonical=Pro (Zero 2026-06-30, Stage1)
export PYTHONPATH="${PYTHONPATH:-$APP_ROOT}"

[ -x "$VENV_PY" ] || { echo "[ERROR] venv python missing: $VENV_PY" >&2; exit 2; }
if [ -z "$MODULE" ]; then
    [ -f "$ENTRY" ] || { echo "[ERROR] entry script missing: $ENTRY" >&2; exit 2; }
fi

cd "$APP_ROOT"

# Build the python invocation. -u forces unbuffered output for real-time logs.
# W21: do NOT redirect stdout/stderr — let launchd's StandardOutPath /
# StandardErrorPath capture them separately (preserves W8 signal/noise split).
if [ -n "$MODULE" ]; then
    set -- "$VENV_PY" -u -m "$MODULE"
else
    set -- "$VENV_PY" -u "$ENTRY"
fi

# ── single-instance gate (flock) ────────────────────────────────────────────
# A concurrent run exits 75 and is skipped — prevents the W7 cron-stacking
# (two run_ner_worker.py at once). Degrade gracefully if flock is absent.
if [ -n "$FLOCK_NAME" ]; then
    FLOCK_BIN="/opt/homebrew/bin/flock"
    LOCK="/tmp/matagaruda-${FLOCK_NAME}.lock"
    if [ -x "$FLOCK_BIN" ]; then
        # flock runs the command; quote each arg for the -c string
        CMD=""
        for a in "$@"; do CMD="$CMD '${a//\'/\'\\\'\'}'"; done
        exec "$FLOCK_BIN" --nonblock --exclusive --conflict-exit-code 75 "$LOCK" -c "$CMD"
    else
        echo "[$LABEL] flock not found at $FLOCK_BIN — running without dedup" >&2
    fi
fi

exec "$@"
