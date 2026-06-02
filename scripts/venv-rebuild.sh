#!/usr/bin/env bash
# venv-rebuild.sh — machine-agnostic backend venv (re)builder.
#
# Why: .venv/ is gitignored and path-specific. When a checkout is rsync'd or
# cloned to a different machine (Pro /Users/nuzantara, Air-M5 /Users/balizero),
# the copied .venv keeps the ORIGINAL machine's pyenv/mise path baked into
# pyvenv.cfg + the python binary's dylib refs → dyld crash on first run
# ("Library not loaded: .../libpython3.11.dylib"). The fix is never to sync the
# venv as files — it's to sync requirements.txt (already git-tracked) and let
# each machine rebuild its own venv locally. This script is that rebuild.
#
# Usage:   bash scripts/venv-rebuild.sh
#          REQ=requirements.lock.txt bash scripts/venv-rebuild.sh   # alt manifest
#          FORCE=1 bash scripts/venv-rebuild.sh                     # always recreate
#
# Detects a stale/broken venv (wrong-machine path OR dyld crash) and recreates
# it from scratch using the local Python (mise-managed if present, else python3).
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../apps/backend-rag" && pwd)"
cd "$BACKEND_DIR"

REQ="${REQ:-requirements.txt}"
VENV=".venv"

# Resolve the local Python 3.11 (mise shim is machine-correct; fall back to python3).
pick_python() {
  if command -v mise >/dev/null 2>&1; then
    local p; p="$(mise which python 2>/dev/null || true)"
    [ -n "$p" ] && { echo "$p"; return; }
  fi
  command -v python3.11 || command -v python3
}
PY="$(pick_python)"
echo "→ local python: $PY ($("$PY" --version 2>&1))"

# Is the existing venv healthy on THIS machine? (binary runs without dyld crash)
venv_healthy() {
  [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import sys" >/dev/null 2>&1
}

if [ "${FORCE:-0}" = "1" ] || ! venv_healthy; then
  if [ -d "$VENV" ]; then
    STAMP="$(cat /dev/urandom | LC_ALL=C tr -dc 'a-f0-9' | head -c 8 || echo dead)"
    echo "→ existing venv is stale/broken on this machine — archiving to ${VENV}.dead-${STAMP}"
    mv "$VENV" "${VENV}.dead-${STAMP}"
  fi
  echo "→ creating fresh venv with $PY"
  "$PY" -m venv "$VENV"
else
  echo "→ existing venv is healthy on this machine (skip recreate; pass FORCE=1 to override)"
fi

echo "→ upgrading pip"
"$VENV/bin/python" -m pip install --upgrade pip -q

echo "→ installing $REQ (this can take several minutes — torch/transformers are large)"
"$VENV/bin/pip" install -r "$REQ"

echo "→ smoke test"
"$VENV/bin/python" -c "import sys; print('prefix:', sys.prefix)"
"$VENV/bin/python" -c "import fastapi, pydantic; print('core imports OK')" 2>&1 || {
  echo "!! smoke import failed — inspect the install log above" >&2; exit 1; }

echo "✓ venv ready at $BACKEND_DIR/$VENV"
echo "  remember: if you ran 'pip install <new-pkg>', add it to requirements.txt and commit"
echo "  so the other machines pick it up on 'git pull' + this script."
