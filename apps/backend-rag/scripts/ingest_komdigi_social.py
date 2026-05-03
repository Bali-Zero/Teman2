import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add backend to path
BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Load .env explicitly from backend root
env_path = BACKEND_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Loaded .env from {env_path}")

# Set Service Account for Google Drive/Gemini
sa_path = Path("/Users/nuzantara/Desktop/nuzantara/.secrets/service-account.json")
if sa_path.exists():
    with open(sa_path) as f:
        sa_content = f.read()
        os.environ["GOOGLE_CREDENTIALS_JSON"] = sa_content
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = sa_content
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_path)
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"] = str(sa_path)
    print(f"Set Google credentials from {sa_path}")

from backend.app.models import TierLevel
from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_komdigi")


async def main():
    # Ensure API Key is set for Gemini fallback
    if "GOOGLEAISTUDIO_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
        os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLEAISTUDIO_API_KEY"]
        logger.info("Set GOOGLE_API_KEY from GOOGLEAISTUDIO_API_KEY")

    pdf_path = "/Users/nuzantara/Desktop/PP TUNAS_Komdigi_26.pdf"

    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return

    logger.info(f"Starting ingestion for {pdf_path}...")

    service = LegalIngestionService(collection_name="legal_unified")

    # Use stable ID for retries
    stable_id = "Permen_Komdigi_17_2025_Child_Protection"

    result = await service.ingest_legal_document(
        file_path=pdf_path,
        title="Rancangan Peraturan Menteri Komunikasi dan Digital tentang Tata Kelola Penyelenggaraan Sistem Elektronik dalam Pelindungan Anak",
        category="01_tech_social",
        tier_override=TierLevel.C,  # Business/General Knowledge
        document_id=stable_id,
    )

    if result.get("success"):
        logger.info("✅ Ingestion successful!")
        logger.info(f"Chunks created: {result.get('chunks_created')}")
        logger.info(f"Structure: {result.get('structure')}")
        if "kg_extraction" in result:
            logger.info(f"KG Extraction: {result['kg_extraction']}")
    else:
        logger.error(f"❌ Ingestion failed: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
