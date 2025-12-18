import asyncio
import logging
import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.qdrant_db import QdrantClient

from app.core.config import settings
from services.golden_answer_service import GoldenAnswerService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def verify_pricing():
    """
    Verify that pricing data is available in GoldenAnswerService.
    """
    logger.info("💰 Verifying Pricing Data...")

    if not settings.database_url:
        logger.error("❌ DATABASE_URL not set")
        return

    service = GoldenAnswerService(settings.database_url)
    try:
        await service.connect()

        # Test Query 1: Investor KITAS Price
        query1 = "How much is Investor KITAS?"
        result1 = await service.lookup_golden_answer(query1)

        if result1:
            logger.info(f"✅ Found answer for '{query1}': {result1['answer']}")
            if "17.000.000 IDR" in result1["answer"]:
                logger.info("   - Price matches expected value (17.000.000 IDR)")
            else:
                logger.warning(f"   - Price mismatch! Got: {result1['answer']}")
        else:
            logger.error(f"❌ No answer found for '{query1}'")

        # Test Query 2: PT PMA Setup Price
        query2 = "Price for PT PMA Company Setup"
        result2 = await service.lookup_golden_answer(query2)

        if result2:
            logger.info(f"✅ Found answer for '{query2}': {result2['answer']}")
        else:
            logger.error(f"❌ No answer found for '{query2}'")

    finally:
        await service.close()


from core.embeddings import EmbeddingsGenerator


async def verify_visa_rules():
    """
    Verify that visa rules are indexed in Qdrant.
    """
    logger.info("📜 Verifying Visa Rules in Qdrant...")

    client = QdrantClient(collection_name="legal_unified_v2")
    stats = await client.get_collection_stats()
    logger.info(f"Collection Stats: {stats}")

    embedder = EmbeddingsGenerator()

    # Search for a specific visa rule content
    query = "visa C1 requirements"
    query_embedding = embedder.generate_query_embedding(query)

    results = await client.search(query_embedding, limit=3)

    if results and results.get("total_found", 0) > 0:
        logger.info(f"✅ Found {results['total_found']} documents for '{query}'")
        for i in range(len(results["ids"])):
            doc_title = results["metadatas"][i].get("book_title", "Unknown")
            score = 1.0 - results["distances"][i]
            logger.info(f"   - Doc: {doc_title} (Score: {score:.2f})")

            # Check content
            content = results["documents"][i]
            if "IDR" in content or "Rp" in content:
                logger.warning(f"   ⚠️ Document might contain pricing info: {doc_title}")
            else:
                logger.info("   - No pricing info detected in snippet (Good)")
    else:
        logger.warning(
            f"⚠️ No documents found for '{query}'. Indexing might have failed or is empty."
        )


async def main():
    logger.info("🚀 Starting Golden Data Verification...")
    await verify_pricing()
    await verify_visa_rules()
    logger.info("✨ Verification Complete!")


if __name__ == "__main__":
    asyncio.run(main())
