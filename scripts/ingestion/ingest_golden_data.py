import asyncio
import hashlib
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

import asyncpg

from app.core.config import settings

# Ensure backend is in path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.legal_ingestion_service import LegalIngestionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Constants
DATA_DIR = Path(__file__).parent.parent / "backend" / "data"
SCRAPER_DATA_DIR = Path(__file__).parent.parent.parent / "scraper" / "data"
PRICING_FILE = DATA_DIR / "bali_zero_official_prices_2025.json"
VISA_RULES_DIR = SCRAPER_DATA_DIR / "raw_laws_targeted"


async def ingest_pricing_to_db(pricing_data: dict[str, Any]):
    """
    Ingest pricing data into golden_answers table.
    """
    logger.info("💾 Ingesting pricing data into Golden Answers DB...")

    if not settings.database_url:
        logger.error("❌ DATABASE_URL not set")
        return

    try:
        conn = await asyncpg.connect(settings.database_url)

        # Helper to insert golden answer
        async def insert_golden_answer(question: str, answer: str, source: str):
            cluster_id = f"price_{uuid.uuid4().hex[:8]}"
            query_hash = hashlib.md5(
                question.lower().strip().encode("utf-8")
            ).hexdigest()

            # Insert into golden_answers
            await conn.execute(
                """
                INSERT INTO golden_answers (cluster_id, canonical_question, answer, sources, confidence, usage_count)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (cluster_id) DO UPDATE
                SET answer = EXCLUDED.answer, sources = EXCLUDED.sources, confidence = EXCLUDED.confidence
            """,
                cluster_id,
                question,
                answer,
                [source],
                1.0,
                0,
            )

            # Insert into query_clusters (for exact match)
            await conn.execute(
                """
                INSERT INTO query_clusters (cluster_id, query_hash, query_text, frequency)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (query_hash) DO UPDATE
                SET cluster_id = EXCLUDED.cluster_id
            """,
                cluster_id,
                query_hash,
                question,
                1,
            )

        # Process Visa Prices
        if "visa_services" in pricing_data:
            for visa_name, details in pricing_data["visa_services"].items():
                # Q1: Price
                q1 = f"How much is {visa_name}?"
                a1 = f"The price for {visa_name} is {details.get('price', 'Contact for quote')}."
                if "notes" in details:
                    a1 += f" Note: {details['notes']}."
                await insert_golden_answer(
                    q1, a1, "bali_zero_official_prices_2025.json"
                )

                # Q2: Requirements
                if "requirements" in details:
                    q2 = f"What are the requirements for {visa_name}?"
                    a2 = f"Requirements for {visa_name}: {details['requirements']}."
                    await insert_golden_answer(
                        q2, a2, "bali_zero_official_prices_2025.json"
                    )

        # Process Business Services
        if "business_legal_services" in pricing_data:
            for service_name, details in pricing_data[
                "business_legal_services"
            ].items():
                q = f"Price for {service_name}"
                a = f"The price for {service_name} is {details.get('price', 'Contact for quote')}."
                if "timeline" in details:
                    a += f" Timeline: {details['timeline']}."
                await insert_golden_answer(q, a, "bali_zero_official_prices_2025.json")

        logger.info("✅ Pricing data inserted into DB successfully")
        await conn.close()

    except Exception as e:
        logger.error(f"❌ Failed to insert pricing to DB: {e}")


async def ingest_pricing_truth():
    """
    Ingest the official pricing JSON as the single source of truth.
    """
    logger.info(f"💰 Ingesting Pricing Source of Truth from {PRICING_FILE}...")

    if not PRICING_FILE.exists():
        logger.error(f"❌ Pricing file not found: {PRICING_FILE}")
        return

    try:
        with open(PRICING_FILE, encoding="utf-8") as f:
            pricing_data = json.load(f)

        # Ingest into DB for GoldenAnswerService
        await ingest_pricing_to_db(pricing_data)

    except Exception as e:
        logger.error(f"❌ Failed to load pricing data: {e}")
        raise


async def ingest_visa_rules():
    """
    Ingest scraped visa rules from text files, explicitly excluding pricing information.
    """
    logger.info(f"📜 Ingesting Visa Rules from {VISA_RULES_DIR}...")

    if not VISA_RULES_DIR.exists():
        logger.warning(f"⚠️ Visa rules directory not found: {VISA_RULES_DIR}")
        return

    ingestion_service = LegalIngestionService()

    # Find all visa text files
    visa_files = list(VISA_RULES_DIR.glob("visa_*.txt"))
    logger.info(f"Found {len(visa_files)} visa rule files.")

    # Ensure collection exists (v2 for OpenAI 1536 dims)
    from core.qdrant_db import QdrantClient

    client = QdrantClient(collection_name="legal_unified_v2")
    stats = await client.get_collection_stats()
    if "error" in stats:
        logger.info("Creating legal_unified_v2 collection (1536 dims)...")
        await client.create_collection(vector_size=1536)

    for file_path in visa_files:
        try:
            logger.info(f"Processing {file_path.name}...")

            await ingestion_service.ingest_legal_document(
                file_path=str(file_path),
                collection_name="legal_unified_v2",  # Use v2 for OpenAI (1536 dims)
                skip_pricing=True,  # EXCLUDE PRICING
            )

            logger.info(f"✅ Ingested {file_path.name}")

        except Exception as e:
            logger.error(f"❌ Failed to ingest {file_path.name}: {e}")


async def ingest_chat_logs():
    """
    Ingest Golden Conversations for tone and style.
    """
    logger.info("💬 Ingesting Golden Chat Logs...")

    # Placeholder for now as files are missing
    logger.warning("⚠️ Golden Chat Logs (C1 Tourism) not found. Skipping for now.")
    # TODO: Implement when files are located


async def main():
    logger.info("🚀 Starting Golden Data Ingestion...")

    await ingest_pricing_truth()
    await ingest_visa_rules()
    await ingest_chat_logs()

    logger.info("✨ Golden Data Ingestion Complete!")


if __name__ == "__main__":
    asyncio.run(main())
