import asyncio
import logging

import asyncpg

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_db():
    print(f"Connecting to DB: {settings.database_url}")
    try:
        pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=1)
        print("✅ DB Connected")

        async with pool.acquire() as conn:
            print("Running context query...")
            user_id = "test-user"
            query_profile = """
                SELECT id, full_name as name, role, department, team,
                       preferred_language, notes, emotional_preferences
                FROM team_members
                WHERE id = $1 OR email = $1
            """
            # Timeout to detect hang
            row = await asyncio.wait_for(conn.fetchrow(query_profile, user_id), timeout=5)
            print(f"✅ Query Result: {row}")

    except asyncio.TimeoutError:
        print("❌ DB Query TIMED OUT (Hung)")
    except Exception as e:
        print(f"❌ DB Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_db())
