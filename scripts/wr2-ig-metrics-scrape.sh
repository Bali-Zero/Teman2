#!/bin/bash
# WR2 IG metrics scraper wrapper (Pro). Sources the IG token (from .env.master,
# falling back to Fly secrets), then runs the smart scraper which repopulates
# engagement_metrics for published carousels missing/stale metrics.
# Cron: daily — see com.balizero.wr2.ig-metrics-scrape.daily.plist.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="/Users/nuzantara/Desktop/nuzantara"
LOG="$HOME/logs/wr2-ig-metrics-scrape.log"
ENV_MASTER="$HOME/.openclaw/workspace/.env.master"
mkdir -p "$HOME/logs"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# 1) token from .env.master (primary — fast, no network)
TOK=""
if [ -f "$ENV_MASTER" ]; then
  TOK=$(grep -E '^INSTAGRAM_ACCESS_TOKEN=' "$ENV_MASTER" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"'' | tr -d '\r')
fi
# 2) fallback: Fly secret (slower, needs network + auth)
if [ -z "$TOK" ]; then
  echo "[$(ts)] token not in .env.master, trying Fly" >> "$LOG"
  TOK=$(fly ssh console -a nuzantara-rag -C "printenv INSTAGRAM_ACCESS_TOKEN" 2>/dev/null \
        | grep -viE 'Connecting|Metrics|No machine|^$' | tr -d '\r' | tail -1)
fi
if [ -z "$TOK" ]; then
  echo "[$(ts)] ERROR: no IG token (env.master + Fly both empty) — abort" >> "$LOG"
  exit 1
fi

# Prefer a modern python (homebrew 3.14) — /usr/bin/python3 is 3.9 (no `X | None` syntax).
PY="/opt/homebrew/bin/python3"; [ -x "$PY" ] || PY="python3"
echo "[$(ts)] scrape start (token len=${#TOK}, py=$PY)" >> "$LOG"
INSTAGRAM_ACCESS_TOKEN="$TOK" "$PY" "$REPO/scripts/wr2_ig_metrics_scraper.py" \
  --max-age-days 3 >> "$LOG" 2>&1
rc=$?
echo "[$(ts)] scrape done rc=$rc" >> "$LOG"

# Discovery step: find posts published BY HAND on @balizero0 that never went
# through the WR2 pipeline (queue stays blind to them otherwise, scar #2).
# Non-fatal on failure — the nightly metrics refresh above is the load-bearing
# job, discovery is a best-effort add-on. MATCH-PENDING lines (fuzzy match to
# an in-flight queue item) land in the same $LOG for a human to resolve via
# `wr2_queue_writer.py mark-published`.
echo "[$(ts)] discovery start" >> "$LOG"
INSTAGRAM_ACCESS_TOKEN="$TOK" "$PY" "$REPO/scripts/wr2_ig_discovery.py" \
  --token-env INSTAGRAM_ACCESS_TOKEN --max-age-days 90 >> "$LOG" 2>&1 \
  || echo "[$(ts)] discovery failed rc=$?" >> "$LOG"
echo "[$(ts)] discovery done" >> "$LOG"

exit $rc
