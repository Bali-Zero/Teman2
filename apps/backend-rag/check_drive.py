#!/usr/bin/env python3
"""Check Google Drive OAuth status."""

import asyncio
import os

import asyncpg


async def check():
    try:
        conn = await asyncpg.connect(os.environ["DATABASE_URL"])

        # Check tables
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('google_drive_tokens', 'user_oauth_tokens')
        """)
        print("Tables found:", [t["table_name"] for t in tables])

        # Check google_drive_tokens
        if any(t["table_name"] == "google_drive_tokens" for t in tables):
            rows = await conn.fetch("SELECT user_id, expires_at FROM google_drive_tokens")
            print(f"google_drive_tokens: {len(rows)} entries")
            for r in rows:
                print(f"  - {r['user_id']}: expires {r['expires_at']}")

        # Check user_oauth_tokens (alternative table)
        if any(t["table_name"] == "user_oauth_tokens" for t in tables):
            rows = await conn.fetch(
                "SELECT user_id, provider, expires_at FROM user_oauth_tokens WHERE provider = 'google_drive'"
            )
            print(f"user_oauth_tokens (google_drive): {len(rows)} entries")
            for r in rows:
                print(f"  - {r['user_id']}: expires {r['expires_at']}")

        await conn.close()
        print("\n✅ Check completed")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(check())
