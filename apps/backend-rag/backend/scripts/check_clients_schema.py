import asyncio

import asyncpg

from backend.app.core.config import settings


async def check():
    conn = await asyncpg.connect(settings.database_url)
    res = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'clients'",
    )
    for _r in res:
        pass
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check())
