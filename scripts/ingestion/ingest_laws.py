#!/usr/bin/env python3
"""
Ingest Laws into Qdrant
-----------------------
Scans 'apps/scraper/data' for PDF and TXT files and ingests them using IngestionService.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from services.ingestion_service import IngestionService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories to scan
DATA_DIRS = [
    Path("apps/scraper/data/raw_laws_local"),
    Path("apps/scraper/data/raw_laws_targeted"),
    Path("apps/scraper/data/raw_laws"),
]


async def main():
    logger.info("🚀 Starting Legal Document Ingestion (Autonomous Mode)...")

    # Configuration from Env or Defaults
    qdrant_url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    qdrant_key = os.getenv("QDRANT_API_KEY", "")  # Default to empty for open instance
    openai_key = os.getenv("OPENAI_API_KEY")

    if not openai_key:
        logger.error("❌ OPENAI_API_KEY is missing! Cannot generate embeddings.")
        return

    logger.info(f"🔌 Qdrant URL: {qdrant_url}")
    logger.info(f"🔑 OpenAI Key: {'*' * 5}{openai_key[-4:] if openai_key else 'None'}")

    # Initialize Service with explicit settings if needed,
    # but IngestionService relies on global settings/env.
    # We ensure env vars are set for it to pick up.
    os.environ["QDRANT_URL"] = qdrant_url
    os.environ["QDRANT_API_KEY"] = qdrant_key

    service = IngestionService()

    total_files = 0
    success_count = 0

    for data_dir in DATA_DIRS:
        root_path = Path.cwd() / data_dir
        if not root_path.exists():
            logger.warning(f"⚠️ Directory not found: {root_path}")
            continue

        logger.info(f"📂 Scanning directory: {root_path}")

        # Find all PDF and TXT files recursively
        files = list(root_path.rglob("*.pdf")) + list(root_path.rglob("*.txt"))

        for file_path in files:
            total_files += 1
            logger.info(f"📄 Processing [{total_files}]: {file_path.name}")

            try:
                # Determine doc_type based on file extension or location
                doc_type = "legal"  # Default to legal for this batch

                result = await service.ingest_book(
                    file_path=str(file_path), doc_type=doc_type
                )

                if result["success"]:
                    logger.info(f"   ✅ Ingested: {file_path.name}")
                    success_count += 1
                else:
                    logger.error(
                        f"   ❌ Failed: {file_path.name} - {result.get('error')}"
                    )

            except Exception as e:
                logger.error(f"   ❌ Error processing {file_path.name}: {e}")

    logger.info("=" * 50)
    logger.info("🎉 Ingestion Complete!")
    logger.info(f"Total Files: {total_files}")
    logger.info(f"Successfully Ingested: {success_count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
