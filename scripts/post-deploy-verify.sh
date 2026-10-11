#!/usr/bin/env bash
# post-deploy-verify.sh
#
# Called by a session after merging a backend PR on the canonical repo.
# Flow (deploys run on the private FastLabsNet/zero, not on Teman2):
#   1. resolve the PR's merge commit M on REPO_CANON (Bali-Zero/Teman2);
#   2. if M touches no deploy path (mirror of zero's fly-deploy `on.push.paths`)
#      there is nothing to wait for -> exit 0;
#   3. wait for a fly-deploy.yml run on DEPLOY_REPO whose head commit carries a
#      `Zero-Sync-Canonical: <sha S>` trailer (written by mini.zero_sync) with
#      M an ancestor of S, then poll that run to completion;
#   4. behavioural proof (W88): /health `build_sha` must descend from M, and
#      the DB must be connected. Merged != live: content, not the run's colour.
#
# Usage: bash post-deploy-verify.sh <PR_NUMBER>
#        bash post-deploy-verify.sh --classify   (stdin paths -> deploy-relevant paths)
#
# Exit codes:
#   0 = deploy completed, health green (or no deploy-relevant change)
#   1 = deploy failed or rollbacked
#   2 = health check red / build_sha does not contain the merge
#   3 = PR not merged, no matching deploy run appeared, or timeout
#
# Env: REPO_CANON, DEPLOY_REPO, MAX_WAIT_START (2700), MAX_WAIT_SEC (2400).

set -u -o pipefail

REPO_CANON="${REPO_CANON:-Bali-Zero/Teman2}"
DEPLOY_REPO="${DEPLOY_REPO:-FastLabsNet/zero}"
WORKFLOW="fly-deploy.yml"
HEALTH_URL="${HEALTH_URL:-https://nuzantara-rag.fly.dev/health}"
MAX_WAIT_START="${MAX_WAIT_START:-2700}"  # sync (5-30 min) + runner queue (~15 min)
MAX_WAIT_SEC="${MAX_WAIT_SEC:-2400}"      # run start -> completion
POLL_INTERVAL="${POLL_INTERVAL:-20}"

# Mirror of `on.push.paths` in FastLabsNet/zero .github/workflows/fly-deploy.yml
# (gh api repos/FastLabsNet/zero/contents/.github/workflows/fly-deploy.yml).
# GitHub semantics: patterns in order, the last matching one wins; "**/" also
# matches zero directories, hence the paired globs. Keep in sync with that file.
is_deploy_path() {
  local p="$1" hit=1
  case "$p" in apps/backend-rag/*) hit=0 ;; esac
  case "$p" in
    apps/backend-rag/docs/*) hit=1 ;;
    apps/backend-rag/README.md | apps/backend-rag/*/README.md) hit=1 ;;
    apps/backend-rag/AGENTS.md) hit=1 ;;
    apps/backend-rag/CLAUDE.md) hit=1 ;;
    apps/backend-rag/tests/* | apps/backend-rag/*/tests/*) hit=1 ;;
    apps/backend-rag/test_*.py | apps/backend-rag/*/test_*.py) hit=1 ;;
    apps/backend-rag/*_test.py) hit=1 ;;
  esac
  case "$p" in .github/workflows/fly-deploy.yml) hit=0 ;; esac
  return $hit
}

if [ "${1:-}" = "--classify" ]; then
  while IFS= read -r f; do is_deploy_path "$f" && printf '%s\n' "$f"; done
  exit 0
fi

PR_NUMBER="${1:-}"
if [ -z "$PR_NUMBER" ]; then
  echo "usage: post-deploy-verify.sh <PR_NUMBER>" >&2
  exit 3
fi

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
  set +a
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-}}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

notify() {
  local emoji="$1" text="$2"
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

have_commit() { git cat-file -e "$1^{commit}" 2>/dev/null; }
ensure_commit() { have_commit "$1" || git fetch -q origin "$1" 2>/dev/null; have_commit "$1"; }
is_ancestor() { git merge-base --is-ancestor "$1" "$2" 2>/dev/null; }

# 1) Merge commit on the canonical repo.
MERGE_SHA=$(gh pr view "$PR_NUMBER" --repo "$REPO_CANON" --json mergeCommit,state \
  --jq 'select(.state == "MERGED") | .mergeCommit.oid // empty' 2>/dev/null)
if [ -z "$MERGE_SHA" ]; then
  echo "[post-deploy-verify] PR #$PR_NUMBER is not merged on $REPO_CANON (or not found)" >&2
  notify "⚠️" "PR not merged on $REPO_CANON — nothing to verify"
  exit 3
fi
echo "[post-deploy-verify] PR #$PR_NUMBER merged as $MERGE_SHA"

git fetch -q origin main 2>/dev/null || true
if ! ensure_commit "$MERGE_SHA"; then
  echo "[post-deploy-verify] cannot fetch merge commit $MERGE_SHA locally" >&2
  exit 3
fi

# 2) Does the merge touch the deploy path?
RELEVANT=$(git diff --name-only "${MERGE_SHA}^1" "$MERGE_SHA" | "$0" --classify)
if [ -z "$RELEVANT" ]; then
  echo "[post-deploy-verify] merge touches no deploy path — no deploy expected, nothing to verify"
  notify "ℹ️" "No deploy-relevant files in $MERGE_SHA (no backend-rag runtime change)"
  exit 0
fi
echo "[post-deploy-verify] deploy-relevant files: $(printf '%s\n' "$RELEVANT" | wc -l | tr -d ' ')"

# 3) Wait for the zero deploy run that carries this merge.
echo "[post-deploy-verify] Waiting for $WORKFLOW on $DEPLOY_REPO to include $MERGE_SHA (max ${MAX_WAIT_START}s)..."
START_TS=$(date +%s)
RUN_ID=""
RUN_SYNC=""
while [ -z "$RUN_ID" ] && [ $(( $(date +%s) - START_TS )) -lt "$MAX_WAIT_START" ]; do
  RUNS=$(gh run list --repo "$DEPLOY_REPO" --workflow="$WORKFLOW" --limit 30 \
    --json databaseId,headSha --jq '.[] | "\(.databaseId) \(.headSha)"' 2>/dev/null)
  while read -r rid hsha; do
    [ -n "$rid" ] || continue
    cache="$WORK/msg.$hsha"
    if [ ! -s "$cache" ]; then
      gh api "repos/$DEPLOY_REPO/commits/$hsha" --jq .commit.message > "$cache" 2>/dev/null || { rm -f "$cache"; continue; }
    fi
    S=$(sed -n 's/^Zero-Sync-Canonical:[[:space:]]*\([0-9a-f]\{40\}\).*/\1/p' "$cache" | tail -n1)
    [ -n "$S" ] || continue
    ensure_commit "$S" || continue
    if is_ancestor "$MERGE_SHA" "$S"; then
      # runs are newest-first: keep the OLDEST run containing the merge
      RUN_ID="$rid"; RUN_SYNC="$S"
    fi
  done <<< "$RUNS"
  [ -n "$RUN_ID" ] || sleep "$POLL_INTERVAL"
done

if [ -z "$RUN_ID" ]; then
  notify "⏱️" "No $WORKFLOW run on $DEPLOY_REPO contains $MERGE_SHA after ${MAX_WAIT_START}s (sync lag or runner stuck?)"
  echo "[post-deploy-verify] no matching deploy run within ${MAX_WAIT_START}s" >&2
  exit 3
fi
echo "[post-deploy-verify] Watching run $RUN_ID (canonical $RUN_SYNC)"
RUN_URL="https://github.com/$DEPLOY_REPO/actions/runs/$RUN_ID"

# 4) Poll until the run completes.
RUN_TS=$(date +%s)
CONCLUSION=""
while [ $(( $(date +%s) - RUN_TS )) -lt "$MAX_WAIT_SEC" ]; do
  DATA=$(gh api "repos/$DEPLOY_REPO/actions/runs/$RUN_ID" --jq '{status: .status, conclusion: .conclusion}' 2>/dev/null)
  STATUS=$(echo "$DATA" | /usr/bin/jq -r '.status // "unknown"')
  if [ "$STATUS" = "completed" ]; then
    CONCLUSION=$(echo "$DATA" | /usr/bin/jq -r '.conclusion // "unknown"')
    break
  fi
  echo "[post-deploy-verify] run $RUN_ID status: $STATUS"
  sleep "$POLL_INTERVAL"
done

if [ -z "$CONCLUSION" ]; then
  notify "⏱️" "Deploy workflow timed out after ${MAX_WAIT_SEC}s — investigate
$RUN_URL"
  exit 3
fi

if [ "$CONCLUSION" != "success" ]; then
  JOB_SUMMARY=$(gh api "repos/$DEPLOY_REPO/actions/runs/$RUN_ID/jobs" --jq '[.jobs[] | "\(.name): \(.conclusion // "?")"] | join(" | ")' 2>/dev/null)
  notify "❌" "Deploy FAILED or ROLLBACKED
conclusion: $CONCLUSION
jobs: $JOB_SUMMARY
$RUN_URL"
  exit 1
fi

# 5) Health + behavioural proof: live build_sha must contain the merge.
echo "[post-deploy-verify] Deploy OK. Probing $HEALTH_URL ..."
HB="$WORK/health"
HEALTHY=0
BUILD_SHA=""
for _ in 1 2 3 4 5 6; do
  HTTP=$(curl -s -o "$HB" -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null || echo 000)
  if [ "$HTTP" = "200" ]; then
    DB_STATUS=$(/usr/bin/jq -r '.database.status // "unknown"' "$HB" 2>/dev/null)
    BUILD_SHA=$(/usr/bin/jq -r '.build_sha // empty' "$HB" 2>/dev/null)
    if [ "$DB_STATUS" = "connected" ] && [ -n "$BUILD_SHA" ] \
       && ensure_commit "$BUILD_SHA" && is_ancestor "$MERGE_SHA" "$BUILD_SHA"; then
      HEALTHY=1
      break
    fi
  fi
  sleep 10
done

if [ "$HEALTHY" -ne 1 ]; then
  HEALTH_SUMMARY=$(head -c 300 "$HB" 2>/dev/null || echo "no body")
  notify "⚠️" "Deploy run green but live is not proven: /health red or build_sha '${BUILD_SHA:-none}' does not contain $MERGE_SHA
last response: $HEALTH_SUMMARY
$RUN_URL"
  exit 2
fi

VERSION=$(/usr/bin/jq -r '.version // "unknown"' "$HB" 2>/dev/null)
notify "✅" "Deploy green and live
version: $VERSION
build_sha: $BUILD_SHA (contains $MERGE_SHA)
db: connected
$RUN_URL"

echo "[post-deploy-verify] ✅ live, version=$VERSION build_sha=$BUILD_SHA contains $MERGE_SHA"
exit 0
