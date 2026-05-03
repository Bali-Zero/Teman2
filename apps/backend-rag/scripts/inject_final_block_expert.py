import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    expert_data = [
        # TRASPORTI & LOGISTICA
        {
            "code": "49422",
            "name": "Noleggio Auto/Moto",
            "bab": "X (Trasporti)",
            "risk": "Menengah Tinggi",
            "pb_umku": ["Izin Penyelenggaraan Angkutan Orang", "Standard Sicurezza Veicoli"],
        },
        {
            "code": "49431",
            "name": "Trasporto Merci",
            "bab": "X (Trasporti)",
            "pb_umku": ["Izin Trasporto Merci"],
        },
        {
            "code": "52291",
            "name": "Logistica / Freight Forwarding",
            "bab": "X (Trasporti)",
            "pb_umku": ["Izin Jasa Pengurusan Transportasi (JPT)"],
        },
        # EDUCAZIONE & TRAINING
        {
            "code": "85491",
            "name": "Corsi di Lingua",
            "bab": "XI (Education)",
            "pb_umku": ["Izin Lembaga Kursus dan Pelatihan (LKP)"],
        },
        {
            "code": "85492",
            "name": "Workshop & Training (Yoga/Cucina)",
            "bab": "XI (Education)",
            "risk": "Menengah Tinggi",
            "pb_umku": ["Izin LKP", "Certificazioni Istruttori Professionisti"],
        },
        {
            "code": "85499",
            "name": "Altri Servizi Istruzione",
            "bab": "XI (Education)",
            "pb_umku": ["Standard Educazione Non Formale"],
        },
    ]

    for item in expert_data:
        entity_id = f"kbli:{item['code']}"
        row = await conn.fetchrow("SELECT properties FROM kg_nodes WHERE entity_id = $1", entity_id)
        current_props = (
            json.loads(row["properties"]) if row and row["properties"] else {"kode": item["code"]}
        )

        current_props["expert_legal"] = {
            "regulation": "PP 28/2025",
            "bab": item["bab"],
            "pasal": "Persyaratan Usaha Sektoral 2025",
            "pb_umku": item.get("pb_umku", []),
            "risk_override": item.get("risk", "Menengah Rendah"),
            "obligations": [
                "Laporan LKPM trimestrale",
                "Conformità agli standard nazionali di settore",
                "Assicurazione responsabilità civile",
            ],
            "pma_implications": "TERBUKA (100%). ALLERTA OPERATIVA: Per Workshop (85492), gli istruttori stranieri devono avere KITAS specifico e la struttura deve essere certificata LKP. Monitoraggio rigoroso su ritiri spirituali e sportivi.",
        }

        sql = """
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (entity_id) DO UPDATE
            SET properties = EXCLUDED.properties, updated_at = CURRENT_TIMESTAMP
        """
        name = f"KBLI {item['code']}: {item['name']}"
        desc = f"Servizi di {item['name']} secondo standard 2025"
        await conn.execute(sql, entity_id, "kbli", name, desc, json.dumps(current_props))
        print(f"✅ Arricchito {entity_id}: Final Block Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
