#!/usr/bin/env python3
"""Apply ONLY migration 018"""
import asyncio
import os

import asyncpg


async def run():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set")
        return

    print("Connecting to database...")
    conn = await asyncpg.connect(database_url)

    try:
        # Read migration SQL
        sql_path = "/app/backend/db/migrations/018_collective_memory.sql"
        print(f"Reading {sql_path}")
        with open(sql_path) as f:
            sql = f.read()

        # Execute
        print("Executing migration 018...")
        await conn.execute(sql)
        print("Migration 018 executed!")

        # Verify
        result = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'collective%'"
        )
        tables = [r["table_name"] for r in result]
        print(f"Tables created: {tables}")

        if "collective_memories" in tables and "collective_memory_sources" in tables:
            print("SUCCESS: All collective memory tables created!")
        else:
            print("WARNING: Some tables missing")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
