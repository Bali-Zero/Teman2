#!/usr/bin/env python3
"""
ZANTARA - Force OCR Re-ingestion for Kepmen 228/2019
"""

import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path("/Users/nuzantara/Desktop/nuzantara")
BACKEND_PATH = PROJECT_ROOT / "apps/backend-rag"
sys.path.insert(0, str(BACKEND_PATH))
sys.path.insert(0, str(BACKEND_PATH / "backend"))

# PRE-IMPORT: Set environment variables so settings picks them up
gemini_key = os.environ.get("GEMINI_API_KEY")
if gemini_key and not gemini_key.startswith("your-"):
    os.environ["GOOGLE_API_KEY"] = gemini_key
    # Also set it in .env temporarily if needed, or just rely on os.environ
    print("INFO: Pre-setting GOOGLE_API_KEY from GEMINI_API_KEY")

import asyncio
import logging
import time

# Load environment
from dotenv import load_dotenv

load_dotenv(BACKEND_PATH / ".env", override=True)

# Ensure GOOGLE_API_KEY is set for Gemini Vision (re-check after dotenv)
if not os.environ.get("GOOGLE_API_KEY") or "your-google-api-key" in os.environ.get(
    "GOOGLE_API_KEY"
):
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
        print("Using GEMINI_API_KEY as GOOGLE_API_KEY for Vision Service")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reingest_kepmen_ocr")


async def run_reingestion():
    try:
        from backend.core.parsers import extract_text_from_pdf_async
        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
    except ImportError as e:
        logger.error(f"Failed to import services: {e}")
        return

    FILE_PATH = "/Users/nuzantara/Desktop/leggi/Kepmen_228_2019.pdf"
    COLLECTION_NAME = "legal_unified_2026"

    logger.info(f"🚀 Starting FORCED OCR re-ingestion for {FILE_PATH}")

    # 1. Manually extract text via OCR
    logger.info("Step 1: Extracting text via OCR (this will take a while for 146 pages)...")
    start_ocr = time.time()
    raw_text = await extract_text_from_pdf_async(FILE_PATH, use_ocr=True)
    duration_ocr = time.time() - start_ocr
    logger.info(f"✅ OCR completed: {len(raw_text)} characters extracted in {duration_ocr:.2f}s")

    if len(raw_text) < 10000:
        logger.warning(
            f"⚠️ Extracted text still seems small ({len(raw_text)} chars). Check PDF quality."
        )

    # 2. Use LegalIngestionService but we'll patch the text if needed or just use it normally
    # Actually, LegalIngestionService.ingest_legal_document calls auto_detect_and_parse.
    # To avoid rewriting the whole service logic, we can temporarily monkey-patch the parser
    # or just use a modified version of the service.

    service = LegalIngestionService(collection_name=COLLECTION_NAME)

    # We will use a trick: ingest_legal_document but we pass the raw_text we just extracted
    # Wait, the service doesn't take raw_text. Let's fix that or use a workaround.

    logger.info("Step 2: Indexing processed text...")

    # Instead of calling ingest_legal_document, we'll manually run the pipeline
    # to ensure our OCR'd text is used.

    # a. Clean
    cleaned_text = service.cleaner.clean(raw_text)

    # b. Metadata
    metadata = service.metadata_extractor.extract(cleaned_text)
    document_title = metadata.get("full_title", "Kepmen 228 Tahun 2019")

    # c. Tier
    tier = service.classifier.classify_book_tier(
        document_title, "Pemerintah Indonesia", cleaned_text[:2000]
    )
    min_level = service.classifier.get_min_access_level(tier)

    # d. Hierarchical Indexing
    doc_id = f"{metadata.get('type_abbrev', 'Kepmen')}_{metadata.get('number', '228')}_{metadata.get('year', '2019')}".replace(
        " ", "_"
    ).replace("/", "_")

    base_metadata = {
        "book_title": document_title,
        "book_author": "Pemerintah Indonesia",
        "category": "peraturan_2026",
        "tier": tier.value,
        "min_level": min_level,
        "language": "id",
        "file_path": FILE_PATH,
        "doc_type": "legal",
        "legal_type": metadata.get("type_abbrev"),
        "legal_number": metadata.get("number"),
        "legal_year": metadata.get("year"),
        "legal_topic": metadata.get("topic"),
        "type_abbrev": metadata.get("type_abbrev"),
        "number": metadata.get("number"),
        "year": metadata.get("year"),
        "topic": metadata.get("topic"),
        "document_id": doc_id,  # For KG filtering
    }

    indexing_result = await service.indexer.index_legal_document(
        document_text=cleaned_text, document_id=doc_id, metadata=base_metadata
    )

    logger.info("✅ Re-ingestion complete!")
    logger.info(f"   - Chunks: {indexing_result['chunks_indexed']}")
    logger.info(
        f"   - Structure: {indexing_result['total_bab']} BAB, {indexing_result['total_pasal']} Pasal"
    )


if __name__ == "__main__":
    asyncio.run(run_reingestion())
