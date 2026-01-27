import asyncio

import asyncpg

from backend.app.core.config import settings


async def check():
    conn = await asyncpg.connect(settings.database_url)
    print("--- Table: team_members ---")
    res = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'team_members'"
    )
    for r in res:
        print(f"{r['column_name']}: {r['data_type']}")

    print("\n--- Table: users ---")
    res = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users'"
    )
    for r in res:
        print(f"{r['column_name']}: {r['data_type']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
