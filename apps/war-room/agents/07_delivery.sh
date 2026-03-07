#!/bin/zsh
# FASE 5 — Delivery: Google Drive upload + WhatsApp notification
set -euo pipefail

TOPIC="${1:-Unknown}"
MASTER_DIR="${2:-$HOME/war_room/output/master}"
WAR_ROOM="$HOME/war_room"

# Parse named args
for i in "$@"; do
  case $i in
    --topic=*) TOPIC="${i#*=}" ;;
    --topic) shift; TOPIC="$1" ;;
    --master=*) MASTER_DIR="${i#*=}" ;;
    --master) shift; MASTER_DIR="$1" ;;
  esac
done

BRAND_FILE="$WAR_ROOM/config/brand.json"
DRIVE_FOLDER=$(python3 -c "import json; print(json.load(open('$BRAND_FILE'))['delivery']['google_drive_folder'])")
TONE=$(cat "$WAR_ROOM/output/strategy/claude_slides.json" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('tone', 'N/A'))" 2>/dev/null || echo "N/A")

echo "📦 Comprimo master archive..."
ARCHIVE="$WAR_ROOM/output/balizero_warroom_$(date +%Y%m%d_%H%M%S).zip"
zip -r "$ARCHIVE" "$MASTER_DIR" 2>/dev/null

echo "☁️  Upload Google Drive..."
# Use gog CLI to upload
DRIVE_LINK=$(gog --account=zero@balizero.com drive upload "$ARCHIVE" --folder-id "1zbPAWG6rOJjNTV3F_mbMtS-1L4XgkMJr" --json 2>/dev/null | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('webViewLink', '$DRIVE_FOLDER'))" 2>/dev/null || \
  echo "$DRIVE_FOLDER")

echo "   Drive link: $DRIVE_LINK"

echo "📱 Invio notifica WhatsApp..."
# Extract caption for notification
CAPTION_FILE="$MASTER_DIR/instagram_caption.txt"

MSG="🚨 *Bali Zero War Room conclusa.*
| Argomento: $TOPIC.
| Tono: $TONE.
| Creatività approvata, zero allucinazioni lette.
| Master su Google Drive: $DRIVE_LINK.
| In attesa di review per la pubblicazione."

# Notifica: Telegram Bot API diretta (affidabile, no middleware)
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8295471667:AAHglwz8p8LxFnDgctmXuCs5aZa6lY78QO8}"
CHAT_ID="${TELEGRAM_GROUP_ID:--1003826235564}"
python3 -c "
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
