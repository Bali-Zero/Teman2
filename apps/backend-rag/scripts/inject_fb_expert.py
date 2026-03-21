import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    fb_data = [
        {
            "code": "56101",
            "name": "Restoran",
            "desc": "Aktivitas penyediaan layanan makanan di bangunan tetap.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "IV (Sektor Pariwisata)",
                "pasal": "Paragraf 2 (Usaha Jasa Makanan dan Minuman)",
                "lampiran": "II (Standar Usaha Restoran)",
                "pb_umku": [
                    "Label Higiene Sanitasi Pangan (HSP)",
                    "Sertifikat Laik Sehat (SLS)",
                    "SKPL A/B/C - per vendita alcolici (se applicabile)",
                    "Sertifikasi Halal (obbligatorio secondo scadenze governative)",
                ],
                "obligations": [
                    "Laporan LKPM trimestrale",
                    "Conformità agli standard di sicurezza alimentare",
                    "Sertifikasi Usaha Restoran via LSPr (per PMA)",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Investimento minimo 10 Miliar IDR (escluso terreno/edifici) richiesto per PT PMA.",
            },
        },
        {
            "code": "56301",
            "name": "Bar",
            "desc": "Aktivitas penyediaan minuman beralkohol e accompagnamenti leggeri.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "IV (Sektor Pariwisata)",
                "pasal": "Paragraf 2 (Usaha Bar)",
                "lampiran": "II (Standar Usaha Bar)",
                "pb_umku": [
                    "Surat Keterangan Penjualan Langsung (SKPL) - Obbligatorio",
                    "Label Higiene Sanitasi Pangan (HSP)",
                    "Izin Gangguan (UUG/HO) - spesso richiesto a livello locale",
                ],
                "obligations": [
                    "Laporan LKPM trimestrale",
                    "Restrizioni su zone di vendita (distanza da luoghi di culto/scuole)",
                    "Monitoraggio dell'età dei clienti (min. 21 anni per alcolici)",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Soggetto a tassazione specifica (Pajak Barang dan Jasa Tertentu - PBJT).",
            },
        },
        {
            "code": "56303",
            "name": "Rumah Minum/Kafe",
            "desc": "Aktivitas penyediaan minuman (caffè, tè, ecc.) e snack in edifici fissi.",
            "expert_legal": {
                "regulation": "PP 28/2025",
                "bab": "IV (Sektor Pariwisata)",
                "pasal": "Paragraf 2 (Usaha Kafe)",
                "lampiran": "II (Standar Usaha Kafe)",
                "pb_umku": [
                    "Label Higiene Sanitasi Pangan (HSP)",
                    "Sertifikat Laik Sehat (SLS)",
                    "Sertifikasi Halal",
                ],
                "obligations": [
                    "Laporan LKPM trimestrale",
                    "Mantenimento degli standard di servizio e pulizia",
                ],
                "pma_implications": "TERBUKA (100% Foreign Ownership allowed). Spesso utilizzato per modelli di business più agili rispetto al ristorante.",
            },
        },
    ]

    sql = """
        INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (entity_id) DO UPDATE
        SET properties = EXCLUDED.properties, description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
    """

    for item in fb_data:
        entity_id = f"kbli:{item['code']}"
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
        print(f"✅ Arricchito {entity_id}: F&B Expert Data")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
