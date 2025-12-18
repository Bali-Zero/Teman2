#!/usr/bin/env python3
"""
DEDUPLICATE QDRANT COLLECTIONS
==============================

Removes duplicate documents from Qdrant collections based on content hash.
For each set of duplicates, keeps the first document and deletes the rest.

Usage:
    python scripts/deduplicate_collections.py --scan      # Scan only
    python scripts/deduplicate_collections.py --purge     # Delete duplicates
"""

import asyncio
import hashlib
import os
import sys
from collections import defaultdict
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

COLLECTIONS = [
    "visa_oracle",
    "tax_genius",
    "legal_unified",
    "training_conversations",
    "bali_zero_pricing",
    "bali_intel_immigration",
    "kbli_unified",
    "property_unified",
]


async def scroll_collection(client, headers, collection, limit=100, offset=None):
    """Scroll through collection"""
    payload = {"limit": limit, "with_payload": True, "with_vector": False}
    if offset:
        payload["offset"] = offset

    resp = await client.post(
        f"{QDRANT_URL}/collections/{collection}/points/scroll",
        headers=headers,
        json=payload,
        timeout=60,
    )

    if resp.status_code == 200:
        data = resp.json().get("result", {})
        return data.get("points", []), data.get("next_page_offset")
    return [], None


async def find_duplicates(client, headers, collection):
    """Find all duplicate documents in a collection"""
    print(f"\n📋 Scanning {collection}...")

    content_hashes = defaultdict(list)
    offset = None
    scanned = 0

    while True:
        points, next_offset = await scroll_collection(
            client, headers, collection, limit=100, offset=offset
        )

        if not points:
            break

        for point in points:
            scanned += 1
            point_id = str(point["id"])
            payload = point.get("payload", {})
            text = payload.get("text", "")

            if text.strip():
                content_hash = hashlib.md5(text.encode()).hexdigest()
                content_hashes[content_hash].append(point_id)

        offset = next_offset
        if not offset:
            break

        if scanned % 500 == 0:
            print(f"  Scanned {scanned}...")

    # Find duplicates (hashes with more than 1 document)
    duplicates = {h: ids for h, ids in content_hashes.items() if len(ids) > 1}

    # Calculate IDs to delete (keep first, delete rest)
    ids_to_delete = []
    for ids in duplicates.values():
        ids_to_delete.extend(ids[1:])  # Keep first, delete rest

    print(
        f"  ✓ Scanned {scanned} docs, found {len(ids_to_delete)} duplicates to remove"
    )
    return ids_to_delete


async def delete_points(client, headers, collection, point_ids):
    """Delete points from collection"""
    if not point_ids:
        return True

    batch_size = 100
    deleted = 0

    for i in range(0, len(point_ids), batch_size):
        batch = point_ids[i : i + batch_size]

        resp = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/delete",
            headers=headers,
            json={"points": batch},
            timeout=60,
            params={"wait": "true"},
        )

        if resp.status_code == 200:
            deleted += len(batch)
            print(f"  🗑️  Deleted {deleted}/{len(point_ids)}")
        else:
            print(f"  ❌ Delete failed: HTTP {resp.status_code}")
            return False

    return True


async def main():
    scan_only = "--scan" in sys.argv
    do_purge = "--purge" in sys.argv

    if not scan_only and not do_purge:
        print("Usage:")
        print("  python scripts/deduplicate_collections.py --scan   # Scan only")
        print(
            "  python scripts/deduplicate_collections.py --purge  # Delete duplicates"
        )
        return

    print("=" * 60)
    print("🧹 QDRANT DEDUPLICATION")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Mode: {'SCAN ONLY' if scan_only else '🚨 PURGE MODE'}")

    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    all_duplicates = {}

    async with httpx.AsyncClient() as client:
        for collection in COLLECTIONS:
            try:
                ids_to_delete = await find_duplicates(client, headers, collection)
                all_duplicates[collection] = ids_to_delete
            except Exception as e:
                print(f"  ❌ Error: {e}")
                all_duplicates[collection] = []

        # Summary
        total = sum(len(ids) for ids in all_duplicates.values())
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY: {total} duplicates found")
        print("=" * 60)

        for coll, ids in all_duplicates.items():
            if ids:
                print(f"  {coll}: {len(ids)} duplicates")

        if scan_only:
            print("\n📝 Run with --purge to delete duplicates")
            return

        if total == 0:
            print("\n✅ No duplicates to remove!")
            return

        # Confirm deletion
        print(f"\n⚠️  This will DELETE {total} duplicate documents.")
        confirm = input("Type 'DEDUPE' to confirm: ")
        if confirm != "DEDUPE":
            print("❌ Aborted.")
            return

        # Delete duplicates
        print("\n🗑️  Deleting duplicates...")
        for coll, ids in all_duplicates.items():
            if ids:
                print(f"\n  Processing {coll}...")
                success = await delete_points(client, headers, coll, ids)
                if success:
                    print(f"  ✅ {coll}: Removed {len(ids)} duplicates")
                else:
                    print(f"  ❌ {coll}: Deletion failed")

        print("\n✨ Deduplication complete!")


if __name__ == "__main__":
    asyncio.run(main())
