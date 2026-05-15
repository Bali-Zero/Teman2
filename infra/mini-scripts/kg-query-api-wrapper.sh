#!/bin/bash
# F3.2 fix: wait for tailscaled to bind 100.93.236.6 before starting kg-query-api
# H10 + K-v3-2 fix: canonical git path
# F3.2-v2 fix: explicit PATH for launchd minimal env (/sbin for ifconfig)
set -uo pipefail
export PATH="/usr/sbin:/sbin:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd /tmp || cd /

TAILSCALE_IP="100.93.236.6"
MAX_WAIT_SEC=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT_SEC ]; do
  if /sbin/ifconfig 2>/dev/null | grep -q "$TAILSCALE_IP"; then
    echo "$(date) tailscaled ready (${WAITED}s wait), starting kg-query-api"
    break
  fi
  sleep 2
  WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT_SEC ]; then
  echo "$(date) ALERT: tailscaled NOT ready after ${MAX_WAIT_SEC}s — refusing start"
  exit 1
fi

cd ~/Desktop/nuzantara/apps/mata-garuda
exec ./.venv/bin/python -m mata_garuda.api.kg_query --bind "$TAILSCALE_IP" --port 8990
