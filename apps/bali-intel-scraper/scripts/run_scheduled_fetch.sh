#!/bin/bash
# Fly.io Scheduled RSS Fetcher
# This script is called by the scheduled machine

set -e

cd /app
python scripts/rss_fetcher.py --max-age 5 --limit 10 --api-url https://balizero.com --send

echo "RSS Fetch completed at $(date)"
