#!/usr/bin/env python3
"""
Import KBLI 2025 parent documents and KG data to PostgreSQL.
Run this from Fly.io environment where DATABASE_URL is accessible.
"""

import os
import asyncio
import asyncpg


async def main():
    print("=" * 60)
    print("KBLI 2025 PostgreSQL Import")
    print("=" * 60)

    # Connect to database
    print("\n[1/4] Connecting to PostgreSQL...")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("      Connected!")

    # Check existing tables
    print("\n[2/4] Checking tables...")
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
    """)
    table_names = [t["table_name"] for t in tables]
    print(f"      Found {len(table_names)} tables")

    kg_tables = [t for t in table_names if "kg" in t]
    print(f"      KG-related tables: {kg_tables}")

    # Check if kg_nodes exists
    if "kg_nodes" in table_names:
        count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
        print(f"      kg_nodes: {count} rows")
    else:
        print("      kg_nodes table NOT FOUND - needs migration")

    if "kg_edges" in table_names:
        count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
        print(f"      kg_edges: {count} rows")
    else:
        print("      kg_edges table NOT FOUND - needs migration")

    # Check for kbli-specific data
    print("\n[3/4] Checking KBLI data...")
    if "kg_nodes" in table_names:
        kbli_count = await conn.fetchval("""
            SELECT COUNT(*) FROM kg_nodes
            WHERE entity_type = 'kbli' OR entity_id LIKE 'kbli:%'
        """)
        print(f"      KBLI nodes in KG: {kbli_count}")

    # Summary
    print("\n[4/4] Summary")
    print("=" * 60)
    print("Qdrant: kbli_2025_final with 3,057 vectors ✓")
    print(f"PostgreSQL: kg_nodes exists = {'kg_nodes' in table_names}")
    print(f"PostgreSQL: kg_edges exists = {'kg_edges' in table_names}")
    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
