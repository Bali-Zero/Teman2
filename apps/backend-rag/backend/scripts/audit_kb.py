import asyncio
import os
import sys

from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), ".."))
sys.path.append(os.getcwd())

# Load Env
dist_env = os.path.join(os.getcwd(), "apps/backend-rag/.env")
if os.path.exists(dist_env):
    load_dotenv(dist_env)

# Qdrant client
from qdrant_client import QdrantClient


async def audit_kb():
    # DIRECTLY USE ENV VARS - TARGET PRODUCTION IF SET
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if not qdrant_url:
        qdrant_url = "http://localhost:6333"

    # Mask API Key for logs
    f"{qdrant_api_key[:5]}...{qdrant_api_key[-5:]}" if qdrant_api_key else "None"

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # Collections to audit
    collections = ["legal_unified", "visa_oracle", "bali_zero_pricing_hybrid"]


    # Check if collections exist
    try:
        existing_collections = client.get_collections().collections
        existing_names = [c.name for c in existing_collections]
    except Exception:
        return

    for col_name in collections:
        if col_name not in existing_names:
            continue

        try:
            # Use SCROLL which is safer
            scroll_res, _ = client.scroll(
                collection_name=col_name,
                limit=3,
                with_payload=True,
                with_vectors=False,
            )

            if not scroll_res:
                pass
            else:
                for _idx, res in enumerate(scroll_res):
                    payload = res.payload
                    # Print relevant fields
                    payload.get("text", str(payload))[:200].replace("\n", " ")
                    payload.get("source", "unknown")

        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(audit_kb())
