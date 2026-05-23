"""
One-shot ingest of PwC Indonesian Pocket Tax Book 2026 into tax_genius_hybrid.

Uses the same legal-ingestion pipeline (BM25 + dense 1536 + flat payload +
hierarchical indexer) but targets the tax canonical collection. Authority
tier secondary so query-time filters can prefer UU/PMK primary over PwC
secondary on high-stakes regulatory questions.

Run:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/ingest_pwc_pocket_tax_book_2026.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("pwc_ingest")


PDF_PATH = "/Users/nuzantara/Desktop/pocket-tax-book-2026.pdf"
SOURCE_TAG = "pwc_pocket_tax_book_2026"
TIGRIS_URL = (
    "https://fly.storage.tigris.dev/nuzantara-warroom-images/tax/"
    "pwc-pocket-tax-book-2026.pdf"
)


async def main() -> int:
    if not Path(PDF_PATH).exists():
        logger.error("PDF missing at %s", PDF_PATH)
        return 1

    os.environ["LEGAL_INGEST_ALLOW_QDRANT_ENV_OVERRIDE"] = "1"

    from backend.app.models import TierLevel
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestionService,
        validate_legal_ingest_result,
    )

    service = LegalIngestionService(collection_name="tax_genius")

    result = await service.ingest_legal_document(
        file_path=PDF_PATH,
        title="PwC Indonesian Pocket Tax Book 2026",
        tier_override=TierLevel.S,
        collection_name="tax_genius",
        skip_pricing=True,
        category="tax_guide_secondary",
        document_id=SOURCE_TAG,
    )

    if not result.get("success"):
        logger.error("Ingestion failed: %s", result.get("error"))
        logger.error("Full result: %s", result)
        return 1

    try:
        validate_legal_ingest_result(result)
    except Exception as exc:
        logger.error("Integrity validation failed: %s", exc)
        return 1

    logger.info("✅ Ingest complete")
    logger.info("   collection      : %s", result.get("collection"))
    logger.info("   chunks created  : %s", result.get("chunks_created"))
    logger.info("   chunks upserted : %s", result.get("chunks_upserted"))
    logger.info("   document_id     : %s", SOURCE_TAG)
    logger.info("   tigris url      : %s", TIGRIS_URL)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
