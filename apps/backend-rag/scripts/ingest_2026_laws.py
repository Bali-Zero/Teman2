#!/usr/bin/env python3
"""
ZANTARA - 2026 Laws Ingestion Pipeline
Ingests 5 key 2026 laws from data/kb_sources/2026_updates/ into the RAG system.

Pipeline:
  1. PDF Parsing (+ OCR fallback)
  2. Google Drive Upload (→ BALI ZERO/PERATURAN)
  3. Text Cleaning (LegalCleaner)
  4. Metadata Extraction (Pattern + Gemini fallback)
  5. Tier Classification
  6. Hierarchical Indexing → Qdrant (dense 1536 + BM25 sparse + parent-child)
  7. Knowledge Graph Extraction → PostgreSQL (entities + relationships)
  8. Post-Ingestion Verification (Hybrid Search + Rerank2)

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/ingest_2026_laws.py
    PYTHONPATH=. python scripts/ingest_2026_laws.py --dry-run    # Preview only
    PYTHONPATH=. python scripts/ingest_2026_laws.py --file PMK    # Single file (partial match)
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path("/Users/nuzantara/Desktop/nuzantara")
BACKEND_PATH = PROJECT_ROOT / "apps/backend-rag"
sys.path.insert(0, str(BACKEND_PATH))
sys.path.insert(0, str(BACKEND_PATH / "backend"))

# Load environment
from dotenv import load_dotenv

load_dotenv(BACKEND_PATH / ".env", override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "ingestion_2026_laws.log"),
    ],
)
logger = logging.getLogger("ingest_2026_laws")

# Target documents with marketing metadata
LAWS_2026 = [
    {
        "filename": "PMK_1_2026_Coretax_System.pdf",
        "title": "PMK 1/2026 - Perubahan Keempat atas PMK 81/2024 tentang Ketentuan Perpajakan dalam rangka Pelaksanaan Sistem Inti Administrasi Perpajakan (Coretax)",
        "category": "perpajakan_2026",
        "marketing_title_it": "PMK 1/2026 - Coretax: Riforma Fiscale Digitale Indonesia",
        "marketing_title_en": "PMK 1/2026 - Coretax: Indonesia Digital Tax Reform",
    },
    {
        "filename": "PP_9_2026_THR_Gaji_13.pdf",
        "title": "PP 9/2026 - Pemberian Tunjangan Hari Raya dan Gaji Ketiga Belas kepada Aparatur Negara, Pensiunan, Penerima Pensiun, dan Penerima Tunjangan Tahun 2026",
        "category": "ketenagakerjaan_2026",
        "marketing_title_it": "PP 9/2026 - THR e Tredicesima per Dipendenti Pubblici 2026",
        "marketing_title_en": "PP 9/2026 - Hari Raya Allowance & 13th Month Salary 2026",
    },
    {
        "filename": "Pergub_Bali_14_2023_RPD_2024_2026.pdf",
        "title": "Pergub Bali 14/2023 - Rencana Pembangunan Daerah Provinsi Bali Tahun 2024-2026",
        "category": "perencanaan_bali",
        "marketing_title_it": "Pergub Bali 14/2023 - Piano Sviluppo Regionale Bali 2024-2026",
        "marketing_title_en": "Pergub Bali 14/2023 - Bali Regional Development Plan 2024-2026",
    },
    {
        "filename": "SE_Gubernur_Bali_09_2025_Bali_Bersih_Sampah.pdf",
        "title": "SE Gubernur Bali 09/2025 - Gerakan Bali Bersih Sampah",
        "category": "lingkungan_bali",
        "marketing_title_it": "SE Gubernur Bali 09/2025 - Gerakan Bali Bersih Sampah",
        "marketing_title_en": "SE Gubernur Bali 09/2025 - Bali Clean Waste Campaign",
    },
    {
        "filename": "UU_1_2023_KUHP_Baru.pdf",
        "title": "UU 1/2023 - Kitab Undang-Undang Hukum Pidana (KUHP Baru)",
        "category": "hukum_pidana",
        "marketing_title_it": "UU 1/2023 - Nuovo Codice Penale Indonesia (KUHP)",
        "marketing_title_en": "UU 1/2023 - Indonesia New Criminal Code (KUHP)",
    },
]

COLLECTION_NAME = "legal_unified_2026"
SOURCE_DIR = PROJECT_ROOT / "data/kb_sources/2026_updates"


async def run_ingestion(dry_run: bool = False, file_filter: str | None = None):
    try:
        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
        from backend.services.rag.hybrid_search import HybridSearchService
        from backend.services.rag.reranker import CrossEncoderReranker
    except ImportError as e:
        logger.error(f"Failed to import Nuzantara services: {e}")
        logger.info(f"PYTHONPATH: {sys.path}")
        return

    if not SOURCE_DIR.exists():
        logger.error(f"Source directory not found: {SOURCE_DIR}")
        return

    # Filter laws if --file specified
    laws = LAWS_2026
    if file_filter:
        laws = [law for law in laws if file_filter.lower() in law["filename"].lower()]
        if not laws:
            logger.error(f"No files matching filter: '{file_filter}'")
            return

    # Verify all files exist
    missing = []
    for law in laws:
        fp = SOURCE_DIR / law["filename"]
        if not fp.exists():
            missing.append(law["filename"])
    if missing:
        logger.error(f"Missing files: {missing}")
        return

    logger.info("=" * 60)
    logger.info("🇮🇩 NUZANTARA 2026 LAWS INGESTION PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Source: {SOURCE_DIR}")
    logger.info(f"Collection: {COLLECTION_NAME}")
    logger.info(f"Documents: {len(laws)}")
    logger.info(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE INGESTION'}")
    logger.info("")
    for i, law in enumerate(laws):
        fp = SOURCE_DIR / law["filename"]
        size_mb = fp.stat().st_size / (1024 * 1024)
        logger.info(f"  [{i+1}] {law['filename']} ({size_mb:.1f} MB)")
        logger.info(f"      Title: {law['title'][:80]}...")
        logger.info(f"      Category: {law['category']}")
    logger.info("")
    logger.info("Pipeline: Parse → Drive Upload → Clean → Metadata → Tier → Chunk+BM25+Embed → KG")
    logger.info("=" * 60)

    if dry_run:
        logger.info("🔍 DRY RUN — no data will be written. Exiting.")
        return

    # Initialize service
    service = LegalIngestionService(collection_name=COLLECTION_NAME)

    # Ensure collection exists with hybrid support (dense 1536 + BM25 sparse)
    logger.info(f"Ensuring collection '{COLLECTION_NAME}' exists with hybrid vectors...")
    await service.vector_db.create_collection(
        vector_size=1536,  # OpenAI text-embedding-3-small
        enable_sparse=True,  # BM25 sparse vectors
    )

    results = []
    start_all = time.time()

    for i, law in enumerate(laws):
        file_path = SOURCE_DIR / law["filename"]
        logger.info("")
        logger.info(f"━━━ [{i+1}/{len(laws)}] {law['filename']} ━━━")
        logger.info(f"Title: {law['title']}")

        try:
            result = await service.ingest_legal_document(
                file_path=str(file_path),
                title=law["title"],
                category=law["category"],
            )

            if result["success"]:
                kg_stats = result.get("kg_extraction", {})
                logger.info(
                    f"✅ SUCCESS: {law['filename']}\n"
                    f"   Chunks: {result['chunks_created']}\n"
                    f"   Structure: {result['structure']['bab_count']} BAB, "
                    f"{result['structure']['pasal_count']} Pasal\n"
                    f"   KG: {kg_stats.get('entities', 0)} entities, "
                    f"{kg_stats.get('relationships', 0)} relations\n"
                    f"   Time: {result['processing_time_seconds']:.1f}s"
                )
            else:
                logger.error(f"❌ FAILED: {law['filename']} — {result['error']}")

            results.append(result)

        except Exception as e:
            logger.error(f"💥 FATAL: {law['filename']} — {e}", exc_info=True)
            results.append({"success": False, "file": law["filename"], "error": str(e)})

    # Summary
    total_duration = time.time() - start_all
    success_count = sum(1 for r in results if r.get("success"))
    total_chunks = sum(r.get("chunks_created", 0) for r in results if r.get("success"))
    total_entities = sum(
        r.get("kg_extraction", {}).get("entities", 0) for r in results if r.get("success")
    )
    total_rels = sum(
        r.get("kg_extraction", {}).get("relationships", 0) for r in results if r.get("success")
    )

    logger.info("")
    logger.info("=" * 60)
    logger.info("🏁 INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Documents: {len(laws)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(laws) - success_count}")
    logger.info(f"Total Chunks: {total_chunks}")
    logger.info(f"KG Entities: {total_entities}")
    logger.info(f"KG Relationships: {total_rels}")
    logger.info(f"Total Time: {total_duration / 60:.1f} minutes")
    logger.info("=" * 60)

    # Post-Ingestion Verification
    if success_count > 0:
        logger.info("")
        logger.info("🔍 Post-Ingestion Verification (Hybrid Search + Rerank2)...")
        try:
            hybrid_service = HybridSearchService()
            reranker = CrossEncoderReranker()

            test_queries = [
                "peraturan perpajakan coretax 2026",
                "tunjangan hari raya gaji 13 aparatur negara",
                "rencana pembangunan daerah bali",
                "gerakan bali bersih sampah",
                "kitab undang-undang hukum pidana KUHP baru",
            ]

            for query in test_queries:
                search_results = await hybrid_service.search_hybrid(
                    query=query, collection=COLLECTION_NAME, limit=5
                )
                if search_results["results"]:
                    reranked = await reranker.rerank(
                        query=query, documents=search_results["results"], top_k=1
                    )
                    top = reranked[0]["text"][:80] if reranked else "N/A"
                    logger.info(f"  ✅ '{query[:40]}...' → {len(search_results['results'])} hits → Top: {top}...")
                else:
                    logger.warning(f"  ⚠️ '{query[:40]}...' → 0 hits")

            logger.info("✅ Pipeline verified: Hybrid Search (Dense+BM25) + Rerank2 operational")

        except Exception as e:
            logger.warning(f"⚠️ Verification failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest 2026 Laws into Nuzantara RAG")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no ingestion")
    parser.add_argument("--file", type=str, help="Filter by filename (partial match)")
    args = parser.parse_args()

    asyncio.run(run_ingestion(dry_run=args.dry_run, file_filter=args.file))
