#!/bin/bash
# Verify Online Status on Fly.io
APP_NAME="nuzantara-rag"
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KEBVNV2N6JDEFC58SP62WKGP"

echo "🚀 Verifying Team Online Status..."

CMD=$(cat <<'EOF'
cat > /app/verify_status.py <<'PYTHON'
import asyncio
import os
import asyncpg
from datetime import datetime
from zoneinfo import ZoneInfo

async def main():
    DB_URL = os.getenv("DATABASE_URL")
    if not DB_URL:
        print("❌ DATABASE_URL missing")
        return

    try:
        pool = await asyncpg.create_pool(DB_URL)
        print("✅ DB Connected")
        
        async with pool.acquire() as conn:
            print("\n📊 TEAM ONLINE STATUS VIEW:")
            print("-" * 60)
            rows = await conn.fetch("SELECT * FROM team_online_status ORDER BY last_action_bali DESC")
            
            if not rows:
                print("No online status records found.")
            
            for row in rows:
                status_icon = "🟢" if row['is_online'] else "🔴"
                email = row['email']
                action_time = row['last_action_bali'].strftime("%H:%M")
                
                print(f"{status_icon} {email:<30} {action_time}")
                
            print("-" * 60)
            
            # Check for specific user 'ruslana'
            print("\n🔍 Checking Ruslana specific status:")
            ruslana = next((r for r in rows if "ruslana" in r['email']), None)
            if ruslana:
                print(f"   Found: {ruslana['email']}")
                print(f"   Online: {ruslana['is_online']}")
                print(f"   Last Action: {ruslana['last_action_bali']}")
            else:
                print("   ❌ Ruslana not found in status view")

        await pool.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

python /app/verify_status.py
EOF
)

fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --name "verify-status-$(date +%s)" \
  --rm \
  --entrypoint "sh" \
  --env FORCE_RUN=1 \
  -- -c "$CMD"
