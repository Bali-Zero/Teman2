#!/bin/bash
# chrome-debug.sh — Avvia Chrome con remote debugging abilitato (porta 9222)
# Necessario per permettere a Playwright di agganciarsi alla sessione esistente.
#
# USO:
#   ./chrome-debug.sh          # avvia/riavvia Chrome con CDP
#   ./chrome-debug.sh --check  # verifica se CDP è attivo senza fare nulla
#
# ALIAS suggerito in ~/.zshrc:
#   alias chrome-debug='~/war_room/chrome-debug.sh'

CDP_PORT=9222
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

check_cdp() {
  curl -s --max-time 2 "http://localhost:${CDP_PORT}/json/version" > /dev/null 2>&1
  return $?
}

if [[ "$1" == "--check" ]]; then
  if check_cdp; then
    echo "✅ Chrome CDP attivo su porta ${CDP_PORT}"
    exit 0
  else
    echo "❌ Chrome CDP NON attivo. Esegui: ~/war_room/chrome-debug.sh"
    exit 1
  fi
fi

# Se CDP già attivo, non fare niente
if check_cdp; then
  echo "✅ Chrome già in esecuzione con CDP sulla porta ${CDP_PORT}"
  exit 0
fi

# Chiudi Chrome se aperto (senza CDP non serve tenerlo)
echo "🔄 Riavvio Chrome con remote debugging abilitato..."
pkill -f "Google Chrome" 2>/dev/null
sleep 2

# Lancia Chrome via binary diretto con user-data-dir separato
# NOTA: `open -a` NON passa correttamente --remote-debugging-port su macOS.
# Serve il binary diretto + --user-data-dir per evitare il join alla sessione esistente.
CDP_PROFILE="${HOME}/.chrome-cdp-profile"
mkdir -p "${CDP_PROFILE}"

"${CHROME}" \
  --remote-debugging-port=${CDP_PORT} \
  --user-data-dir="${CDP_PROFILE}" \
  --no-first-run \
  --no-default-browser-check </dev/null >/dev/null 2>&1 &

# Aspetta che sia pronto
for i in {1..10}; do
  sleep 1
  if check_cdp; then
    echo "✅ Chrome avviato con CDP su porta ${CDP_PORT}"
    echo "   Ora apri gemini.google.com e sei pronto."
    exit 0
  fi
done

echo "❌ Chrome non risponde su porta ${CDP_PORT} dopo 10s"
exit 1
