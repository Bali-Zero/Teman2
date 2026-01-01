import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv

# Load env directly
load_dotenv("apps/backend-rag/.env")

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

async def audit_kbli_96121():
    print(f"Connecting to Qdrant: {QDRANT_URL}...")
    if not QDRANT_URL:
        print("❌ QDRANT_URL missing in .env")
        return

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    # Search in kbli_unified
    print("\n--- SEARCHING KBLI_UNIFIED ---")
    try:
        results = client.scroll(
            collection_name="kbli_unified",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.code",
                        match=models.MatchValue(value="96121")
                    )
                ]
            ),
            limit=5,
            with_payload=True
        )
        
        points, _ = results
        if not points:
            print("❌ No direct match for code '96121' found in metadata.")
        else:
            for p in points:
                print(f"\nID: {p.id}")
                print(f"Content Preview: {p.payload.get('content', '')[:200]}...")
                print(f"Metadata: {p.payload.get('metadata', {})}")

    except Exception as e:
        print(f"Error querying Qdrant: {e}")

if __name__ == "__main__":
    asyncio.run(audit_kbli_96121())