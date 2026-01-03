import asyncio
import os
import sys

from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), '..'))
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
        print("⚠️ QDRANT_URL not found, defaulting to localhost")

    print(f"🔍 CONNECTING TO QDRANT: {qdrant_url}")
    # Mask API Key for logs
    masked_key = f"{qdrant_api_key[:5]}...{qdrant_api_key[-5:]}" if qdrant_api_key else "None"
    print(f"🔑 API KEY: {masked_key}")

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # Collections to audit
    collections = ["legal_unified", "visa_oracle", "bali_zero_pricing", "kbli_unified"]

    print("\n🧠 DEEP AUDIT FOR DATA EXISTENCE\n" + "="*50)

    # Check if collections exist
    try:
        existing_collections = client.get_collections().collections
        existing_names = [c.name for c in existing_collections]
    except Exception as e:
         print(f"💥 Connection Failed: {e}")
         return

    for col_name in collections:
        if col_name not in existing_names:
            print(f"❌ COLLECTION MISSING: {col_name}")
            continue

        print(f"\n📂 COLLECTION: {col_name}")
        try:
            # Use SCROLL which is safer
            scroll_res, _ = client.scroll(
                collection_name=col_name,
                limit=3,
                with_payload=True,
                with_vectors=False
            )

            if not scroll_res:
                print("   ⚠️ EMPTY COLLECTION (0 Points)")
            else:
                print(f"   ✅ FOUND {len(scroll_res)} SAMPLE POINTS")
                for idx, res in enumerate(scroll_res):
                    payload = res.payload
                    # Print relevant fields
                    text = payload.get('text', str(payload))[:200].replace('\n', ' ')
                    source = payload.get('source', 'unknown')
                    print(f"   [{idx+1}] Source: {source} | Text: {text}...")

        except Exception as e:
            print(f"   💥 ERROR AUDITING COLLECTION: {e}")


if __name__ == "__main__":
    asyncio.run(audit_kb())
