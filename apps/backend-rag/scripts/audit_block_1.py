import asyncio
import json

import asyncpg


async def review_block_1():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    target_codes = ["kbli:46333", "kbli:47111", "kbli:47721", "kbli:47811"]

    print("--- REVISIONE INTEGRITA DATI BLOCO 1 ---")
    for entity_id in target_codes:
        row = await conn.fetchrow(
            "SELECT name, properties FROM kg_nodes WHERE entity_id = $1", entity_id
        )
        if row:
            props = (
                json.loads(row["properties"])
                if isinstance(row["properties"], str)
                else row["properties"]
            )
            print("\nID: " + entity_id + " | Nome: " + row["name"])
            print("Expert Legal: " + json.dumps(props.get("expert_legal"), indent=2))
            if "bali_moratorium" in props:
                print("ALERT: Bali Moratorium: " + json.dumps(props["bali_moratorium"], indent=2))
        else:
            print("\nNOT FOUND: " + entity_id)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(review_block_1())
