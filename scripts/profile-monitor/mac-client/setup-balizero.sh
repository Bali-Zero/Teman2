#!/usr/bin/env bash
# setup-balizero.sh — Setup unificato profilo Mac balizero
#
# Esegue in sequenza tutto quello che serve per consegnare un Mac aziendale al dipendente:
#   1. Verifica profilo macOS = balizero (refuse altrimenti)
#   2. Verifica connettività Tailscale al Pro
#   3. Installa daemon profile-monitor (alert check-out durante ore lavoro)
#   4. Installa Employee Handbook PDF immutable sul Desktop
#   5. Riepilogo finale + test end-to-end
#
# Eseguito SOLO da Antonello dal profilo balizero del Mac del dipendente.
# Singolo argomento: <nome_dipendente> (es. surya, ari, krisna)
#
# Uso:
#   cd ~/Downloads/mac-client
#   bash setup-balizero.sh surya
#
# Disinstallazione completa (solo Antonello):
#   chflags nouchg ~/Desktop/employee-handbook-v1-ID.pdf
#   rm ~/Desktop/employee-handbook-v1-ID.pdf
#   launchctl bootout gui/$(id -u)/com.balizero.profile-monitor
#   rm ~/Library/LaunchAgents/com.balizero.profile-monitor.plist
#   rm -rf ~/Library/Application\ Support/BaliZero

set -euo pipefail

EMPLOYEE="${1:-}"
if [[ -z "$EMPLOYEE" ]]; then
    echo "❌ Uso: bash setup-balizero.sh <nome_dipendente>"
    echo "    Es: bash setup-balizero.sh surya"
    echo ""
    echo "    Nomi validi: surya vino damar krisna adit ari asya sahira"
    exit 1
fi

VALID_EMPLOYEES="surya vino damar krisna adit ari asya sahira"
if [[ ! " $VALID_EMPLOYEES " =~ " $EMPLOYEE " ]]; then
    echo "❌ Employee non valido: $EMPLOYEE"
    echo "   Validi: $VALID_EMPLOYEES"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Banner ────────────────────────────────────────────────────────────
cat << 'BANNER'

  ╔══════════════════════════════════════════════════════════════╗
  ║                                                              ║
  ║          B A L I   Z E R O   —   M a c   S e t u p           ║
  ║                                                              ║
  ║          Powered by humans, fueled by a thinking engine.     ║
  ║                                                              ║
  ╚══════════════════════════════════════════════════════════════╝

BANNER

echo "  Dipendente:   $EMPLOYEE"
echo "  Data setup:   $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  Script dir:   $SCRIPT_DIR"
echo ""

# ─── STEP 0: Profilo macOS = balizero ──────────────────────────────────
echo "━━━ STEP 0/4 — Verifica profilo macOS ━━━"
CURRENT_USER=$(whoami)
if [[ "$CURRENT_USER" != "balizero" ]]; then
    echo "❌ Devi eseguire questo setup dal profilo macOS 'balizero'"
    echo "   Profilo attuale: $CURRENT_USER"
    echo ""
    echo "   PROCEDURA CORRETTA:"
    echo "   1. Crea profilo balizero: System Settings → Users & Groups → Add User → Standard"
    echo "   2. Logout dal profilo personale del dipendente"
    echo "   3. Login al profilo balizero"
    echo "   4. Riesegui questo script"
    exit 1
fi
echo "✅ Profilo macOS verificato: balizero"
echo ""

# ─── STEP 1: Tailscale + connettività al Pro ───────────────────────────
echo "━━━ STEP 1/4 — Verifica Tailscale + Pro reachable ━━━"
WRAPPER_HOST="100.107.22.111"
WRAPPER_PORT=9099
WRAPPER_URL="http://${WRAPPER_HOST}:${WRAPPER_PORT}"

if ! command -v tailscale &>/dev/null && [ ! -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]; then
    echo "⚠️  Tailscale non rilevato."
    echo "   1. Scarica Tailscale: https://tailscale.com/download/mac"
    echo "   2. Login con account Bali Zero (Antonello invita)"
    echo "   3. Riesegui questo script"
    exit 1
fi
echo "   Tailscale installato ✓"

echo "   Verifico connettività verso Pro ($WRAPPER_HOST)..."
if ! curl -s --max-time 5 "$WRAPPER_URL/health" | grep -q '"status": "ok"'; then
    echo "❌ Wrapper Pro non raggiungibile su $WRAPPER_URL/health"
    echo "   Possibili cause:"
    echo "   - Tailscale non connesso (verifica icona menubar)"
    echo "   - Non sei nel tailnet 'balizero' (Antonello deve invitare device)"
    echo "   - Pro spento o profile-monitor wrapper offline"
    exit 1
fi
echo "✅ Wrapper Pro raggiungibile"
echo ""

# ─── STEP 2: Daemon profile-monitor ────────────────────────────────────
echo "━━━ STEP 2/4 — Installazione daemon profile-monitor ━━━"

INSTALL_DIR="$HOME/Library/Application Support/BaliZero"
mkdir -p "$INSTALL_DIR"

if [[ ! -f "$SCRIPT_DIR/profile-monitor" ]]; then
    echo "❌ Binario profile-monitor non trovato: $SCRIPT_DIR/profile-monitor"
    exit 1
fi

cp "$SCRIPT_DIR/profile-monitor" "$INSTALL_DIR/profile-monitor"
chmod +x "$INSTALL_DIR/profile-monitor"
echo "   Binario copiato → $INSTALL_DIR/profile-monitor ✓"

PLIST_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$PLIST_DIR"
PLIST_PATH="$PLIST_DIR/com.balizero.profile-monitor.plist"

sed \
    -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
    -e "s|__HOME__|$HOME|g" \
    -e "s|__EMPLOYEE__|$EMPLOYEE|g" \
    "$SCRIPT_DIR/com.balizero.profile-monitor.plist.template" > "$PLIST_PATH"

mkdir -p "$HOME/Library/Logs"
echo "   LaunchAgent generato → $PLIST_PATH ✓"

launchctl bootout "gui/$(id -u)/com.balizero.profile-monitor" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
sleep 2

if launchctl list com.balizero.profile-monitor &>/dev/null; then
    PID=$(launchctl list com.balizero.profile-monitor | awk -F'"' '/PID/ {print $4}' | head -1)
    echo "✅ Daemon attivo (PID $PID)"
else
    echo "❌ Daemon non avviato. Controlla log:"
    echo "   $HOME/Library/Logs/balizero-profile-monitor.error.log"
    exit 1
fi

sleep 1
if grep -q "DAEMON_START" "$HOME/Library/Logs/balizero-profile-events.log" 2>/dev/null; then
    echo "   Evento DAEMON_START registrato ✓"
fi
echo ""

# ─── STEP 3: Employee Handbook immutable ───────────────────────────────
echo "━━━ STEP 3/4 — Installazione Employee Handbook (immutable) ━━━"

SOURCE_PDF="$SCRIPT_DIR/handbook-asset/employee-handbook-v1-ID.pdf"
DEST_PDF="$HOME/Desktop/employee-handbook-v1-ID.pdf"

if [[ ! -f "$SOURCE_PDF" ]]; then
    echo "❌ Handbook PDF non trovato: $SOURCE_PDF"
    exit 1
fi

if [[ -f "$DEST_PDF" ]]; then
    echo "   File già presente, rimuovo flag immutable per aggiornamento..."
    chflags nouchg "$DEST_PDF" 2>/dev/null || true
    rm -f "$DEST_PDF"
fi

cp "$SOURCE_PDF" "$DEST_PDF"
chmod 0444 "$DEST_PDF"
chflags uchg "$DEST_PDF"
echo "   Handbook copiato → $DEST_PDF"
echo "   Permessi: 0444 (read-only)"
echo "   Flag immutable (uchg) applicato"

# Test immutability
if rm "$DEST_PDF" 2>/dev/null; then
    echo "❌ ATTENZIONE: file ancora eliminabile"
    exit 1
fi
if mv "$DEST_PDF" "${DEST_PDF}.test" 2>/dev/null; then
    mv "${DEST_PDF}.test" "$DEST_PDF" 2>/dev/null || true
    echo "❌ ATTENZIONE: file ancora rinominabile"
    exit 1
fi
echo "✅ Handbook NON spostabile, NON rinominabile, NON eliminabile (verificato)"
echo ""

# ─── STEP 4: Test end-to-end ────────────────────────────────────────────
echo "━━━ STEP 4/4 — Verifica finale + summary ━━━"

LOG_DIR="$HOME/Library/Logs"
DAEMON_LOG="$LOG_DIR/balizero-profile-events.log"

echo ""
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  SUMMARY SETUP                                              │"
echo "  ├─────────────────────────────────────────────────────────────┤"
printf "  │  Employee:           %-39s │\n" "$EMPLOYEE"
printf "  │  Profilo macOS:      %-39s │\n" "balizero (Standard)"
printf "  │  Daemon profile:     %-39s │\n" "ATTIVO (PID $PID)"
printf "  │  Handbook PDF:       %-39s │\n" "Desktop, immutable"
printf "  │  Tailscale:          %-39s │\n" "connesso al tailnet balizero"
echo "  └─────────────────────────────────────────────────────────────┘"
echo ""
echo "  File installati:"
echo "    • $INSTALL_DIR/profile-monitor (binary 64KB)"
echo "    • $PLIST_PATH (LaunchAgent)"
echo "    • $DEST_PDF (Handbook PDF, immutable)"
echo "    • $DAEMON_LOG (event log)"
echo ""
echo "  Test manuale check-out (opzionale):"
echo "    Apple menu → Logout 'balizero'... → riconferma"
echo "    → Antonello dovrebbe ricevere alert Telegram entro 10 secondi"
echo "    → Login di nuovo a balizero, evento CHECKIN registrato"
echo ""
echo "✅ Setup balizero COMPLETO per $EMPLOYEE"
echo ""
