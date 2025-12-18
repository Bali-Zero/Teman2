#!/usr/bin/env python3
"""
PURGE OUTDATED VISA CODES FROM QDRANT
=====================================

This script scans visa_oracle (and related collections) for documents
containing outdated/deprecated visa code references and removes them.

OUTDATED CODES TO PURGE:
- C317: Old family reunion visa code (now replaced with new system)
- VITAS C317: Old naming convention
- Old KITAS naming conventions that reference C317

The problem: Zantara was citing C317 for family reunion visas, which
is outdated information. This script purges those documents.

Usage:
    python scripts/purge_outdated_visa_codes.py --scan      # Scan only, no delete
    python scripts/purge_outdated_visa_codes.py --purge     # Actually delete

Author: Nuzantara Team
Date: 2025-12-13
"""

import asyncio
import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# Collections to scan for outdated visa codes
COLLECTIONS_TO_SCAN = [
    "visa_oracle",
    "legal_unified",
    "kbli_unified",
    "tax_unified",
    "property_unified",
    "bali_zero_team",
    "bali_zero_pricing",
    "training_conversations",
    "user_memory",
    "conversation_memory",
]

# Outdated visa codes to search for in documents
# NOTE: E31A, E31B, E31C, E31D are VALID current codes - do NOT include them
OUTDATED_PATTERNS = [
    # C317 variants (old family reunion) - FAKE
    "C317",
    "VITAS C317",
    "C 317",
    "C-317",
    "visa C317",
    "KITAS C317",
    # Old C-series index codes (replaced by E-series) - OBSOLETE
    "C312",
    "C313",
    "C314",
    "C315",
    "C316",
    # FAKE codes that never existed
    "B211A",
    "B211B",
    "C211A",
    "C211B",
    # Only match standalone "211A" or "211B" (not part of E211A which doesn't exist anyway)
    " 211A",
    " 211B",
    "211A ",
    "211B ",
]


async def get_collection_stats(client: httpx.AsyncClient, collection: str) -> dict:
    """Get collection statistics."""
    headers = {"api-key": QDRANT_API_KEY}
    try:
        resp = await client.get(
            f"{QDRANT_URL}/collections/{collection}", headers=headers, timeout=30
        )
        if resp.status_code == 200:
            data = resp.json().get("result", {})
            return {
                "name": collection,
                "points_count": data.get("points_count", 0),
                "status": data.get("status", "unknown"),
            }
        return {"name": collection, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"name": collection, "error": str(e)}


async def scroll_collection(
    client: httpx.AsyncClient,
    collection: str,
    limit: int = 100,
    offset: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    Scroll through collection to retrieve all points.
    Returns (points, next_offset)
    """
    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    payload: dict[str, Any] = {
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
    }

    if offset:
        payload["offset"] = offset

    try:
        resp = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if resp.status_code == 200:
            data = resp.json().get("result", {})
            points = data.get("points", [])
            next_offset = data.get("next_page_offset")
            return points, next_offset
        else:
            print(f"  Error scrolling {collection}: HTTP {resp.status_code}")
            return [], None
    except Exception as e:
        print(f"  Error scrolling {collection}: {e}")
        return [], None


def check_for_outdated_codes(point: dict) -> list[str]:
    """
    Check if a point contains outdated visa codes.
    Returns list of matched patterns.
    """
    matches = []

    # Get text content
    payload = point.get("payload", {})
    text = payload.get("text", "")

    # Also check metadata fields
    metadata = payload.get("metadata", {})
    metadata_str = str(metadata)

    # Combined searchable content
    searchable = f"{text} {metadata_str}".upper()

    for pattern in OUTDATED_PATTERNS:
        if pattern.upper() in searchable:
            matches.append(pattern)

    return matches


async def scan_collection(client: httpx.AsyncClient, collection: str) -> list[dict]:
    """
    Scan a collection for outdated visa codes.
    Returns list of points to delete.
    """
    print(f"\n📋 Scanning collection: {collection}")

    outdated_points = []
    total_scanned = 0
    offset = None

    while True:
        points, next_offset = await scroll_collection(
            client, collection, limit=100, offset=offset
        )

        if not points:
            break

        for point in points:
            total_scanned += 1
            matches = check_for_outdated_codes(point)

            if matches:
                point_id = point.get("id")
                text_preview = point.get("payload", {}).get("text", "")[:100]
                outdated_points.append(
                    {
                        "id": point_id,
                        "collection": collection,
                        "matches": matches,
                        "text_preview": text_preview,
                    }
                )

        offset = next_offset
        if not offset:
            break

        # Progress indicator
        if total_scanned % 500 == 0:
            print(
                f"  ... scanned {total_scanned} points, found {len(outdated_points)} outdated"
            )

    print(
        f"  ✓ Scanned {total_scanned} points, found {len(outdated_points)} with outdated codes"
    )
    return outdated_points


async def delete_points(
    client: httpx.AsyncClient, collection: str, point_ids: list[str]
) -> bool:
    """Delete points by ID from a collection."""
    if not point_ids:
        return True

    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    # Delete in batches of 100
    batch_size = 100
    deleted = 0

    for i in range(0, len(point_ids), batch_size):
        batch = point_ids[i : i + batch_size]

        payload = {"points": batch}

        try:
            resp = await client.post(
                f"{QDRANT_URL}/collections/{collection}/points/delete",
                headers=headers,
                json=payload,
                timeout=60,
                params={"wait": "true"},
            )

            if resp.status_code == 200:
                deleted += len(batch)
                print(f"  🗑️  Deleted batch: {deleted}/{len(point_ids)}")
            else:
                print(f"  ❌ Delete failed: HTTP {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  ❌ Delete error: {e}")
            return False

    return True


async def main():
    """Main function."""
    # Parse arguments
    scan_only = "--scan" in sys.argv
    do_purge = "--purge" in sys.argv

    if not scan_only and not do_purge:
        print("Usage:")
        print("  python scripts/purge_outdated_visa_codes.py --scan   # Scan only")
        print(
            "  python scripts/purge_outdated_visa_codes.py --purge  # Scan and delete"
        )
        return

    print("=" * 60)
    print("🔍 OUTDATED VISA CODE PURGER")
    print("=" * 60)
    print(f"\nQdrant URL: {QDRANT_URL}")
    print(f"Mode: {'SCAN ONLY' if scan_only else '🚨 PURGE MODE'}")
    print(f"\nPatterns to search: {OUTDATED_PATTERNS}")
    print(f"Collections to scan: {COLLECTIONS_TO_SCAN}")

    if not QDRANT_API_KEY:
        print("\n❌ ERROR: QDRANT_API_KEY not set in environment")
        return

    async with httpx.AsyncClient() as client:
        # First, show collection stats
        print("\n📊 Collection Statistics:")
        for coll in COLLECTIONS_TO_SCAN:
            stats = await get_collection_stats(client, coll)
            if "error" in stats:
                print(f"  - {coll}: {stats['error']}")
            else:
                print(
                    f"  - {coll}: {stats['points_count']:,} points ({stats['status']})"
                )

        # Scan all collections
        all_outdated = []

        for collection in COLLECTIONS_TO_SCAN:
            outdated = await scan_collection(client, collection)
            all_outdated.extend(outdated)

        # Report findings
        print("\n" + "=" * 60)
        print("📋 SCAN RESULTS")
        print("=" * 60)

        if not all_outdated:
            print("\n✅ No outdated visa codes found! Your data is clean.")
            return

        print(f"\n⚠️  Found {len(all_outdated)} documents with outdated codes:")

        # Group by collection
        by_collection: dict[str, list] = {}
        for item in all_outdated:
            coll = item["collection"]
            if coll not in by_collection:
                by_collection[coll] = []
            by_collection[coll].append(item)

        for coll, items in by_collection.items():
            print(f"\n  📁 {coll}: {len(items)} documents")
            for item in items[:5]:  # Show first 5
                print(f"      ID: {item['id']}")
                print(f"      Matches: {item['matches']}")
                print(f"      Preview: {item['text_preview'][:80]}...")
                print()
            if len(items) > 5:
                print(f"      ... and {len(items) - 5} more")

        # If scan only, stop here
        if scan_only:
            print("\n📝 Run with --purge to delete these documents")
            return

        # Confirmation for purge
        print("\n" + "=" * 60)
        print("🚨 PURGE CONFIRMATION")
        print("=" * 60)
        print(f"\nThis will DELETE {len(all_outdated)} documents from Qdrant.")
        print("This action is IRREVERSIBLE.")

        confirm = input("\nType 'DELETE' to confirm: ")
        if confirm != "DELETE":
            print("❌ Aborted.")
            return

        # Perform deletion
        print("\n🗑️  Deleting outdated documents...")

        for coll, items in by_collection.items():
            point_ids = [item["id"] for item in items]
            print(f"\n  Deleting {len(point_ids)} from {coll}...")
            success = await delete_points(client, coll, point_ids)
            if success:
                print(f"  ✅ {coll}: Deleted {len(point_ids)} documents")
            else:
                print(f"  ❌ {coll}: Deletion failed")

        # Verify
        print("\n📊 Verification - New Collection Statistics:")
        for coll in COLLECTIONS_TO_SCAN:
            stats = await get_collection_stats(client, coll)
            if "error" not in stats:
                print(f"  - {coll}: {stats['points_count']:,} points")

        print("\n✨ Purge complete! Outdated visa codes have been removed.")


if __name__ == "__main__":
    asyncio.run(main())
