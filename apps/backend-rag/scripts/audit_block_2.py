import asyncio
import json

import asyncpg


async def review_block_2():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )
    target_codes = ["kbli:96101", "kbli:86201", "kbli:62019", "kbli:63122"]
    print("--- REVISIONE INTEGRITA DATI BLOCO 2 (Tech & Wellness) ---")
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
            expert = props.get("expert_legal")
            if expert:
                print("Expert Legal found for " + entity_id)
                print(" - Regulation: " + str(expert.get("regulation")))
                print(" - Risk Override: " + str(expert.get("risk_override")))
                print(" - PB-UMKU: " + ", ".join(expert.get("pb_umku", [])))
            else:
                print("MISSING expert_legal")
        else:
            print("NOT FOUND: " + entity_id)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(review_block_2())
