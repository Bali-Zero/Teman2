import asyncio
import json

import asyncpg


async def run():
    # Database connection using provided credentials
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    hospitality_data = [
        {
            "code": "55101",
            "name": "Hotel Bintang Lima",
            "desc": "Aktivitas Hotel Bintang Lima (5 Stars)",
        },
        {
            "code": "55102",
            "name": "Hotel Bintang Empat",
            "desc": "Aktivitas Hotel Bintang Empat (4 Stars)",
        },
        {
            "code": "55103",
            "name": "Hotel Bintang Tiga",
            "desc": "Aktivitas Hotel Bintang Tiga (3 Stars)",
        },
        {
            "code": "55104",
            "name": "Hotel Bintang Dua",
            "desc": "Aktivitas Hotel Bintang Dua (2 Stars)",
        },
        {
            "code": "55105",
            "name": "Hotel Bintang Satu",
            "desc": "Aktivitas Hotel Bintang Satu (1 Star)",
        },
        {"code": "55106", "name": "Aparthotel", "desc": "Aktivitas Apartemen Hotel"},
    ]

    expert_legal = {
        "regulation": "PP 28/2025",
        "bab": "IV (Sektor Pariwisata)",
        "pasal": "Paragraf 1 (Usaha Penyediaan Akomodasi)",
        "lampiran": "II (Standar Usaha Perhotelan)",
        "pb_umku": [
            "Sertifikat Laik Sehat (Health Eligibility)",
            "SKPL A/B/C (Licenza vendita alcolici)",
            "Izin Mempekerjakan Tenaga Kerja Asing (IMTA)",
        ],
        "obligations": [
            "Self-assessment standard hotel (Sarana, SDM, Pelayanan)",
            "Laporan LKPM (Investment Activity Report) trimestrale",
            "Sertifikasi Usaha Hotel via LSPr (obbligatorio per PMA)",
        ],
        "pma_implications": "100% Foreign Ownership allowed (TERBUKA)",
    }

    sql = """
        INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (entity_id) DO UPDATE
        SET properties = EXCLUDED.properties, description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
    """

    for item in hospitality_data:
        entity_id = f"kbli:{item['code']}"
        props = {"kode": item["code"], "pma_status": "TERBUKA", "expert_legal": expert_legal}

        await conn.execute(
            sql, entity_id, "kbli", f"KBLI {item['code']}", item["desc"], json.dumps(props)
        )
        print(f"✅ Populated and Enriched: {entity_id}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
