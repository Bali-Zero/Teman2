#!/usr/bin/env python3
"""
TKA Knowledge Graph Ingestion Script
Ingests TKA data from SQL file into PostgreSQL kg_nodes and kg_edges tables.
"""

import asyncio
import os
import sys
from datetime import datetime

import asyncpg


def get_database_url():
    """Construct DATABASE_URL from environment variables or return existing one."""
    if db_url := os.getenv("DATABASE_URL"):
        return db_url

    # Construct from PG* variables
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "nuzantara")
    # Use current system user if PGUSER is postgres (which may not exist)
    import getpass

    current_user = getpass.getuser()
    user = os.getenv("PGUSER", current_user)
    if user == "postgres":
        user = current_user
    password = os.getenv("PGPASSWORD", "")

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    else:
        return f"postgresql://{user}@{host}:{port}/{db}"


async def verify_tables(conn):
    """Verify kg_nodes and kg_edges tables exist."""
    print("\n📋 Verifying database tables...")

    tables = ["kg_nodes", "kg_edges"]
    results = {}

    for table in tables:
        try:
            result = await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = '{table}'
                );
            """)
            results[table] = result
            if result:
                print(f"  ✅ Table '{table}' exists")
            else:
                print(f"  ❌ Table '{table}' NOT FOUND")
        except Exception as e:
            print(f"  ❌ Error checking '{table}': {e}")
            results[table] = False

    return all(results.values())


async def get_pre_ingestion_counts(conn):
    """Get counts before ingestion."""
    print("\n📊 Pre-ingestion counts:")

    # Count nodes by type
    node_counts = await conn.fetch("""
        SELECT entity_type, COUNT(*) as count
        FROM kg_nodes
        WHERE entity_type IN ('KBLI', 'Jabatan', 'KepmenCategory', 'ISCOGroup')
        GROUP BY entity_type
        ORDER BY entity_type;
    """)

    if node_counts:
        for row in node_counts:
            print(f"  - {row['entity_type']}: {row['count']}")
    else:
        print("  (No relevant nodes found)")

    # Count edges
    edge_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges;")
    print(f"  - Total edges: {edge_count}")

    return node_counts, edge_count


async def ingest_sql_file(conn, sql_file_path):
    """Execute SQL file for ingestion."""
    print(f"\n📥 Ingesting SQL file: {sql_file_path}")

    if not os.path.exists(sql_file_path):
        print(f"  ❌ File not found: {sql_file_path}")
        return False

    file_size = os.path.getsize(sql_file_path)
    print(f"  File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

    # Read and execute SQL
    with open(sql_file_path) as f:
        sql_content = f.read()

    # Execute in transaction
    async with conn.transaction():
        print("  Executing SQL statements...")
        await conn.execute(sql_content)

    print("  ✅ SQL execution completed")
    return True


async def get_post_ingestion_counts(conn):
    """Get counts after ingestion."""
    print("\n📊 Post-ingestion counts:")

    # Count nodes by type
    node_counts = await conn.fetch("""
        SELECT entity_type, COUNT(*) as count
        FROM kg_nodes
        WHERE entity_type IN ('KBLI', 'Jabatan', 'KepmenCategory', 'ISCOGroup')
        GROUP BY entity_type
        ORDER BY entity_type;
    """)

    print("  Nodes by type:")
    expected = {"KBLI": 246, "Jabatan": 59, "KepmenCategory": 12, "ISCOGroup": 8}

    for row in node_counts:
        entity_type = row["entity_type"]
        count = row["count"]
        exp = expected.get(entity_type, 0)
        status = "✅" if count >= exp else "⚠️"
        print(f"    {status} {entity_type}: {count} (expected: ~{exp})")

    # Count edges
    edge_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges;")
    print(f"\n  Total edges: {edge_count} (expected: ~1370)")

    # Count total nodes
    total_nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes;")
    print(f"  Total nodes: {total_nodes}")

    return node_counts, edge_count


async def run_sample_queries(conn):
    """Run sample verification queries."""
    print("\n🔍 Running sample queries:")

    # Query 1: TKA positions for KBLI 62110
    print("\n  1. TKA positions for KBLI 62110:")
    results = await conn.fetch("""
        SELECT j.name, j.properties->>'isco' as isco
        FROM kg_nodes k
        JOIN kg_edges e ON k.entity_id = e.source_entity_id
        JOIN kg_nodes j ON e.target_entity_id = j.entity_id
        WHERE k.entity_type = 'KBLI' AND k.properties->>'code' = '62110'
        AND e.relationship_type = 'HAS_ELIGIBLE_POSITION';
    """)

    if results:
        for row in results[:5]:  # Show first 5
            print(f"     - {row['name']} (ISCO: {row['isco']})")
        if len(results) > 5:
            print(f"     ... and {len(results) - 5} more")
    else:
        print("     (No results found)")

    # Query 2: Sample KBLI with positions
    print("\n  2. Sample KBLI entries with position counts:")
    sample_kbli = await conn.fetch("""
        SELECT k.properties->>'code' as code, k.name, COUNT(e.*) as position_count
        FROM kg_nodes k
        LEFT JOIN kg_edges e ON k.entity_id = e.source_entity_id
            AND e.relationship_type = 'HAS_ELIGIBLE_POSITION'
        WHERE k.entity_type = 'KBLI'
        GROUP BY k.entity_id, k.properties->>'code', k.name
        ORDER BY position_count DESC
        LIMIT 5;
    """)

    for row in sample_kbli:
        print(f"     - {row['code']}: {row['name']} ({row['position_count']} positions)")

    # Query 3: ISCO groups
    print("\n  3. ISCO Groups:")
    isco_groups = await conn.fetch("""
        SELECT name, properties->>'group_code' as code
        FROM kg_nodes
        WHERE entity_type = 'ISCOGroup'
        ORDER BY name;
    """)

    for row in isco_groups:
        print(f"     - {row['code']}: {row['name']}")


async def generate_report(conn, start_time, end_time):
    """Generate final verification report."""
    print("\n" + "=" * 60)
    print("📋 TKA KNOWLEDGE GRAPH INGESTION REPORT")
    print("=" * 60)

    print(f"\n⏱️  Execution time: {(end_time - start_time).total_seconds():.2f} seconds")
    print(f"🕐 Timestamp: {end_time.isoformat()}")

    # Final counts
    kbli_count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'KBLI';")
    jabatan_count = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'Jabatan';"
    )
    kepmen_count = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'KepmenCategory';"
    )
    isco_count = await conn.fetchval(
        "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'ISCOGroup';"
    )
    edge_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges;")

    print("\n📈 Final Statistics:")
    print(f"   - KBLI nodes: {kbli_count} (expected: 246)")
    print(f"   - Jabatan nodes: {jabatan_count} (expected: 59)")
    print(f"   - KepmenCategory nodes: {kepmen_count} (expected: 12)")
    print(f"   - ISCOGroup nodes: {isco_count} (expected: 8)")
    print(f"   - Total edges: {edge_count} (expected: ~1370)")

    # Verification
    print("\n✅ Verification:")
    checks = [
        (kbli_count >= 200, f"KBLI nodes >= 200: {kbli_count}"),
        (jabatan_count >= 50, f"Jabatan nodes >= 50: {jabatan_count}"),
        (kepmen_count >= 10, f"KepmenCategory nodes >= 10: {kepmen_count}"),
        (isco_count >= 5, f"ISCOGroup nodes >= 5: {isco_count}"),
        (edge_count >= 1000, f"Edges >= 1000: {edge_count}"),
    ]

    all_passed = True
    for passed, message in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {message}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All verification checks PASSED!")
    else:
        print("\n⚠️ Some verification checks FAILED - review needed")

    return all_passed


async def main():
    """Main ingestion workflow."""
    sql_file = "/Users/nuzantara/Desktop/TKA_KG_INSERTS.sql"

    start_time = datetime.now()
    print("=" * 60)
    print("🚀 TKA KNOWLEDGE GRAPH INGESTION")
    print("=" * 60)
    print(f"Started at: {start_time.isoformat()}")

    # Get database URL
    db_url = get_database_url()
    masked_url = (
        db_url.replace(db_url.split("@")[0].split("://")[1], "***") if "@" in db_url else db_url
    )
    print(f"\n🔌 Database URL: {masked_url}")

    # Connect to database
    print("\n📡 Connecting to database...")
    try:
        conn = await asyncpg.connect(db_url)
        print("  ✅ Connected successfully")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        sys.exit(1)

    try:
        # Step 1: Verify tables exist
        if not await verify_tables(conn):
            print("\n❌ Required tables do not exist. Please run migration 028 first.")
            sys.exit(1)

        # Step 2: Get pre-ingestion counts
        await get_pre_ingestion_counts(conn)

        # Step 3: Ingest SQL file
        if not await ingest_sql_file(conn, sql_file):
            print("\n❌ Ingestion failed")
            sys.exit(1)

        # Step 4: Get post-ingestion counts
        await get_post_ingestion_counts(conn)

        # Step 5: Run sample queries
        await run_sample_queries(conn)

        # Step 6: Generate report
        end_time = datetime.now()
        success = await generate_report(conn, start_time, end_time)

        if success:
            print("\n✅ Ingestion completed successfully!")
        else:
            print("\n⚠️ Ingestion completed with warnings")

    finally:
        await conn.close()
        print("\n🔌 Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
