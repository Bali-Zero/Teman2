#!/usr/bin/env python3
"""Advanced Knowledge Graph Tests for KBLI 2025."""

import os
import asyncio
import asyncpg
import json


async def test_kg_advanced():
    print("=" * 70)
    print("🧪 KBLI 2025 - TEST AVANZATI PARTE 3 (Knowledge Graph)")
    print("=" * 70)

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    print("\n" + "=" * 50)
    print("TEST 25: Graph Traversal - Find All Restaurant Requirements")
    print("=" * 50)

    # Get all edges from Restaurant KBLI
    edges = await conn.fetch(
        """
        SELECT e.relationship_type, e.target_entity_id, n.name, n.entity_type, n.properties
        FROM kg_edges e
        JOIN kg_nodes n ON e.target_entity_id = n.entity_id
        WHERE e.source_entity_id = $1
    """,
        "kbli:56101",
    )

    print(f"KBLI 56101 (Restaurant) has {len(edges)} outgoing edges:")
    by_type = {}
    for e in edges:
        rt = e["relationship_type"]
        by_type[rt] = by_type.get(rt, [])
        by_type[rt].append({"target": e["name"], "type": e["entity_type"]})

    for rt, targets in by_type.items():
        print(f"\n  --[{rt}]--> ({len(targets)} targets):")
        for t in targets[:3]:
            print(f"      • {t['target'][:50]} ({t['type']})")
        if len(targets) > 3:
            print(f"      ... and {len(targets) - 3} more")

    print("\n" + "=" * 50)
    print("TEST 26: Reverse Graph Traversal - What Requires NIB?")
    print("=" * 50)

    # Find a NIB node
    nib_node = await conn.fetchrow("""
        SELECT entity_id, name FROM kg_nodes
        WHERE name LIKE '%NIB%' AND entity_type = 'perizinan'
        LIMIT 1
    """)

    if nib_node:
        print(f"Found NIB node: {nib_node['entity_id']}")

        # Get incoming edges
        incoming = await conn.fetch(
            """
            SELECT e.source_entity_id, n.name, n.entity_type
            FROM kg_edges e
            JOIN kg_nodes n ON e.source_entity_id = n.entity_id
            WHERE e.target_entity_id = $1
            LIMIT 10
        """,
            nib_node["entity_id"],
        )

        print(f"KBLI codes that require this license ({len(incoming)}):")
        for i in incoming[:5]:
            print(f"  • {i['name'][:50]} ({i['entity_type']})")

    print("\n" + "=" * 50)
    print("TEST 27: Sector Analysis - KBLI per Sector")
    print("=" * 50)

    sector_stats = await conn.fetch("""
        SELECT n.entity_id, n.name, COUNT(e.source_entity_id) as kbli_count
        FROM kg_nodes n
        LEFT JOIN kg_edges e ON e.target_entity_id = n.entity_id AND e.relationship_type = 'BELONGS_TO'
        WHERE n.entity_type = 'sektor'
        GROUP BY n.entity_id, n.name
        ORDER BY kbli_count DESC
    """)

    print("KBLI codes per sector:")
    for s in sector_stats[:10]:
        print(f"  {s['entity_id']}: {s['kbli_count']} KBLI codes")

    print("\n" + "=" * 50)
    print("TEST 28: License Complexity Analysis")
    print("=" * 50)

    # Count unique license types
    license_types = await conn.fetch("""
        SELECT DISTINCT name, COUNT(*) as occurrences
        FROM kg_nodes
        WHERE entity_type = 'perizinan'
        GROUP BY name
        ORDER BY occurrences DESC
        LIMIT 15
    """)

    print("Top 15 license types:")
    for lic in license_types:
        name = lic["name"][:50] if lic["name"] else "N/A"
        print(f"  {lic['occurrences']:4d}x | {name}")

    print("\n" + "=" * 50)
    print("TEST 29: Multi-Hop Query - KBLI → Sector → Other KBLIs")
    print("=" * 50)

    # Find sector for Restaurant
    sector = await conn.fetchrow(
        """
        SELECT n.entity_id, n.name
        FROM kg_edges e
        JOIN kg_nodes n ON e.target_entity_id = n.entity_id
        WHERE e.source_entity_id = $1 AND e.relationship_type = 'BELONGS_TO'
        LIMIT 1
    """,
        "kbli:56101",
    )

    if sector:
        print(
            f"Restaurant (56101) belongs to: {sector['name']} ({sector['entity_id']})"
        )

        # Find other KBLIs in same sector
        same_sector = await conn.fetch(
            """
            SELECT n.entity_id, n.name
            FROM kg_edges e
            JOIN kg_nodes n ON e.source_entity_id = n.entity_id
            WHERE e.target_entity_id = $1 AND e.relationship_type = 'BELONGS_TO'
            AND n.entity_id != 'kbli:56101'
            LIMIT 10
        """,
            sector["entity_id"],
        )

        print(f"\nOther KBLIs in same sector ({len(same_sector)}):")
        for s in same_sector:
            kode = s["entity_id"].replace("kbli:", "")
            print(f"  • [{kode}] {s['name'][:40]}")

    print("\n" + "=" * 50)
    print("TEST 30: Entity Properties Inspection")
    print("=" * 50)

    # Check properties of KBLI nodes
    sample_with_props = await conn.fetch("""
        SELECT entity_id, name, properties
        FROM kg_nodes
        WHERE entity_type = 'kbli' AND properties IS NOT NULL
        LIMIT 3
    """)

    print("Sample KBLI node properties:")
    for s in sample_with_props:
        print(f"\n  {s['entity_id']}:")
        if s["properties"]:
            props = (
                json.loads(s["properties"])
                if isinstance(s["properties"], str)
                else s["properties"]
            )
            for k, v in props.items():
                v_str = str(v)[:40] if v else "null"
                print(f"    {k}: {v_str}")

    print("\n" + "=" * 50)
    print("TEST 31: Data Integrity - Orphan Check")
    print("=" * 50)

    # Find nodes without edges
    orphans = await conn.fetchval("""
        SELECT COUNT(*) FROM kg_nodes n
        WHERE NOT EXISTS (
            SELECT 1 FROM kg_edges e
            WHERE e.source_entity_id = n.entity_id OR e.target_entity_id = n.entity_id
        )
    """)

    total_nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")

    print(f"Total nodes: {total_nodes}")
    print(f"Orphan nodes (no edges): {orphans} ({orphans / total_nodes * 100:.1f}%)")
    print(f"Connected nodes: {total_nodes - orphans}")

    print("\n" + "=" * 50)
    print("TEST 32: Cross-Collection Stats")
    print("=" * 50)

    collections = await conn.fetch("""
        SELECT source_collection, COUNT(*) as nodes
        FROM kg_nodes
        GROUP BY source_collection
        ORDER BY nodes DESC
    """)

    print("Nodes by source collection:")
    for c in collections:
        coll = c["source_collection"] or "null"
        print(f"  {coll}: {c['nodes']} nodes")

    print("\n" + "=" * 70)
    print("✅ TEST AVANZATI PARTE 3 COMPLETATI")
    print("=" * 70)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(test_kg_advanced())
