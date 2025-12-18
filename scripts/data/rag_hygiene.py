import asyncio
import os
import sys

# Add backend directory to path
# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag"))
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag/backend"))

from app.core.config import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Known junk files to remove
JUNK_FILES = [
    "Refund-3509-6917.pdf",
    "Resume Sarah Sendouw.pdf",
    "Kitas giga 2.pdf",
    "KBLI_RAG_API_ISSUE.md",
    "test_kbli.txt",
]

COLLECTIONS = [
    "visa_oracle",
    "tax_genius",
    "kbli_unified",
    "legal_unified",
    "bali_zero_team",
    "global_context"
]

def get_client():
    print(f"DEBUG: Qdrant URL: {settings.qdrant_url}")
    print(f"DEBUG: API Key Set: {'Yes' if settings.qdrant_api_key else 'No'}")
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=60
    )

async def audit_collection(client: QdrantClient, collection_name: str):
    print(f"\n--- Auditing Collection: {collection_name} ---")
    try:
        # Get count
        count = client.count(collection_name).count
        print(f"Total Vectors: {count}")
        
        if count == 0:
            return

        # Scroll to get unique filenames (approximation with limit)
        # For a full audit we would need to scroll everything, but let's sample 1000
        points, _ = client.scroll(
            collection_name=collection_name,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        filenames = {}
        for point in points:
            payload = point.payload or {}
            # Try various keys for filename
            fname = payload.get("source") or payload.get("filename") or payload.get("file_name") or "unknown"
            filenames[fname] = filenames.get(fname, 0) + 1
            
        print("Top Files (by chunk count in sample):")
        sorted_files = sorted(filenames.items(), key=lambda x: x[1], reverse=True)
        for fname, chunk_count in sorted_files[:10]:
            print(f"  - {fname}: {chunk_count} chunks")
            
        # Check for junk
        found_junk = []
        for junk in JUNK_FILES:
            # Check if junk exists in filenames keys (partial match or exact)
            matches = [f for f in filenames.keys() if junk in f]
            if matches:
                found_junk.extend(matches)
                print(f"  [!] FOUND JUNK: {matches}")

    except Exception as e:
        print(f"Error auditing {collection_name}: {e}")

async def clean_junk(client: QdrantClient):
    print("\n=== STARTING CLEANUP ===")
    for collection_name in COLLECTIONS:
        for junk in JUNK_FILES:
            print(f"Checking {collection_name} for '{junk}'...")
            
            # Construct filter
            # match "source" or "filename"
            try:
                # We try "source" field first
                client.delete(
                    collection_name=collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="source",
                                    match=models.MatchValue(value=junk)
                                )
                            ]
                        )
                    )
                )
                # Also try fuzzy filename match if strict failed? 
                # Strict is safer. Let's stick to strict or simple logic.
            except Exception as e:
                print(f"  Error cleaning {junk} from {collection_name}: {e}")

SEGUI IL TUO DEPLOY COSTNATEMENTE



if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
