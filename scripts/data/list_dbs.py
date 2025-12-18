import asyncio

import asyncpg


async def list_dbs():
    conn = await asyncpg.connect("postgres://localhost:5432/postgres")
    rows = await conn.fetch(
        "SELECT datname FROM pg_database WHERE datistemplate = false;"
    )
    print("Databases:")
    for row in rows:
        print(f"- {row['datname']}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(list_dbs())
