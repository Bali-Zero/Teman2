import asyncio
import os

import asyncpg


async def apply_migrations():
    db_url = "postgres://localhost:5432/nuzantara_dev"
    print(f"Connecting to {db_url}...")

    try:
        conn = await asyncpg.connect(db_url)

        migrations = [
            "backend/db/migrations/013_agentic_rag_tables.sql",
            "backend/db/migrations/014_knowledge_graph_tables.sql",
            "backend/db/migrations/015_add_drive_columns.sql",
        ]

        for mig_file in migrations:
            print(f"Applying {mig_file}...")
            if not os.path.exists(mig_file):
                print(f"❌ File not found: {mig_file}")
                continue

            with open(mig_file) as f:
                sql = f.read()

            await conn.execute(sql)
            print(f"✅ Applied {mig_file}")

        await conn.close()
        print("All migrations applied.")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(apply_migrations())
