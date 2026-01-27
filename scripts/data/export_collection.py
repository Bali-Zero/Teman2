#!/usr/bin/env python3
"""Export Qdrant collection to local JSON file."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

HEADERS = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}


async def export_collection(collection_name: str, output_dir: Path) -> None:
    """Export all points from a Qdrant collection."""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{collection_name}_{timestamp}.json"
    
    print(f"📦 Exporting collection: {collection_name}")
    print(f"📍 Qdrant URL: {QDRANT_URL}")
    
    all_points = []
    offset = None
    batch_size = 100
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get collection info first
        info_resp = await client.get(
            f"{QDRANT_URL}/collections/{collection_name}",
            headers=HEADERS
        )
        if info_resp.status_code != 200:
            print(f"❌ Collection not found: {collection_name}")
            sys.exit(1)
            
        info = info_resp.json()["result"]
        total_points = info.get("points_count", 0)
        print(f"📊 Total points: {total_points:,}")
        
        # Scroll through all points
        while True:
            payload = {
                "limit": batch_size,
                "with_payload": True,
                "with_vector": False,  # Skip vectors to save space
            }
            if offset:
                payload["offset"] = offset
                
            resp = await client.post(
                f"{QDRANT_URL}/collections/{collection_name}/points/scroll",
                headers=HEADERS,
                json=payload
            )
            
            if resp.status_code != 200:
                print(f"❌ Scroll failed: {resp.text}")
                break
                
            data = resp.json()["result"]
            points = data.get("points", [])
            
            if not points:
                break
                
            all_points.extend(points)
            offset = data.get("next_page_offset")
            
            print(f"  ⏳ Fetched {len(all_points):,}/{total_points:,} points...", end="\r")
            
            if not offset:
                break
    
    print(f"\n✅ Fetched {len(all_points):,} points total")
    
    # Save to file
    export_data = {
        "collection": collection_name,
        "exported_at": datetime.now().isoformat(),
        "total_points": len(all_points),
        "points": all_points
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    file_size = output_file.stat().st_size / (1024 * 1024)
    print(f"💾 Saved to: {output_file}")
    print(f"📁 File size: {file_size:.2f} MB")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_collection.py <collection_name>")
        sys.exit(1)
    
    collection = sys.argv[1]
    output = Path(__file__).parent.parent.parent / "data" / "exports"
    
    asyncio.run(export_collection(collection, output))
