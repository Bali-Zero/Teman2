import asyncio
import json

import asyncpg


async def inspect():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )
    row = await conn.fetchrow("SELECT properties FROM kg_nodes WHERE entity_id = 'kbli:56303'")
    if row:
        props = (
            json.loads(row["properties"])
            if isinstance(row["properties"], str)
            else row["properties"]
        )
        print(json.dumps(props, indent=2))
    await conn.close()


if __name__ == "__main__":
    asyncio.run(inspect())
