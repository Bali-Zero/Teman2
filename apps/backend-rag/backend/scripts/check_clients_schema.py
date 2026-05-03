import asyncio

import asyncpg

from backend.app.core.config import settings


async def check():
    conn = await asyncpg.connect(settings.database_url)
    print("--- Table: clients ---")
    res = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'clients'",
    )
    for r in res:
        print(f"{r['column_name']}: {r['data_type']}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
