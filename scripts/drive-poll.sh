#!/bin/bash
# Drive Poll — cron every 5 min on Air (H24)
# Calls Fly.io backend to poll Google Drive for new client documents.
# If Fly.io is sleeping, curl wakes it (cold start ~35s).
# If Air is down for 2 hours, next run catches up via page_token.

BACKEND_URL="https://nuzantara-rag.fly.dev"
ENDPOINT="/api/admin/drive/poll"
TIMEOUT=60  # seconds (includes cold start time)

result=$(curl -s -m "$TIMEOUT" -X POST "${BACKEND_URL}${ENDPOINT}" \
  -H "Content-Type: application/json" 2>&1)

status=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null)
processed=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('processed',0))" 2>/dev/null)

if [ "$status" = "ok" ] && [ "$processed" != "0" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Drive poll: $processed new files"
elif [ "$status" = "ok" ]; then
  : # silent on no changes
elif [ -z "$result" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Drive poll: timeout (Fly.io cold start?)"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') Drive poll error: $result"
fi
