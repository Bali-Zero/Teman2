import asyncio
import aiohttp
import time
import asyncpg
from jose import jwt

BASE_URL = "http://localhost:8080"
TEST_USER_ID = "test_memory_user_001"
# Real secret from .env
JWT_SECRET = "07XoX6Eu24amEuUye7MhTFO62jzaYJ48myn04DvECN0="
JWT_ALGORITHM = "HS256"


def create_jwt(user_id, email, role="user"):
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "name": "Test User",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def check_health():
    """Checks if the backend is healthy."""
    print("STEP 1: Checking Health...", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as resp:
                print(f"Health Check Status: {resp.status}", flush=True)
                return resp.status == 200
    except Exception as e:
        print(f"❌ Could not connect to API: {e}", flush=True)
        return False


async def inject_test_memory():
    """Injects a test memory fact directly into PostgreSQL."""
    print("STEP 2: Injecting Fact into PostgreSQL...", flush=True)

    candidates = [
        "postgresql://user:password@127.0.0.1:5432/nuzantara_dev",
        "postgresql://postgres:password@127.0.0.1:5432/nuzantara_dev",
        "postgresql://postgres:postgres@127.0.0.1:5432/nuzantara_dev",
        "postgresql://backend_rag_v2:2zEjit43IF6gNUV@127.0.0.1:5432/nuzantara_rag",
    ]

    conn = None
    for db_url in candidates:
        print(f"Trying DB connection: {db_url.split('@')[1]}...", flush=True)
        try:
            conn = await asyncpg.connect(db_url)
            print("✅ Connected to DB!", flush=True)
            break
        except Exception as e:
            print(f"⚠️ Connect failed: {e}. Trying next...", flush=True)
            try:
                conn = await asyncpg.connect(db_url, ssl=False)
                print("✅ Connected to DB (No SSL)!", flush=True)
                break
            except:
                pass

    if not conn:
        print("❌ All DB connection attempts failed.", flush=True)
        return

    # Insert fact
    try:
        # Check if table memory_facts exists?
        # Directly insert
        await conn.execute(
            """
            INSERT INTO memory_facts (user_id, content, fact_type, confidence, source)
            VALUES ($1, $2, $3, $4, $5)
        """,
            TEST_USER_ID,
            "My favorite food is Nasi Goreng Special.",
            "profile_fact",
            1.0,
            "test_script",
        )
        print("✅ Fact injected successfully via SQL.", flush=True)
    except Exception as e:
        print(f"⚠️ SQL Injection failed: {e}", flush=True)
    finally:
        await conn.close()


async def query_agentic_rag():
    """Queries the Agentic RAG endpoint."""
    print("\nSTEP 3: Querying Agentic RAG...", flush=True)

    # Create valid JWT
    token = create_jwt(TEST_USER_ID, "test@example.com")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        query_payload = {
            "query": "What is my favorite food?",
            "user_id": TEST_USER_ID,
            "enable_vision": False,
        }

        try:
            async with session.post(
                f"{BASE_URL}/api/agentic-rag/query", json=query_payload, headers=headers
            ) as response:
                print(f"Query Status: {response.status}", flush=True)
                if response.status == 200:
                    data = await response.json()
                    answer = data.get("answer", "")
                    print(f"🤖 Answer: {answer}", flush=True)

                    if "nasi goreng" in answer.lower():
                        print("✅ SUCCESS: Memory was retrieved!", flush=True)
                    else:
                        print("❌ FAILURE: Memory was ignored.", flush=True)
                else:
                    text = await response.text()
                    print(f"❌ Query failed: {text}", flush=True)
        except Exception as e:
            print(f"❌ Query Exception: {e}", flush=True)


async def main():
    print(f"🔍 Testing RAG Memory against {BASE_URL}", flush=True)

    if not await check_health():
        print("❌ Backend not healthy. Aborting.", flush=True)
        return

    await inject_test_memory()
    await query_agentic_rag()


if __name__ == "__main__":
    asyncio.run(main())
