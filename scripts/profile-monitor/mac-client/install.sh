#!/usr/bin/env bash
# install.sh — installer del profile-monitor sul Mac dipendente
#
# Esegui SOLO sul profilo macOS `balizero` (verificato all'avvio):
#   bash install.sh <employee_name>
#
# Es:  bash install.sh surya
#
# Cosa fa:
#   1. Verifica di essere sul profilo balizero (refuse altrimenti)
#   2. Verifica connettività Tailscale al Pro
#   3. Copia binario in ~/Library/Application Support/BaliZero/
#   4. Installa LaunchAgent in ~/Library/LaunchAgents/
#   5. Bootstrap del LaunchAgent
#   6. Verifica daemon attivo + healthcheck endpoint Pro
#
# NO sudo richiesto — tutto user-scope.

set -euo pipefail

EMPLOYEE="${1:-}"
if [[ -z "$EMPLOYEE" ]]; then
    echo "❌ Uso: bash install.sh <employee_name>"
    echo "    Es: bash install.sh surya"
    exit 1
fi

VALID_EMPLOYEES="surya vino damar krisna adit ari asya sahira"
if [[ ! " $VALID_EMPLOYEES " =~ " $EMPLOYEE " ]]; then
    echo "❌ Employee non valido: $EMPLOYEE"
    echo "   Validi: $VALID_EMPLOYEES"
    exit 1
fi

echo "═══ Bali Zero Profile-Monitor Installer ═══"
echo "Employee: $EMPLOYEE"
echo ""

# 1. Verifica profilo macOS = balizero
CURRENT_USER=$(whoami)
if [[ "$CURRENT_USER" != "balizero" ]]; then
    echo "❌ Devi eseguire questo installer dal profilo macOS 'balizero'"
    echo "   Profilo attuale: $CURRENT_USER"
    echo ""
    echo "   1. Crea profilo balizero (System Settings → Users & Groups → Add User → Standard)"
    echo "   2. Login al profilo balizero"
    echo "   3. Riesegui questo script"
    exit 1
fi
echo "✅ Profilo macOS verificato: balizero"

# 2. Verifica Tailscale + connettività al Pro
WRAPPER_HOST="100.107.22.111"
WRAPPER_PORT=9099
WRAPPER_URL="http://${WRAPPER_HOST}:${WRAPPER_PORT}"

if ! command -v tailscale &>/dev/null && [ ! -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]; then
    echo "⚠️  Tailscale non rilevato. Installa Tailscale e fai join al tailnet 'balizero' prima di continuare."
    exit 1
fi

echo "  Verifico connettività verso Pro ($WRAPPER_HOST)..."
if ! curl -s --max-time 5 "$WRAPPER_URL/health" | grep -q '"status": "ok"'; then
    echo "❌ Wrapper Pro non raggiungibile su $WRAPPER_URL/health"
    echo "   Possibili cause:"
    echo "   - Tailscale non connesso"
    echo "   - Non sei nel tailnet 'balizero'"
    echo "   - Pro spento"
    exit 1
fi
echo "✅ Wrapper Pro raggiungibile"

# 3. Copia binario
INSTALL_DIR="$HOME/Library/Application Support/BaliZero"
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/profile-monitor" "$INSTALL_DIR/profile-monitor"
chmod +x "$INSTALL_DIR/profile-monitor"
echo "✅ Binario installato: $INSTALL_DIR/profile-monitor"

# 4. Genera plist da template
PLIST_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$PLIST_DIR"
PLIST_PATH="$PLIST_DIR/com.balizero.profile-monitor.plist"

sed \
    -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
    -e "s|__HOME__|$HOME|g" \
    -e "s|__EMPLOYEE__|$EMPLOYEE|g" \
    "$SCRIPT_DIR/com.balizero.profile-monitor.plist.template" > "$PLIST_PATH"

# Crea log dir
mkdir -p "$HOME/Library/Logs"

echo "✅ LaunchAgent installato: $PLIST_PATH"

# 5. Bootstrap (se già caricato, ricarica)
launchctl bootout "gui/$(id -u)/com.balizero.profile-monitor" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
sleep 2

# 6. Verifica daemon attivo
if launchctl list com.balizero.profile-monitor &>/dev/null; then
    PID=$(launchctl list com.balizero.profile-monitor | awk -F'"' '/PID/ {print $4}' | head -1)
    echo "✅ Daemon attivo (PID $PID)"
else
    echo "❌ Daemon non avviato. Controlla log: $HOME/Library/Logs/balizero-profile-monitor.error.log"
    exit 1
fi

# 7. Verifica log evento DAEMON_START
sleep 1
if grep -q "DAEMON_START" "$HOME/Library/Logs/balizero-profile-events.log" 2>/dev/null; then
    echo "✅ Daemon ha registrato evento DAEMON_START"
else
    echo "⚠️  Log eventi non ancora popolato. Controlla manualmente:"
    echo "    tail -f $HOME/Library/Logs/balizero-profile-events.log"
fi

echo ""
echo "═══ Installazione completata ═══"
echo ""
echo "Eventi registrati in: $HOME/Library/Logs/balizero-profile-events.log"
echo ""
echo "Test manuale (simula check-out):"
echo "  Apri Apple menu → Logout '$CURRENT_USER'..."
echo "  → Dovrebbe arrivare alert Telegram a Antonello"
echo ""
echo "Disinstallazione futura:"
echo "  launchctl bootout gui/\$(id -u)/com.balizero.profile-monitor"
echo "  rm '$PLIST_PATH'"
echo "  rm -rf '$INSTALL_DIR'"
