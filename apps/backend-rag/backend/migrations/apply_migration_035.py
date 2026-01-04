import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv("apps/backend-rag/.env")
DATABASE_URL = os.getenv("DATABASE_URL")


async def apply():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kbli_blueprints (
                kbli_code TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                risk_level TEXT,
                min_capital TEXT,
                summary TEXT,
                access_level TEXT DEFAULT 'client',
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        print("✅ Table kbli_blueprints created.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(apply())
