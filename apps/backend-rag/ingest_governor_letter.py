import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Set the file path
    file_path = "/Users/nuzantara/Desktop/SURAT GUB PENUTUPAN PMA TINGKAT RISIKO RENDAH & MENENGAH RENDAH.pdf"

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    # Import LegalIngestionService
    try:
        from backend.app.models import TierLevel
        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.info(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
        logger.info(f"sys.path: {sys.path}")
        return

    service = LegalIngestionService(collection_name="legal_unified")

    logger.info(f"Starting ingestion of {file_path}")

    result = await service.ingest_legal_document(
        file_path=file_path,
        title="Surat Gubernur Bali tentang Penutupan PMA Risiko Rendah & Menengah Rendah",
        category="peraturan_bali",
        tier_override=TierLevel.S,  # Strategic/Public tier
    )

    if result.get("success"):
        logger.info("✅ Ingestion successful!")
        logger.info(f"Chunks created: {result.get('chunks_created')}")
        logger.info(f"Metadata: {result.get('legal_metadata')}")
        if "kg_extraction" in result:
            logger.info(f"KG Entities: {result['kg_extraction'].get('entities')}")
            logger.info(f"KG Relationships: {result['kg_extraction'].get('relationships')}")
    else:
        logger.error(f"❌ Ingestion failed: {result.get('message')}")
        logger.error(f"Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
