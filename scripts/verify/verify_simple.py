import asyncio

import asyncpg


async def verify_simple():
    try:
        conn = await asyncpg.connect("postgres://localhost:5432/nuzantara_dev")

        kg_count = await conn.fetchval("SELECT COUNT(*) FROM kg_entities")
        gr_count = await conn.fetchval("SELECT COUNT(*) FROM golden_routes")

        print(f"KG Entities: {kg_count}")
        print(f"Golden Routes: {gr_count}")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(verify_simple())
