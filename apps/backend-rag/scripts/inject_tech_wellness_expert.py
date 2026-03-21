import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    expert_data = [
        # DIGITAL & TECH
        {
            "code": "62011",
            "name": "Sviluppo Software",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["TDPSE (PSE Kominfo)"],
        },
        {
            "code": "62012",
            "name": "App Mobile",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["TDPSE (PSE Kominfo)"],
        },
        {"code": "62015", "name": "Consulenza IT", "bab": "IX (Digital/IT)", "pb_umku": []},
        {
            "code": "62019",
            "name": "AI & Programmazione Avanzata",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["Certificazione Algoritmi (se applicabile)", "Conformità Data Privacy"],
        },
        {
            "code": "63111",
            "name": "Hosting/Data Center",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["Certificazione Sicurezza Infrastruttura"],
        },
        {
            "code": "63121",
            "name": "Portali Web",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["PSE Kominfo"],
        },
        {
            "code": "63122",
            "name": "E-commerce Terzi",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["PSE Kominfo", "Licenza intermediario digitale"],
        },
        {
            "code": "63912",
            "name": "Agenzie Stampa",
            "bab": "IX (Digital/IT)",
            "pb_umku": ["Registrazione Consiglio Stampa"],
        },
        # WELLNESS & HEALTH
        {
            "code": "96101",
            "name": "SPA",
            "bab": "VIII (Wellness)",
            "risk": "Menengah Tinggi",
            "pb_umku": [
                "Sertifikat Laik Sehat (SLS)",
                "Standard Usaha SPA (Lampiran VIII)",
                "Licenza operatore tecnico SPA",
            ],
        },
        {
            "code": "96102",
            "name": "Massaggi Terapeutici",
            "bab": "VIII (Wellness)",
            "pb_umku": ["Sertifikat SLS"],
        },
        {
            "code": "96111",
            "name": "Saloni Bellezza",
            "bab": "VIII (Wellness)",
            "pb_umku": ["Standard Igiene Bellezza"],
        },
        {"code": "96112", "name": "Barbieri", "bab": "VIII (Wellness)", "pb_umku": []},
        {
            "code": "86101",
            "name": "Ospedali Privati",
            "bab": "VIII (Health)",
            "risk": "Tinggi",
            "pb_umku": [
                "Izin Operasional Rumah Sakit",
                "Sertifikat Akreditasi",
                "Permesso impiego medici stranieri (TKWNA)",
            ],
        },
        {
            "code": "86201",
            "name": "Cliniche Mediche",
            "bab": "VIII (Health)",
            "risk": "Tinggi",
            "pb_umku": ["Izin Klinik", "Sertifikat SLS", "TKWNA permits"],
        },
        {
            "code": "86901",
            "name": "Medicina Alternativa",
            "bab": "VIII (Health)",
            "pb_umku": ["Sertifikat STPT (Medicina Tradizionale)"],
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
            "pasal": "Persyaratan Usaha Sektoral (Lampiran VIII/IX)",
            "pb_umku": item.get("pb_umku", []),
            "risk_override": item.get("risk", "Menengah Rendah"),
            "obligations": [
                "Laporan LKPM trimestrale",
                "Conformità agli standard professionali di settore",
                "Protezione dati e privacy (per Tech)",
            ],
            "pma_implications": "TERBUKA (100% Foreign Ownership). Settore ad alto potenziale per investitori a Bali.",
        }

        sql = """
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (entity_id) DO UPDATE
            SET properties = EXCLUDED.properties, updated_at = CURRENT_TIMESTAMP
        """
        name = f"KBLI {item['code']}: {item['name']}"
        desc = f"Attività di {item['name']} secondo standard 2025"

        await conn.execute(sql, entity_id, "kbli", name, desc, json.dumps(current_props))
        print(f"✅ Arricchito {entity_id}: Tech/Wellness Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
