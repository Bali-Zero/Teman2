import asyncio
import asyncpg
import datetime
import uuid

# Config
# Force TCP with 127.0.0.1
DB_DSN = "postgresql://user:password@127.0.0.1:5432/nuzantara_dev"

TEST_USER_ID = "test_memory_user_001"
FACTS = [
    "My favorite food is Nasi Goreng Special.",
    "I live in South Jakarta.",
    "I prefer Python over JavaScript.",
    "My budget for the project is $10k.",
    "I hate cilantro.",
]


async def inject_facts():
    print(f"🔌 Connecting to DB: {DB_DSN}")
    try:
        conn = await asyncpg.connect(DB_DSN)
        print("✅ Connected!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    try:
        # Check if table exists
        # schema: id, user_id, content, confidence, source, metadata, created_at

        # Insert Facts
        print(f"💾 Injecting {len(FACTS)} facts for {TEST_USER_ID}...")

        for fact in FACTS:
            fact_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO memory_facts (id, user_id, content, confidence, source, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                fact_id,
                TEST_USER_ID,
                fact,
                1.0,
                "direct_injection",
                "{}",
                datetime.datetime.now(),
            )
            print(f"   -> Injected: {fact}")

        print("✅ Injection Complete.")

    except Exception as e:
        print(f"❌ Injection failed: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(inject_facts())
