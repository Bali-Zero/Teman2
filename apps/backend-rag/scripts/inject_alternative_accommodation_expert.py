import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    accommodation_data = [
        {
            "code": "55203",
            "name": "Aktivitas Vila",
            "desc": "Fornitura di servizi di alloggio a breve termine in case private o appartamenti affittati a turisti.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "IV (Sektor Pariwisata)",
                "pasal": "Paragraf 1 (Usaha Vila)",
                "lampiran": "II (Standar Usaha Vila)",
                "pb_umku": [
                    "Sertifikat Laik Sehat (Health Eligibility)",
                    "Tanda Daftar Usaha Pariwisata (TDUP) - per attività turistiche",
                    "Persetujuan Bangunan Gedung (PBG) - funzione alloggio",
                ],
                "obligations": [
                    "Laporan LKPM (Laporan Kegiatan Penanaman Modal) trimestrale",
                    "Self-assessment kesiapan penerapan standar usaha Vila",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed) se operata tramite PT PMA. Attenzione: affitto giornaliero richiede licenze specifiche e conformità alla zona turistica.",
            },
        },
        {
            "code": "55106",
            "name": "Apartemen Hotel (Aparthotel)",
            "desc": "Alloggio in stile appartamento con servizi alberghieri integrati (nuovo codice 2025).",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "IV (Sektor Pariwisata)",
                "pasal": "Paragraf 1 (Usaha Apartemen Hotel)",
                "lampiran": "II (Standar Usaha Apartemen Hotel)",
                "pb_umku": [
                    "Sertifikat Laik Sehat (Health Eligibility)",
                    "Sertifikasi Usaha Hotel via LSPr (obbligatorio per PMA)",
                    "SKPL A/B/C (se presente vendita alcolici)",
                ],
                "obligations": [
                    "Laporan LKPM trimestrale",
                    "Monitoraggio standard qualitativi alberghieri",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Richiede investimenti minimi di capitale (PT PMA).",
            },
        },
        {
            "code": "55201",
            "name": "Pondok Wisata (Guesthouse)",
            "desc": "Alloggio in case private gestite dal proprietario, tipico per turismo rurale/locale.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "IV (Sektor Pariwisata)",
                "pasal": "Paragraf 1 (Usaha Pondok Wisata)",
                "lampiran": "II (Standar Usaha Pondok Wisata)",
                "pb_umku": ["Sertifikat Laik Sehat (SLS)", "TDUP - Tanda Daftar Usaha Pariwisata"],
                "obligations": [
                    "Conformità alle norme di sicurezza locali",
                    "Registrazione ospiti per fini statistici e di sicurezza",
                ],
                "pma_implications": "ATTENZIONE: Solitamente riservato a micro e piccole imprese locali (UMKM). Per gli stranieri (PT PMA), lo status è TERBATAS o richiede requisiti speciali di capitale.",
            },
        },
    ]

    sql = """
        INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (entity_id) DO UPDATE
        SET properties = EXCLUDED.properties, description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
    """

    for item in accommodation_data:
        entity_id = f"kbli:{item['code']}"
        props = {
            "kode": item["code"],
            "pma_status": "TERBUKA" if item["code"] != "55201" else "TERBATAS",
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
        print(f"✅ Arricchito {entity_id}: Accommodation Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
