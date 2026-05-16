#!/usr/bin/env bash
# NextDNS weekly DNS digest → Telegram
# Runs: Monday 08:55 WITA via crontab (before wa-audit-bot reminder)
# Mostra top-20 domain visitati nella settimana — log-only, nessun blocco
# Richiede: NEXTDNS_API_KEY, NEXTDNS_PROFILE_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID

set -euo pipefail

SECRETS="${HOME}/.nuzantara-secrets.env"
[[ -f "$SECRETS" ]] && source "$SECRETS"

: "${NEXTDNS_API_KEY:?NEXTDNS_API_KEY mancante}"
: "${NEXTDNS_PROFILE_ID:?NEXTDNS_PROFILE_ID mancante}"
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN mancante}"
: "${TELEGRAM_OWNER_CHAT_ID:?TELEGRAM_OWNER_CHAT_ID mancante}"

WEEK_START=$(date -v-7d +%Y-%m-%dT00:00:00Z 2>/dev/null || date -d "7 days ago" +%Y-%m-%dT00:00:00Z)
WEEK_END=$(date +%Y-%m-%dT23:59:59Z)

# Fetch top domains via NextDNS Logs API
RESPONSE=$(curl -sf \
    -H "X-Api-Key: ${NEXTDNS_API_KEY}" \
    "https://api.nextdns.io/profiles/${NEXTDNS_PROFILE_ID}/analytics/domains?from=${WEEK_START}&to=${WEEK_END}&limit=20" \
    2>/dev/null || echo '{"data":[]}')

TOP_DOMAINS=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
if not data:
    print('(nessun dato disponibile)')
else:
    for i, d in enumerate(data[:20], 1):
        name = d.get('name','?')
        count = d.get('queries', d.get('count', '?'))
        print(f'{i:2}. {name} — {count} query')
")

WEEK_LABEL=$(date -v-7d +"%d/%m" 2>/dev/null || date -d "7 days ago" +"%d/%m")
TODAY_LABEL=$(date +"%d/%m/%Y")

MSG="📊 *NextDNS Digest — settimana ${WEEK_LABEL}–${TODAY_LABEL}*

Top 20 domini visitati dalla rete ufficio Bali Zero:

\`\`\`
${TOP_DOMAINS}
\`\`\`

_Log completi:_ nextdns.io → Logs → filtra per periodo."

curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_OWNER_CHAT_ID}" \
    -d parse_mode="Markdown" \
    --data-urlencode text="${MSG}" \
    > /dev/null

echo "[nextdns-digest] Inviato digest settimana ${WEEK_LABEL}–${TODAY_LABEL}"
