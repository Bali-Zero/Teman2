import os
import asyncio
from qdrant_client import QdrantClient, AsyncQdrantClient

# Hardcoded for verification based on previous context, or relying on env vars if set in the environment
# Adjusting to use the local service logic if possible, but a direct client is safer for a quick check.
# I will try to load from environment or use typical defaults if not gathered.
# In this environment, I might not have the .env keys loaded in the shell unless I source them.
# I'll rely on the app's config loading if possible, or just try to connect to the cloud if I had the creds.
# Since I can't easily see user's env vars, I will try to use the `services.collection_manager` if I can import it.

import sys
sys.path.append('/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag/backend')

from config import settings
from qdrant_client import AsyncQdrantClient

async def check_stats():
    try:
        url = settings.QDRANT_URL
        api_key = settings.QDRANT_API_KEY
        
        print(f"Connecting to Qdrant at: {url} (Key hidden)")
        
        client = AsyncQdrantClient(url=url, api_key=api_key)
        
        collections_to_check = [
            "legal_unified_hybrid",
            "visa_oracle",
            "pricing_data",
            "kbli_unified",
            "collective_memories",
            "cultural_insights",
            "team_knowledge" # If it exists
        ]
        
        print("\n--- Qdrant Collection Stats ---")
        for name in collections_to_check:
            try:
                info = await client.get_collection(name)
                count = info.points_count
                status = info.status
                print(f"[{name}]: {count} vectors (Status: {status})")
            except Exception as e:
                print(f"[{name}]: ERROR/NOT FOUND ({str(e)})")
                
    except Exception as e:
        print(f"Fatal connection error: {e}")

if __name__ == "__main__":
    asyncio.run(check_stats())
