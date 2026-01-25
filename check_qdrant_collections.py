#!/usr/bin/env python3
"""
Qdrant Collection Diagnostics
==============================

Direct check of Qdrant collections from production environment.
"""

import asyncio
import httpx
import json

QDRANT_URL = "https://nuzantara-rag.fly.dev"  # Production endpoint

async def check_qdrant_collections():
    """Check Qdrant collections via backend proxy."""
    print("🔍 Checking Qdrant Collections...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Try to hit a diagnostic endpoint if available
            # Or we can create a simple test script that runs IN production
            
            # For now, let's check if there's a collections endpoint
            response = await client.get(f"{QDRANT_URL}/api/collections")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ Collections Found: {len(data.get('collections', []))}")
                for col in data.get('collections', []):
                    print(f"  - {col['name']}: {col.get('vectors_count', 0)} vectors")
            else:
                print(f"❌ Failed to fetch collections: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_qdrant_collections())
