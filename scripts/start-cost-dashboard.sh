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

# Use `next build` + `next start` instead of `next dev` (Turbopack).
# Turbopack's on-demand route compilation was observed to freeze after
# 2-3 route hits in smoke tests (Next.js 16.2 + multiple lockfiles in
# monorepo root). Production build is cached in .next/ so subsequent
# runs are fast; the one-time build cost is ~15s.
if [ ! -d .next ] || [ "$(find . -name '*.ts' -o -name '*.tsx' -newer .next 2>/dev/null | head -1)" ]; then
  echo "Building (one-time or after source changes)…"
  npx next build
fi

# Launch production server in background, open browser, wait for server.
npx next start -p 3100 &
PID=$!

# Wait for the server to bind. `next start` is ready in <1s after build.
sleep 2

URL="http://localhost:3100/cost-dashboard"
if command -v open >/dev/null 2>&1; then
  open "$URL" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" || true
else
  echo "Open $URL in your browser."
fi

wait "$PID"
