import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    trade_data = [
        {
            "code": "46100",
            "name": "Intermediazione all'ingrosso",
            "pb_umku": ["Registrazione intermediario commerciale (Ministero Commercio)"],
        },
        {
            "code": "46333",
            "name": "Wholesale Alcolici",
            "risk": "Tinggi",
            "pb_umku": [
                "SIUP-MB (Bevande Alcoliche)",
                "Licenza distribuzione NPPBKC",
                "NIB con validazione speciale",
            ],
        },
        {
            "code": "46411",
            "name": "Wholesale Tessili",
            "pb_umku": ["Standard sicurezza tessile (K3L)"],
        },
        {
            "code": "46421",
            "name": "Wholesale Abbigliamento",
            "pb_umku": ["Etichettatura conforme lingua indonesiana"],
        },
        {
            "code": "46491",
            "name": "Wholesale Mobili/Export",
            "pb_umku": ["V-Legal (SVKP) - Obbligatorio per export legno"],
        },
        {
            "code": "46530",
            "name": "Wholesale Macchine Agricole",
            "pb_umku": ["Certificato garanzia e manuale in Bahasa Indonesia"],
        },
        {
            "code": "46631",
            "name": "Wholesale Mat. Costruzione",
            "pb_umku": ["SNI (Standard Nazionale Indonesiano) per materiali certificati"],
        },
        {
            "code": "47111",
            "name": "Minimarket",
            "risk": "Menengah Tinggi",
            "pb_umku": ["Izin Toko Swalayan (ITS)", "Kemitraan obbligatoria con UMKM locali"],
        },
        {
            "code": "47411",
            "name": "Retail Computer/Software",
            "pb_umku": ["Registrazione garanzia post-vendita"],
        },
        {
            "code": "47591",
            "name": "Retail Mobili",
            "pb_umku": ["Esposizione showroom conforme norme sicurezza"],
        },
        {"code": "47711", "name": "Retail Abbigliamento", "pb_umku": ["Standard retail moderno"]},
        {
            "code": "47721",
            "name": "Retail Cosmetici",
            "pb_umku": ["Izin Edar BPOM (Requisito bloccante)", "Notifikasi Kosmetika"],
        },
        {
            "code": "47733",
            "name": "Retail Arte/Antiquariato",
            "pb_umku": ["Certificato autenticità/origine (Cagar Budaya se antico)"],
        },
        {
            "code": "47811",
            "name": "E-commerce",
            "risk": "Menengah Tinggi",
            "pb_umku": ["TDPSE (Tanda Daftar Penyelenggara Sistem Elektronik)"],
        },
        {
            "code": "47912",
            "name": "Retail Mail Order/TV",
            "pb_umku": ["PSE Kominfo", "Licenza televendite"],
        },
    ]

    for item in trade_data:
        entity_id = f"kbli:{item['code']}"
        row = await conn.fetchrow(
            "SELECT properties, name FROM kg_nodes WHERE entity_id = $1", entity_id
        )

        current_props = (
            json.loads(row["properties"]) if row and row["properties"] else {"kode": item["code"]}
        )

        # Expert Legal Enrichment
        current_props["expert_legal"] = {
            "regulation": "PP 28/2025",
            "bab": "VI (Sektor Perdagangan)",
            "pasal": "Persyaratan Usaha Perdagangan (Lampiran III)",
            "pb_umku": item.get("pb_umku", []),
            "risk_override": item.get("risk", "Rendah"),
            "obligations": [
                "Laporan LKPM trimestrale",
                "Laporan Distribuzione (per alcolici/beni regolamentati)",
                "Pajak Pertambahan Nilai (PPN) compliance",
            ],
            "pma_implications": "TERBUKA (100% Foreign Ownership) per commercio all'ingrosso. Il commercio al dettaglio (47xxx) richiede investimenti minimi di 10 Miliar IDR per PT PMA.",
        }

        # Esecuzione Update
        sql = """
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (entity_id) DO UPDATE
            SET properties = EXCLUDED.properties, updated_at = CURRENT_TIMESTAMP
        """
        name = row["name"] if row else f"KBLI {item['code']}: {item['name']}"
        desc = f"Attività di {item['name']} secondo standard 2025"

        await conn.execute(sql, entity_id, "kbli", name, desc, json.dumps(current_props))
        print(f"✅ Arricchito {entity_id}: Trade Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
