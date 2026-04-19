#!/usr/bin/env bash
#
# Start the Pro-local LLM cost dashboard on http://localhost:3100.
# LOCAL_ONLY=1 is set so next.config.mjs allows startup.
#
# Prerequisites (set one of these in your env or .env.local):
#   DATABASE_URL_LOCAL  — preferred, Pro local Postgres
#   FLY_TUNNEL_URL      — fallback; requires `fly proxy 15432 -a nuzantara-postgres` running
#
# NOT deployed. NOT a production service. Ctrl-C stops.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
APP="$ROOT/apps/admin-dashboard-local"

cd "$APP"

if [ ! -d node_modules ]; then
  echo "Installing dependencies (first run)…"
  npm install
fi

export LOCAL_ONLY=1

# Launch Next dev server in background, open browser, wait for server.
npm run dev -- --port 3100 &
PID=$!

# Wait briefly for the server to bind; 2s is usually enough, 5s for cold starts.
sleep 3

URL="http://localhost:3100/cost-dashboard"
if command -v open >/dev/null 2>&1; then
  open "$URL" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" || true
else
  echo "Open $URL in your browser."
fi

wait "$PID"
