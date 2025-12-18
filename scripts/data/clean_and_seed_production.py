import asyncio
import aiohttp

# Proxied URL: localhost:5433
# Original: postgres://backend_rag_v2:2zEjit43IF6gNUV@nuzantara-postgres.flycast:5432/nuzantara_rag?sslmode=disable
DB_URL = "postgres://backend_rag_v2:2zEjit43IF6gNUV@localhost:5433/nuzantara_rag?sslmode=disable"
MIGRATION_ENDPOINT = "https://nuzantara-rag.fly.dev/api/auth/team/run-migration-010"
SEED_ENDPOINT = "https://nuzantara-rag.fly.dev/api/auth/team/seed-team"


async def clean_and_seed():
    print("🚀 Running Migration 010 to fix schema...")
    headers = {"X-API-Key": "REDACTED-ROTATED-KEY"}

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Run Migration
            print(f"🔧 Calling Migration Endpoint: {MIGRATION_ENDPOINT}")
            async with session.post(MIGRATION_ENDPOINT, headers=headers) as response:
                print(f"📡 Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("✅ Migration Success!")
                    print(data)
                else:
                    print(f"❌ Migration Failed: {await response.text()}")

            # 2. Retry Seed
            print(f"🌱 Calling Seed Endpoint: {SEED_ENDPOINT}")
            async with session.post(SEED_ENDPOINT, headers=headers) as response:
                print(f"📡 Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print("✅ Seed Success!")
                    print(data)
                else:
                    print(f"❌ Seed Failed: {await response.text()}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(clean_and_seed())
