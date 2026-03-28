#!/bin/bash
# setup-air.sh — Allinea Air dopo git pull
# Risolve: venv corrotto, path diversi, dipendenze mancanti
# Uso: ssh air 'cd ~/Projects/nuzantara && bash scripts/setup-air.sh'

set -euo pipefail

REPO_DIR="/Users/antonellosiano/Projects/nuzantara"
BACKEND_DIR="$REPO_DIR/apps/backend-rag"
PYENV_PYTHON="$HOME/.pyenv/versions/3.11.9/bin/python3"
VENV_DIR="$BACKEND_DIR/venv"
SENTINEL_WRAPPER="$REPO_DIR/sentinel"
LOG_DIR="$REPO_DIR/logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo "========================================="
echo "  Air Setup — $(date '+%Y-%m-%d %H:%M')"
echo "========================================="

# --- Verifiche pre-flight ---
if [ "$(whoami)" != "antonellosiano" ]; then
    fail "Questo script va eseguito su Air (antonellosiano), non su $(whoami)"
fi

if [ ! -d "$REPO_DIR" ]; then
    fail "Repo non trovato: $REPO_DIR"
fi

if [ ! -f "$PYENV_PYTHON" ]; then
    fail "Python 3.11.9 non trovato via pyenv. Installa: pyenv install 3.11.9"
fi

cd "$REPO_DIR"

# --- 1. Venv ---
echo ""
echo "--- 1. Python venv ---"

REBUILD_VENV=false

if [ ! -d "$VENV_DIR" ]; then
    warn "venv non esiste, lo creo"
    REBUILD_VENV=true
elif [ ! -f "$VENV_DIR/bin/python3" ]; then
    warn "venv/bin/python3 mancante, ricreo"
    REBUILD_VENV=true
elif ! "$VENV_DIR/bin/python3" --version &>/dev/null; then
    warn "venv/bin/python3 rotto (symlink loop?), ricreo"
    REBUILD_VENV=true
else
    VENV_PY_VER=$("$VENV_DIR/bin/python3" --version 2>&1)
    if [[ "$VENV_PY_VER" != *"3.11"* ]]; then
        warn "venv usa $VENV_PY_VER invece di 3.11, ricreo"
        REBUILD_VENV=true
    fi
fi

if [ "$REBUILD_VENV" = true ]; then
    rm -rf "$VENV_DIR"
    "$PYENV_PYTHON" -m venv "$VENV_DIR"
    ok "venv creato con $($VENV_DIR/bin/python3 --version)"
else
    ok "venv OK — $($VENV_DIR/bin/python3 --version)"
fi

# --- 2. Dipendenze minime ---
echo ""
echo "--- 2. Dipendenze ---"

DEPS=(httpx ruff pytest pytest-asyncio)
MISSING=()

for dep in "${DEPS[@]}"; do
    if ! "$VENV_DIR/bin/python3" -c "import ${dep//-/_}" &>/dev/null; then
        MISSING+=("$dep")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "  Installo: ${MISSING[*]}"
    "$VENV_DIR/bin/pip" install --quiet "${MISSING[@]}"
    ok "Dipendenze installate"
else
    ok "Tutte le dipendenze presenti"
fi

# --- 3. Sentinel wrapper ---
echo ""
echo "--- 3. Sentinel wrapper ---"

EXPECTED_SENTINEL='#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec apps/backend-rag/venv/bin/python3 apps/core/sentinel.py "$@"'

if [ ! -f "$SENTINEL_WRAPPER" ]; then
    echo "$EXPECTED_SENTINEL" > "$SENTINEL_WRAPPER"
    chmod +x "$SENTINEL_WRAPPER"
    ok "Sentinel wrapper creato"
elif ! grep -q "apps/core/sentinel.py" "$SENTINEL_WRAPPER"; then
    echo "$EXPECTED_SENTINEL" > "$SENTINEL_WRAPPER"
    chmod +x "$SENTINEL_WRAPPER"
    ok "Sentinel wrapper fixato (puntava al path sbagliato)"
else
    ok "Sentinel wrapper OK"
fi

# --- 4. Cron venv path ---
echo ""
echo "--- 4. Cron venv path ---"

CRON_CURRENT=$(crontab -l 2>/dev/null || true)
if echo "$CRON_CURRENT" | grep -q "\.venv/bin/python3"; then
    echo "$CRON_CURRENT" | sed 's|\.venv/bin/python3|venv/bin/python3|g' | crontab -
    ok "Cron fixato: .venv → venv"
else
    ok "Cron path OK (usa venv)"
fi

# --- 5. Logs directory ---
echo ""
echo "--- 5. Logs ---"

mkdir -p "$LOG_DIR"
ok "Logs directory presente"

# --- 6. Verifica finale ---
echo ""
echo "--- 6. Verifica ---"

ERRORS=0

# Python funziona
if "$VENV_DIR/bin/python3" -c "import httpx; print(f'  httpx {httpx.__version__}')" 2>/dev/null; then
    ok "Python + httpx"
else
    warn "Python o httpx rotto"
    ERRORS=$((ERRORS + 1))
fi

# Ruff funziona
if "$VENV_DIR/bin/python3" -m ruff --version &>/dev/null; then
    ok "ruff $($VENV_DIR/bin/python3 -m ruff --version 2>&1)"
else
    warn "ruff non funziona"
    ERRORS=$((ERRORS + 1))
fi

# Sentinel eseguibile
if [ -x "$SENTINEL_WRAPPER" ]; then
    ok "Sentinel eseguibile"
else
    warn "Sentinel non eseguibile"
    ERRORS=$((ERRORS + 1))
fi

# System doctor importabile
if "$VENV_DIR/bin/python3" -c "import ast; ast.parse(open('scripts/system_doctor.py').read()); print('  system_doctor.py parseable')" 2>/dev/null; then
    ok "System doctor parseable"
else
    warn "System doctor ha errori di sintassi"
    ERRORS=$((ERRORS + 1))
fi

# Git sync check
LOCAL_HEAD=$(git rev-parse --short=8 HEAD 2>/dev/null)
REMOTE_HEAD=$(ssh -o ConnectTimeout=3 pro 'cd ~/Desktop/nuzantara && git rev-parse --short=8 HEAD' 2>/dev/null || echo "UNREACHABLE")
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    ok "Git sync OK ($LOCAL_HEAD)"
elif [ "$REMOTE_HEAD" = "UNREACHABLE" ]; then
    warn "Pro non raggiungibile per sync check"
else
    warn "Git OUT OF SYNC — Air: ${LOCAL_HEAD} | Pro: ${REMOTE_HEAD}"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "========================================="
if [ $ERRORS -eq 0 ]; then
    ok "Air setup completo — 0 errori"
else
    warn "Air setup completo — $ERRORS problemi trovati"
fi
echo "========================================="
# Last verified: 2026-03-28 18:01

