#!/usr/bin/env python3
import asyncio
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
from app.core.config import settings

async def run_migration():
    if not settings.database_url:
        print("❌ DATABASE_URL missing")
        return False
    
    try:
        print("🔌 Connecting to DB...")
        conn = await asyncpg.connect(settings.database_url)
        print("✅ Connected")
        
        print("🛠 Fixing team_online_status view...")
        # We assume created_at is TIMESTAMPTZ (UTC). 
        # We convert to Asia/Makassar to match the 'last_action_bali' expectation of being naive Bali time.
        # DISTINCT ON (user_id) ensures we get the very last action per user.
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
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run_migration()) else 1)
