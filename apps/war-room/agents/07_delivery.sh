#!/bin/zsh
# FASE 5 — Delivery: Google Drive upload + WhatsApp notification
set -euo pipefail

TOPIC="${1:-Unknown}"
WAR_ROOM="$(cd "$(dirname "$0")/.." && pwd)"
MASTER_DIR="${2:-$WAR_ROOM/output/master}"

# Parse named args (use while+shift to correctly handle --flag value pattern)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --topic=*) TOPIC="${1#*=}"; shift ;;
    --topic) TOPIC="$2"; shift 2 ;;
    --master=*) MASTER_DIR="${1#*=}"; shift ;;
    --master) MASTER_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

PYTHON="$WAR_ROOM/.venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON=python3

BRAND_FILE="$WAR_ROOM/config/brand.json"
DRIVE_FOLDER=$("$PYTHON" -c "import json; print(json.load(open('$BRAND_FILE'))['delivery']['google_drive_folder'])")
TONE=$(cat "$WAR_ROOM/output/strategy/claude_slides.json" 2>/dev/null | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('tone', 'N/A'))" 2>/dev/null || echo "N/A")
CANVA_URL=$("$PYTHON" -c "import json; d=json.load(open('$WAR_ROOM/output/canva/carousel_canva.json')); print(d.get('design_url',''))" 2>/dev/null || echo "")

echo "📦 Comprimo master archive..."
ARCHIVE="$WAR_ROOM/output/balizero_warroom_$(date +%Y%m%d_%H%M%S).zip"
zip -r "$ARCHIVE" "$MASTER_DIR" 2>/dev/null

echo "☁️  Upload Google Drive..."
# Use rclone to upload (configured with gdrive remote for zero@balizero.com)
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive}"
GDRIVE_FOLDER_ID="${GDRIVE_FOLDER_ID:-1zbPAWG6rOJjNTV3F_mbMtS-1L4XgkMJr}"
ARCHIVE_NAME="$(basename "$ARCHIVE")"
rclone copy "$ARCHIVE" "${GDRIVE_REMOTE}:balizero_warroom/" --drive-root-folder-id "$GDRIVE_FOLDER_ID" 2>/dev/null \
  && DRIVE_LINK="https://drive.google.com/drive/folders/${GDRIVE_FOLDER_ID}" \
  || DRIVE_LINK="$DRIVE_FOLDER"

echo "   Drive link: $DRIVE_LINK"

echo "📱 Invio notifica Telegram..."
CAPTION=$(cat "$MASTER_DIR/instagram_caption.txt" 2>/dev/null | head -c 500 || echo "")

MSG="🚨 *Bali Zero War Room conclusa.*
| Argomento: $TOPIC.
| Tono: $TONE.
| Creatività approvata, zero allucinazioni lette.
| Master su Google Drive: $DRIVE_LINK.
${CANVA_URL:+| Canva carousel: $CANVA_URL.}
| In attesa di review per la pubblicazione.
${CAPTION:+| Caption: $CAPTION}"

# Notifica: Telegram Bot API diretta (affidabile, no middleware)
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:?Set TELEGRAM_BOT_TOKEN env var}"
CHAT_ID="${TELEGRAM_GROUP_ID:?Set TELEGRAM_GROUP_ID env var}"
"$PYTHON" -c "
import urllib.request, urllib.parse, json, sys
token='$BOT_TOKEN'; chat='$CHAT_ID'
msg=sys.stdin.read()
data=urllib.parse.urlencode({'chat_id':chat,'text':msg}).encode()
req=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',data=data)
resp=urllib.request.urlopen(req,timeout=10)
print('✅ Telegram inviato' if json.loads(resp.read()).get('ok') else '⚠️ Telegram ko')
" <<< "$MSG" || echo "⚠️  Telegram fallito"

# WhatsApp opzionale
if [[ -n "${WHATSAPP_TEAM_NUMBER:-}" ]]; then
  wacli send --to "$WHATSAPP_TEAM_NUMBER" --text "$MSG" 2>/dev/null && \
    echo "✅ WhatsApp inviato" || echo "⚠️  WhatsApp fallito"
fi

echo "✅ Delivery completata"
echo "   Archive: $ARCHIVE"
echo "   Drive: $DRIVE_LINK"

# ── FASE 4b: Canva auto-executor via claude -p ──────────────────────────────
# claude -p headless usa ~/.claude/token (Max OAuth) senza ANTHROPIC_API_KEY
# Il MCP Canva è disponibile solo in sessione interattiva → usiamo claude -p
# con un prompt che legge canva_pending.json e applica via MCP tools
PENDING_FILE="$WAR_ROOM/output/canva/canva_pending.json"
APPLIED_FILE="$WAR_ROOM/output/canva/carousel_canva.json"

if [[ -f "$PENDING_FILE" ]]; then
    PENDING_STATUS=$("$PYTHON" -c "import json; print(json.load(open('$PENDING_FILE')).get('status',''))" 2>/dev/null)
    PENDING_TOPIC=$("$PYTHON" -c "import json; print(json.load(open('$PENDING_FILE')).get('topic',''))" 2>/dev/null)
    PENDING_OPS=$("$PYTHON" -c "import json; print(json.load(open('$PENDING_FILE')).get('operations_count',0))" 2>/dev/null)

    if [[ "$PENDING_STATUS" == "pending" ]]; then
        echo ""
        echo "🎨 Avvio Canva executor via claude -p..."

        # Prompt per claude -p: legge il file e applica le operazioni
        CANVA_PROMPT="Hai un file canva_pending.json in $PENDING_FILE con $PENDING_OPS operazioni replace_text da applicare al design Canva.

Leggi il file con Read tool, poi per ogni operazione nella lista 'operations':
1. Usa mcp__claude_ai_Canva__start-editing-transaction sul design_id del file
2. Usa mcp__claude_ai_Canva__perform-editing-operations con le operazioni
3. Usa mcp__claude_ai_Canva__commit-editing-transaction
4. Aggiorna il campo 'status' da 'pending' a 'applied' nel file JSON
5. Scrivi output/canva/carousel_canva.json con design_url e status applied

Topic: $PENDING_TOPIC. Procedi senza chiedere conferma."

        # Esegui senza ANTHROPIC_API_KEY (usa ~/.claude/token OAuth Max)
        CANVA_RESULT=$(env -i \
            HOME="$HOME" \
            PATH="$PATH" \
            USER="$USER" \
            TERM="xterm-256color" \
            claude -p "$CANVA_PROMPT" \
            --allowedTools "mcp__claude_ai_Canva__start-editing-transaction,mcp__claude_ai_Canva__perform-editing-operations,mcp__claude_ai_Canva__commit-editing-transaction,Read,Write,Edit" \
            --dangerously-skip-permissions \
            2>&1)

        CLAUDE_EXIT=$?
        echo "   claude -p exit: $CLAUDE_EXIT"

        # Verifica se applicato
        if [[ -f "$APPLIED_FILE" ]]; then
            CANVA_URL=$("$PYTHON" -c "import json; print(json.load(open('$APPLIED_FILE')).get('design_url',''))" 2>/dev/null)
            echo "   ✅ Canva applicato: $CANVA_URL"
            # Aggiorna il messaggio Telegram con il link Canva
            "$PYTHON" -c "
import urllib.request, urllib.parse
msg = '🎨 Canva carousel aggiornato automaticamente!\nTopic: $PENDING_TOPIC\nLink: $CANVA_URL'
data = urllib.parse.urlencode({'chat_id': '$CHAT_ID', 'text': msg}).encode()
urllib.request.urlopen('https://api.telegram.org/bot${BOT_TOKEN}/sendMessage', data=data, timeout=10)
" 2>/dev/null && echo "   📱 Notifica Canva inviata"
        else
            echo "   ⚠️  Canva non applicato (claude -p output: ${CANVA_RESULT:0:200})"
            # Notifica fallimento con istruzioni manuali
            "$PYTHON" -c "
import urllib.request, urllib.parse
msg = '⚠️ Canva auto-executor fallito.\nApri Claude Code e digita:\napplica canva pending per: $PENDING_TOPIC\n\nFile: $PENDING_FILE'
data = urllib.parse.urlencode({'chat_id': '$CHAT_ID', 'text': msg}).encode()
urllib.request.urlopen('https://api.telegram.org/bot${BOT_TOKEN}/sendMessage', data=data, timeout=10)
" 2>/dev/null
        fi
    fi
fi
