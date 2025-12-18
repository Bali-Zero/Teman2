import os
import asyncio
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv()

async def main():
    url = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    key = os.getenv("QDRANT_API_KEY")
    
    print(f"Connecting to {url}...")
    client = QdrantClient(url=url, api_key=key, timeout=60)
    
    try:
        collections = client.get_collections()
        print(f"Found {len(collections.collections)} collections:")
        for col in collections.collections:
            stats = client.get_collection(col.name)
            print(f"- {col.name}: {stats.points_count} vectors")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
