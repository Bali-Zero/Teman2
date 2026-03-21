import asyncio
import logging
import os

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Transcription of the document
    text = """GUBERNUR BALI

Bali, 28 Januari 2026

Nomor: B.27.000/642/PM/DPMPTSP
Sifat: Segera
Lampiran: -
Hal: Permohonan Penutupan Penanaman Modal Asing (PMA) pada kegiatan usaha dengan Tingkat Risiko Rendah dan Menengah Rendah dan Penutupan Penanaman Modal Asing (PMA) di virtual office pada Provinsi Bali

Yth. Menteri Investasi dan Hilirisasi/ Kepala BKPM Republik Indonesia
di Jakarta

Menindaklanjuti Nota Kesepakatan antara Kementerian Investasi dan Hilirisasi/BKPM RI dan Pemerintah Provinsi Bali Nomor KS.01.00/2.S/A.1/2026 dan Nomor B.36.100.3.7/2767/KS/B.PEMKESRA tentang Pengendalian Pelaksanaan Penanaman Modal di Provinsi Bali, dengan ini kami sampaikan sebagai berikut:

1. Bahwa berdasarkan rekapitulasi penerbitan Nomor Induk Berusaha (NIB) PMA periode tahun 2021-2025, Provinsi Bali tercatat memiliki 19.262 pelaku usaha PMA, atau sekitar 40 persen dari total NIB PMA nasional, dengan jumlah proyek mencapai 55.458 proyek, dimana 47,55 persen diantaranya merupakan proyek berisiko rendah yang tidak memerlukan sertifikat standar maupun izin lainnya.

2. Kegiatan usaha yang diajukan oleh PMA di Provinsi Bali pada Sistem Online Single Submission (OSS) sebagian besar mengajukan dengan Klasifikasi Baku Lapangan Usaha Indonesia (KBLI):
- 68111 (Real Estate yang Dimiliki Sendiri atau Disewa);
- 70209 (Aktivitas Konsultasi Manajemen Lainnya);
- 77311 (Penyewaan Motor Tanpa Hak Opsi);
- 77100 (Penyewaan Mobil, Bus, Truk dan Sejenisnya);
- 79121 (Aktivitas Biro Perjalanan Wisata);
- 47711 (Perdagangan Eceran Pakaian);
- 47511 (Perdagangan Eceran Tekstil);
- 47249 (Perdagangan Eceran Makanan Lainnya);
- 47991 (Perdagangan Eceran Keliling Komoditi Makanan Dari Hasil Pertanian).

Kegiatan usaha tersebut di atas, hanya memerlukan NIB dan tidak memerlukan Sertifikat Standar atau Perizinan Berusaha lainnya karena memiliki tingkat risiko rendah dan menengah rendah.

3. Skema Perizinan Berusaha tersebut, digunakan sebagai sarana memperoleh izin tinggal bagi WNA (Warga Negara Asing) tanpa adanya kegiatan berusaha yang nyata maupun kontribusi terhadap realisasi investasi.

Sehubungan dengan hal tersebut, kami mohon kepada Bapak Menteri untuk melakukan penutupan pada Sistem Online Single Submission (OSS) dengan kategori:
1. PMA yang menjalankan kegiatan usaha dengan Tingkat Risiko Rendah dan Menengah Rendah yang berada di Provinsi Bali; dan
2. PMA yang berlokasi usaha di virtual office yang berada di Provinsi Bali.

Demikian disampaikan, atas perhatian dan kerjasamanya diucapkan terima kasih.

GUBERNUR BALI,
(Tanda Tangan & Cap)
S. B. WAYAN KOSTER

Tembusan:
1. Menteri Koordinator Bidang Perekonomian Republik Indonesia di Jakarta;
2. Menteri Dalam Negeri Republik Indonesia di Jakarta;
3. Menteri Perdagangan Republik Indonesia di Jakarta;
4. Menteri Hukum Republik Indonesia di Jakarta;
5. Menteri Keuangan Republik Indonesia di Jakarta;
6. Menteri Komunikasi dan Digital Republik Indonesia di Jakarta;
7. Menteri Imigrasi dan Pemasyarakatan Republik Indonesia di Jakarta;
8. Ketua DPRD Provinsi Bali di Bali;
9. Walikota/Bupati se-Bali;
10. Ketua DPRD Kota/Kabupaten se-Bali."""

    # Set metadata manually
    metadata = {
        "type": "SURAT GUBERNUR",
        "type_abbrev": "SURAT_GUB",
        "number": "B.27.000/642/PM/DPMPTSP",
        "year": "2026",
        "topic": "Penutupan PMA Risiko Rendah/Menengah dan Virtual Office di Bali",
        "status": "berlaku",
        "full_title": "Surat Gubernur Bali Nomor B.27.000/642/PM/DPMPTSP Tahun 2026",
    }

    try:
        from backend.app.models import TierLevel
        from backend.core.bm25_vectorizer import BM25Vectorizer
        from backend.core.embeddings import create_embeddings_generator
        from backend.core.legal import HierarchicalIndexer, LegalChunker, LegalStructureParser
        from backend.core.qdrant_db import QdrantClient
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return

    # Initialize components
    vector_db = QdrantClient(collection_name="legal_unified")
    embedder = create_embeddings_generator()
    chunker = LegalChunker()
    sparse_vectorizer = BM25Vectorizer()

    indexer = HierarchicalIndexer(
        structure_parser=LegalStructureParser(),
        qdrant_client=vector_db,
        embeddings=embedder,
        chunker=chunker,
        sparse_vectorizer=sparse_vectorizer,
    )

    # Prepare base metadata for indexing
    doc_id = "SURAT_GUB_BALI_2026_B27000"
    base_metadata = {
        "book_title": metadata["full_title"],
        "book_author": "Gubernur Bali",
        "category": "peraturan_bali",
        "tier": TierLevel.S.value,
        "min_level": 0,
        "language": "id",
        "doc_type": "legal",
        "legal_type": metadata["type_abbrev"],
        "legal_number": metadata["number"],
        "legal_year": metadata["year"],
        "legal_topic": metadata["topic"],
        "legal_status": metadata["status"],
        "type_abbrev": metadata["type_abbrev"],
        "number": metadata["number"],
        "year": metadata["year"],
        "topic": metadata["topic"],
    }

    logger.info(f"Starting manual ingestion for doc_id: {doc_id}")

    result = await indexer.index_legal_document(
        document_text=text, document_id=doc_id, metadata=base_metadata
    )

    if result.get("chunks_indexed") > 0:
        logger.info(f"✅ Successfully ingested {result['chunks_indexed']} chunks!")

        # Trigger KG extraction manually for these chunks
        try:
            # We need to import the script correctly
            import sys

            sys.path.append(os.path.join(os.getcwd(), "scripts"))
            import asyncpg
            from kg_incremental_extraction import KGIncrementalExtractor

            from backend.app.core.config import settings

            db_pool = await asyncpg.create_pool(settings.database_url)
            kg_extractor = KGIncrementalExtractor(
                db_pool=db_pool,
                qdrant_url=settings.qdrant_url,
                qdrant_api_key=settings.qdrant_api_key,
                gemini_client=None,  # Will use pattern-based if Gemini not configured
            )

            logger.info("Extracting Knowledge Graph entities...")
            kg_result = await kg_extractor.extract_from_collection(
                collection_name="legal_unified", document_id=doc_id
            )
            logger.info(
                f"✅ KG Result: {kg_result.get('entities_extracted')} entities, {kg_result.get('relationships_extracted')} relationships"
            )
        except Exception as kg_e:
            logger.warning(f"⚠️ KG extraction failed: {kg_e}")
    else:
        logger.error("❌ Indexing failed (0 chunks indexed)")


if __name__ == "__main__":
    asyncio.run(main())
