import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

# ------------------------------------------------------------------------------
# SETUP & CONFIG
# ------------------------------------------------------------------------------

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
BACKEND_DIR = BASE_DIR / "apps" / "backend-rag"
ENV_FILE = BACKEND_DIR / ".env"
DATA_FILE = BACKEND_DIR / "backend" / "data" / "bali_zero_official_prices_2025.json"

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("KB_SEEDER")

# Load Env
if ENV_FILE.exists():
    logger.info(f"Loading env from {ENV_FILE}")
    load_dotenv(ENV_FILE)
else:
    logger.warning("No .env file found! Trying system env vars.")

# Overrides for LOCAL DEV
# Overrides for LOCAL DEV (Default) - Can be overridden by ENV
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # None by default for local
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.error("❌ OPENAI_API_KEY is missing. Cannot generate embeddings.")
    sys.exit(1)

# Collections to Create & Populate
COLLECTIONS = {
    "visa_oracle": 1536,
    "legal_unified": 1536,
    "bali_zero_pricing": 1536,
    "training_conversations": 1536,  # Will remain empty-ish but created
}

# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------


def get_embedding(text: str, client: OpenAI) -> List[float]:
    text = text.replace("\n", " ")
    return (
        client.embeddings.create(input=[text], model="text-embedding-3-small")
        .data[0]
        .embedding
    )


async def setup_collections(client: QdrantClient):
    """Ensure collections exist with correct config"""
    for name, dim in COLLECTIONS.items():
        exists = client.collection_exists(name)
        if not exists:
            logger.info(f"Creating collection: {name} ({dim} dim)")
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=dim, distance=models.Distance.COSINE
                ),
            )
        else:
            logger.info(f"Collection {name} exists.")


async def ingest_pricing_json(q_client: QdrantClient, openai_client: OpenAI):
    """Transform JSON pricing -> Qdrant Points"""

    if not DATA_FILE.exists():
        logger.error(f"❌ Data file not found: {DATA_FILE}")
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    logger.info(f"Reading from {DATA_FILE.name}...")

    points_visa = []
    points_pricing = []
    points_legal = []

    # 1. Official Notice & Disclaimer -> Legal Unified
    disclaimers = data.get("disclaimer", {})
    warnings = data.get("important_warnings", {})

    for key, text in warnings.items():
        # Clean text
        content = f"IMPORTANT WARNING - {key.upper()}: {text}"
        emb = get_embedding(content, openai_client)
        points_legal.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={
                    "text": content,
                    "category": "legal_warning",
                    "source": "official_pricing_json",
                },
            )
        )

    # 2. Services -> Visa Oracle & Pricing
    services = data.get("services", {})

    # Traverse all service categories
    for category, items in services.items():
        for name, details in items.items():
            price = details.get("price", "Contact for Quote")
            notes = details.get("notes", "-")
            duration = details.get("duration", "")
            validity = details.get("validity", duration)  # fallback

            # ------------------------------------------------------------------
            # GOLD STANDARD FORMATTING (Matching visa_oracle / legal_unified)
            # ------------------------------------------------------------------
            # Structure:
            # [CONTEXT: Header]
            # # Title
            # ## Informazioni Base (Italian Labels)
            # ## Details
            # ---
            # Source

            clean_name = name.strip()
            clean_category = category.replace("_", " ").title()

            # Enrich text for semantic retrieval (PURE ENGLISH)
            semantic_text = f"""[CONTEXT: Bali Zero Pricing 2025 - {clean_category} - {clean_name}]

# {clean_name}

## Economic Details
- **Official Price**: {price}
- **Category**: {clean_category}
- **Validity**: {validity if validity else "N/A"}

## Description & Notes
{notes}

---
Source: Bali Zero Official Pricing 2025 ({DATA_FILE.name})
"""

            # Generate Embedding on this RICH text
            emb = get_embedding(semantic_text, openai_client)
            point_id = str(uuid.uuid4())

            # Payload follows the schema observed in visa_oracle
            payload = {
                "text": semantic_text,
                "service_name": clean_name,
                "price_raw": price,
                "category": category,
                "validity": validity,
                "source": "official_pricing_json",
                "doc_type": "pricing",
                "version": "2025.12.24",
                "language": "en",  # PURE ENGLISH
            }

            # Add to Pricing Collection
            points_pricing.append(
                models.PointStruct(id=point_id, vector=emb, payload=payload)
            )

            # Also add to Visa Oracle if relevant (Cross-Pollination)
            if (
                "visa" in category.lower()
                or "kitas" in category.lower()
                or "kitap" in category.lower()
            ):
                points_visa.append(
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=emb,  # Same rich vector
                        payload=payload,  # Same rich payload
                    )
                )

    # BURST MODE: Atomic Uploads with Retries to bypass Network Instability
    # The network is hostile (Connection Reset), so we sneak points in one by one.

    import time

    def atomic_upsert(collection_name, points, max_retries=5):
        logger.info(
            f"⚡ Starting ATOMIC upsert for {collection_name} ({len(points)} points)..."
        )
        success_count = 0

        for i, point in enumerate(points):
            retries = 0
            while retries < max_retries:
                try:
                    # Upsert SINGLE point
                    q_client.upsert(collection_name, [point])
                    success_count += 1
                    sys.stdout.write(
                        f"\r  Progress: {success_count}/{len(points)} [OK]"
                    )
                    sys.stdout.flush()
                    break  # Success, move to next point
                except Exception:
                    retries += 1
                    wait_time = retries * 2
                    # logger.warning(f"\n  ⚠️ Fail on pt {i} (Try {retries}/{max_retries}): {e}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
            else:
                logger.error(
                    f"\n❌ FAILED to upload point {i} after {max_retries} retries. Skipping."
                )

        print("")  # Newline
        logger.info(
            f"✅ Completed {collection_name}: {success_count}/{len(points)} uploaded."
        )

    # Execute Atomic Uploads
    if points_pricing:
        atomic_upsert("bali_zero_pricing", points_pricing)

    if points_visa:
        atomic_upsert("visa_oracle", points_visa)

    if points_legal:
        atomic_upsert(
            "legal_unified_hybrid", points_legal
        )  # Renamed to actual prod collection


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------


async def main():
    logger.info("🚀 STARTING LITE KNOWLEDGE BASE SEEDING (BULLETPROOF MODE)...")

    # Init Clients
    # timeout: longer wait for handshake
    q_client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=30,  # Lower timeout per request, rely on retries
    )
    openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0)

    # 1. Create/Verify Collections (Blind firing, ignore errors if they exist)
    try:
        await setup_collections(q_client)
    except Exception as e:
        logger.warning(
            f"Setup check failed (might be network), trying to proceed to ingestion anyway: {e}"
        )

    # 2. Ingest Data
    await ingest_pricing_json(q_client, openai_client)

    logger.info("✨ SEEDING COMPLETE! The Brain is now active (Lite Mode).")


if __name__ == "__main__":
    asyncio.run(main())
