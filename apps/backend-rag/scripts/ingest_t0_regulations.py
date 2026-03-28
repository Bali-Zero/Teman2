#!/usr/bin/env python3
"""
ZANTARA - T0 Immigration Regulations Ingestion
Ingests immigration regulations from the project source_documents folder into the RAG system.
Supports: Semantic Chunks, BM25, BAB Structure, and Knowledge Graph.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path("/Users/nuzantara/Desktop/nuzantara")
BACKEND_PATH = PROJECT_ROOT / "apps/backend-rag"
# Add both to sys.path for absolute imports
sys.path.insert(0, str(BACKEND_PATH))
sys.path.insert(0, str(BACKEND_PATH / "backend"))

# Load environment
from dotenv import load_dotenv

load_dotenv(BACKEND_PATH / ".env", override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(PROJECT_ROOT / "ingestion_t0_regulations.log")],
)
logger = logging.getLogger("ingest_t0_regulations")


async def run_ingestion():
    try:
        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
        from backend.services.rag.hybrid_search import HybridSearchService
        from backend.services.rag.reranker import CrossEncoderReranker
    except ImportError as e:
        logger.error(f"Failed to import Nuzantara services: {e}")
        logger.info(f"PYTHONPATH: {sys.path}")
        return

    DESKTOP_PATH = PROJECT_ROOT / "data/source_documents/t0_regulations"
    COLLECTION_NAME = "legal_unified_2026"

    if not DESKTOP_PATH.exists():
        logger.error(f"Directory not found: {DESKTOP_PATH}")
        return

    files = sorted(DESKTOP_PATH.glob("*.pdf"))
    logger.info(f"🚀 Starting ingestion of {len(files)} PDF files from {DESKTOP_PATH}")
    logger.info(f"Target Collection: {COLLECTION_NAME}")
    logger.info("Features: Semantic Chunking, BM25 Sparse Vectors, BAB Parsing, KG Extraction")

    service = LegalIngestionService(collection_name=COLLECTION_NAME)

    # Ensure collection exists with hybrid support
    logger.info(f"Ensuring collection '{COLLECTION_NAME}' exists...")
    await service.vector_db.create_collection(
        vector_size=1536,  # OpenAI
        enable_sparse=True,
    )

    results = []
    start_all = time.time()

    for i, file_path in enumerate(files):
        logger.info(f"--- [{i + 1}/{len(files)}] Processing: {file_path.name} ---")
        try:
            # Step 1: Ingest into Qdrant + Drive + Metadata + BAB + BM25 + KG
            result = await service.ingest_legal_document(
                file_path=str(file_path),
                category="t0_immigration_2026",
            )

            if result["success"]:
                kg_stats = result.get("kg_extraction", {})
                success_msg = (
                    f"✅ Success: {file_path.name}\n"
                    f"   - Chunks: {result['chunks_created']}\n"
                    f"   - Structure: {result['structure']['bab_count']} BAB, {result['structure']['pasal_count']} Pasal\n"
                    f"   - KG: {kg_stats.get('entities', 0)} entities, {kg_stats.get('relationships', 0)} relations\n"
                    f"   - Time: {result['processing_time_seconds']:.2f}s"
                )
                logger.info(success_msg)
            else:
                logger.error(f"❌ Failed: {file_path.name} - {result['error']}")

            results.append(result)
        except Exception as e:
            logger.error(f"💥 Fatal error processing {file_path.name}: {e}", exc_info=True)
            results.append({"success": False, "file": file_path.name, "error": str(e)})

    total_duration = time.time() - start_all
    success_count = sum(1 for r in results if r.get("success"))

    logger.info("=" * 50)
    logger.info("🏁 Ingestion Summary")
    logger.info(f"Total Files: {len(files)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(files) - success_count}")
    logger.info(f"Total Time: {total_duration / 60:.2f} minutes")
    logger.info("=" * 50)

    # Post-Ingestion Verification (Rerank2 check)
    if success_count > 0:
        logger.info("🔍 Performing Post-Ingestion Rerank2 Verification...")
        try:
            hybrid_service = HybridSearchService()
            reranker = CrossEncoderReranker()

            test_query = "peraturan terbaru tahun 2026"
            search_results = await hybrid_service.search_hybrid(
                query=test_query, collection=COLLECTION_NAME, limit=10
            )

            if search_results["results"]:
                logger.info(
                    f"   Found {len(search_results['results'])} candidates via Hybrid Search (BM25 + Dense)"
                )
                reranked = await reranker.rerank(
                    query=test_query, documents=search_results["results"], top_k=3
                )
                logger.info(f"   Rerank2 Top Result: {reranked[0]['text'][:100]}...")
                logger.info("✅ Post-ingestion pipeline verified (Hybrid + Rerank2 operational)")
            else:
                logger.warning("   No results found for verification query.")
        except Exception as e:
            logger.warning(f"⚠️ Post-ingestion verification failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_ingestion())
