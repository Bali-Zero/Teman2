import asyncio
import os
import asyncpg

async def verify_prices():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        # Check specific critical visas
        codes_to_check = ["D1", "E23A", "C5A", "B1"]
        
        print(f"{'CODE':<6} | {'NAME':<40} | {'PUBLIC PRICE (What User Sees)':<30}")
        print("-" * 85)
        
        for code in codes_to_check:
            row = await conn.fetchrow("SELECT code, name, cost_visa FROM visa_types WHERE code = $1", code)
            if row:
                print(f"{row['code']:<6} | {row['name'][:38]:<40} | {row['cost_visa']:<30}")
            else:
                print(f"{code:<6} | NOT FOUND")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_prices())
