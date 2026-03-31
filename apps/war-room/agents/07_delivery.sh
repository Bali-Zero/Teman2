#!/bin/zsh
# FASE 5 — Delivery: Telegram notifications to Zero + Damar
# Rimossi: ZIP archive, Google Drive upload
set -euo pipefail

WAR_ROOM="$(cd "$(dirname "$0")/.." && pwd)"
MASTER_DIR="${2:-$WAR_ROOM/output/master}"
TOPIC="${1:-Unknown}"

# Parse named args
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

# ── Read pipeline outputs ──────────────────────────────────────────────────
TONE=$(cat "$WAR_ROOM/output/strategy/claude_slides.json" 2>/dev/null \
  | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('tone', 'N/A'))" 2>/dev/null || echo "N/A")

SLIDE_COUNT=$(cat "$WAR_ROOM/output/strategy/claude_slides.json" 2>/dev/null \
  | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin).get('slides', [])))" 2>/dev/null || echo "?")

IMG_GENERATED=0
IMG_TOTAL=0
if [[ -f "$WAR_ROOM/output/images/image_manifest.json" ]]; then
  IMG_GENERATED=$("$PYTHON" -c "import json; m=json.load(open('$WAR_ROOM/output/images/image_manifest.json')); print(sum(1 for x in m if x.get('generated')))" 2>/dev/null || echo "0")
  IMG_TOTAL=$("$PYTHON" -c "import json; m=json.load(open('$WAR_ROOM/output/images/image_manifest.json')); print(len(m))" 2>/dev/null || echo "0")
fi

NLM_STATUS=$("$PYTHON" -c "
import json
d = json.load(open('$WAR_ROOM/output/strategy/claude_slides.json'))
v = d.get('nlm_validation', {})
if v.get('skipped'):
    print('skipped')
else:
    r = v.get('result', {})
    print(r.get('overall', 'N/A') + ' (' + str(len(r.get('flags',[]))) + ' flags)')
" 2>/dev/null || echo "N/A")

CAPTION=$(cat "$MASTER_DIR/instagram_caption.txt" 2>/dev/null | head -c 600 || echo "")

# ── Telegram setup ──────────────────────────────────────────────────────────
echo "📱 Invio notifiche Telegram..."
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_IDS="${TELEGRAM_GROUP_ID:-}"

if [[ -z "$BOT_TOKEN" || -z "$CHAT_IDS" ]]; then
  echo "⚠️  TELEGRAM_BOT_TOKEN o TELEGRAM_GROUP_ID non settati — skip Telegram"
  exit 0
fi

DAMAR_CHAT_ID="1813875994"

send_telegram() {
  local chat="$1" msg="$2" parse_mode="${3:-Markdown}"
  "$PYTHON" -c "
import urllib.request, urllib.parse, json, sys
token='$BOT_TOKEN'; chat='$chat'; parse_mode='$parse_mode'
msg=sys.stdin.read()
data=urllib.parse.urlencode({'chat_id':chat,'text':msg,'parse_mode':parse_mode}).encode()
req=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',data=data)
try:
    resp=urllib.request.urlopen(req,timeout=10)
    ok=json.loads(resp.read()).get('ok',False)
    print(f'✅ Telegram → {chat}' if ok else f'⚠️ Telegram ko per {chat}')
except Exception as e:
    print(f'⚠️  Telegram error {chat}: {e}')
" <<< "$msg" || true
}

# ── Notify each chat ID ──────────────────────────────────────────────────────
CHAT_ID_ARRAY=("${(@s:,:)CHAT_IDS}")
for CID in "${CHAT_ID_ARRAY[@]}"; do
  CID=$(echo "$CID" | xargs)
  [[ -z "$CID" ]] && continue

  # ── Canva pending (inline) ─────────────────────────────────────────────────
  PENDING_FILE="$WAR_ROOM/output/canva/canva_pending.json"
  CANVA_LINE=""
  if [[ -f "$PENDING_FILE" ]]; then
    PENDING_OPS=$("$PYTHON" -c "import json; print(json.load(open('$PENDING_FILE')).get('operations_count',0))" 2>/dev/null || echo "?")
    if [[ "$CID" == "$DAMAR_CHAT_ID" ]]; then
      CANVA_LINE="
🎨 Canva: $PENDING_OPS operasi siap — buka Claude app desktop"
    else
      CANVA_LINE="
🎨 Canva: $PENDING_OPS operazioni pronte — Claude app desktop (Pro) → APPLICA_WAR_ROOM.md"
    fi
  fi

  if [[ "$CID" == "$DAMAR_CHAT_ID" ]]; then
    MSG="🚨 *Bali Zero War Room selesai.*
Topik: *$TOPIC*
Slide: $SLIDE_COUNT | Nada: $TONE
Gambar: $IMG_GENERATED/$IMG_TOTAL | NLM: $NLM_STATUS
Siap untuk di-review dan publikasi.${CANVA_LINE}${CAPTION:+
📝 Caption:
$CAPTION}"
  else
    MSG="🚨 *Bali Zero War Room conclusa.*
Argomento: *$TOPIC*
Slide: $SLIDE_COUNT | Tono: $TONE
Immagini: $IMG_GENERATED/$IMG_TOTAL | NLM check: $NLM_STATUS
In attesa di review per la pubblicazione.${CANVA_LINE}${CAPTION:+
📝 Caption:
$CAPTION}"
  fi

  send_telegram "$CID" "$MSG"
done

echo "✅ Delivery completata — notifiche Telegram inviate"
