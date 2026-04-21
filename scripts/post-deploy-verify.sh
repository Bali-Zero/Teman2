#!/usr/bin/env bash
# post-deploy-verify.sh
#
# Called by Claude after merging a PR to main. Waits for `fly-deploy.yml`
# to finish, then probes /health on nuzantara-rag and posts the outcome to
# Telegram. If the workflow auto-rollbacked or health is unhealthy,
# exits non-zero and alerts.
#
# Usage: bash post-deploy-verify.sh <PR_NUMBER>
#
# Exit codes:
#   0 = deploy completed, health green
#   1 = deploy failed or rollbacked
#   2 = health check red (requires investigation)
#   3 = workflow did not start or timed out

set -u -o pipefail

PR_NUMBER="${1:-}"
REPO="Balizero1987/Teman2"
APP="nuzantara-rag"
HEALTH_URL="https://nuzantara-rag.fly.dev/health"
MAX_WAIT_SEC=900   # 15 minutes — deploy + post-health
POLL_INTERVAL=15

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
  set +a
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-}}"

notify() {
  local emoji="$1"
  local text="$2"
  if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    return
  fi
  local msg="${emoji} Post-deploy verify (PR #${PR_NUMBER:-?})
${text}"
  curl -s --max-time 5 \
    -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d chat_id="${CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    > /dev/null 2>&1 || true
}

echo "[post-deploy-verify] Waiting for fly-deploy.yml to start..."
START_TS=$(date +%s)

# 1) Find the fly-deploy run triggered by this merge (latest run on main).
RUN_ID=""
while [ -z "$RUN_ID" ] && [ $(( $(date +%s) - START_TS )) -lt 120 ]; do
  RUN_ID=$(GH_REPO="$REPO" gh run list --workflow=fly-deploy.yml --branch=main --limit=1 --json databaseId,status,createdAt --jq '.[0] | select(.status != "completed") | .databaseId' 2>/dev/null)
  if [ -z "$RUN_ID" ]; then
    sleep 5
  fi
done

if [ -z "$RUN_ID" ]; then
  echo "[post-deploy-verify] fly-deploy did not start within 2 min — maybe no backend changes?"
  notify "ℹ️" "fly-deploy did not trigger (likely no backend-rag changes)"
  exit 0
fi

echo "[post-deploy-verify] Watching run $RUN_ID"

# 2) Poll until the run completes.
CONCLUSION=""
while [ $(( $(date +%s) - START_TS )) -lt $MAX_WAIT_SEC ]; do
  DATA=$(GH_REPO="$REPO" gh api "repos/$REPO/actions/runs/$RUN_ID" --jq '{status: .status, conclusion: .conclusion}' 2>/dev/null)
  STATUS=$(echo "$DATA" | /usr/bin/jq -r '.status // "unknown"')
  if [ "$STATUS" = "completed" ]; then
    CONCLUSION=$(echo "$DATA" | /usr/bin/jq -r '.conclusion // "unknown"')
    break
  fi
  echo "[post-deploy-verify] run $RUN_ID status: $STATUS"
  sleep $POLL_INTERVAL
done

if [ -z "$CONCLUSION" ]; then
  notify "⏱️" "Deploy workflow timed out after ${MAX_WAIT_SEC}s — investigate"
  exit 3
fi

if [ "$CONCLUSION" != "success" ]; then
  JOB_SUMMARY=$(GH_REPO="$REPO" gh api "repos/$REPO/actions/runs/$RUN_ID/jobs" --jq '[.jobs[] | "\(.name): \(.conclusion // "?")"] | join(" | ")' 2>/dev/null)
  notify "❌" "Deploy FAILED or ROLLBACKED
conclusion: $CONCLUSION
jobs: $JOB_SUMMARY
https://github.com/$REPO/actions/runs/$RUN_ID"
  exit 1
fi

# 3) Health check
echo "[post-deploy-verify] Deploy OK. Probing $HEALTH_URL ..."
HEALTHY=0
for _ in 1 2 3 4 5; do
  HTTP=$(curl -s -o /tmp/hd_body -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null || echo 000)
  if [ "$HTTP" = "200" ]; then
    DB_STATUS=$(/usr/bin/jq -r '.database.status // "unknown"' /tmp/hd_body 2>/dev/null)
    if [ "$DB_STATUS" = "connected" ]; then
      HEALTHY=1
      break
    fi
  fi
  sleep 5
done

if [ "$HEALTHY" -ne 1 ]; then
  HEALTH_SUMMARY=$(head -c 300 /tmp/hd_body 2>/dev/null || echo "no body")
  notify "⚠️" "Deploy completed but /health is red
last response: $HEALTH_SUMMARY"
  exit 2
fi

VERSION=$(/usr/bin/jq -r '.version // "unknown"' /tmp/hd_body 2>/dev/null)
notify "✅" "Deploy green
version: $VERSION
db: connected
https://github.com/$REPO/actions/runs/$RUN_ID"

echo "[post-deploy-verify] ✅ healthy, version=$VERSION"
exit 0
