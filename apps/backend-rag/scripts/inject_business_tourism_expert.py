import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    expert_data = [
        # BUSINESS SERVICES
        {
            "code": "70209",
            "name": "Consulenza Gestionale",
            "bab": "VII (Business Services)",
            "pb_umku": [],
        },
        {
            "code": "73100",
            "name": "Pubblicità & Marketing",
            "bab": "VII (Business Services)",
            "pb_umku": [],
        },
        {
            "code": "74101",
            "name": "Design Interni",
            "bab": "VII (Business Services)",
            "pb_umku": ["Certificato Competenza Professionale"],
        },
        {
            "code": "74102",
            "name": "Design Grafico",
            "bab": "VII (Business Services)",
            "pb_umku": [],
        },
        {"code": "74201", "name": "Fotografia", "bab": "VII (Business Services)", "pb_umku": []},
        {
            "code": "74902",
            "name": "Traduzione",
            "bab": "VII (Business Services)",
            "pb_umku": ["Certificato Traduttore Giurato"],
        },
        {
            "code": "82110",
            "name": "Uffici Virtuali/Amm.",
            "bab": "VII (Business Services)",
            "pb_umku": ["Izin Operasional Virtual Office"],
        },
        {
            "code": "82301",
            "name": "Organizzazione Eventi/MICE",
            "bab": "IV (Turismo)",
            "risk": "Menengah Tinggi",
            "pb_umku": ["Standard Usaha MICE", "Certificazione LSPr"],
        },
        # TURISMO & SVAGO
        {
            "code": "79111",
            "name": "Agenzie Viaggio",
            "bab": "IV (Turismo)",
            "pb_umku": ["TDUP", "Sertifikat Standar"],
        },
        {
            "code": "79121",
            "name": "Tour Operator",
            "bab": "IV (Turismo)",
            "risk": "Menengah Tinggi",
            "pb_umku": ["Certificazione LSPr", "TDUP"],
        },
        {"code": "79911", "name": "Info Turistiche", "bab": "IV (Turismo)", "pb_umku": []},
        {
            "code": "93193",
            "name": "Diving/Sub",
            "bab": "IV (Turismo)",
            "risk": "Menengah Tinggi",
            "pb_umku": ["Standard Sicurezza Subacquea", "Certificazione Istruttori"],
        },
        {
            "code": "93210",
            "name": "Parchi a tema",
            "bab": "IV (Turismo)",
            "risk": "Tinggi",
            "pb_umku": ["Izin Taman Rekreasi", "Certificato SLS"],
        },
        {
            "code": "93221",
            "name": "Beach Clubs / Nightclubs",
            "bab": "IV (Turismo)",
            "risk": "Tinggi",
            "pb_umku": [
                "Sertifikat Laik Sehat (SLS)",
                "SKPL A/B/C (Alcolici)",
                "Izin Gangguan (UUG/HO)",
            ],
        },
        {
            "code": "93224",
            "name": "Musica dal vivo",
            "bab": "IV (Turismo)",
            "pb_umku": ["Permesso Diritti d'Autore (LMKN)"],
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
            "risk_override": item.get("risk", "Rendah"),
            "obligations": [
                "Laporan LKPM trimestrale",
                "Conformità agli standard professionali",
                "Pagamento tasse locali (PBJT) se applicabile",
            ],
            "pma_implications": "TERBUKA (100% Foreign Ownership). Tour Operator e Eventi richiedono certificazioni LSPr per PMA.",
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
        print(f"✅ Arricchito {entity_id}: Business/Tourism Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
