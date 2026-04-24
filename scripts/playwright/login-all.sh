#!/usr/bin/env bash
# One-shot login helper. Run this from ANY terminal location.
# Usage: bash ~/Desktop/nuzantara/scripts/playwright/login-all.sh [canva|gemini|flow]
set -e
SITE="${1:-}"
if [ -z "$SITE" ]; then
  echo "Usage: $0 <site>"
  echo "Sites: canva, gemini, flow"
  exit 1
fi
cd ~/Desktop/nuzantara
exec python3 scripts/playwright/playwright_login.py "$SITE"
