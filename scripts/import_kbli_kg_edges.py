#!/usr/bin/env python3
"""
Import KBLI 2025 Knowledge Graph EDGES to PostgreSQL.
Fixes the relationship_id issue.
"""

import os
import json
import asyncio
import asyncpg
import hashlib
from typing import Dict, List


def extract_edges_from_kbli(items: List[Dict]) -> List[Dict]:
    """Extract KG edges from KBLI items."""
    edges = []

    for item in items:
        kode = item["kode_kbli_2025"]
        kbli_entity_id = f"kbli:{kode}"

        # Sector edge
        sektor_id = item.get("sektor_id")
        if sektor_id:
            sektor_entity_id = f"sektor:{sektor_id}"
            rel_id = hashlib.md5(
                f"{kbli_entity_id}:BELONGS_TO:{sektor_entity_id}".encode()
            ).hexdigest()
            edges.append(
                {
                    "relationship_id": rel_id,
                    "source_entity_id": kbli_entity_id,
                    "target_entity_id": sektor_entity_id,
                    "relationship_type": "BELONGS_TO",
                    "properties": json.dumps({}),
                    "source_collection": "kbli_2025_final",
                    "confidence": 0.95,
                }
            )

        # License requirements from per_skala
        for skala in item.get("per_skala", []):
            skala_usaha = skala.get("skala_usaha", "")
            perizinan = skala.get("perizinan", "")
            if not skala_usaha or not perizinan:
                continue

            license_id = hashlib.md5(
                f"{kode}:{skala_usaha}:{perizinan[:50]}".encode()
            ).hexdigest()[:12]
            license_entity_id = f"perizinan:{license_id}"
            rel_id = hashlib.md5(
                f"{kbli_entity_id}:REQUIRES:{license_entity_id}".encode()
            ).hexdigest()

            edges.append(
                {
                    "relationship_id": rel_id,
                    "source_entity_id": kbli_entity_id,
                    "target_entity_id": license_entity_id,
                    "relationship_type": "REQUIRES",
                    "properties": json.dumps({"skala_usaha": skala_usaha}),
                    "source_collection": "kbli_2025_final",
                    "confidence": 0.90,
                }
            )

    return edges


async def main():
    print("=" * 60)
    print("KBLI 2025 KG EDGES Import (Fixed)")
    print("=" * 60)

    # Connect
    print("\n[1/4] Connecting to PostgreSQL...")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("      Connected!")

    # Check current state
    print("\n[2/4] Checking current KG edges...")
    edges_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
    kbli_edges = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_edges WHERE source_collection = $1", "kbli_2025_final"
    )
    print(f"      Total edges: {edges_count}")
    print(f"      KBLI edges: {kbli_edges}")

    if kbli_edges > 0:
        print(f"\n      ⚠️  KBLI edges already exist ({kbli_edges})")
        print("      Deleting existing KBLI edges first...")
        await conn.execute(
            "DELETE FROM kg_edges WHERE source_collection = $1", "kbli_2025_final"
        )
        print("      Deleted.")

    # Load KBLI data
    print("\n[3/4] Loading KBLI 2025 data...")
    kbli_path = "/data/KBLI_2025_FINAL_CLEAN.json"

    with open(kbli_path, "r", encoding="utf-8") as f:
        kbli_raw = json.load(f)

    items = kbli_raw.get("data", kbli_raw) if isinstance(kbli_raw, dict) else kbli_raw
    print(f"      Loaded {len(items)} KBLI codes")

    # Extract edges
    edges = extract_edges_from_kbli(items)
    print(f"      Edges to import: {len(edges)}")

    # Insert edges
    print("\n[4/4] Inserting edges...")
    batch_size = 100
    inserted = 0
    errors = 0

    for i in range(0, len(edges), batch_size):
        batch = edges[i : i + batch_size]
        for edge in batch:
            try:
                await conn.execute(
                    """
                    INSERT INTO kg_edges (
                        relationship_id, source_entity_id, target_entity_id,
                        relationship_type, properties, source_collection, confidence
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                    ON CONFLICT (relationship_id) DO NOTHING
                """,
                    edge["relationship_id"],
                    edge["source_entity_id"],
                    edge["target_entity_id"],
                    edge["relationship_type"],
                    edge["properties"],
                    edge["source_collection"],
                    edge["confidence"],
                )
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"      Error: {e}")

        if (i + batch_size) % 1000 == 0:
            print(f"      Progress: {inserted}/{len(edges)} edges")

    # Verify
    final_edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
    final_kbli = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_edges WHERE source_collection = $1", "kbli_2025_final"
    )

    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"Inserted: {inserted} edges")
    print(f"Errors: {errors}")
    print(f"Total kg_edges: {final_edges}")
    print(f"KBLI edges: {final_kbli}")
    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
