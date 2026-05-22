import asyncio
import asyncpg
import sys

DB_URL = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15444/nuzantara_rag?sslmode=disable"

async def main():
    try:
        print(f"Connecting to: {DB_URL}")
        conn = await asyncpg.connect(DB_URL)
        print("Connected to DB successfully.")
        
        # Test query
        res = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [r['table_name'] for r in res]
        print(f"Tables: {', '.join(tables)}")
        
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
