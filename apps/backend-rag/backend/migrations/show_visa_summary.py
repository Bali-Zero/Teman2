#!/usr/bin/env python3
import asyncio
import os
import asyncpg

async def show():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    rows = await conn.fetch("""
        SELECT code, name, category, duration
        FROM visa_types
        WHERE code ~ '^[ABFC]'
        ORDER BY code
    """)

    current_series = ""
    for row in rows:
        series = row['code'][0]
        if series != current_series:
            current_series = series
            names = {'A': 'Visa Free', 'B': 'VOA', 'F': 'VOA (Short)', 'C': 'Visit Visa'}
            print(f"\n=== Series {series} - {names.get(series, '')} ===")

        print(f"  {row['code']:6} | {row['name'][:38]:38} | {row['category']}")

    print(f"\nTotal: {len(rows)} visas in A/B/F/C series")
    await conn.close()

asyncio.run(show())
