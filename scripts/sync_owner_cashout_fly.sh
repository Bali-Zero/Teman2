#!/usr/bin/env bash
# Owner Weekly Cashout — trigger sync on Fly via ssh console
# Called by cron on Air (Monday 09:00 WITA)
set -euo pipefail

FLY=/opt/homebrew/bin/fly
APP=nuzantara-rag

echo "$(date '+%Y-%m-%d %H:%M:%S') [owner-cashout] starting sync on $APP"

$FLY ssh console -a "$APP" -C "python3 -c \"
import sys, os, asyncio, asyncpg
sys.path.insert(0, '/app')
os.chdir('/app')
from backend.services.hr.owner_cashout.sync_service import run_sync

async def main():
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'])
    r = await run_sync(pool, triggered_by='cron')
    print(f'sync done status={r.status} weeks={r.weeks_processed} rows={r.rows_upserted}')
    await pool.close()

asyncio.run(main())
\""

echo "$(date '+%Y-%m-%d %H:%M:%S') [owner-cashout] done"
