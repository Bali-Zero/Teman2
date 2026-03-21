import asyncio
import json

import asyncpg


async def run():
    # Database connection with local credentials
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    real_estate_data = [
        {
            "code": "68111",
            "name": "Real Estat Dimiliki/Disewa",
            "desc": "Aktivitas real estat che sono di proprietà o in affitto, include lo sviluppo e la vendita di proprietà.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "V (Sektor Properti)",
                "pasal": "Norme Specifiche (Lampiran III)",
                "pb_umku": [
                    "Sertifikat Hak Guna Bangunan (HGB) - per entità legali",
                    "Hak Pakai - per stranieri (diritto d'uso/possesso)",
                    "Persetujuan Bangunan Gedung (PBG) - ex IMB",
                    "Sertifikat Laik Fungsi (SLF)",
                ],
                "obligations": [
                    "Laporan LKPM (Laporan Kegiatan Penanaman Modal) trimestrale",
                    "Conformità alla pianificazione spaziale (KKPR/ITR)",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Gli investitori stranieri operano tipicamente tramite Hak Pakai o HGB (tramite PT PMA).",
            },
        },
        {
            "code": "68112",
            "name": "Real Estat Berdasarkan Balas Jasa",
            "desc": "Aktivitas real estat su commissione (fee basis), es. Property Management.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "V (Sektor Properti)",
                "pasal": "Norme Specifiche (Lampiran III)",
                "pb_umku": [
                    "Sertifikat Laik Higiene Sanitasi (SLHS) - obbligatorio per gestione affitti brevi",
                    "Sertifikat Laik Sehat (SLS)",
                    "Tanda Daftar Usaha Pariwisata (TDUP) - se la proprietà è registrata come alloggio turistico",
                ],
                "obligations": [
                    "Laporan LKPM (Laporan Kegiatan Penanaman Modal) trimestrale",
                    "Registrazione come gestore professionale di proprietà",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Non implica il possesso del terreno.",
            },
        },
        {
            "code": "68210",
            "name": "Broker Real Estat",
            "desc": "Servizi di intermediazione e pialang immobiliare (nuovo codice KBLI 2025).",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "V (Sektor Properti)",
                "pasal": "Norme Specifiche (Lampiran III)",
                "pb_umku": [
                    "Sertifikat Keahlian Broker Properti (Lisenza Professionale)",
                    "Izin Usaha Pialang Properti (IUPP) - Licenza aziendale",
                ],
                "obligations": [
                    "Registrazione presso le associazioni di categoria riconosciute",
                    "Conformità alle normative anti-riciclaggio (APU PPT)",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Richiede professionisti certificati a livello locale.",
            },
        },
    ]

    sql = """
        INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (entity_id) DO UPDATE
        SET properties = EXCLUDED.properties, description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
    """

    for item in real_estate_data:
        entity_id = f"kbli:{item['code']}"
        # Pre-populate properties with pma_status and expert_legal
        props = {
            "kode": item["code"],
            "pma_status": "TERBUKA",
            "expert_legal": item["expert_legal"],
        }

        await conn.execute(
            sql,
            entity_id,
            "kbli",
            f"KBLI {item['code']}: {item['name']}",
            item["desc"],
            json.dumps(props),
        )
        print(f"✅ Arricchito {entity_id}: Real Estate Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
