#!/bin/bash
# Deactivate specific users from team_members
# Usage: ./scripts/deactivate_users.sh

APP_NAME="nuzantara-rag"
REGION="sin"
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KE8BCX7GYCYM6P4NR00071B3"

echo "🚀 TRIGGERING USER DEACTIVATION on $APP_NAME..."

CMD=$(cat <<'EOF'
cat > /app/run_fix.py <<'PYTHON'
import asyncio
import os
import asyncpg

async def main():
    print("🔌 Connecting to DB...")
    DB_URL = os.getenv("DATABASE_URL")
    if not DB_URL:
        print("❌ DATABASE_URL missing")
        return

    pool = await asyncpg.create_pool(DB_URL)
    print("✅ Connected")
    
    targets = [
        'test.sim.cfdb9611@example.com',
        'antonello@test.com',
        'testclient3@example.com',
        'demo4@balizero.com'
    ]
    
    async with pool.acquire() as conn:
        print(f"🎯 Deactivating {len(targets)} users...")
        for email in targets:
            result = await conn.execute(
                "UPDATE team_members SET active = false WHERE email = $1", 
                email
            )
            print(f"   - {email}: {result}")
            
    await pool.close()
    print("✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

python /app/run_fix.py
EOF
)

fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --region "$REGION" \
  --name "admin-fix-$(date +%s)" \
  --vm-memory "512" \
  --env FORCE_RUN=1 \
  --entrypoint "sh" \
  --rm \
  -- -c "$CMD"
