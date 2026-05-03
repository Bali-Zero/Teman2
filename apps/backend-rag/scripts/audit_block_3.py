import asyncio
import json

import asyncpg


async def review_block_3():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )
    target_codes = ["kbli:70209", "kbli:93221", "kbli:79121", "kbli:82110"]
    print("--- REVISIONE INTEGRITA DATI BLOCO 3 (Business & Tourism) ---")
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
            print("\nID: " + str(entity_id))
            expert = props.get("expert_legal")
            if expert:
                print(" - Risk: " + str(expert.get("risk_override")))
                print(" - PMA Note: " + str(expert.get("pma_implications")))
            else:
                print("MISSING expert_legal")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(review_block_3())
