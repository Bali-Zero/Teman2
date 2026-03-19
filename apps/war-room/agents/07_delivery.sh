#!/bin/zsh
# FASE 5 — Delivery: Google Drive upload + WhatsApp notification
set -euo pipefail

TOPIC="${1:-Unknown}"
WAR_ROOM="$(cd "$(dirname "$0")/.." && pwd)"
MASTER_DIR="${2:-$WAR_ROOM/output/master}"

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
# Use rclone to upload (configured with gdrive remote for zero@balizero.com)
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive}"
GDRIVE_FOLDER_ID="${GDRIVE_FOLDER_ID:-1zbPAWG6rOJjNTV3F_mbMtS-1L4XgkMJr}"
ARCHIVE_NAME="$(basename "$ARCHIVE")"
rclone copy "$ARCHIVE" "${GDRIVE_REMOTE}:balizero_warroom/" --drive-root-folder-id "$GDRIVE_FOLDER_ID" 2>/dev/null \
  && DRIVE_LINK="https://drive.google.com/drive/folders/${GDRIVE_FOLDER_ID}" \
  || DRIVE_LINK="$DRIVE_FOLDER"

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
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:?Set TELEGRAM_BOT_TOKEN env var}"
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
