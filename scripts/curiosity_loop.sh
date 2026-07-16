#!/bin/bash
# Curiosity Loop — SYMBIOSIS Pillar 6 cron wrapper
# Invoked by ~/Library/LaunchAgents/com.graph.curiosity-loop.plist (04:30 WITA)
#
# gap_detector.scan_all_domains() → prioritize → tier dispatch
# → Self-RAG grade → propose-only in kg_proposals.
# Zero approves via `kg-propose apply <id>`. No auto-apply.
#
# VADEMECUM §11: launchd does NOT inherit PATH/HOME.

set -euo pipefail

# Machine-aware repo + python (Pro vs Air). Dirname fallback so a future
# user rename doesn't silently fail.
case "$(whoami)" in
    nuzantara)      REPO="$HOME/nuzantara" ;;
    antonellosiano) REPO="$HOME/Projects/nuzantara" ;;
    *)
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
        ;;
esac

LOG_DIR="$HOME/logs/cron"
mkdir -p "$LOG_DIR"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    # shellcheck disable=SC1091
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Pick a Python that can actually run this app, not just any python3 on PATH.
# curiosity.models imports enum.StrEnum (3.11+); the Pro's ~/.pyenv/shims/python3
# is an orphan shim that resolves to system 3.9.6 (no StrEnum), and so does
# /usr/bin/python3 — both would die on ImportError before touching the DB
# (cicatrix "Esiste != Armato": the cron was green but would crash at import).
# So we VERIFY capability instead of guessing by path. The repo venv (3.11.11)
# is the source of truth; we still fall back to whatever else can import StrEnum.
_py_ok() { [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; }

PY=""
for cand in \
    "$REPO/apps/backend-rag/.venv/bin/python" \
    "$HOME/.pyenv/shims/python3" \
    "/opt/homebrew/bin/python3" \
    "/usr/bin/python3"; do
    if _py_ok "$cand"; then PY="$cand"; break; fi
done

if [ -z "$PY" ]; then
    echo "FATAL curiosity_loop: no Python >= 3.11 found (need enum.StrEnum). " \
         "Tried repo venv, pyenv shim, homebrew, /usr/bin. Aborting." >&2
    exit 1
fi

cd "$REPO"
export PYTHONPATH="$REPO/apps/graph-engine/src:$REPO/packages/cell-core:${PYTHONPATH:-}"

exec "$PY" scripts/gap_fill_autonomous.py \
    >> "$LOG_DIR/curiosity-loop.log" 2>&1
