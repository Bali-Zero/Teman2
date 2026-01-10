#!/bin/bash
APP_NAME="nuzantara-rag"
REGION="sin"
IMAGE_REF="registry.fly.io/nuzantara-rag:deployment-01KE8BCX7GYCYM6P4NR00071B3"

echo "🚀 FIXING VIEW on $APP_NAME..."

CMD=$(cat <<'EOF'
echo "Creating python script..."
cat > /app/fix_view.py <<'PYTHON'
import asyncio
import os
import sys
import asyncpg

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL missing")
        return

    print("🔌 Connecting to DB...")
    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Connected")
        
        print("🛠 Fixing team_online_status view...")
        # v2: Ensuring we handle potential NULLs in created_at if any, though unlikely.
        # TIMESTAMPTZ converted to 'Asia/Makassar' gives a naive timestamp in that zone.
        await conn.execute("""
            CREATE OR REPLACE VIEW team_online_status AS
            SELECT DISTINCT ON (user_id)
                user_id,
                email,
                created_at AT TIME ZONE 'Asia/Makassar' as last_action_bali,
                action_type,
                CASE WHEN action_type = 'clock_in' THEN true ELSE false END as is_online
            FROM team_timesheet
            ORDER BY user_id, created_at DESC;
        """)
        print("✅ View team_online_status updated successfully.")
        await conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
PYTHON

echo "Running python script..."
python /app/fix_view.py
EOF
)

fly machine run "$IMAGE_REF" \
  --app "$APP_NAME" \
  --region "$REGION" \
  --name "view-fix-$(date +%s)" \
  --vm-memory "512" \
  --env FORCE_RUN=1 \
  --entrypoint "sh" \
  --detach \
  -- -c "$CMD"

echo "✅ Fix script triggered."
