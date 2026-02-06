#!/usr/bin/env python3
"""
Import KBLI 2025 Knowledge Graph data to PostgreSQL.
This script should be run from Fly.io environment.
"""

import os
import json
import asyncio
import asyncpg
import hashlib
from typing import Dict, List, Tuple


# KBLI 2025 codes to import - simplified KG extraction
def extract_kg_from_kbli(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Extract KG nodes and edges from KBLI items."""
    nodes = []
    edges = []

    for item in items:
        kode = item["kode_kbli_2025"]
        kbli_entity_id = f"kbli:{kode}"

        # Main KBLI node
        nodes.append(
            {
                "entity_id": kbli_entity_id,
                "name": f"KBLI {kode}",
                "entity_type": "kbli",
                "description": item.get("judul", ""),
                "properties": json.dumps(
                    {
                        "kode": kode,
                        "uraian": (item.get("uraian", "") or "")[:500],
                        "pma_status": item.get("pma_status"),
                        "licensing_status": item.get("licensing_status"),
                    }
                ),
                "source_collection": "kbli_2025_final",
                "confidence": 0.95,
            }
        )

        # Sector node and edge
        sektor_id = item.get("sektor_id")
        if sektor_id:
            sektor_entity_id = f"sektor:{sektor_id}"
            nodes.append(
                {
                    "entity_id": sektor_entity_id,
                    "name": item.get("sektor_nama", f"Sector {sektor_id}"),
                    "entity_type": "sektor",
                    "description": f"Economic sector {sektor_id}",
                    "properties": json.dumps({"sektor_id": sektor_id}),
                    "source_collection": "kbli_2025_final",
                    "confidence": 0.95,
                }
            )
            edges.append(
                {
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

            nodes.append(
                {
                    "entity_id": license_entity_id,
                    "name": perizinan[:100] if len(perizinan) > 100 else perizinan,
                    "entity_type": "perizinan",
                    "description": f"License for {skala_usaha} scale",
                    "properties": json.dumps(
                        {
                            "skala_usaha": skala_usaha,
                            "kategori_risiko": skala.get("kategori_risiko"),
                            "jangka_waktu": skala.get("jangka_waktu"),
                            "kewajiban": skala.get("kewajiban"),
                        }
                    ),
                    "source_collection": "kbli_2025_final",
                    "confidence": 0.90,
                }
            )
            edges.append(
                {
                    "source_entity_id": kbli_entity_id,
                    "target_entity_id": license_entity_id,
                    "relationship_type": "REQUIRES",
                    "properties": json.dumps({"skala_usaha": skala_usaha}),
                    "source_collection": "kbli_2025_final",
                    "confidence": 0.90,
                }
            )

    return nodes, edges


async def main():
    print("=" * 60)
    print("KBLI 2025 Knowledge Graph Import")
    print("=" * 60)

    # Connect
    print("\n[1/5] Connecting to PostgreSQL...")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("      Connected!")

    # Check current state
    print("\n[2/5] Checking current KG state...")
    nodes_count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
    edges_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
    kbli_count = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = $1", "kbli"
    )
    print(f"      kg_nodes: {nodes_count} (KBLI: {kbli_count})")
    print(f"      kg_edges: {edges_count}")

    if kbli_count > 0:
        print(f"\n      ⚠️  KBLI data already exists ({kbli_count} nodes)")
        print("      Skipping import to avoid duplicates.")
        await conn.close()
        return

    # Load KBLI data
    print("\n[3/5] Loading KBLI 2025 data...")
    kbli_path = "/app/data/KBLI_2025_FINAL_CLEAN.json"

    if not os.path.exists(kbli_path):
        # Try alternative path
        kbli_path = "/data/KBLI_2025_FINAL_CLEAN.json"

    if not os.path.exists(kbli_path):
        print(f"      ERROR: KBLI file not found at {kbli_path}")
        await conn.close()
        return

    with open(kbli_path, "r", encoding="utf-8") as f:
        kbli_raw = json.load(f)

    items = kbli_raw.get("data", kbli_raw) if isinstance(kbli_raw, dict) else kbli_raw
    print(f"      Loaded {len(items)} KBLI codes")

    # Extract KG
    print("\n[4/5] Extracting Knowledge Graph...")
    nodes, edges = extract_kg_from_kbli(items)

    # Deduplicate nodes
    seen = {}
    unique_nodes = []
    for node in nodes:
        if node["entity_id"] not in seen:
            seen[node["entity_id"]] = True
            unique_nodes.append(node)

    print(f"      Nodes: {len(unique_nodes)}")
    print(f"      Edges: {len(edges)}")

    # Insert nodes
    print("\n[5/5] Inserting into PostgreSQL...")

    # Insert nodes in batches
    batch_size = 100
    inserted_nodes = 0
    for i in range(0, len(unique_nodes), batch_size):
        batch = unique_nodes[i : i + batch_size]
        for node in batch:
            try:
                await conn.execute(
                    """
                    INSERT INTO kg_nodes (entity_id, name, entity_type, description, properties, source_collection, confidence)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                    ON CONFLICT (entity_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        properties = EXCLUDED.properties,
                        confidence = EXCLUDED.confidence
                """,
                    node["entity_id"],
                    node["name"],
                    node["entity_type"],
                    node["description"],
                    node["properties"],
                    node["source_collection"],
                    node["confidence"],
                )
                inserted_nodes += 1
            except Exception as e:
                print(f"      Error inserting node {node['entity_id']}: {e}")

        if (i + batch_size) % 500 == 0:
            print(f"      Nodes: {inserted_nodes}/{len(unique_nodes)}")

    print(f"      Inserted {inserted_nodes} nodes")

    # Insert edges in batches
    inserted_edges = 0
    for i in range(0, len(edges), batch_size):
        batch = edges[i : i + batch_size]
        for edge in batch:
            try:
                await conn.execute(
                    """
                    INSERT INTO kg_edges (source_entity_id, target_entity_id, relationship_type, properties, source_collection, confidence)
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                    ON CONFLICT DO NOTHING
                """,
                    edge["source_entity_id"],
                    edge["target_entity_id"],
                    edge["relationship_type"],
                    edge["properties"],
                    edge["source_collection"],
                    edge["confidence"],
                )
                inserted_edges += 1
            except Exception as e:
                print(f"      Error inserting edge: {e}")

        if (i + batch_size) % 500 == 0:
            print(f"      Edges: {inserted_edges}/{len(edges)}")

    print(f"      Inserted {inserted_edges} edges")

    # Verify
    final_nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
    final_edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
    final_kbli = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = $1", "kbli"
    )

    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"kg_nodes: {nodes_count} → {final_nodes} (+{final_nodes - nodes_count})")
    print(f"kg_edges: {edges_count} → {final_edges} (+{final_edges - edges_count})")
    print(f"KBLI nodes: {final_kbli}")
    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
