#!/bin/bash
# Manual Trigger for Daily Report (Injection Strategy)
# Features: Raw Data Dump, Safe Markdown, Truncation, Connection Pool Fix, Dynamic Missing Check, Ruslana Filter
# Update: Switched to local httpx telegram sender to avoid loading heavy AI services and silencing warnings.

APP_NAME="nuzantara-rag"
REGION="sin"
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KE8BCX7GYCYM6P4NR00071B3"

echo "🚀 TRIGGERING MANUAL REPORT to $APP_NAME..."

# The injected python script
CMD=$(cat <<'EOF'
echo "🔍 Debugging Application State..."

cat > /app/debug_run.py <<'PYTHON'
import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, "/app")

import asyncpg

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL missing")
        return
        
    print(f"🔌 Connecting to DB...")
    pool = await asyncpg.create_pool(db_url)
    
    async with pool.acquire() as conn:
        print("\n📋 --- LAST 10 TIMESHEET EVENTS ---")
        rows = await conn.fetch("SELECT * FROM team_timesheet ORDER BY created_at DESC LIMIT 10")
        for r in rows:
            # Simple format: Time | Email | Action
            ts = r['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            print(f"{ts} | {r['email']} | {r['action_type']}")
            
        print("\n📊 --- TODAY'S VIEW STATE (Asia/Makassar) ---")
        # Re-create/Ensure view exists just in case (though it should be persistent if manually triggered previously)
        # We'll just select from it
        try:
            rows = await conn.fetch("SELECT * FROM daily_work_hours WHERE work_date = (NOW() AT TIME ZONE 'Asia/Makassar')::date ORDER BY created_at DESC LIMIT 20") # Wait, view fields are different
            # View definition: user_id, email, work_date, clock_in_bali, clock_out_bali, hours_worked
            rows = await conn.fetch("SELECT * FROM daily_work_hours WHERE work_date = (NOW() AT TIME ZONE 'Asia/Makassar')::date")
            for r in rows:
                 c_in = r['clock_in_bali'].strftime("%H:%M") if r['clock_in_bali'] else "--:--"
                 c_out = r['clock_out_bali'].strftime("%H:%M") if r['clock_out_bali'] else "ACTIVE"
                 print(f"{r['email']} | In: {c_in} | Out: {c_out} | Hours: {r['hours_worked']}")
        except Exception as e:
            print(f"Could not query view: {e}")

        print("\n👀 --- TEAM ONLINE STATUS VIEW ---")
        try:
            rows = await conn.fetch("SELECT * FROM team_online_status")
            for r in rows:
                 # Print concise status
                 print(f"{r['email']} | {r['action_type']} | Online: {r['is_online']} | Last: {r['last_action_bali']}")
        except Exception as e:
            print(f"Could not query online status view: {e}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

python /app/debug_run.py
EOF
)

# Run once (--rm is back? No, keep it persistent for debugging if it fails)
fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --region "$REGION" \
  --name "manual-fix-test-$(date +%s)" \
  --vm-memory "2048" \
  --env TELEGRAM_ADMIN_CHAT_ID=8290313965 \
  --env FORCE_RUN=1 \
  --entrypoint "sh" \
  --entrypoint "sh" \
  -- -c "$CMD"

echo "✅ Manual trigger sent."
