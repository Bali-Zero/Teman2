import asyncio
import json
import httpx
import os

QDRANT_URL = "https://nuzantara-qdrant.fly.dev"
# API Key is in the environment as per memories
API_KEY = os.environ.get("QDRANT_API_KEY")

async def get_chunks():
    headers = {
        "api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Specific IDs from the ingestion log
    target_ids = [
        "95f87ab5-2f05-5308-8afd-2f591e5476df",
        "484faee5-5d4d-57d2-86b1-46f0502edf30",
        "fb1e2b71-28c4-5dec-a6ba-6c2c4b84a760"
    ]
    
    payload = {
        "ids": target_ids,
        "with_payload": True,
        "with_vector": False
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{QDRANT_URL}/collections/legal_unified/points",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            points = result.get("result", [])
            
            print("\n" + "="*80)
            print(f"🔍 INSPECTION: Target Chunks for UU_63_2024")
            print("="*80)
            
            for i, p in enumerate(points):
                payload = p.get("payload", {})
                metadata = payload.get("metadata", {})
                
                print(f"\n📦 CHUNK {i+1} (ID: {p['id']})")
                print(f"📂 Category: {metadata.get('category')}")
                print(f"🏷️ Hierarchy Path: {metadata.get('hierarchy_path')}")
                print(f"📖 Book Title: {metadata.get('book_title')}")
                print(f"🏛️ Legal Type: {metadata.get('legal_type')} {metadata.get('legal_number')}/{metadata.get('legal_year')}")
                print("-" * 40)
                content = payload.get("text", "No text found")
                print(f"CONTENT SNIPPET:\n{content[:500]}...")
                print("-" * 40)
                print("🛠️ RAW METADATA KEYS:", list(metadata.keys()))
                print("-" * 80)
        else:
            print(f"❌ Error fetching from Qdrant: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    if not API_KEY:
        print("❌ QDRANT_API_KEY not found in environment.")
    else:
        asyncio.run(get_chunks())
