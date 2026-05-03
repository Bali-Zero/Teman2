import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    retail_codes = ["47111", "47112", "47113", "47191"]

    # Dettaglio Moratoria Bali - Basato su INGUB 6/2025
    bali_moratorium = {
        "is_active": True,
        "regulation": "INGUB Bali No. 6/2025",
        "description": "Moratoria totale (penghentian sementara) sul rilascio di nuove licenze per Toko Modern Berjejaring.",
        "impact": "Blocco PBG e licenze commerciali per catene/franchising retail a Bali.",
        "geographic_scope": "Intera Provincia di Bali",
        "legal_basis": "Visi Nangun Sat Kerthi Loka Bali / Haluan Bali 100 Tahun.",
    }

    for code in retail_codes:
        entity_id = f"kbli:{code}"
        row = await conn.fetchrow(
            "SELECT properties, name FROM kg_nodes WHERE entity_id = $1", entity_id
        )

        # Se il nodo non esiste (es. retail non ancora iniettato), lo creo base
        current_props = (
            json.loads(row["properties"]) if row and row["properties"] else {"kode": code}
        )

        # Iniezione allerta
        current_props["bali_moratorium"] = bali_moratorium
        if "expert_legal" not in current_props:
            current_props["expert_legal"] = {"regulation": "PP 28/2025"}

        current_props["expert_legal"]["special_alerts"] = [
            "BALI EXCLUSIVE MORATORIUM: INGUB 6/2025 halts all new modern retail chain licenses."
        ]

        sql = """
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (entity_id) DO UPDATE
            SET properties = EXCLUDED.properties, updated_at = CURRENT_TIMESTAMP
        """
        name = row["name"] if row else f"KBLI {code} (Retail)"
        desc = "Aktivitas Perdagangan Eceran / Toko Modern Berjejaring"

        await conn.execute(sql, entity_id, "kbli", name, desc, json.dumps(current_props))
        print(f"✅ Moratoria Bali iniettata in {entity_id}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
