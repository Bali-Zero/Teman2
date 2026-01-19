#!/bin/bash
# Fly.io Scheduled RSS Fetcher
# This script is called by the scheduled machine

set -e

cd /app

# Use NUZANTARA_API_URL from environment (set in .env or Fly secrets)
# Fallback to BACKEND_API_URL for local dev, final fallback to production URL
API_URL=${NUZANTARA_API_URL:-${BACKEND_API_URL:-https://nuzantara-rag.fly.dev}}

python scripts/rss_fetcher.py --max-age 5 --limit 10 --api-url "$API_URL" --send

echo "RSS Fetch completed at $(date)"
