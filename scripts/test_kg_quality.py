#!/usr/bin/env python3
"""Test KBLI 2025 Knowledge Graph quality in PostgreSQL."""

import os
import asyncio
import asyncpg


async def test_kg():
    print("=" * 70)
    print("🧪 KBLI 2025 QUALITY TESTS - POSTGRESQL KG")
    print("=" * 70)

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    print("\n[TEST 1] KG Statistics")
    print("-" * 50)
    nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
    edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
    kbli_nodes = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = $1", "kbli"
    )
    kbli_edges = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_edges WHERE source_collection = $1", "kbli_2025_final"
    )

    print(f"Total nodes: {nodes}")
    print(f"Total edges: {edges}")
    print(f"KBLI nodes: {kbli_nodes}")
    print(f"KBLI edges: {kbli_edges}")

    print("\n[TEST 2] Entity Type Distribution")
    print("-" * 50)
    types = await conn.fetch(
        "SELECT entity_type, COUNT(*) as cnt FROM kg_nodes GROUP BY entity_type ORDER BY cnt DESC"
    )
    for t in types:
        print(f"  {t['entity_type']}: {t['cnt']}")

    print("\n[TEST 3] Relationship Type Distribution")
    print("-" * 50)
    rels = await conn.fetch(
        "SELECT relationship_type, COUNT(*) as cnt FROM kg_edges GROUP BY relationship_type ORDER BY cnt DESC"
    )
    for r in rels:
        print(f"  {r['relationship_type']}: {r['cnt']}")

    print("\n[TEST 4] Sample KBLI Node")
    print("-" * 50)
    sample = await conn.fetchrow(
        "SELECT * FROM kg_nodes WHERE entity_type = $1 LIMIT 1", "kbli"
    )
    if sample:
        print(f"  entity_id: {sample['entity_id']}")
        print(f"  name: {sample['name']}")
        desc = sample["description"] or ""
        print(f"  description: {desc[:60]}...")

    print("\n[TEST 5] Graph Traversal - Restaurant KBLI")
    print("-" * 50)
    restaurant = await conn.fetchrow(
        "SELECT * FROM kg_nodes WHERE entity_id = $1", "kbli:56101"
    )
    if restaurant:
        print(f"Found: {restaurant['name']}")

        edges_out = await conn.fetch(
            """
            SELECT e.relationship_type, n.name, n.entity_type
            FROM kg_edges e
            JOIN kg_nodes n ON e.target_entity_id = n.entity_id
            WHERE e.source_entity_id = $1
            LIMIT 5
        """,
            "kbli:56101",
        )

        print(f"Outgoing relationships ({len(edges_out)}):")
        for e in edges_out:
            print(
                f"  --[{e['relationship_type']}]--> {e['name'][:40]} ({e['entity_type']})"
            )
    else:
        print("Restaurant KBLI not found")

    print("\n[TEST 6] Sector Coverage")
    print("-" * 50)
    sectors = await conn.fetch(
        """
        SELECT entity_id, name FROM kg_nodes
        WHERE entity_type = $1
        ORDER BY entity_id
        LIMIT 10
    """,
        "sektor",
    )
    print(f"Sample sectors ({len(sectors)}):")
    for s in sectors:
        print(f"  {s['entity_id']}: {s['name']}")

    print("\n[TEST 7] License Requirements Sample")
    print("-" * 50)
    licenses = await conn.fetch(
        """
        SELECT name FROM kg_nodes
        WHERE entity_type = $1
        LIMIT 5
    """,
        "perizinan",
    )
    print(f"Sample licenses ({len(licenses)}):")
    for lic in licenses:
        name = lic["name"] or ""
        print(f"  - {name[:60]}...")

    print("\n[TEST 8] Cross-Reference Check")
    print("-" * 50)
    # Count edges per relationship type for KBLI
    cross = await conn.fetch("""
        SELECT relationship_type, COUNT(*) as cnt
        FROM kg_edges
        WHERE source_entity_id LIKE 'kbli:%'
        GROUP BY relationship_type
    """)
    for c in cross:
        print(f"  KBLI --[{c['relationship_type']}]--> : {c['cnt']}")

    print("\n" + "=" * 70)
    print("✅ POSTGRESQL KG TESTS COMPLETE")
    print("=" * 70)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(test_kg())
