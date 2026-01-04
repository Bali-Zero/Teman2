import asyncio
import logging
import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "backend"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use production DATABASE_URL from environment (set by Fly.io secrets)
# or override for local dev
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"
    logger.info(f"Set DATABASE_URL to default: {os.environ['DATABASE_URL']}")

from backend.app.modules.identity.service import IdentityService


async def check_user_facts():
    """Check if user_memory_facts exist for zero@balizero.com"""
    user_id = "zero@balizero.com"

    logger.info(f"Checking user_memory_facts for: {user_id}")

    service = IdentityService()
    conn = await service.get_db_connection()

    try:
        # Check if table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'user_memory_facts'
            );
            """
        )

        if not table_exists:
            logger.error("❌ Table 'user_memory_facts' does not exist!")
            return

        # Query user facts
        rows = await conn.fetch(
            """
            SELECT user_id, fact_type, content, created_at
            FROM user_memory_facts
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 10
            """,
            user_id,
        )

        if rows:
            logger.info(f"✅ FOUND {len(rows)} user facts for {user_id}:")
            logger.info("-" * 100)
            for i, row in enumerate(rows, 1):
                logger.info(f"{i}. Type: {row['fact_type']}")
                logger.info(f"   Content: {row['content'][:200]}")
                logger.info(f"   Created: {row['created_at']}")
                logger.info("")
        else:
            logger.warning(f"❌ NO user facts found for {user_id}")
            logger.warning("This explains why user recognition doesn't work!")

            # Check if there are ANY user facts in the table
            total_count = await conn.fetchval("SELECT COUNT(*) FROM user_memory_facts")
            logger.info(f"Total user_memory_facts in database: {total_count}")

            if total_count > 0:
                # Show sample of other users
                sample_users = await conn.fetch(
                    """
                    SELECT DISTINCT user_id
                    FROM user_memory_facts
                    LIMIT 5
                    """
                )
                logger.info("Sample users with facts:")
                for user in sample_users:
                    logger.info(f"  - {user['user_id']}")

    except Exception as e:
        logger.error(f"Query failed: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_user_facts())
