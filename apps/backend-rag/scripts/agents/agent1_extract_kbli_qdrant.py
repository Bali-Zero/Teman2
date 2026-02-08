#!/usr/bin/env python3
"""
Agent 1: Extract KBLI from Qdrant
==================================
Extracts all KBLI codes from Qdrant collection kbli_2025_final (9,612 documents).

Output: data/kbli_extraction_YYYYMMDD_HHMMSS.json
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend-rag"))

import httpx

from backend.app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [AGENT-1] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Qdrant configuration from backend settings
QDRANT_URL = os.getenv("QDRANT_URL") or settings.qdrant_url
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or (settings.qdrant_api_key or "")
COLLECTION_NAME = "kbli_2025_final"
BATCH_SIZE = 100  # Scroll batch size


async def extract_kbli_from_qdrant() -> list[dict]:
    """
    Extract all KBLI documents from Qdrant collection.

    Returns:
        List of KBLI documents with all fields
    """
    headers = {}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    all_documents = []
    offset = None

    async with httpx.AsyncClient(base_url=QDRANT_URL, headers=headers, timeout=30.0) as client:
        logger.info(f"Connecting to Qdrant: {QDRANT_URL}")
        logger.info(f"Collection: {COLLECTION_NAME}")

        while True:
            # Scroll API for pagination
            scroll_payload = {
                "limit": BATCH_SIZE,
                "with_payload": True,
                "with_vector": False,
            }

            if offset:
                scroll_payload["offset"] = offset

            try:
                response = await client.post(
                    f"/collections/{COLLECTION_NAME}/points/scroll",
                    json=scroll_payload,
                )
                response.raise_for_status()
                data = response.json()

                points = data.get("result", {}).get("points", [])
                if not points:
                    logger.info("No more points to fetch")
                    break

                # Extract payloads
                for point in points:
                    payload = point.get("payload", {})
                    if payload:
                        all_documents.append(payload)

                offset = data.get("result", {}).get("next_page_offset")
                logger.info(f"Fetched {len(points)} documents (total: {len(all_documents)})")

                if not offset:
                    logger.info("Reached end of collection")
                    break

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error during extraction: {e}", exc_info=True)
                raise

    logger.info(f"✅ Extracted {len(all_documents)} KBLI documents")
    return all_documents


async def main():
    """Main execution"""
    logger.info("=" * 70)
    logger.info("AGENT 1: KBLI EXTRACTION FROM QDRANT")
    logger.info("=" * 70)

    # Extract documents
    documents = await extract_kbli_from_qdrant()

    if not documents:
        logger.error("❌ No documents extracted!")
        sys.exit(1)

    # Analyze structure
    logger.info("\nDocument structure analysis:")
    sample = documents[0]
    logger.info(f"Sample keys: {list(sample.keys())}")
    logger.info(f"Sample KBLI code: {sample.get('kode_kbli', 'N/A')}")
    logger.info(f"Sample judul: {sample.get('judul', 'N/A')}")

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"kbli_extraction_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✅ Data saved to: {output_file}")
    logger.info(f"📊 Total documents: {len(documents):,}")
    logger.info(f"📦 File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
